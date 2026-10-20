"""Fix the weakest case: viewers whose likes are less-loved movies ("niche taste").

    python training/evaluate_long_tail.py --data-dir ml-32m

Same 1-in-5 MovieLens 32M sample, time split, and 3,000 validation / 3,000 test viewers as
training/benchmark_cf.py. Niche viewers: the 25% whose 3 random likes have the fewest fans
(cut set on validation viewers).

Candidates, all from 3 random likes:
- item-kNN top-100 (shipped now)
- item-kNN with a popularity penalty: score / fans^b, b in {0.1, 0.2, 0.35, 0.5}
- implicit ALS, sparse EASE (top-100)
- rank fusion of item-kNN and ALS: w * kNN percentile + (1 - w) * ALS percentile, w in {0.25, 0.5, 0.75}
- RP3beta (a two-step random walk, viewer -> movie -> viewer -> movie, with each movie's
  score divided by fans^beta), a standard fix for popularity bias, beta in {0.3, 0.5, 0.7}

Rule written before running (pick on validation, score once on test, paired bootstrap):
1. Upgrade for everyone if a candidate beats the shipped model on all test viewers (NDCG@10
   interval above zero) and doesn't make niche viewers significantly worse.
2. Otherwise, upgrade niche viewers only if a candidate beats the shipped model on niche test
   viewers (interval above zero). The app spots niche viewers the same way, from their likes.
Also reported: long-tail share (top-10 picks outside the 20% most-loved movies) and catalog
coverage, so accuracy gains aren't bought by recommending only blockbusters.
Writes data/long_tail_results.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_als, m_ease, m_knn, matrix  # noqa: E402
from train_cf import FIRST_HIT_DEPTH, metrics, paired_bootstrap, time_split  # noqa: E402


def pct(s):
    order = np.argsort(s, kind="stable")
    r = np.empty(len(s))
    r[order] = np.arange(len(s))
    return r / max(len(s) - 1, 1)


def rp3beta(X, beta, top=100, block=1000):
    """RP3beta item-item weights, built in blocks and kept sparse (top-100 per movie)."""
    from scipy.sparse import csr_matrix, diags
    fans = np.asarray(X.sum(axis=0)).ravel()
    Pui = (diags(1.0 / np.maximum(np.asarray(X.sum(axis=1)).ravel(), 1)) @ X).tocsc()
    Piu = (diags(1.0 / np.maximum(fans, 1)) @ X.T.tocsr()).tocsr()
    damp = np.power(np.maximum(fans, 1), beta).astype(np.float32)
    rows, cols, vals = [], [], []
    for start in range(0, X.shape[1], block):
        b = np.arange(start, min(start + block, X.shape[1]))
        W = (Piu[b] @ Pui).toarray().astype(np.float32) / damp[None, :]
        W[np.arange(len(b)), b] = 0
        keep = np.argpartition(-W, top, axis=1)[:, :top]
        rows.append(np.repeat(b, top)); cols.append(keep.ravel()); vals.append(np.take_along_axis(W, keep, axis=1).ravel())
    S = csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(X.shape[1], X.shape[1]))
    return lambda seeds: np.asarray(S[seeds].sum(axis=0)).ravel()


def shipped_ranker(X, shrink):
    """The ranking model the app ships: RP3beta if confirm_long_tail.py promoted it, else item-kNN."""
    path = ROOT / "data" / "long_tail_confirm.json"
    confirm = json.loads(path.read_text()) if path.exists() else {}
    if confirm.get("replaces_item_knn"):
        return rp3beta(X, float(confirm["beta"]))
    return m_knn(X, shrink, top=100)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--user-sample", type=int, default=5)
    args = ap.parse_args()
    pos, n = load_sample(args.data_dir, args.user_sample, 20)
    train, test = time_split(pos)
    X = matrix(train, n)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    eligible = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]
    picked = np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False)
    val, tst = list(picked[:N_EVAL]), list(picked[N_EVAL:])
    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    shrink = float(bench["results"]["item-kNN"]["params"][0])
    fans = X.getnnz(axis=0).astype(float)
    fan_pct = pct(fans)
    head = fan_pct >= 0.8                                          # the 20% most-loved movies

    knn, _ = m_knn(X, shrink, top=100)
    als, _ = m_als(X, alpha=10)
    ease, _ = m_ease(X, 4000, top=100)
    print("models ready", flush=True)
    cands = {"item-kNN (shipped)": knn, "Implicit ALS": als, "EASE, top-100": ease}
    for b in (0.1, 0.2, 0.35, 0.5):
        cands[f"item-kNN, popularity penalty {b}"] = (lambda b: (lambda seeds: knn(seeds) / np.power(fans + 1, b)))(b)
    for beta in (0.3, 0.5, 0.7):
        cands[f"RP3beta, beta {beta}"] = rp3beta(X, beta)
    for w in (0.25, 0.5, 0.75):
        cands[f"kNN + ALS fusion, {w:.0%} kNN"] = (lambda w: (lambda seeds: w * pct(knn(seeds)) + (1 - w) * pct(als(seeds))))(w)

    def run(users, score, seed=5):
        rng = np.random.default_rng(seed)
        res, tails, seen_items, niche = [], [], set(), []
        for u in users:
            hist = tb[u]
            seeds = np.asarray([hist[i] for i in sorted(rng.choice(len(hist), 3, replace=False))])
            s = np.asarray(score(seeds), dtype=np.float64)
            s[hist] = -np.inf
            top = np.argpartition(-s, FIRST_HIT_DEPTH)[:FIRST_HIT_DEPTH]
            top = top[np.argsort(-s[top])]
            res.append(metrics(top, te[u]))
            tails.append(float((~head[top[:10]]).mean()))
            seen_items.update(top[:10].tolist())
            niche.append(float(np.median(fan_pct[seeds])))
        return np.asarray(res, float), np.asarray(tails), len(seen_items) / n, np.asarray(niche)

    runs_val = {k: run(val, f) for k, f in cands.items()}
    cut = float(np.quantile(runs_val["item-kNN (shipped)"][3], 0.25))
    print(f"niche cut (median fan percentile of the 3 likes): {cut:.3f}", flush=True)

    def summary(r, mask):
        return {"hit@1": round(float(r[0][mask, 2].mean()), 4), "ndcg@10": round(float(r[0][mask, 1].mean()), 4)}

    base = "item-kNN (shipped)"
    v_all = {k: float(r[0][:, 1].mean()) for k, r in runs_val.items()}
    v_niche = {k: float(r[0][r[3] <= cut, 1].mean()) for k, r in runs_val.items()}
    best_all = max(v_all, key=v_all.get)
    best_niche = max(v_niche, key=v_niche.get)
    runs_test = {k: run(tst, cands[k]) for k in {base, best_all, best_niche}}
    nmask = runs_test[base][3] <= cut

    def boot(k, mask):
        d, lo, hi, _ = paired_bootstrap(runs_test[k][0][mask, 1], runs_test[base][0][mask, 1], np.mean)
        return {"ndcg_diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)]}

    allmask = np.ones(len(tst), bool)
    g_all, g_niche = boot(best_all, allmask), boot(best_all, nmask)
    n_niche, n_rest = boot(best_niche, nmask), boot(best_niche, ~nmask)
    if best_all != base and g_all["ci95"][0] > 0 and g_niche["ci95"][1] >= 0:
        decision, model = "everyone", best_all
    elif best_niche != base and n_niche["ci95"][0] > 0:
        decision, model = "niche viewers only", best_niche
    else:
        decision, model = "no change", base
    out = {
        "method": " ".join(__doc__.split("\n\n")[1:4]).replace("\n", " "),
        "niche_cut_fan_percentile": round(cut, 3), "test_niche_viewers": int(nmask.sum()), "test_viewers": len(tst),
        "validation_ndcg_all": {k: round(v, 4) for k, v in v_all.items()},
        "validation_ndcg_niche": {k: round(v, 4) for k, v in v_niche.items()},
        "best_for_everyone": best_all, "best_for_niche": best_niche,
        "test": {k: {"all": summary(r, allmask), "niche": summary(r, nmask), "others": summary(r, ~nmask),
                     "long_tail_share_top10": round(float(r[1].mean()), 3), "catalog_coverage_top10": round(r[2], 3)}
                 for k, r in runs_test.items()},
        "everyone_vs_shipped": {"all": g_all, "niche": g_niche},
        "niche_pick_vs_shipped": {"niche": n_niche, "others": n_rest},
        "decision": decision, "model": model,
    }
    (ROOT / "data" / "long_tail_results.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("method",)}, indent=1))


if __name__ == "__main__":
    main()
