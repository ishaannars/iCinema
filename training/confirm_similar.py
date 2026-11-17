"""More like this: should "like X" re-rank X's fan neighbors by what the movies are like?

    python training/confirm_similar.py --data-dir ml-32m

Test, written before running. Same held-out viewers and time split as the other tests: for each
viewer, X is their most recent liked movie in the training period, and the truth is the movies they
went on to love afterwards. Every method ranks the same candidates, X's 100 fan neighbors (item-kNN,
the app's "similar to this movie" list), so only the ordering differs.
- Fans only: the neighbors in fan order (what the app did before this change).
- Re-ranked: (1 - w) * fan rank + w * genre-and-fan-tag rank (content model) - p * popularity,
  for w in {0, 0.25, 0.5, 0.75} and p in {0, 0.15, 0.3}, chosen on 3,000 validation viewers.
Decision rule: keep the re-rank only if, on 3,000 different test viewers, its NDCG@10 is no worse
than fans-only by more than 0.002 (paired-bootstrap 95% lower bound above -0.002) and its top 10
is less dominated by famous titles (lower mean popularity percentile). Otherwise the app goes back to
fans-only ordering. Writes data/similar_confirm.json, which the app reads.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_knn, matrix  # noqa: E402
from evaluate_blends import content_embeddings  # noqa: E402
from train_cf import metrics, paired_bootstrap, time_split  # noqa: E402

TOP = 100
GRID_W = [0.0, 0.25, 0.5, 0.75]
GRID_P = [0.0, 0.15, 0.3]
MARGIN = 0.002


def rerank(near, source, E, pop_pct, w, p):
    """X's neighbors ordered by fan rank, content rank and a popularity discount (the app's rule)."""
    fan_rank = 1 - np.arange(len(near)) / len(near)
    cos = E[near] @ E[source]
    tag_rank = 1 - np.argsort(np.argsort(-cos)) / len(near)
    score = (1 - w) * fan_rank + w * tag_rank - p * pop_pct[near]
    return near[np.argsort(-score)]


def run(users, tb, te, knn, E, pop_pct, w, p):
    rows, pops = [], []
    for u in users:
        hist = tb[u]
        source = hist[-1]
        s = np.asarray(knn(np.asarray([source])), dtype=np.float64).ravel()
        s[hist] = -np.inf
        near = np.argpartition(-s, TOP)[:TOP]
        near = near[np.argsort(-s[near])]
        near = near[np.isfinite(s[near])]
        ranked = rerank(near, source, E, pop_pct, w, p) if (w or p) else near
        rows.append(metrics(ranked, te[u]))
        pops.append(float(pop_pct[ranked[:10]].mean()))
    return np.asarray(rows, dtype=float), np.asarray(pops)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--user-sample", type=int, default=5)
    ap.add_argument("--n-eval", type=int, default=N_EVAL)   # smaller only for a quick check on ml-latest-small
    args = ap.parse_args()
    pos, n_items = load_sample(args.data_dir, args.user_sample, 20)
    train, test = time_split(pos)
    X = matrix(train, n_items)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    eligible = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]
    n_eval = min(args.n_eval, len(eligible) // 2)
    picked = np.random.default_rng(7).choice(eligible, 2 * n_eval, replace=False)
    val, tst = list(picked[:n_eval]), list(picked[n_eval:])
    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    knn, _ = m_knn(X, shrink, top=TOP)
    E = content_embeddings(args.data_dir, pos)
    counts = np.bincount(train["item"], minlength=n_items).astype(float)
    pop_pct = np.argsort(np.argsort(counts)) / max(n_items - 1, 1)
    print("ready", flush=True)

    val_ndcg = {}
    for w in GRID_W:
        for p in GRID_P:
            r, _ = run(val, tb, te, knn, E, pop_pct, w, p)
            val_ndcg[(w, p)] = float(r[:, 1].mean())
            print(f"validation w={w} p={p}: NDCG@10 {val_ndcg[(w, p)]:.4f}", flush=True)
    best = max((k for k in val_ndcg if k != (0.0, 0.0)), key=val_ndcg.get)
    r_best, pop_best = run(tst, tb, te, knn, E, pop_pct, *best)
    r_fan, pop_fan = run(tst, tb, te, knn, E, pop_pct, 0.0, 0.0)
    d, lo, hi, _ = paired_bootstrap(r_best[:, 1], r_fan[:, 1], np.mean)
    keep = bool(lo > -MARGIN and pop_best.mean() < pop_fan.mean())
    out = {
        "method": "python training/confirm_similar.py --data-dir " + Path(args.data_dir).name,
        "test_viewers": len(tst), "candidates": f"each viewer's last liked movie's {TOP} fan neighbors",
        "validation_ndcg": {f"w={w},p={p}": round(v, 4) for (w, p), v in val_ndcg.items()},
        "chosen": {"content_weight": best[0], "popularity_discount": best[1]},
        "test_ndcg": {"re-ranked": round(float(r_best[:, 1].mean()), 4), "fans only": round(float(r_fan[:, 1].mean()), 4)},
        "ndcg_diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "margin": MARGIN,
        "top10_popularity_pct": {"re-ranked": round(float(pop_best.mean()), 3), "fans only": round(float(pop_fan.mean()), 3)},
        "ship": keep,
    }
    (ROOT / "data" / "similar_confirm.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
