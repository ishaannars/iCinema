"""Should Seen thumbs also train the personal model? Simulation on held-out MovieLens viewers (version 2).

    python training/confirm_seen_thumbs.py --data-dir ml-32m

There are no real iCinema users yet, so this is a simulation, and the README says so. For each held-out
viewer, ratings are put in time order. Their first 3 movies rated 4+ are the onboarding likes. The next
20 rated movies stand in for Saves and Skips (rated 4+ = save, rated 2 or less = skip). Movies they had
rated before onboarding stand in for Seen thumbs (4+ = thumbs up, 2 or less = thumbs down; up to 20).
The test is the next 30 rated movies after the decisions (4+ vs 2 or less; 3s left out).

The personal model is a per-viewer logistic regression on signals like the ones the app gives it, all from
data the viewer couldn't have influenced: how close each movie is to every movie they liked before the
decisions (item-kNN, fit only on other viewers), how popular it is, and how highly other viewers rate it.
Version 1 used only the first 3 likes and popularity; both arms scored ~0.5 AUC (chance), so it could not
detect harm. Version 2 adds the signals above and uses 40 decisions per viewer.
A = trained on saves and skips only (what ships). B = trained on saves, skips and Seen thumbs.
Rules written before running version 2: (1) validity: A's mean AUC must be at least 0.55, or the test is
inconclusive and nothing ships; (2) non-inferiority: B ships only if the lower end of the paired-bootstrap
95% interval of AUC(B) - AUC(A) is above -0.01 (one AUC point). The margin keeps the personal model's
held-out accuracy essentially where it is; starting sooner is a design fact, not a test result.
Writes data/seen_thumbs_confirm.json; the app reads its "ship" field.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import m_knn, matrix  # noqa: E402
from train_cf import paired_bootstrap  # noqa: E402

N_USERS, MARGIN, VALID_AUC, N_DECISIONS = 3000, -0.01, 0.55, 40


def auc(y, s):
    """Rank AUC; None if only one class is present."""
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    pos, neg = s[y == 1], s[y == 0]
    if not len(pos) or not len(neg):
        return None
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def fit_predict(Xtr, ytr, Xte):
    from sklearn.linear_model import LogisticRegression
    if len(set(ytr)) < 2:
        return np.full(len(Xte), float(np.mean(ytr)))
    return LogisticRegression(C=1.0, max_iter=500).fit(Xtr, ytr).predict_proba(Xte)[:, 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--user-sample", type=int, default=5)
    args = ap.parse_args()
    cols = {"userId": "int32", "movieId": "int32", "rating": "float32", "timestamp": "int64"}
    r = pd.concat(ch[ch["userId"] % args.user_sample == 0]
                  for ch in pd.read_csv(Path(args.data_dir) / "ratings.csv", chunksize=4_000_000, dtype=cols))
    r = r.sort_values(["userId", "timestamp"])
    counts = r.loc[r["rating"] >= 4, "movieId"].value_counts()
    r = r[r["movieId"].isin(counts[counts >= 20].index)]
    items = np.sort(r["movieId"].unique())
    r = r.assign(item=r["movieId"].map({m: i for i, m in enumerate(items)}).astype(np.int32))
    n_items = len(items)

    per_user = {u: g for u, g in r.groupby("userId") if len(g) >= 80}
    users = list(np.random.default_rng(7).choice(list(per_user), min(N_USERS, len(per_user)), replace=False))
    held = set(users)
    others = r[(~r["userId"].isin(held)) & (r["rating"] >= 4)]
    X = matrix(others, n_items)
    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    knn, _ = m_knn(X, float(bench["results"]["item-kNN"]["params"][0]), top=100)
    pop = np.asarray(X.sum(axis=0)).ravel().astype(float)
    pop_pct = np.argsort(np.argsort(pop)) / max(len(pop) - 1, 1)
    rest = r[~r["userId"].isin(held)]
    mean_r = rest.groupby("item")["rating"].mean().reindex(range(n_items)).fillna(rest["rating"].mean()).to_numpy()
    mean_z = (mean_r - mean_r.mean()) / (mean_r.std() or 1.0)

    a_scores, b_scores, used = [], [], 0
    for u in users:
        g = per_user[u]
        likes_idx = np.flatnonzero(g["rating"].to_numpy() >= 4)
        if len(likes_idx) < 3:
            continue
        start = likes_idx[2] + 1
        onboarding = g["item"].to_numpy()[likes_idx[:3]]
        before = g.iloc[:likes_idx[0]]
        after = g.iloc[start:]
        decisions, test = after.iloc[:N_DECISIONS], after.iloc[N_DECISIONS:N_DECISIONS + 30]
        prior = g.iloc[:start]
        liked_before = prior.loc[prior["rating"] >= 4, "item"].to_numpy()
        s = np.asarray(knn(liked_before if len(liked_before) else onboarding), dtype=float).ravel()
        s_pct = np.argsort(np.argsort(s)) / max(len(s) - 1, 1)

        def xy(df):
            df = df[(df["rating"] >= 4) | (df["rating"] <= 2)]
            it = df["item"].to_numpy()
            return np.c_[s_pct[it], pop_pct[it], mean_z[it]], (df["rating"].to_numpy() >= 4).astype(int)

        Xa, ya = xy(decisions)
        Xt, yt = xy(before.iloc[-20:])
        Xe, ye = xy(test)
        if len(ya) < 5 or len(set(ye)) < 2:
            continue
        a = auc(ye, fit_predict(Xa, ya, Xe))
        b = auc(ye, fit_predict(np.r_[Xa, Xt], np.r_[ya, yt], Xe))
        if a is None or b is None:
            continue
        a_scores.append(a); b_scores.append(b); used += 1

    A, B = np.asarray(a_scores), np.asarray(b_scores)
    d, lo, hi, _ = paired_bootstrap(B, A, np.mean)
    valid = bool(A.mean() >= VALID_AUC)
    ship = bool(valid and lo > MARGIN)
    out = {
        "method": "Simulation on held-out MovieLens viewers; see the docstring of training/confirm_seen_thumbs.py.",
        "viewers": used,
        "auc": {"saves_and_skips": round(float(A.mean()), 4), "plus_seen_thumbs": round(float(B.mean()), 4)},
        "difference": {"point": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "margin": MARGIN},
        "baseline_valid": valid,
        "validity_rule": f"saves-and-skips AUC must be at least {VALID_AUC}",
        "version": 2,
        "simulation": True,
        "ship": ship,
    }
    print(json.dumps(out, indent=1))
    (ROOT / "data" / "seen_thumbs_confirm.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
