"""Learned ranker: one gradient-boosted model that combines every recommender iCinema has.

data/ltr_model.joblib is saved by training/confirm_ltr.py only if it beat the fixed 80/20 mix on
3,000 held-out MovieLens viewers. The app builds the same six inputs the test used, each a
percentile over every movie for this viewer: the routed ranking, item-kNN, RP3beta, EASE, the
content model, and popularity. The ranker turns them into one score, which takes the place of the
"viewers like you" score; the content score that carries your Step 2 and 3 answers still counts.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from src import cf_model, content_model

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def _load():
    path = DATA / "ltr_model.joblib"
    if not path.exists():
        return None
    try:
        import joblib
        bundle = joblib.load(path)
        return bundle["model"], list(bundle["features"])
    except Exception:
        return None


def available():
    return _load() is not None and cf_model._load() is not None


@lru_cache(maxsize=1)
def result():
    try:
        return json.loads((DATA / "ltr_confirm.json").read_text())
    except Exception:
        return {}


def _pct(s):
    order = np.argsort(s, kind="stable")
    r = np.empty(len(s), dtype=np.float64)
    r[order] = np.arange(len(s))
    return r / max(len(s) - 1, 1)


def viewer_scores(signals):
    """0-1 score for every movie in data/cf_knn.npz (percentile of the ranker's output), or None."""
    loaded = _load()
    sim = cf_model._load()
    if loaded is None or sim is None or not signals:
        return None
    model, names = loaded
    routed_taste = cf_model.user_vector(signals)
    if routed_taste is None:
        return None
    knn = cf_model.scores_with(sim, signals)
    rank = cf_model._load_rank()
    rp3 = cf_model.scores_with(rank, signals) if rank is not sim else knn
    full, _ = cf_model._history_cut()
    ease = cf_model.scores_with(full, signals) if full is not None else knn
    feats = {"routed": _pct(routed_taste.scores), "item_knn": _pct(knn), "rp3beta": _pct(rp3), "ease": _pct(ease),
             "popularity": sim.fan_pct.astype(np.float64)}
    vecs = content_model._load()
    if vecs is not None:
        E, has = vecs
        rows = [cf_model._index(m) for m, a in signals if a in ("favorite", "like", "save")]
        rows = [i for i in rows if i is not None and has[i]]
        user = E[rows].mean(axis=0) if rows else np.zeros(E.shape[1], np.float32)
        feats["content"] = _pct(E @ user)
    else:
        feats["content"] = np.full(sim.n, 0.5)
    X = np.stack([feats[k] for k in names], axis=1)
    prob = model.predict_proba(X)[:, 1]
    return _pct(prob)
