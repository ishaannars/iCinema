"""
Train iCinema's collaborative-filtering layer on MovieLens (free), evaluate it
against a popularity baseline, and export item embeddings for the app.

Usage:
    python training/train_cf.py --data-dir ml-latest-small
    python training/train_cf.py --data-dir ml-32m --min-count 20

Outputs:
    data/cf_model.npz        item embeddings + TMDB ids + titles (loaded by the app)
    data/cf_results.md       evaluation table for your README
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds

K = 10  # evaluate top-10 recommendations


def normalize_title(title):
    """'Matrix, The (1999)' -> ('the matrix', 1999). Used to match app titles."""
    title = str(title).strip()
    year = None
    m = re.search(r"\((\d{4})\)\s*$", title)
    if m:
        year = int(m.group(1))
        title = title[: m.start()].strip()
    # Drop alternate/original titles: "Memories of Murder (Salinui chueok)" -> "Memories of Murder"
    title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip() or title
    m = re.match(r"^(.*), (The|A|An|Les|La|Le|Il|El|Die|Der|Das)$", title)
    if m:
        title = f"{m.group(2)} {m.group(1)}"
    title = re.sub(r"[^\w\s]", "", title.casefold())
    return " ".join(title.split()), year


def load(data_dir, min_count):
    d = Path(data_dir)
    ratings = pd.read_csv(d / "ratings.csv")
    movies = pd.read_csv(d / "movies.csv")
    links = pd.read_csv(d / "links.csv")

    # Implicit positives: a rating of 4+ behaves like a Like/Save in iCinema.
    pos = ratings[ratings["rating"] >= 4.0][["userId", "movieId", "timestamp"]]
    counts = pos["movieId"].value_counts()
    keep = counts[counts >= min_count].index
    pos = pos[pos["movieId"].isin(keep)]
    user_counts = pos["userId"].value_counts()
    pos = pos[pos["userId"].isin(user_counts[user_counts >= 5].index)]

    item_ids = np.sort(pos["movieId"].unique())
    item_index = {m: i for i, m in enumerate(item_ids)}
    pos = pos.assign(item=pos["movieId"].map(item_index))

    meta = (
        pd.DataFrame({"movieId": item_ids})
        .merge(movies[["movieId", "title"]], on="movieId", how="left")
        .merge(links[["movieId", "tmdbId"]], on="movieId", how="left")
    )
    return pos, meta


def time_split(pos, test_frac=0.2):
    """Per user: earlier positives train, most recent positives test (no look-ahead)."""
    pos = pos.sort_values(["userId", "timestamp"])
    rank = pos.groupby("userId").cumcount()
    size = pos.groupby("userId")["item"].transform("size")
    n_test = np.maximum(1, (size * test_frac).astype(int))
    is_test = rank >= (size - n_test)
    return pos[~is_test], pos[is_test]


def fit_embeddings(train, n_items, dim):
    users = train["userId"].astype("category")
    rows = users.cat.codes.to_numpy()
    cols = train["item"].to_numpy()
    X = csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)),
                   shape=(users.cat.categories.size, n_items))
    # Downweight heavy users and very popular items so SVD learns taste, not just popularity.
    user_norm = 1.0 / np.sqrt(np.asarray(X.sum(axis=1)).ravel() + 1)
    item_norm = 1.0 / np.power(np.asarray(X.sum(axis=0)).ravel() + 1, 0.25)
    X = csr_matrix(X.multiply(user_norm[:, None]).multiply(item_norm[None, :]))
    dim = min(dim, min(X.shape) - 1)
    _, s, vt = svds(X, k=dim)
    emb = (vt.T * np.sqrt(s)).astype(np.float32)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-8
    return emb


FIRST_HIT_DEPTH = 50  # "how many recommendations until a movie they loved?"


def metrics(ranked, truth):
    """Recall@10, NDCG@10, Hit@1, and position of the first loved movie."""
    first = next((i + 1 for i, r in enumerate(ranked[:FIRST_HIT_DEPTH]) if r in truth),
                 FIRST_HIT_DEPTH + 1)
    hits = [1.0 if r in truth else 0.0 for r in ranked[:K]]
    recall = sum(hits) / min(K, len(truth))
    dcg = sum(h / np.log2(i + 2) for i, h in enumerate(hits))
    idcg = sum(1 / np.log2(i + 2) for i in range(min(K, len(truth))))
    return recall, dcg / idcg, float(ranked[0] in truth), first


def evaluate(train, test, emb, n_items, seed_size=None, max_users=3000, rng_seed=7):
    popularity = np.bincount(train["item"], minlength=n_items).astype(float)
    train_by_user = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    test_by_user = test.groupby("userId")["item"].apply(set)
    users = [u for u in test_by_user.index if u in train_by_user.index]
    rng = np.random.default_rng(rng_seed)
    if len(users) > max_users:
        users = list(rng.choice(users, max_users, replace=False))

    out = {"popularity": [], "cf": []}
    for u in users:
        seeds = train_by_user[u]
        if seed_size:  # simulate onboarding: user only told us a few likes
            seeds = seeds[-seed_size:]
        truth = test_by_user[u]
        seen = set(train_by_user[u])

        pop_scores = popularity.copy()
        pop_scores[list(seen)] = -np.inf
        out["popularity"].append(metrics(np.argsort(-pop_scores)[:FIRST_HIT_DEPTH], truth))

        uvec = emb[seeds].mean(axis=0)
        cf_scores = emb @ uvec
        cf_scores[list(seen)] = -np.inf
        out["cf"].append(metrics(np.argsort(-cf_scores)[:FIRST_HIT_DEPTH], truth))

    return {m: {"recall@10": float(np.mean([x[0] for x in v])),
                "ndcg@10": float(np.mean([x[1] for x in v])),
                "hit@1": float(np.mean([x[2] for x in v])),
                "median_recs_to_first_hit": float(np.median([x[3] for x in v]))}
            for m, v in out.items()}, len(users)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--min-count", type=int, default=5)
    ap.add_argument("--dim", type=int, default=64)
    ap.add_argument("--out-dir", default="data")
    args = ap.parse_args()

    pos, meta = load(args.data_dir, args.min_count)
    n_items = len(meta)
    print(f"{pos['userId'].nunique():,} users · {n_items:,} movies · {len(pos):,} positives")

    train, test = time_split(pos)
    emb = fit_embeddings(train, n_items, args.dim)
    full, n_users = evaluate(train, test, emb, n_items)
    cold, _ = evaluate(train, test, emb, n_items, seed_size=3)

    rows = [
        ("Popularity baseline", full["popularity"]),
        ("Collaborative filtering (full history)", full["cf"]),
        ("Collaborative filtering (only 3 likes, like onboarding)", cold["cf"]),
    ]
    def first_hit(m):
        v = m["median_recs_to_first_hit"]
        return f">{FIRST_HIT_DEPTH}" if v > FIRST_HIT_DEPTH else f"{v:.0f}"
    table = ("| Model | Recall@10 | NDCG@10 | Hit@1 (Tonight's Pick) | Median recs to first loved movie |\n"
             "|---|---|---|---|---|\n" + "\n".join(
        f"| {name} | {m['recall@10']:.3f} | {m['ndcg@10']:.3f} | {m['hit@1']:.1%} | {first_hit(m)} |"
        for name, m in rows))
    report = (f"**Offline evaluation** — MovieLens ({Path(args.data_dir).name}), "
              f"time-based split, {n_users:,} held-out users, ratings ≥ 4 as positives.\n\n{table}\n")
    print("\n" + report)

    # Retrain on all data for the shipped model.
    emb_all = fit_embeddings(pos, n_items, args.dim)
    norm = [normalize_title(t) for t in meta["title"]]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out / "cf_model.npz",
        emb=emb_all.astype(np.float16),
        tmdb_id=meta["tmdbId"].fillna(-1).astype(np.int64).to_numpy(),
        norm_title=np.array([t for t, _ in norm]),
        year=np.array([y or 0 for _, y in norm], dtype=np.int32),
        popularity=np.bincount(pos["item"], minlength=n_items).astype(np.int32),
    )
    (out / "cf_results.md").write_text(report)
    (out / "cf_results.json").write_text(json.dumps({"full": full, "three_likes": cold}, indent=2))
    print(f"Saved {out / 'cf_model.npz'}")


if __name__ == "__main__":
    main()
