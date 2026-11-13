"""Test the hand-set Showroom settings: each row's mix and the variety step. Held-out MovieLens.

    python training/evaluate_knobs.py --data-dir ml-32m

Same 1-in-5 MovieLens 32M sample, time split, shipped ranking and 3 random likes per viewer as
training/evaluate_rows.py; 3,000 validation and 3,000 different test viewers. Rules written before running:

1. Row mixes. Each row scores every movie as (1 - w) x your fit + w x the row's own signal, with the
   MovieLens stand-ins evaluate_rows.py uses: Critically Acclaimed = average rating (4.0+ from 500+
   ratings qualifies), Hidden Gems = how little-known a movie is (outside the 20% most-loved qualifies),
   Something Different = outside your 3 most-liked genres. As in the app, only qualifying movies can
   enter a row; the weight decides their order. The weight with the most loved movies of that kind in
   the row's top 10 on validation viewers is picked, then scored once on test viewers against the app's
   current weight. The app changes only if the new weight wins with a paired-bootstrap 95%
   interval above zero; otherwise the current weight stays and is labeled tested.
2. Variety step (MMR). Critics' picks, hidden gems and the fourth row re-order their top 50 to avoid near-duplicates, with similarity from
   genres and fan tags. Variety can't win on accuracy alone, so the rule is: the app uses the most
   variety (lowest setting) whose loved-movies-in-top-10 is not significantly worse than no variety
   (paired-bootstrap interval for the difference reaches zero), scored on test viewers.
Writes data/knobs_results.json; the app reads its "use" fields.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_knn, matrix  # noqa: E402
from confirm_routing import routed_scorer  # noqa: E402
from evaluate_blends import content_embeddings  # noqa: E402
from evaluate_long_tail import pct, rp3beta  # noqa: E402
from train_cf import paired_bootstrap, time_split  # noqa: E402

ROW_GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8]
CURRENT = {"Critically Acclaimed": 0.30, "Hidden Gems": 0.28, "Something Different": 0.20}
LAMBDAS = [1.0, 0.9, 0.8, 0.74, 0.6, 0.5]


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
    picked = list(np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False))
    val, tst = picked[:N_EVAL], picked[N_EVAL:]
    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    rt = json.loads((ROOT / "data" / "routing_confirm.json").read_text())
    beta = float(json.loads((ROOT / "data" / "long_tail_confirm.json").read_text())["beta"])
    fan_pct = pct(X.getnnz(axis=0).astype(float))
    ranker = routed_scorer(m_knn(X, shrink, top=100)[0], rp3beta(X, beta), fan_pct, rt["niche_cut_fan_percentile"]) \
        if rt.get("ship_routing") else m_knn(X, shrink, top=100)[0]

    d = Path(args.data_dir)
    item_movie = pos.drop_duplicates("item").set_index("item")["movieId"].sort_index()
    movies = pd.read_csv(d / "movies.csv").set_index("movieId")
    genres = np.array([movies.loc[m, "genres"].split("|")[0] if m in movies.index else "" for m in item_movie.values])
    sums, counts = Counter(), Counter()
    users = set(pos["userId"].unique())
    for ch in pd.read_csv(d / "ratings.csv", chunksize=4_000_000, usecols=["userId", "movieId", "rating"]):
        g = ch[ch["userId"].isin(users)].groupby("movieId")["rating"].agg(["sum", "count"])
        sums.update(g["sum"].to_dict()); counts.update(g["count"].to_dict())
    avg = np.array([sums[m] / counts[m] if counts[m] else 0 for m in item_movie.values])
    cnt = np.array([counts[m] for m in item_movie.values])
    E = content_embeddings(args.data_dir, pos)

    rng = np.random.default_rng(5)
    seeds = {u: [tb[u][i] for i in sorted(rng.choice(len(tb[u]), 3, replace=False))] for u in val + tst}
    fit = {u: pct(np.asarray(ranker(np.asarray(seeds[u])), dtype=np.float64)).astype(np.float32) for u in val + tst}

    acclaimed = (avg >= 4.0) & (cnt >= 500)
    rows = {
        "Critically Acclaimed": (lambda u: np.where(cnt >= 500, pct(avg), 0.0), lambda u: acclaimed),
        "Hidden Gems": (lambda u: 1 - fan_pct, lambda u: fan_pct < 0.80),
        "Something Different": (
            lambda u: (~np.isin(genres, [g for g, _ in Counter(genres[i] for i in tb[u]).most_common(3)])).astype(float),
            lambda u: ~np.isin(genres, [g for g, _ in Counter(genres[i] for i in tb[u]).most_common(3)])),
    }

    def row_eval(users, signal_fn, qual_fn, w):
        hits = []
        for u in users:
            q = qual_fn(u).copy()
            q[tb[u]] = False
            truth = [i for i in te[u] if q[i]]
            if not truth or q.sum() < 10:
                continue
            idx = np.flatnonzero(q)
            s = (1 - w) * fit[u][idx] + w * signal_fn(u)[idx]
            top = idx[np.argsort(-s)[:10]]
            hits.append(float(bool(set(top.tolist()) & set(truth))))
        return np.asarray(hits)

    out = {"method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "), "rows": {}}
    for name, (signal_fn, qual_fn) in rows.items():
        grid = {w: row_eval(val, signal_fn, qual_fn, w) for w in ROW_GRID}
        best = max(ROW_GRID, key=lambda w: grid[w].mean())
        hb = row_eval(tst, signal_fn, qual_fn, best)
        hc = row_eval(tst, signal_fn, qual_fn, CURRENT[name])
        diff, lo, hi, _ = paired_bootstrap(hb, hc, np.mean)
        change = bool(best != CURRENT[name] and lo > 0)
        out["rows"][name] = {
            "validation_hit@10": {str(w): round(float(grid[w].mean()), 4) for w in ROW_GRID},
            "best_weight": best, "current_weight": CURRENT[name],
            "test_hit@10": {"best": round(float(hb.mean()), 4), "current": round(float(hc.mean()), 4)}, "viewers": len(hb),
            "diff": round(diff, 4), "ci95": [round(lo, 4), round(hi, 4)], "change": change,
            "use": best if change else CURRENT[name],
        }
        print(name, out["rows"][name]["test_hit@10"], "best", best, "change" if change else "keep", flush=True)

    def mmr_hits(users, lam):
        hits, sim4 = [], []
        for u in users:
            s = fit[u].copy()
            s[tb[u]] = -np.inf
            pool = list(np.argpartition(-s, 50)[:50])
            chosen = []
            while pool and len(chosen) < 10:
                vals = [lam * s[i] - (1 - lam) * max((float(E[i] @ E[j]) for j in chosen), default=0.0) for i in pool]
                chosen.append(pool.pop(int(np.argmax(vals))))
            hits.append(float(bool(set(chosen) & te[u])))
            c4 = chosen[:4]
            sim4.append(float(np.mean([E[a] @ E[b] for k, a in enumerate(c4) for b in c4[k + 1:]])))
        return np.asarray(hits), float(np.mean(sim4))

    base_h, base_s = mmr_hits(tst, 1.0)
    curve, use = {}, 1.0
    for lam in LAMBDAS:
        h, simv = mmr_hits(tst, lam) if lam != 1.0 else (base_h, base_s)
        d_, lo, hi, _ = paired_bootstrap(h, base_h, np.mean)
        curve[str(lam)] = {"hit@10": round(float(h.mean()), 4), "similarity_top4": round(simv, 3),
                           "diff_vs_no_variety": round(d_, 4), "ci95": [round(lo, 4), round(hi, 4)]}
        if hi >= 0:
            use = min(use, lam)
    out["variety"] = {"curve": curve, "current": 0.74, "use": use}
    print("variety", json.dumps(out["variety"], indent=1), flush=True)
    (ROOT / "data" / "knobs_results.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
