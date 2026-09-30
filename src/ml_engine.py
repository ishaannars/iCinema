"""Browser-local supervised learning and evaluation for iCinema.

The analytical hybrid recommender remains the cold-start model. Supervised
learning activates only after enough explicit preference evidence exists.

Design goals:
- Save is positive preference/intent.
- Skip is negative preference feedback.
- Seen is exposure/history, not automatically a positive label.
- Position is logged for bias analysis but is not used as a preference feature.
- Recent outcomes receive more training weight than stale outcomes.
- Validation prefers a temporal holdout so evaluation better resembles future use.
- Gradient Boosting is only considered once the browser has enough labels.
"""
from dataclasses import dataclass
import math
import time
from typing import Optional

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split


FEATURE_NAMES = [
    "genre_affinity",
    "trait_affinity",
    "semantic_similarity",
    "quality_alignment",
    "discovery_alignment",
    "priority_alignment",
    "availability_alignment",
    "vote_confidence",
    "profile_confidence",
    "model_score",
    "decision_utility",
    "match_scaled",
    "cf_affinity",
]

DEFAULT_MIN_SAMPLES = 50
DEFAULT_MIN_CLASS = 12
GB_MIN_SAMPLES = 100
GB_MIN_CLASS = 24
RECENCY_HALF_LIFE_DAYS = 120.0


@dataclass
class LearningResult:
    ready: bool
    model_name: str = "Hybrid analytical model"
    model: object = None
    metrics: dict = None
    samples: int = 0
    positives: int = 0
    negatives: int = 0


def _safe_float(value, default=0.5):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _features_from_context(ctx):
    """Preference features only.

    Rank position is intentionally excluded. Position can influence user actions,
    so feeding it into the preference model would let exposure bias masquerade as
    taste.
    """
    ctx = ctx or {}

    def f(name, default=0.5):
        return _safe_float(ctx.get(name, default), default)

    return [
        f("genre_affinity"),
        f("trait_affinity"),
        f("semantic_similarity"),
        f("quality_alignment"),
        f("discovery_alignment"),
        f("priority_alignment"),
        f("availability_alignment"),
        f("vote_confidence"),
        f("profile_confidence"),
        f("model_score"),
        f("decision_utility"),
        f("match", 50.0) / 100.0,
        f("cf_affinity"),  # MovieLens collaborative-filtering fit; 0.5 when unknown
    ]


def _joined_examples(events):
    """Return explicit preference labels joined to their first session impression.

    Save -> positive
    Skip -> negative
    Seen -> exposure only (not a supervised target)

    If a title is both skipped and later saved in the same session, the most recent
    explicit preference action wins.
    """
    events = list(events or [])
    impressions = {}
    labels = {}

    for e in events:
        if e.get("event") != "impression":
            continue
        key = (e.get("session_id"), e.get("title"))
        if not all(key):
            continue
        impressions.setdefault(key, e)

    for e in events:
        typ = str(e.get("event") or "").lower()
        if typ not in {"save", "skip"}:
            continue
        key = (e.get("session_id"), e.get("title"))
        if not all(key):
            continue
        labels[key] = {
            "label": 1 if typ == "save" else 0,
            "timestamp": _safe_float(e.get("timestamp"), 0.0),
        }

    rows = []
    for key, info in labels.items():
        imp = impressions.get(key)
        if not imp:
            continue
        rows.append(
            {
                "x": _features_from_context(imp),
                "y": int(info["label"]),
                "timestamp": float(info["timestamp"] or imp.get("timestamp") or 0.0),
                "session_id": key[0],
                "title": key[1],
            }
        )
    rows.sort(key=lambda r: r["timestamp"])
    return rows


def labeled_examples(events):
    """Backward-compatible public helper returning X, y."""
    rows = _joined_examples(events)
    if not rows:
        return (
            np.empty((0, len(FEATURE_NAMES)), dtype=float),
            np.asarray([], dtype=int),
        )
    return (
        np.asarray([r["x"] for r in rows], dtype=float),
        np.asarray([r["y"] for r in rows], dtype=int),
    )


def _recency_weights(timestamps, half_life_days=RECENCY_HALF_LIFE_DAYS):
    """Exponential time decay with a floor so older evidence still matters."""
    if len(timestamps) == 0:
        return np.asarray([], dtype=float)
    latest = max(float(t) for t in timestamps if t) if any(timestamps) else time.time()
    half_life_seconds = max(1.0, float(half_life_days) * 86400.0)
    decay = math.log(2.0) / half_life_seconds
    weights = []
    for ts in timestamps:
        age = max(0.0, latest - float(ts or latest))
        weights.append(max(0.35, math.exp(-decay * age)))
    return np.asarray(weights, dtype=float)


