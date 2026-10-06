"""
Collaborative-filtering layer for iCinema, pretrained offline on MovieLens.

The model file contains only movie embeddings. Each user's taste vector is
computed on the fly from their browser-local Likes/Favorites/Saves/Skips, so
no user data ever leaves the browser.
"""
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "cf_model.npz"

# How strongly each action moves the user's taste vector.
WEIGHTS = {"favorite": 2.0, "like": 1.0, "save": 1.0, "seen": 0.5, "skip": -0.2, "dislike": -0.8}


def _norm_title(title):
    title = re.sub(r"[^\w\s]", "", str(title).casefold())
    return " ".join(title.split())


@lru_cache(maxsize=1)
def _load():
    if not MODEL_PATH.exists():
        return None
    d = np.load(MODEL_PATH)
    emb = d["emb"].astype(np.float32)
    by_tmdb = {int(t): i for i, t in enumerate(d["tmdb_id"]) if t > 0}
    by_title = {}
    for i, (t, y) in enumerate(zip(d["norm_title"], d["year"])):
        by_title.setdefault((str(t), int(y)), i)
        by_title.setdefault((str(t), 0), i)  # year-less fallback
    return emb, by_tmdb, by_title


def cf_available():
    return _load() is not None


def _index(movie):
    model = _load()
    if model is None or not movie:
        return None
    _, by_tmdb, by_title = model
    tmdb_id = int(movie.get("tmdb_id") or 0)
    if tmdb_id and tmdb_id in by_tmdb:
        return by_tmdb[tmdb_id]
    key = _norm_title(movie.get("title", ""))
    year = int(movie.get("year") or 0)
    for y in (year, year - 1, year + 1, 0):  # tolerate off-by-one release years
        if (key, y) in by_title:
            return by_title[(key, y)]
    return None


def user_vector(signals):
    """signals: list of (movie_dict, action) pairs, action in WEIGHTS."""
    model = _load()
    if model is None:
        return None
    emb = model[0]
    total, weight_sum = np.zeros(emb.shape[1], dtype=np.float32), 0.0
    for movie, action in signals:
        idx = _index(movie)
        w = WEIGHTS.get(action, 0.0)
        if idx is None or w == 0:
            continue
        total += w * emb[idx]
        weight_sum += max(w, 0)
    if weight_sum == 0:
        return None
    norm = np.linalg.norm(total)
    return total / norm if norm > 0 else None


def cf_affinity(movie, uvec):
    """0–1 score for how well a movie fits the user's taste, or None if unknown."""
    if uvec is None:
        return None
    idx = _index(movie)
    if idx is None:
        return None  # movie not in MovieLens: fall back to content signals
    cos = float(_load()[0][idx] @ uvec)
    return (cos + 1.0) / 2.0


# Only explicit approval can be quoted as "you're a fan": Seen means watched, not loved.
FAN_ACTIONS = ("favorite", "like", "save")


def closest_liked(movie, signals, allowed=FAN_ACTIONS):
    """Title of the viewer's liked/saved movie most similar to this one, or None.

    Makes the collaborative-filtering reason concrete ("Loved by fans of Parasite")
    instead of an abstract "viewers like you".
    """
    model = _load()
    idx = _index(movie)
    if model is None or idx is None:
        return None
    emb = model[0]
    best, best_score = None, -2.0
    for liked, action in signals or []:
        if action not in allowed:
            continue
        j = _index(liked)
        if j is None or j == idx:
            continue
        denom = float(np.linalg.norm(emb[idx]) * np.linalg.norm(emb[j]))
        score = float(emb[idx] @ emb[j]) / denom if denom > 0 else -2.0   # cosine, not raw dot product
        if score > best_score:
            best, best_score = liked.get("title"), score
    return best


def item_similarity(a, b):
    """0–1 cosine similarity between two movies' embeddings, or None if either is unknown.

    Used by Watch next: a high score means the same viewers tend to love both movies.
    """
    model = _load()
    i, j = _index(a), _index(b)
    if model is None or i is None or j is None or i == j:
        return None
    emb = model[0]
    denom = float(np.linalg.norm(emb[i]) * np.linalg.norm(emb[j]))
    if denom <= 0:
        return None
    return (float(emb[i] @ emb[j]) / denom + 1.0) / 2.0
