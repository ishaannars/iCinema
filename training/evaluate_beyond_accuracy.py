"""Beyond accuracy: how much of the catalog each model reaches, how well-known its picks are, and
how varied a top 10 is.

    python training/evaluate_beyond_accuracy.py --data-dir ml-32m

Same viewers and same 3 random likes as the benchmark (first 1-in-5 slice, the 3,000 test viewers,
seed 5), so these sit next to the accuracy numbers. For each viewer, each model's top 10 (movies
they already liked removed):
- Catalog coverage: share of the benchmark's movies that appear in at least one viewer's top 10.
- Popularity of picks: average fan percentile of the top 10 (0 = fewest MovieLens fans, 100 = most).
  Lower means less obvious picks.
- Variety in a top 10: average share of movie pairs in the list that have different genre sets
  (1 minus genre Jaccard similarity, MovieLens genres).
Models: popularity, item-kNN (top-100), RP3beta (top-100, shipped beta), and routed (what the app
does).

Rule written before running: these numbers describe the shipped models; nothing is tuned or
changed because of them, and there's no pass or fail. Routed vs item-kNN gets paired-bootstrap 95%
intervals on popularity of picks and variety (2,000 resamples of viewers). Coverage is reported as
a single number. Writes data/beyond_accuracy.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_knn, m_popularity, matrix  # noqa: E402
from confirm_routing import routed_scorer  # noqa: E402
from evaluate_long_tail import pct, rp3beta  # noqa: E402
from train_cf import paired_bootstrap, time_split  # noqa: E402

K = 10


def genre_variety(items, genre_sets):
    sets = [genre_sets[i] for i in items]
    d = []
    for a in range(len(sets)):
        for b in range(a + 1, len(sets)):
            u = sets[a] | sets[b]
            d.append(1.0 - (len(sets[a] & sets[b]) / len(u) if u else 1.0))
    return float(np.mean(d)) if d else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    pos, n = load_sample(args.data_dir, 5, 20)
    train, test = time_split(pos)
    X = matrix(train, n)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    eligible = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]   # same viewers as evaluate_rows.py
    tst = list(np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False))[N_EVAL:]

    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    shrink = float(bench["results"]["item-kNN"]["params"][0])
    beta = float(json.loads((ROOT / "data" / "long_tail_confirm.json").read_text())["beta"])
    cut = float(json.loads((ROOT / "data" / "routing_confirm.json").read_text())["niche_cut_fan_percentile"])
    fan_pct = pct(X.getnnz(axis=0).astype(float))
    knn, _ = m_knn(X, shrink, top=100)
    rp3 = rp3beta(X, beta)
    pop, _ = m_popularity(X)
    models = {"Popularity": pop, "item-kNN": knn, "RP3beta": rp3, "Routed (what the app does)": routed_scorer(knn, rp3, fan_pct, cut)}

    item_movie = pos.drop_duplicates("item").set_index("item")["movieId"].sort_index()
    movies = pd.read_csv(Path(args.data_dir) / "movies.csv").set_index("movieId")
    genre_sets = [frozenset(str(movies.loc[m, "genres"]).split("|")) if m in movies.index else frozenset()
                  for m in item_movie.values]

    rng = np.random.default_rng(5)
    seeds = {}
    for u in tst:
        hist = tb[u]
        seeds[u] = [hist[i] for i in sorted(rng.choice(len(hist), 3, replace=False))]

    per = {}
    out = {"method": " ".join(__doc__.split("\n\n")[1:4]).replace("\n", " "), "viewers": len(tst),
           "catalog_movies": int(n), "top_k": K, "models": {}}
    for name, f in models.items():
        shown, popv, var = set(), [], []
        for u in tst:
            s = np.asarray(f(np.asarray(seeds[u])), dtype=np.float64)
            s[tb[u]] = -np.inf
            top = np.argpartition(-s, K)[:K]
            top = top[np.argsort(-s[top])]
            shown.update(top.tolist())
            popv.append(float(fan_pct[top].mean() * 100))
            var.append(genre_variety(top.tolist(), genre_sets))
        per[name] = (np.asarray(popv), np.asarray(var))
        out["models"][name] = {"catalog_coverage": round(len(shown) / n, 4),
                               "pick_popularity_percentile": round(float(np.mean(popv)), 1),
                               "top10_variety": round(float(np.mean(var)), 3)}
        print(name, out["models"][name], flush=True)
    r, k = per["Routed (what the app does)"], per["item-kNN"]
    dp, lp, hp, _ = paired_bootstrap(r[0], k[0], np.mean)
    dv, lv, hv, _ = paired_bootstrap(r[1], k[1], np.mean)
    out["routed_vs_knn"] = {"pick_popularity_diff": round(dp, 2), "pick_popularity_ci95": [round(lp, 2), round(hp, 2)],
                            "variety_diff": round(dv, 4), "variety_ci95": [round(lv, 4), round(hv, 4)]}
    (ROOT / "data" / "beyond_accuracy.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["routed_vs_knn"], indent=1))


if __name__ == "__main__":
    main()
