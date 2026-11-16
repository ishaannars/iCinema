"""Test, then build, the order-aware ("what fans liked next") model for "More like X" and What's Next.

    python training/build_sequential.py --data-dir ml-32m

training/benchmark_sequential.py found that the order of likes predicts what people love next
(NDCG@10 0.127 vs 0.113 for item-kNN from the 3 most recent likes, 95% CI +0.010 to +0.018).
"More like X" starts from one movie, so it gets its own test before anything ships. Rules written
before running, on the same 1-in-5 sample, time split and 3,000 + 3,000 viewers as confirm_like.py:
source = each viewer's most recent like; the score is (1 - a) x fans' closeness + a x "liked next";
a is picked on validation viewers, then compared once on test viewers with fans alone (what ships
today). Only if it wins with a 95% interval above zero is the model built on all of MovieLens 32M
(each movie's 100 most likely next movies, same movie index as the app) into data/seq_chain.npz.
A second test, same rules, checks the main ranking (Top Picks, Tonight's Show) against the shipped
fan ranking from each viewer's 3 most recent likes. Writes data/seq_like_confirm.json and
data/seq_main_confirm.json either way; the model is built if either test passes.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_knn, matrix  # noqa: E402
from benchmark_sequential import WINDOW, transitions  # noqa: E402
from benchmark_cf import evaluate, summary  # noqa: E402
from confirm_like import run  # noqa: E402
from confirm_routing import routed_scorer  # noqa: E402
from evaluate_long_tail import pct, rp3beta  # noqa: E402
from train_cf import load, paired_bootstrap, time_split  # noqa: E402

TOP = 100


def rank01(order, n_items, size=100):
    r = np.zeros(n_items, dtype=np.float32)
    r[order[:size]] = 1 - np.arange(min(size, len(order))) / size
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    pos, n = load_sample(args.data_dir, 5, 20)
    train, test = time_split(pos)
    X = matrix(train, n)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    eligible = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]
    picked = np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False)
    val, tst = list(picked[:N_EVAL]), list(picked[N_EVAL:])
    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    knn = m_knn(X, shrink, top=100)[0]
    T = transitions(tb.values, n).tocsr()

    def fan_order(src):
        s = np.asarray(knn(np.asarray([src])), dtype=float).ravel()
        s[src] = -np.inf
        top = np.argpartition(-s, 100)[:100]
        return top[np.argsort(-s[top])]

    def chain_order(src):
        row = T.getrow(src)
        return row.indices[np.argsort(-row.data)][:100]

    def blended(a):
        def f(src):
            fo, co = fan_order(src), chain_order(src)
            score = (1 - a) * rank01(fo, n) + a * rank01(co, n)
            score[src] = -1
            cand = np.union1d(fo, co)
            return list(cand[np.argsort(-score[cand])])
        return f

    grid = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    val_ndcg = {a: float(run(val, tb, te, blended(a))[:, 1].mean()) for a in grid}
    best = max(grid, key=val_ndcg.get)
    rf, rb = run(tst, tb, te, blended(0.0)), run(tst, tb, te, blended(best))
    d, lo, hi, _ = paired_bootstrap(rb[:, 1], rf[:, 1], np.mean)
    ship = bool(best > 0 and lo > 0)
    out = {"method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "),
           "validation_ndcg@10": {str(a): round(v, 4) for a, v in val_ndcg.items()}, "weight": best,
           "test_ndcg@10": {"fans_only": round(float(rf[:, 1].mean()), 4), "with_liked_next": round(float(rb[:, 1].mean()), 4)},
           "hit@1": {"fans_only": round(float(rf[:, 2].mean()), 4), "with_liked_next": round(float(rb[:, 2].mean()), 4)},
           "diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "ship": ship}
    print(json.dumps(out, indent=1), flush=True)
    (ROOT / "data" / "seq_like_confirm.json").write_text(json.dumps(out, indent=1))

    # Second test, same rules: does "what you liked last" improve the main ranking (Top Picks, Tonight's
    # Show)? Baseline = the shipped fan ranking (routed item-kNN / RP3beta), scored from each viewer's
    # 3 most recent likes; blend = (1 - a) x shipped + a x liked-next.
    rt = json.loads((ROOT / "data" / "routing_confirm.json").read_text())
    beta = float(json.loads((ROOT / "data" / "long_tail_confirm.json").read_text())["beta"])
    fan_pct = pct(X.getnnz(axis=0).astype(float))
    shipped = routed_scorer(knn, rp3beta(X, beta), fan_pct, rt["niche_cut_fan_percentile"]) if rt.get("ship_routing") else knn

    def chain(seeds):
        w = np.array([0.25, 0.5, 1.0][-len(seeds):])
        return np.asarray((sp.csr_matrix((w, (np.zeros(len(seeds), int), seeds)), shape=(1, n)) @ T).todense()).ravel()

    def main_blend(a):
        return lambda seeds: (1 - a) * pct(np.asarray(shipped(seeds), dtype=float)) + a * pct(chain(seeds))

    vm = {a: summary(evaluate(main_blend(a), val, tb, te, "last3"))["ndcg@10"] for a in grid}
    bm = max(grid, key=vm.get)
    r0, r1 = evaluate(main_blend(0.0), tst, tb, te, "last3"), evaluate(main_blend(bm), tst, tb, te, "last3")
    dm, lom, him, _ = paired_bootstrap(r1[:, 1], r0[:, 1], np.mean)
    main_out = {"validation_ndcg@10": {str(a): round(v, 4) for a, v in vm.items()}, "weight": bm,
                "test_ndcg@10": {"shipped": round(float(r0[:, 1].mean()), 4), "with_liked_next": round(float(r1[:, 1].mean()), 4)},
                "hit@1": {"shipped": round(float(r0[:, 2].mean()), 4), "with_liked_next": round(float(r1[:, 2].mean()), 4)},
                "diff": round(dm, 4), "ci95": [round(lom, 4), round(him, 4)], "ship": bool(bm > 0 and lom > 0)}
    print("main ranking", json.dumps(main_out, indent=1), flush=True)
    (ROOT / "data" / "seq_main_confirm.json").write_text(json.dumps(main_out, indent=1))
    if not (ship or main_out["ship"]):
        return

    full, meta = load(args.data_dir, 20)        # the app's 14,407-movie index
    seqs = full.sort_values("timestamp").groupby("userId")["item"].apply(list).values
    m = len(meta)
    keys = []
    for seq in seqs:
        a = np.asarray(seq, dtype=np.int64)
        for k in range(1, WINDOW + 1):
            if len(a) > k:
                keys.append(a[:-k] * m + a[k:])
    keys, counts = np.unique(np.concatenate(keys), return_counts=True)
    C = sp.csr_matrix((counts.astype(np.float32), (keys // m, keys % m)), shape=(m, m))
    nbr = np.full((m, TOP), -1, dtype=np.int32)
    w = np.zeros((m, TOP), dtype=np.float32)
    for i in range(m):
        row = C.getrow(i)
        if row.nnz:
            o = np.argsort(-row.data)[:TOP]
            nbr[i, :len(o)] = row.indices[o]
            w[i, :len(o)] = row.data[o] / row.data.sum()
    np.savez_compressed(ROOT / "data" / "seq_chain.npz", nbr=nbr, w=w, weight=np.float32(best))
    print(f"built data/seq_chain.npz for {m:,} movies")


if __name__ == "__main__":
    main()
