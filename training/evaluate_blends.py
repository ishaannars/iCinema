"""Test iCinema's hand-set blend weights and error patterns offline on MovieLens.

    python training/evaluate_blends.py --data-dir ml-32m

Same 1-in-5 MovieLens 32M sample, time split, and 3,000 validation / 3,000 test viewers as
training/benchmark_cf.py. Rules written before running:

1. Content vs "viewers like you" blend (the app uses 65% content, 35% viewers like you).
   Content here is a stand-in for the app's content score: TF-IDF + SVD over each movie's
   MovieLens genres and user tags. Both scores are turned into percentiles, as in the app.
   The weight is picked on validation viewers and scored once on test viewers. The app's
   weight changes only if the best weight beats 65% on test by a paired-bootstrap interval
   above zero. Otherwise 65% is kept and labeled as tested. MovieLens can't measure the
   viewer's own Step 2-3 answers (genres, reviews vs enjoyment, openness), which only the
   content score carries, so content always keeps at least 20%.
2. What's next (the app uses 60% similarity to the watched movie, 40% personal match).
   Source = each viewer's most recent liked movie. Same pick-on-validation rule, and the
   personal match (which carries the Step 2-3 answers) keeps at least 20%.
3. Where it's wrong: hit rate by how many movies a viewer has liked, and by how popular
   the movie they went on to love was.
Writes data/blend_results.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_knn, matrix  # noqa: E402
from train_cf import FIRST_HIT_DEPTH, metrics, paired_bootstrap, time_split  # noqa: E402

GRID = [0.0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0]


def pct(s):
    """Rank-percentile in [0, 1] (ties share a rank), like the app's 0-1 scores."""
    order = s.argsort(kind="stable")
    r = np.empty(len(s), dtype=np.float64)
    r[order] = np.arange(len(s))
    return r / max(len(s) - 1, 1)


def content_embeddings(data_dir, pos):
    d = Path(data_dir)
    movies = pd.read_csv(d / "movies.csv")
    tags = pd.read_csv(d / "tags.csv", usecols=["movieId", "tag"])
    tags = tags.dropna(subset=["tag"])
    tags["tag"] = tags["tag"].astype(str).str.lower().str.replace(r"[^\w\s]", " ", regex=True)
    tag_text = tags.groupby("movieId")["tag"].apply(lambda t: " ".join(str(x) for x in t.head(300)))
    item_movie = pos.drop_duplicates("item").set_index("item")["movieId"].sort_index()
    m = movies.set_index("movieId")
    docs = [(m.loc[mid, "genres"].replace("|", " ") + " ") * 3 + tag_text.get(mid, "") if mid in m.index else ""
            for mid in item_movie.values]
    X = TfidfVectorizer(min_df=3, max_features=20000, sublinear_tf=True).fit_transform(docs)
    E = TruncatedSVD(64, random_state=7).fit_transform(X).astype(np.float32)
    E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-8
    return E


def run(users, train_by_user, test_by_user, score_fn, seed=5):
    rng = np.random.default_rng(seed)
    out = []
    for u in users:
        hist = train_by_user[u]
        seeds = [hist[i] for i in sorted(rng.choice(len(hist), 3, replace=False))]
        s = score_fn(seeds, hist)
        s[hist] = -np.inf
        top = np.argpartition(-s, FIRST_HIT_DEPTH)[:FIRST_HIT_DEPTH]
        out.append(metrics(top[np.argsort(-s[top])], test_by_user[u]))
    return np.asarray(out, dtype=float)


