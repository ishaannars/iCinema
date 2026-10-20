"""Does each Showroom row find movies you'll love within its own kind of movie?

    python training/evaluate_rows.py --data-dir ml-32m

Each row limits itself to one kind of movie, so a row is only useful if, inside that limit, the
shipped "viewers like you" ranking still finds what you'll love. On the benchmark's 3,000 test
viewers (3 random likes each), every row is scored against the obvious alternative: the most
popular movies of that same kind.
- Hidden Gems: movies outside the 20% most-loved.
- Critically Acclaimed: movies averaging 4.0+ stars from at least 500 ratings (MovieLens stands in
  for critic scores).
- Something Different: movies outside the viewer's 3 most-liked genres.
A viewer counts for a row only if they later loved at least one movie of that kind.
Rule written before running: a row is supported if the shipped ranking beats popularity of the
same kind on Hit@10 (paired-bootstrap 95% interval above zero). Writes data/rows_results.json.
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
from evaluate_long_tail import pct, rp3beta  # noqa: E402
from train_cf import paired_bootstrap, time_split  # noqa: E402


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
    tst = list(np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False))[N_EVAL:]
    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    rt = json.loads((ROOT / "data" / "routing_confirm.json").read_text())
    beta = float(json.loads((ROOT / "data" / "long_tail_confirm.json").read_text())["beta"])
    fans = X.getnnz(axis=0).astype(float)
    fan_pct = pct(fans)
    ranker = routed_scorer(m_knn(X, shrink, top=100)[0], rp3beta(X, beta), fan_pct, rt["niche_cut_fan_percentile"]) \
        if rt.get("ship_routing") else m_knn(X, shrink, top=100)[0]

    d = Path(args.data_dir)
    item_movie = pos.drop_duplicates("item").set_index("item")["movieId"].sort_index()
    movies = pd.read_csv(d / "movies.csv").set_index("movieId")
    genres = [movies.loc[m, "genres"].split("|")[0] if m in movies.index else "" for m in item_movie.values]
    sums, counts = Counter(), Counter()
    sample_users = set(pos["userId"].unique())
    for ch in pd.read_csv(d / "ratings.csv", chunksize=4_000_000, usecols=["userId", "movieId", "rating"]):
        ch = ch[ch["userId"].isin(sample_users)]
        g = ch.groupby("movieId")["rating"].agg(["sum", "count"])
        sums.update(g["sum"].to_dict()); counts.update(g["count"].to_dict())
    avg = np.array([sums[m] / counts[m] if counts[m] else 0 for m in item_movie.values])
    cnt = np.array([counts[m] for m in item_movie.values])
    rows = {
        "Hidden Gems": lambda u: fan_pct < 0.80,
        "Critically Acclaimed": lambda u: (avg >= 4.0) & (cnt >= 500),
        "Something Different": lambda u: ~np.isin(np.array(genres), [g for g, _ in Counter(genres[i] for i in tb[u]).most_common(3)]),
    }
    rng = np.random.default_rng(5)
    seeds_by_user = {}
    for u in tst:
        hist = tb[u]
        seeds_by_user[u] = [hist[i] for i in sorted(rng.choice(len(hist), 3, replace=False))]
    out = {"method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "), "rows": {}}
    for name, allowed_fn in rows.items():
        hit_m, hit_p = [], []
        for u in tst:
            allowed = allowed_fn(u).copy()
            allowed[tb[u]] = False
            truth = [i for i in te[u] if allowed[i]]
            if not truth or allowed.sum() < 10:
                continue
            idx = np.flatnonzero(allowed)
            s = np.asarray(ranker(np.asarray(seeds_by_user[u])), dtype=np.float64)[idx]
            top_m = set(idx[np.argsort(-s)[:10]].tolist())
            top_p = set(idx[np.argsort(-fans[idx])[:10]].tolist())
            hit_m.append(float(bool(top_m & set(truth))))
            hit_p.append(float(bool(top_p & set(truth))))
        hm, hp = np.asarray(hit_m), np.asarray(hit_p)
        diff, lo, hi, _ = paired_bootstrap(hm, hp, np.mean)
        out["rows"][name] = {"viewers": len(hm), "hit@10_shipped": round(float(hm.mean()), 4),
                             "hit@10_popular_of_that_kind": round(float(hp.mean()), 4),
                             "diff": round(diff, 4), "ci95": [round(lo, 4), round(hi, 4)], "supported": bool(lo > 0)}
        print(name, out["rows"][name], flush=True)
    (ROOT / "data" / "rows_results.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