def _split_indices(y, timestamps):
    """Prefer a chronological holdout; fall back to stratification if necessary."""
    n = len(y)
    if n < 2:
        return None

    order = np.argsort(np.asarray(timestamps, dtype=float))
    test_n = max(12, int(math.ceil(n * 0.25)))
    test_n = min(test_n, max(1, n // 3))

    train_idx = order[:-test_n]
    test_idx = order[-test_n:]

    if (
        len(train_idx) >= 2
        and len(test_idx) >= 2
        and len(set(y[train_idx])) > 1
        and len(set(y[test_idx])) > 1
    ):
        return train_idx, test_idx, "temporal_holdout"

    indices = np.arange(n)
    try:
        train_idx, test_idx = train_test_split(
            indices,
            test_size=0.25,
            random_state=42,
            stratify=y,
        )
        return np.asarray(train_idx), np.asarray(test_idx), "stratified_holdout"
    except Exception:
        return None


def _evaluate_model(model, Xtr, ytr, Xte, yte, wtr=None):
    model.fit(Xtr, ytr, sample_weight=wtr)
    prob = np.clip(model.predict_proba(Xte)[:, 1], 1e-5, 1 - 1e-5)
    pred = (prob >= 0.5).astype(int)
    auc = float(roc_auc_score(yte, prob)) if len(set(yte)) > 1 else 0.5
    acc = float(accuracy_score(yte, pred))
    loss = float(log_loss(yte, prob, labels=[0, 1]))
    brier = float(brier_score_loss(yte, prob))
    selection = auc - 0.08 * loss - 0.10 * brier
    return selection, {
        "auc": auc,
        "accuracy": acc,
        "log_loss": loss,
        "brier_score": brier,
    }


def train_learning_model(events, min_samples=DEFAULT_MIN_SAMPLES):
    rows = _joined_examples(events)
    if not rows:
        return LearningResult(False, metrics={})

    X = np.asarray([r["x"] for r in rows], dtype=float)
    y = np.asarray([r["y"] for r in rows], dtype=int)
    timestamps = np.asarray([r["timestamp"] for r in rows], dtype=float)

    positives = int(y.sum())
    negatives = int(len(y) - positives)
    effective_min = max(int(min_samples or DEFAULT_MIN_SAMPLES), DEFAULT_MIN_SAMPLES)

    base_metrics = {
        "activation_threshold": effective_min,
        "min_class_threshold": DEFAULT_MIN_CLASS,
        "position_feature_excluded": True,
        "seen_used_as_label": False,
        "recency_half_life_days": RECENCY_HALF_LIFE_DAYS,
    }
    base = LearningResult(
        False,
        samples=len(y),
        positives=positives,
        negatives=negatives,
        metrics=base_metrics,
    )

    if (
        len(y) < effective_min
        or positives < DEFAULT_MIN_CLASS
        or negatives < DEFAULT_MIN_CLASS
    ):
        return base

    split = _split_indices(y, timestamps)
    if split is None:
        return base

    train_idx, test_idx, validation_method = split
    Xtr, Xte = X[train_idx], X[test_idx]
    ytr, yte = y[train_idx], y[test_idx]
    weights = _recency_weights(timestamps)
    wtr = weights[train_idx]

    candidates = [
        (
            "Logistic Regression",
            LogisticRegression(
                max_iter=1500,
                class_weight="balanced",
                C=0.75,
                random_state=42,
            ),
        )
    ]

    # Nonlinear modeling is deliberately delayed until there is enough evidence.
    if (
        len(y) >= GB_MIN_SAMPLES
        and positives >= GB_MIN_CLASS
        and negatives >= GB_MIN_CLASS
    ):
        candidates.append(
            (
                "Gradient Boosting",
                GradientBoostingClassifier(
                    random_state=42,
                    n_estimators=90,
                    max_depth=2,
                    learning_rate=0.04,
                    min_samples_leaf=5,
                ),
            )
        )

    results = []
    try:
        for name, model in candidates:
            selection, metrics = _evaluate_model(
                model, Xtr, ytr, Xte, yte, wtr=wtr
            )
            results.append((selection, name, model, metrics))

        results.sort(key=lambda x: x[0], reverse=True)
        _, name, best, metrics = results[0]

        # Refit the selected architecture on all labeled evidence using the same
        # recency weighting used during validation.
        best.fit(X, y, sample_weight=weights)

        metrics.update(
            {
                "validation": validation_method,
                "test_samples": int(len(test_idx)),
                "compared_models": [x[1] for x in results],
                "recency_half_life_days": RECENCY_HALF_LIFE_DAYS,
                "position_feature_excluded": True,
                "seen_used_as_label": False,
            }
        )
        return LearningResult(
            True,
            name,
            best,
            metrics,
            len(y),
            positives,
            negatives,
        )
    except Exception:
        return base


def predict_success(result, context):
    if not result or not result.ready or result.model is None:
        return None
    try:
        x = np.asarray([_features_from_context(context)], dtype=float)
        return float(result.model.predict_proba(x)[0, 1])
    except Exception:
        return None


def ranking_metrics(events, k=4):
    """Ranking metrics using Save as the explicit relevance outcome.

    Seen is intentionally excluded from relevance because it indicates exposure,
    not whether the recommendation was actually preferred.
    """
    events = list(events or [])
    by_session = {}
    outcomes = {}
    row_order = {
        "Top Matches for You": 0,
        "Critically Acclaimed": 1,
        "Hidden Gems": 2,
        "Something Different": 3,
    }

    for e in events:
        sid = e.get("session_id")
        title = e.get("title")
        if not sid or not title:
            continue

        if e.get("event") == "impression":
            rank = row_order.get(e.get("row"), 9) * 4 + int(e.get("position") or 4)
            by_session.setdefault(sid, {})[title] = min(
                rank, by_session.setdefault(sid, {}).get(title, 999)
            )
        elif e.get("event") == "save":
            outcomes[(sid, title)] = 1
        elif e.get("event") == "skip" and (sid, title) not in outcomes:
            outcomes[(sid, title)] = 0

    precisions, recalls, hits, ndcgs, rrs = [], [], [], [], []

    for sid, ranks in by_session.items():
        relevant = {
            title
            for (s, title), y in outcomes.items()
            if s == sid and y == 1
        }
        if not relevant:
            continue

        ordered = sorted(ranks, key=ranks.get)
        top = ordered[:k]
        hit_count = sum(t in relevant for t in top)

        precisions.append(hit_count / max(1, k))
        recalls.append(hit_count / len(relevant))
        hits.append(1.0 if hit_count else 0.0)

        dcg = sum(
            1.0 / math.log2(i + 2)
            for i, t in enumerate(top)
            if t in relevant
        )
        ideal = sum(
            1.0 / math.log2(i + 2)
            for i in range(min(k, len(relevant)))
        )
        ndcgs.append(dcg / ideal if ideal else 0.0)

        rr = 0.0
        for i, t in enumerate(ordered, 1):
            if t in relevant:
                rr = 1.0 / i
                break
        rrs.append(rr)

    def avg(xs):
        return sum(xs) / len(xs) if xs else None

    return {
        "precision_at_k": avg(precisions),
        "recall_at_k": avg(recalls),
        "hit_rate_at_k": avg(hits),
        "ndcg_at_k": avg(ndcgs),
        "mrr": avg(rrs),
        "evaluated_sessions": len(precisions),
        "k": k,
    }


def calibration_metrics(events):
    """Observed Save rate by displayed Match band.

    The displayed Match remains a compatibility index. This diagnostic checks
    whether higher Match bands correspond to higher observed Save rates without
    claiming that the index is already a calibrated probability.
    """
    events = list(events or [])
    impressions = {}
    labels = {}

    for e in events:
        key = (e.get("session_id"), e.get("title"))
        if not all(key):
            continue
        if e.get("event") == "impression" and key not in impressions:
            impressions[key] = e
        elif e.get("event") == "save":
            labels[key] = 1
        elif e.get("event") == "skip" and key not in labels:
            labels[key] = 0

    bins = {
        "20–59": [],
        "60–69": [],
        "70–79": [],
        "80–89": [],
        "90–97": [],
    }
    absolute_errors = []
    squared_errors = []

    for key, y in labels.items():
        imp = impressions.get(key)
        if not imp or imp.get("match") is None:
            continue

        m = float(imp.get("match"))
        p = max(0.0, min(1.0, m / 100.0))
        absolute_errors.append(abs(p - y))
        squared_errors.append((p - y) ** 2)

        if m < 60:
            label = "20–59"
        elif m < 70:
            label = "60–69"
        elif m < 80:
            label = "70–79"
        elif m < 90:
            label = "80–89"
        else:
            label = "90–97"
        bins[label].append(y)

    return {
        "mae": (
            sum(absolute_errors) / len(absolute_errors)
            if absolute_errors
            else None
        ),
        "brier_like_index_error": (
            sum(squared_errors) / len(squared_errors)
            if squared_errors
            else None
        ),
        "bands": {
            b: (sum(v) / len(v) if v else None)
            for b, v in bins.items()
        },
        "labeled": len(absolute_errors),
    }
