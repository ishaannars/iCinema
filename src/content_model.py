"""Content model: how alike two movies are, from MovieLens genres and fan tags.

Built by training/build_content.py and row-aligned with data/cf_knn.npz, so a movie is found the
same way the "viewers like you" model finds it. No TMDB content goes into this model; TMDB is used
only for display. Movies it doesn't know get a neutral score, and the other models rank them.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np

from src import cf_model

PATH = Path(__file__).resolve().parents[1] / "data" / "content_ml.npz"


@lru_cache(maxsize=1)
def _load():
    if not PATH.exists() or cf_model._load() is None or cf_model._load().kind != "knn":
        return None
    d = np.load(PATH)
    return d["vec"].astype(np.float32), d["has"].astype(bool)


def available():
    return _load() is not None


def vector(movie):
    """The movie's 64-number description, or None if the content model doesn't know it."""
    data = _load()
    if data is None:
        return None
    idx = cf_model._index(movie)
    if idx is None or idx >= len(data[1]) or not data[1][idx]:
        return None
    return data[0][idx]


def similarity_scores(movies, signals):
    """signals: list of (movie, weight). Returns {id(movie): score in [0, 1]}; 0.5 means no evidence."""
    vecs = [(vector(m), w) for m, w in signals]
    vecs = [(v, w) for v, w in vecs if v is not None and w]
    if not vecs:
        return {id(m): 0.5 for m in movies}
    user = sum(w * v for v, w in vecs)
    norm = float(np.linalg.norm(user))
    if norm <= 1e-12:
        return {id(m): 0.5 for m in movies}
    user = user / norm
    out = {}
    for m in movies:
        v = vector(m)
        out[id(m)] = 0.5 if v is None else max(0.0, min(1.0, (float(v @ user) + 1.0) / 2.0))
    return out
