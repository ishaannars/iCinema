"""Should "More Like X" also use your own taste? Held-out test on MovieLens.

    python training/confirm_like_blend.py --data-dir ml-32m

Same 1-in-5 MovieLens 32M sample, time split, and 3,000 validation / 3,000 test viewers as
training/confirm_like.py. Source movie X = each viewer's most recent liked movie ("I just watched X").
Target = the movies they went on to love (held-out ratings of 4+). Only ratings before the target
period are used, so nothing from the answer key leaks into the ranking. Rules written before running:

1. A (shipped): X's 100 closest movies by item-kNN, closest first.
2. B (blend): the same 100, ordered by (1 - w) x closeness rank + w x your-fit rank, where your fit is
   the item-kNN score from your own earlier likes. w is chosen from 0.2, 0.4, 0.6 on the validation
   viewers only, then fixed before the single test run.
3. B ships only if, on test viewers, it beats A on NDCG@10 by at least 2% relative AND the paired-
   bootstrap 95% interval of the difference is above zero.
4. Guard so it still means "like X": B's top 10 must keep at least 90% of A's average closeness to X.
   If it doesn't, B does not ship even if rule 3 passes.
Writes data/like_blend_confirm.json; the app reads its "ship" and "weight" fields.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_knn, matrix  # noqa: E402
from train_cf import FIRST_HIT_DEPTH, metrics, paired_bootstrap, time_split  # noqa: E402

WEIGHTS = [0.2, 0.4, 0.6]


def ranks01(values):
    """1.0 for the highest value, falling to ~0 for the lowest (ties share the order they came in)."""
    v = np.asarray(values, dtype=float)
    return 1 - np.argsort(np.argsort(-v)) / max(len(v), 1)


def blend_order(near, close, fit, w):
    score = (1 - w) * ranks01(close) + w * ranks01(fit)
    return near[np.argsort(-score)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--user-sample", type=int, default=5)
    args = ap.parse_args()
    pos, n_items = load_sample(args.data_dir, args.user_sample, 20)
    train, test = time_split(pos)
    X = matrix(train, n_items)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    eligible = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]
    picked = np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False)
    val, tst = list(picked[:N_EVAL]), list(picked[N_EVAL:])
    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    knn, _ = m_knn(X, float(bench["results"]["item-kNN"]["params"][0]), top=100)

    def lists(u):
        hist = tb[u]
        src = hist[-1]
        s = np.asarray(knn(np.asarray([src])), dtype=float).ravel()
        s[src] = -np.inf
        near = np.argpartition(-s, 100)[:100]
        near = near[np.argsort(-s[near])]
        seen = set(hist)
        keep = np.asarray([i for i in near if i not in seen], dtype=int)
        fit = np.asarray(knn(np.asarray(hist)), dtype=float).ravel()
        return keep, s[keep], fit[keep]

    cache = {u: lists(u) for u in val + tst}

    def run(users, w):
        res, closeness = [], []
        for u in users:
            near, close, fit = cache[u]
            order = near if w == 0 else blend_order(near, close, fit, w)
            res.append(metrics(np.asarray(order[:FIRST_HIT_DEPTH], dtype=int), te[u]))
            top = order[:10]
            lookup = dict(zip(near.tolist(), close.tolist()))
            closeness.append(float(np.mean([lookup[i] for i in top])) if len(top) else 0.0)
        return np.asarray(res, dtype=float), float(np.mean(closeness))

    val_scores = {w: float(run(val, w)[0][:, 1].mean()) for w in WEIGHTS}
    w_best = max(val_scores, key=val_scores.get)
    rA, closeA = run(tst, 0)
    rB, closeB = run(tst, w_best)
    d, lo, hi, _ = paired_bootstrap(rB[:, 1], rA[:, 1], np.mean)
    a_mean, b_mean = float(rA[:, 1].mean()), float(rB[:, 1].mean())
    lift = (b_mean - a_mean) / a_mean if a_mean else 0.0
    guard = closeB >= 0.9 * closeA
    ship = bool(lo > 0 and lift >= 0.02 and guard)
    out = {
        "method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "),
        "validation_ndcg@10_by_weight": {str(k): round(v, 4) for k, v in val_scores.items()},
        "weight": w_best,
        "test_viewers": len(tst),
        "ndcg@10": {"closest_first": round(a_mean, 4), "blend": round(b_mean, 4)},
        "hit@1": {"closest_first": round(float(rA[:, 2].mean()), 4), "blend": round(float(rB[:, 2].mean()), 4)},
        "blend_vs_closest": {"diff": round(d, 4), "relative": round(lift, 4), "ci95": [round(lo, 4), round(hi, 4)]},
        "closeness_kept": round(closeB / closeA, 4) if closeA else None,
        "guard_passed": bool(guard),
        "ship": ship,
    }
    print(json.dumps(out, indent=1))
    (ROOT / "data" / "like_blend_confirm.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
