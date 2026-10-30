"""Mood search over MovieLens fan tags (data/mood_index.npz, built by training/confirm_mood.py
only if its test passed). A few words in, a 0-1 match for every movie out."""
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

PATH = Path(__file__).resolve().parent.parent / "data" / "mood_index.npz"
_STOP = {"the", "a", "an", "of", "and", "in", "on", "to", "for", "by", "with", "movie", "film", "s"}


def words(text):
    return [w for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", str(text).lower()) if w not in _STOP and len(w) > 1]


@lru_cache(maxsize=1)
def _load():
    if not PATH.exists():
        return None
    from scipy.sparse import csr_matrix
    d = np.load(PATH)
    M = csr_matrix((d["data"].astype(np.float32), d["indices"], d["indptr"]), shape=tuple(d["shape"]))
    return M, {str(w): i for i, w in enumerate(d["vocab"])}, d["idf"].astype(np.float32)


def available():
    return _load() is not None


@lru_cache(maxsize=64)
def _scores(query):
    d = _load()
    if d is None:
        return None
    M, vocab, idf = d
    q = np.zeros(M.shape[1], np.float32)
    for w in words(query):
        if w in vocab:
            q[vocab[w]] += idf[vocab[w]]
    if not q.any():
        return None
    return np.asarray(M @ (q / np.linalg.norm(q))).ravel()


def scores(query):
    """Match of every movie (rows of data/cf_knn.npz) to the words, or None if no word is known."""
    return _scores(" ".join(words(query)))


def top_rows(query, k=150):
    """Rows of the movies that best match the words (strongest first), for adding to the pool."""
    s = scores(query)
    if s is None:
        return []
    idx = np.argpartition(-s, min(k, len(s) - 1))[:k]
    return [int(i) for i in idx[np.argsort(-s[idx])] if s[i] > 0]
