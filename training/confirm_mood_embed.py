"""Mood search with meaning: do word embeddings help fans' words find the right movies?

    pip install model2vec
    python training/confirm_mood_embed.py --data-dir ml-32m

Same split and queries as training/confirm_mood.py: taggers split 80/20 at random, 2,000 movies, each
queried with three words from held-out taggers, success = the movie lands in the top 50 (recall@50).
A (shipped): TF-IDF over fan tags. B: half TF-IDF, half meaning: each movie's tag words and the query are
turned into vectors by a small static embedding model (model2vec potion-base-8M), compared by cosine.
Rules written before running, both must pass (each at 97.5% intervals, so the two together stay at 95%):
1. No worse overall: lower end of the interval of recall@50(B) - recall@50(A) above -0.02 (2 points).
2. Better on rare words: on queries where at least two of the three words are rare (used by fewer than
   20 movies' taggers), the interval of the difference is above zero.
If both pass, writes data/mood_embed.npz (movie vectors plus the model's word vectors, so the app needs
no model at runtime). Writes data/mood_embed_confirm.json; the app reads its "ship" field.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from confirm_mood import N_QUERIES, TOPN, build, rows_for, search, words  # noqa: E402
from train_cf import paired_bootstrap  # noqa: E402

MODEL, RARE_DF, MARGIN = "minishlab/potion-base-8M", 20, -0.02


def load_encoder():
    if os.environ.get("ICINEMA_FAKE_ENCODER"):            # dry runs only: random but consistent vectors
        class Fake:
            def encode(self, texts):
                out = []
                for t in texts:
                    v = np.zeros(32, np.float32)
                    for w in words(t):
                        v += np.random.default_rng(abs(hash(w)) % (2 ** 32)).standard_normal(32)
                    out.append(v)
                return np.asarray(out)
        return Fake()
    from model2vec import StaticModel
    return StaticModel.from_pretrained(MODEL)


def unit(M):
    n = np.linalg.norm(M, axis=1, keepdims=True)
    return M / np.where(n == 0, 1, n)


def movie_texts(M, vocab, n):
    inv = {k: w for w, k in vocab.items()}
    return [" ".join(inv[k] for k in M.indices[M.indptr[i]:M.indptr[i + 1]]) for i in range(n)]


def interval(a, b, level):
    d, _lo, _hi, _ = paired_bootstrap(a, b, np.mean)
    rng = np.random.default_rng(11)
    idx = rng.integers(0, len(a), size=(2000, len(a)))
    diffs = a[idx].mean(axis=1) - b[idx].mean(axis=1)
    lo, hi = np.percentile(diffs, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(d), float(lo), float(hi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    row_of, n, _fans = rows_for(args.data_dir)
    tags = pd.read_csv(Path(args.data_dir) / "tags.csv", usecols=["userId", "movieId", "tag"]).dropna()
    tags = tags[tags["movieId"].isin(row_of)]
    tags["row"] = tags["movieId"].map(row_of)
    taggers = tags["userId"].unique()
    held = set(np.random.default_rng(41).choice(taggers, len(taggers) // 5, replace=False).tolist())
    is_held = tags["userId"].isin(held)
    M, vocab, idf = build(zip(tags.loc[~is_held, "row"], tags.loc[~is_held, "tag"]), n)
    df = np.asarray((M > 0).sum(axis=0)).ravel()
    enc = load_encoder()
    E = unit(np.asarray(enc.encode(movie_texts(M, vocab, n)), dtype=np.float32))
    held_words = {}
    for r, t in zip(tags.loc[is_held, "row"], tags.loc[is_held, "tag"]):
        held_words.setdefault(int(r), set()).update(w for w in words(t) if w in vocab)
    cands = [r for r, w in held_words.items() if len(w) >= 3]
    rng = np.random.default_rng(43)
    pick = rng.choice(cands, min(N_QUERIES, len(cands)), replace=False)
    a_hit, b_hit, rare = [], [], []
    for r in pick:
        qw = list(rng.choice(sorted(held_words[int(r)]), 3, replace=False))
        q = " ".join(qw)
        s = search(M, vocab, idf, q)
        qv = unit(np.asarray(enc.encode([q]), dtype=np.float32))[0]
        e = E @ qv
        b = e if s is None else 0.5 * s + 0.5 * e
        top = lambda v: set(np.argpartition(-v, TOPN)[:TOPN].tolist())
        a_hit.append(float(s is not None and int(r) in top(s)))
        b_hit.append(float(int(r) in top(b)))
        rare.append(sum(df[vocab[w]] < RARE_DF for w in qw) >= 2)
    A, B, rare = np.asarray(a_hit), np.asarray(b_hit), np.asarray(rare)
    d_all, lo_all, hi_all = interval(B, A, 0.975)
    if rare.sum() >= 30:
        d_rare, lo_rare, hi_rare = interval(B[rare], A[rare], 0.975)
    else:
        d_rare = lo_rare = hi_rare = float("nan")
    ship = bool(lo_all > MARGIN and lo_rare > 0)
    out = {"method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "), "queries": int(len(pick)),
           "recall_at_50": {"tfidf": round(float(A.mean()), 4), "tfidf_plus_meaning": round(float(B.mean()), 4)},
           "overall": {"diff": round(d_all, 4), "ci97_5": [round(lo_all, 4), round(hi_all, 4)], "margin": MARGIN},
           "rare_word_queries": int(rare.sum()),
           "rare": {"tfidf": round(float(A[rare].mean()), 4) if rare.any() else None,
                    "tfidf_plus_meaning": round(float(B[rare].mean()), 4) if rare.any() else None,
                    "diff": round(d_rare, 4), "ci97_5": [round(lo_rare, 4), round(hi_rare, 4)]},
           "ship": ship}
    path = ROOT / "data" / "mood_embed.npz"
    if ship:
        M_all, vocab_all, _ = build(zip(tags["row"], tags["tag"]), n)
        E_all = unit(np.asarray(enc.encode(movie_texts(M_all, vocab_all, n)), dtype=np.float32))
        tok = enc.tokenizer.get_vocab() if hasattr(enc, "tokenizer") else {}
        words_ok = sorted(w for w in tok if w.isalpha() and len(w) > 1)
        W = unit(np.asarray(enc.encode(words_ok), dtype=np.float32)) if words_ok else np.zeros((0, E_all.shape[1]), np.float32)
        np.savez_compressed(path, movies=E_all.astype(np.float16), words=np.array(words_ok), word_vecs=W.astype(np.float16))
    else:
        path.unlink(missing_ok=True)
    (ROOT / "data" / "mood_embed_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