def pick(name, grid, make, val, test, tb, te, current, allowed):
    val_ndcg = {w: float(run(val, tb, te, make(w))[:, 1].mean()) for w in grid}
    unconstrained = max(val_ndcg, key=val_ndcg.get)
    best = max((w for w in grid if allowed(w)), key=val_ndcg.get)
    r_best, r_cur = run(test, tb, te, make(best)), run(test, tb, te, make(current))
    d, lo, hi, win = paired_bootstrap(r_best[:, 1], r_cur[:, 1], np.mean)
    change = bool(best != current and lo > 0)
    print(f"{name}: best on validation {best} | test NDCG {r_best[:, 1].mean():.4f} vs current {current}: "
          f"{r_cur[:, 1].mean():.4f} (diff {d:+.4f}, CI {lo:+.4f} to {hi:+.4f}) -> {'CHANGE' if change else 'keep'}", flush=True)
    return {"validation_ndcg_by_weight": {str(k): round(v, 4) for k, v in val_ndcg.items()},
            "best_weight_without_floor": unconstrained, "best_weight": best, "current_weight": current,
            "test_best": {"hit@1": round(float(r_best[:, 2].mean()), 4), "ndcg@10": round(float(r_best[:, 1].mean()), 4)},
            "test_current": {"hit@1": round(float(r_cur[:, 2].mean()), 4), "ndcg@10": round(float(r_cur[:, 1].mean()), 4)},
            "ndcg_diff_vs_current": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "change": change}


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
    E = content_embeddings(args.data_dir, pos)
    print("content embeddings ready", flush=True)

    def blend(w):  # w = content weight
        return lambda seeds, hist: w * pct(E @ E[seeds].mean(axis=0)) + (1 - w) * pct(knn(np.asarray(seeds)))

    def whats_next(a):  # a = similarity-to-watched weight; source = most recent like
        return lambda seeds, hist: a * pct(knn(np.asarray(hist[-1:]))) + (1 - a) * pct(
            0.65 * pct(E @ E[seeds].mean(axis=0)) + 0.35 * pct(knn(np.asarray(seeds))))

    out = {"method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " ")}
    out["content_blend"] = pick("Content vs viewers-like-you", GRID, blend, val, tst, tb, te, 0.65, lambda w: w >= 0.2)
    out["whats_next"] = pick("What's next", [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], whats_next, val, tst, tb, te, 0.6, lambda a: a <= 0.8)
    out["content_only_ndcg"] = round(float(run(tst, tb, te, blend(1.0))[:, 1].mean()), 4)
    out["viewers_like_you_only_ndcg"] = round(float(run(tst, tb, te, blend(0.0))[:, 1].mean()), 4)

    # Where it's wrong: shipped item-kNN on 3 random likes, by viewer history and by movie popularity.
    pop = np.bincount(train["item"], minlength=n_items)
    rng = np.random.default_rng(5)
    rows = []
    for u in tst:
        hist = tb[u]
        seeds = [hist[i] for i in sorted(rng.choice(len(hist), 3, replace=False))]
        s = knn(np.asarray(seeds)).astype(np.float64)
        s[hist] = -np.inf
        first = int(np.argmax(s))
        loved = te[u]
        rows.append({"history": len(hist), "hit": float(first in loved),
                     "median_pop_of_loved": float(np.median(pop[list(loved)]))})
    r = pd.DataFrame(rows)
    r["history_band"] = pd.cut(r["history"], [0, 10, 30, 100, 10**6], labels=["3–10", "11–30", "31–100", "100+"])
    q = r["median_pop_of_loved"].quantile([0.25, 0.75]).to_numpy()
    r["taste_band"] = np.where(r["median_pop_of_loved"] <= q[0], "Niche taste (least popular 25%)",
                               np.where(r["median_pop_of_loved"] >= q[1], "Mainstream taste (most popular 25%)", "Middle 50%"))
    out["errors"] = {
        "by_history": [{"liked_movies": str(k), "viewers": int(len(g)), "hit@1": round(float(g["hit"].mean()), 4)}
                       for k, g in r.groupby("history_band", observed=True)],
        "by_taste": [{"group": k, "viewers": int(len(g)), "hit@1": round(float(g["hit"].mean()), 4)}
                     for k, g in r.groupby("taste_band")],
        "overall_hit@1": round(float(r["hit"].mean()), 4),
    }
    print(json.dumps(out["errors"], indent=1))
    (ROOT / "data" / "blend_results.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
