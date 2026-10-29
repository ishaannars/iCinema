"""Mood search: can a few words like "slow-burn, twist ending" find the movies people mean?

    python training/confirm_mood.py --data-dir ml-32m

The index is built from the tags MovieLens fans wrote on movies (no TMDB content, no LLM):
each movie's tag words, weighted by TF-IDF.

Test, written before running. Taggers are split at random: 80% build the index, 20% are held out.
For 2,000 random movies with tags from held-out taggers, the query is three of those held-out
tag words, so the words come from people the index never saw. A search succeeds if the movie
lands in the top 50 of all 14,407 movies (recall@50).
- Baseline: the 50 most popular movies (what you'd get with no search).
- Ships if recall@50 beats the baseline (paired-bootstrap 95% interval above zero).
If it ships, the index is rebuilt from every tagger: data/mood_index.npz. In the app, a mood
re-orders Top Matches by a 50/50 mix of how well each movie fits you and how well it matches
the words. Writes data/mood_confirm.json.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from train_cf import normalize_title, paired_bootstrap  # noqa: E402

TOP_TERMS = 60
MIN_DF = 3
N_QUERIES = 2000
TOPN = 50
_STOP = {"the", "a", "an", "of", "and", "in", "on", "to", "for", "by", "with", "movie", "film", "s"}


def words(text):
    return [w for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", str(text).lower()) if w not in _STOP and len(w) > 1]


def build(tag_rows, n):
    """tag_rows: (row index, tag text) -> CSR (n x vocab) of TF-IDF weights, vocab, idf."""
    df, tf = {}, [dict() for _ in range(n)]
    for i, text in tag_rows:
        for w in words(text):
            tf[i][w] = tf[i].get(w, 0) + 1
    for d in tf:
        for w in d:
            df[w] = df.get(w, 0) + 1
    vocab = {w: k for k, w in enumerate(sorted(w for w, c in df.items() if c >= MIN_DF))}
    idf = np.zeros(len(vocab), np.float32)
    for w, k in vocab.items():
        idf[k] = np.log(n / df[w])
    ri, ci, vals = [], [], []
    for i, d in enumerate(tf):
        items = [(vocab[w], (1 + np.log(c)) * idf[vocab[w]]) for w, c in d.items() if w in vocab]
        items.sort(key=lambda x: -x[1])
        items = items[:TOP_TERMS]
        norm = np.sqrt(sum(v * v for _, v in items)) or 1.0
        for k, v in items:
            ri.append(i)
            ci.append(k)
            vals.append(v / norm)
    M = csr_matrix((np.array(vals, np.float32), (ri, ci)), shape=(n, max(len(vocab), 1)))
    return M, vocab, idf


def search(M, vocab, idf, query):
    q = np.zeros(M.shape[1], np.float32)
    for w in words(query):
        if w in vocab:
            q[vocab[w]] += idf[vocab[w]]
    if not q.any():
        return None
    return M @ (q / np.linalg.norm(q))


def rows_for(data_dir):
    knn = np.load(ROOT / "data" / "cf_knn.npz")
    links = pd.read_csv(Path(data_dir) / "links.csv")
    movies = pd.read_csv(Path(data_dir) / "movies.csv")
    by_tmdb = {int(t): i for i, t in enumerate(knn["tmdb_id"]) if t > 0}
    by_title = {}
    for i, (t, y) in enumerate(zip(knn["norm_title"], knn["year"])):
        by_title.setdefault((str(t), int(y)), i)
    tmdb_of = {int(m): int(t) for m, t in zip(links["movieId"], links["tmdbId"].fillna(-1)) if t > 0}
    row_of = {}
    for mid, title in zip(movies["movieId"], movies["title"]):
        i = by_tmdb.get(tmdb_of.get(int(mid), -2))
        if i is None:
            t, y = normalize_title(title)
            i = by_title.get((t, y or 0))
        if i is not None:
            row_of[int(mid)] = i
    return row_of, len(knn["norm_title"]), knn["popularity"].astype(float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    row_of, n, fans = rows_for(args.data_dir)
    tags = pd.read_csv(Path(args.data_dir) / "tags.csv", usecols=["userId", "movieId", "tag"]).dropna()
    tags = tags[tags["movieId"].isin(row_of)]
    tags["row"] = tags["movieId"].map(row_of)
    taggers = tags["userId"].unique()
    held = set(np.random.default_rng(41).choice(taggers, len(taggers) // 5, replace=False).tolist())
    is_held = tags["userId"].isin(held)
    M, vocab, idf = build(zip(tags.loc[~is_held, "row"], tags.loc[~is_held, "tag"]), n)
    held_words = {}
    for r, t in zip(tags.loc[is_held, "row"], tags.loc[is_held, "tag"]):
        held_words.setdefault(int(r), set()).update(w for w in words(t) if w in vocab)
    cands = [r for r, w in held_words.items() if len(w) >= 3]
    rng = np.random.default_rng(43)
    pick = rng.choice(cands, min(N_QUERIES, len(cands)), replace=False)
    popular = set(np.argsort(-fans)[:TOPN].tolist())
    hit, base = [], []
    for r in pick:
        q = " ".join(rng.choice(sorted(held_words[int(r)]), 3, replace=False))
        s = search(M, vocab, idf, q)
        hit.append(float(s is not None and int(r) in set(np.argpartition(-s, TOPN)[:TOPN].tolist())))
        base.append(float(int(r) in popular))
    hit, base = np.asarray(hit), np.asarray(base)
    d, lo, hi, _ = paired_bootstrap(hit, base, np.mean)
    out = {"method": " ".join(__doc__.split("\n\n")[1:4]).replace("\n", " "), "queries": int(len(pick)),
           "recall_at_50": {"mood search": round(float(hit.mean()), 4), "most popular": round(float(base.mean()), 4)},
           "diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "ship": bool(lo > 0)}
    path = ROOT / "data" / "mood_index.npz"
    if out["ship"]:
        M, vocab, idf = build(zip(tags["row"], tags["tag"]), n)
        words_sorted = sorted(vocab, key=vocab.get)
        np.savez_compressed(path, data=M.data.astype(np.float16), indices=M.indices.astype(np.int32),
                            indptr=M.indptr.astype(np.int64), shape=np.array(M.shape), vocab=np.array(words_sorted),
                            idf=idf.astype(np.float32))
    else:
        path.unlink(missing_ok=True)
    (ROOT / "data" / "mood_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
