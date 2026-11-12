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


class _Trees:
    """The shipped gradient-boosting ranker, read from plain arrays (data/ltr_trees.npz).

    The same 107 trees as data/ltr_model.joblib, exported once and checked to give identical
    probabilities. Reading arrays instead of a pickle means any scikit-learn version (or none) can
    run it, so a library update can never switch the ranker off silently.
    """

    def __init__(self, d):
        self.feature, self.threshold = d["feature"], d["threshold"]
        self.missing_left, self.left, self.right = d["missing_left"].astype(bool), d["left"], d["right"]
        self.is_leaf, self.value, self.offsets = d["is_leaf"].astype(bool), d["value"], d["offsets"]
        self.baseline = float(d["baseline"])

    def predict_proba(self, X):
        X = np.asarray(X, dtype=np.float64)
        rows, raw = np.arange(len(X)), np.full(len(X), self.baseline)
        for t in range(len(self.offsets) - 1):
            o, node = self.offsets[t], np.zeros(len(X), dtype=np.int64)
            while True:
                g = o + node
                leaf = self.is_leaf[g]
                if leaf.all():
                    break
                x = X[rows, self.feature[g]]
                go_left = np.where(np.isnan(x), self.missing_left[g], x <= self.threshold[g])
                node = np.where(leaf, node, np.where(go_left, self.left[g], self.right[g]))
            raw += self.value[o + node]
        p = 1.0 / (1.0 + np.exp(-raw))
        return np.stack([1 - p, p], axis=1)


LOAD_ERROR = None


@lru_cache(maxsize=1)
def _load():
    trees = DATA / "ltr_trees.npz"
    if trees.exists():
        try:
            d = np.load(trees)
            return _Trees(d), [str(x) for x in d["features"]]
        except Exception as exc:
            global LOAD_ERROR
            LOAD_ERROR = f"{type(exc).__name__}: {exc}"
    path = DATA / "ltr_model.joblib"
    if not path.exists():
        return None
    try:
        import joblib
        bundle = joblib.load(path)
        return bundle["model"], list(bundle["features"])
    except Exception as exc:          # e.g. a scikit-learn version that can't read the saved model
        LOAD_ERROR = f"{type(exc).__name__}: {exc}"
        import sys
        print("iCinema: learned ranker not loaded:", LOAD_ERROR, file=sys.stderr, flush=True)
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
