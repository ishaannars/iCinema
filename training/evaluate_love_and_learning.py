"""Two tests behind two claims in the app: the love chance on a card, and "it learns you."

    python training/evaluate_love_and_learning.py --data-dir ml-32m

Uses the benchmark's sample, time split, and viewers (training/benchmark_cf.py) and the shipped
routed ranking (item-kNN, or RP3beta for less mainstream likes).

1. Love chance. "If you watch it, how likely are you to love it?" Each viewer is ranked over a
   pool shaped like the app's: the 600 most-loved movies they haven't seen. Every movie they
   later rated (any star rating) is a data point: its top-% rank in the pool, and whether they
   gave it 4+ stars. Isotonic regression maps rank to chance, fit on 3,000 validation viewers
   and checked once on 3,000 test viewers.
   Rule written before running: it ships only if test calibration error (ECE) is under 3 points
   and its Brier score beats always guessing the average (paired-bootstrap interval below zero).

2. Learning curve. For test viewers with 50+ earlier loves, picks are made from 3, 5, 10, 25,
   and 50 of those loves, and scored against what they loved later.
   Rule written before running: "gets sharper as you use it" may be claimed only if NDCG@10 with
   10 choices beats 3 choices (paired-bootstrap interval above zero).

Writes data/love_chance.json and data/learning_curve.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_knn, matrix  # noqa: E402
from confirm_routing import routed_scorer  # noqa: E402
from evaluate_long_tail import pct, rp3beta  # noqa: E402
from train_cf import metrics, paired_bootstrap, time_split  # noqa: E402

POOL = 600
BANDS = [1, 2, 5, 10, 20, 35, 50, 75, 100]   # top-% cut points shown in the results table
STEPS = [3, 5, 10, 25, 50]


def ece(p, y, bins=10):
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
    return float(sum(abs(p[idx == b].mean() - y[idx == b].mean()) * (idx == b).mean()
                     for b in range(bins) if (idx == b).any()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    pos, n = load_sample(args.data_dir, 5, 20)
    train, test = time_split(pos)
    X = matrix(train, n)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    cutoff = train.groupby("userId")["timestamp"].max()
    eligible = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]
    picked = np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False)
    val, tst = list(picked[:N_EVAL]), list(picked[N_EVAL:])

    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    beta = float(json.loads((ROOT / "data" / "long_tail_confirm.json").read_text())["beta"])
    cut = float(json.loads((ROOT / "data" / "routing_confirm.json").read_text())["niche_cut_fan_percentile"])
    fans = X.getnnz(axis=0).astype(float)
    rank = routed_scorer(m_knn(X, shrink, top=100)[0], rp3beta(X, beta), pct(fans), cut)
    by_fans = np.argsort(-fans)
    item_of = pos.drop_duplicates("movieId").set_index("movieId")["item"]

    # Every later rating (any stars) for the viewers we score, after their training cutoff.
    wanted = set(val) | set(tst)
    later = []
    for ch in pd.read_csv(Path(args.data_dir) / "ratings.csv", chunksize=4_000_000,
                          dtype={"userId": "int32", "movieId": "int32", "rating": "float32", "timestamp": "int64"}):
        ch = ch[ch["userId"].isin(wanted) & ch["movieId"].isin(item_of.index)]
        later.append(ch[ch["timestamp"] > ch["userId"].map(cutoff)])
    later = pd.concat(later)
    later["item"] = later["movieId"].map(item_of)
    rated = {u: dict(zip(g["item"], g["rating"] >= 4.0)) for u, g in later.groupby("userId")}
    print(f"ready: {len(later):,} later ratings", flush=True)

    def points(users, seed=5):
        r = np.random.default_rng(seed)
        out = []
        for u in users:
            hist = tb[u]
            seeds = [hist[i] for i in sorted(r.choice(len(hist), 3, replace=False))]
            seen = set(hist)
            pool = [i for i in by_fans if i not in seen][:POOL]
            s = np.asarray(rank(np.asarray(seeds)), dtype=float)[pool]
            order = np.argsort(-s)
            top_pct = np.empty(len(pool)); top_pct[order] = (np.arange(len(pool)) + 1) / len(pool) * 100
            where = {item: k for k, item in enumerate(pool)}
            for item, loved in (rated.get(u) or {}).items():
                if item in where:
                    out.append((u, top_pct[where[item]], float(loved)))
        return out

    pv, pt = points(val), points(tst)
    iso = IsotonicRegression(increasing=False, y_min=0.0, y_max=1.0, out_of_bounds="clip")
    iso.fit([p for _, p, _ in pv], [y for _, _, y in pv])
    users_t = np.array([u for u, _, _ in pt]); xt = np.array([p for _, p, _ in pt]); yt = np.array([y for _, _, y in pt])
    pred = iso.predict(xt)
    base = float(np.mean([y for _, _, y in pv]))
    # Per-viewer Brier, so the bootstrap resamples viewers rather than ratings.
    ids = np.unique(users_t)
    b_model = np.array([np.mean((pred[users_t == u] - yt[users_t == u]) ** 2) for u in ids])
    b_base = np.array([np.mean((base - yt[users_t == u]) ** 2) for u in ids])
    d, lo, hi, _ = paired_bootstrap(b_model, b_base, np.mean)
    err = ece(pred, yt)
    from sklearn.metrics import roc_auc_score
    love = {"method": " ".join(__doc__.split("\n\n")[1].split()), "pool": POOL,
            "validation_points": len(pv), "test_points": len(pt), "test_viewers": int(len(ids)),
            "average_love_rate": round(base, 4),
            "table": [{"top_pct": b, "chance": round(float(iso.predict([b])[0]), 4)} for b in BANDS],
            "test_ece": round(err, 4), "test_auc": round(float(roc_auc_score(yt, -xt)), 4),
            "brier_diff_vs_average": round(d, 5), "brier_ci95": [round(lo, 5), round(hi, 5)],
            "ships": bool(err < 0.03 and hi < 0)}
    (ROOT / "data" / "love_chance.json").write_text(json.dumps(love, indent=1))
    print(json.dumps({k: v for k, v in love.items() if k != "method"}, indent=1), flush=True)

    # Learning curve.
    heavy = [u for u in tst if len(tb[u]) >= max(STEPS)]
    r = np.random.default_rng(13)
    res = {k: [] for k in STEPS}
    for u in heavy:
        hist = tb[u]
        order = r.permutation(len(hist))
        for k in STEPS:
            seeds = [hist[i] for i in sorted(order[:k])]
            s = np.asarray(rank(np.asarray(seeds)), dtype=float)
            s[hist] = -np.inf
            top = np.argpartition(-s, 50)[:50]
            res[k].append(metrics(top[np.argsort(-s[top])], te[u]))
    res = {k: np.asarray(v, dtype=float) for k, v in res.items()}
    d, lo, hi, _ = paired_bootstrap(res[10][:, 1], res[3][:, 1], np.mean)
    curve = {"method": " ".join(__doc__.split("\n\n")[2].split()), "viewers": len(heavy),
             "steps": [{"choices": k, "hit@1": round(float(res[k][:, 2].mean()), 4),
                        "ndcg@10": round(float(res[k][:, 1].mean()), 4)} for k in STEPS],
             "ndcg_gain_10_vs_3": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)],
             "claim_allowed": bool(lo > 0)}
    (ROOT / "data" / "learning_curve.json").write_text(json.dumps(curve, indent=1))
    print(json.dumps({k: v for k, v in curve.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
