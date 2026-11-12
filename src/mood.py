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


def correct(text):
    """Fix one-letter typos against the words fans actually use ("dakr" -> "dark", "fuuny" -> "funny").

    Candidates are every word one edit away (a swap, a missing, extra, or wrong letter); the most
    commonly used one wins. Words already known, short words, and anything with no close match pass through.
    """
    d = _load()
    if d is None:
        return text
    vocab, idf = d[1], d[2]
    letters = "abcdefghijklmnopqrstuvwxyz-"
    out = []
    for w in str(text).split():
        lw = w.lower()
        if lw in vocab or len(lw) < 4 or not lw.replace("-", "").isalpha():
            out.append(w)
            continue
        splits = [(lw[:i], lw[i:]) for i in range(len(lw) + 1)]
        edits = {a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1}          # swapped letters
        edits |= {a + b[1:] for a, b in splits if b}                                 # a letter too many
        edits |= {a + c + b[1:] for a, b in splits if b for c in letters}            # a wrong letter
        edits |= {a + c + b for a, b in splits for c in letters}                     # a missing letter
        known = [e for e in edits if e in vocab]
        out.append(min(known, key=lambda e: idf[vocab[e]]) if known else w)
    return " ".join(out)


def is_mood_word(word, common=0.35):
    """True if fans use this word often enough to be a mood or genre ("dark", "funny", "mystery"),
    not a rare tag that is really a title or a name ("hokum"). Common = the most-used 35% of tag words."""
    d = _load()
    if d is None:
        return False
    vocab, idf = d[1], d[2]
    w = str(word).lower()
    if w not in vocab:
        return False
    if not hasattr(is_mood_word, "_cut"):
        import numpy as _np
        is_mood_word._cut = float(_np.quantile(idf, common))
    return float(idf[vocab[w]]) <= is_mood_word._cut
