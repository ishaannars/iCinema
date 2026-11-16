"""A sequence-aware baseline: does the order of your likes predict what you love next better than fans?

    python training/benchmark_sequential.py --data-dir ml-32m

Reviewers ask whether a sequential model was tried. This is the classic one that needs no GPU: a
first-order Markov chain over each viewer's time-ordered likes (how often movie j is liked within
the next 3 likes after movie i), blended with item-kNN so unseen transitions still score. Same 1-in-5
MovieLens 32M sample, time split, and 3,000 validation / 3,000 test viewers as benchmark_cf.py,
scored from each viewer's 3 most recent likes. Rules written before running: the blend weight is
picked on validation viewers, then compared once on test viewers with item-kNN alone (paired
bootstrap). It is reported either way; it would only enter the app if it wins with a 95% interval
above zero. Writes data/sequential_results.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, evaluate, load_sample, m_knn, matrix, summary  # noqa: E402
from evaluate_long_tail import pct  # noqa: E402
from train_cf import paired_bootstrap, time_split  # noqa: E402

WINDOW = 3


def transitions(train_by_user, n):
    rows, cols = [], []
    for seq in train_by_user:
        for k, i in enumerate(seq):
            for j in seq[k + 1:k + 1 + WINDOW]:
                rows.append(i)
                cols.append(j)
    T = sp.csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)), shape=(n, n))
    out = np.asarray(T.sum(axis=1)).ravel()
    return sp.diags(1.0 / np.maximum(out, 1.0)) @ T          # row-normalized: P(next = j | liked i)


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
    T = transitions(tb.values, n)

    def chain(seeds):
        w = np.array([0.25, 0.5, 1.0][-len(seeds):])      # the most recent like counts most
        return np.asarray((sp.csr_matrix((w, (np.zeros(len(seeds), int), seeds)), shape=(1, n)) @ T).todense()).ravel()

    def blend(a):
        return lambda seeds: (1 - a) * pct(np.asarray(knn(seeds), dtype=float)) + a * pct(chain(seeds))

    grid = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    val_ndcg = {a: summary(evaluate(blend(a), val, tb, te, "last3"))["ndcg@10"] for a in grid}
    best = max(grid, key=val_ndcg.get)
    rk = evaluate(blend(0.0), tst, tb, te, "last3")
    rb = evaluate(blend(best), tst, tb, te, "last3")
    rc = evaluate(blend(1.0), tst, tb, te, "last3")
    d, lo, hi, _ = paired_bootstrap(rb[:, 1], rk[:, 1], np.mean)
    out = {"method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "),
           "validation_ndcg@10": {str(a): round(v, 4) for a, v in val_ndcg.items()}, "best_weight": best,
           "test_ndcg@10": {"item_knn": round(float(rk[:, 1].mean()), 4), "best_blend": round(float(rb[:, 1].mean()), 4),
                            "markov_chain_alone": round(float(rc[:, 1].mean()), 4)},
           "diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "ship": bool(best > 0 and lo > 0)}
    print(json.dumps(out, indent=1))
    (ROOT / "data" / "sequential_results.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
