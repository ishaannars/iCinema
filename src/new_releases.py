"""Scores for recent movies that MovieLens fans haven't rated yet.

data/new_releases.npz (built by training/confirm_new_releases.py, only if its test passed) holds,
for each recent movie, a predicted position in the viewers-like-you space of data/cf_model.npz,
learned from public Wikidata facts. A viewer's position is the weighted mix of the movies they
liked, saved, or turned down; a new movie scores by how close it is to that.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"
WEIGHTS = {"favorite": 2.0, "like": 1.0, "save": 1.0, "seen": 0.5, "skip": -0.2, "dislike": -0.8}


@lru_cache(maxsize=1)
def _load():
    path = DATA / "new_releases.npz"
    if not path.exists():
        return None
    d = np.load(path)
    emb = d["emb"].astype(np.float32)
    space = np.load(DATA / "cf_model.npz")["emb"].astype(np.float32)
    space /= np.maximum(np.linalg.norm(space, axis=1, keepdims=True), 1e-9)
    return {int(t): i for i, t in enumerate(d["tmdb_id"])}, emb, space


def available():
    return _load() is not None


def viewer(signals, index_of):
    """signals: (movie, action) pairs; index_of(movie) -> row in cf_model.npz or None.
    Returns (viewer vector, cosine of every placed recent movie to it), or None."""
    d = _load()
    if d is None:
        return None
    by_tmdb, emb, space = d
    v, used = np.zeros(space.shape[1], np.float32), False
    for movie, action in signals or []:
        i, w = index_of(movie), WEIGHTS.get(action, 0.0)
        if i is None or w == 0:
            continue
        v += w * space[i]
        used = used or w > 0
    n = float(np.linalg.norm(v))
    if not used or n == 0:
        return None
    v /= n
    return v, np.sort(emb @ v)


def affinity(movie, view):
    """0-1 like cf_affinity: 0.5 = no evidence, higher = closer to what the viewer liked than most
    recent movies. None if the movie wasn't placed or there's no viewer yet."""
    d = _load()
    if d is None or view is None:
        return None
    by_tmdb, emb, _ = d
    i = by_tmdb.get(int((movie or {}).get("tmdb_id") or 0))
    if i is None:
        return None
    v, sorted_cos = view
    c = float(emb[i] @ v)
    pct = float(np.searchsorted(sorted_cos, c, side="right")) / max(len(sorted_cos), 1)
    return round(0.5 + 0.5 * (2 * pct - 1), 4)       # middle of the recent pack = 0.5
