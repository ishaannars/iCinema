"""Behavioral analytics for iCinema.

This module remains UI-agnostic. It records recommendation exposure and outcomes
locally so ranking, learning, and product efficiency can be evaluated without
changing the finished interface.
"""
import time
import uuid
from statistics import median

MAX_EVENTS = 2000


def new_session_id():
    return uuid.uuid4().hex[:12]


def ensure_session(state):
    if not state.get("showroom_session_id"):
        state["showroom_session_id"] = new_session_id()
        state["showroom_session_start"] = time.time()
        state["showroom_impression_keys"] = set()
    return state["showroom_session_id"]


def start_new_session(state):
    state["showroom_session_id"] = new_session_id()
    state["showroom_session_start"] = time.time()
    state["showroom_impression_keys"] = set()
    return state["showroom_session_id"]


def record_event(state, event_type, title, context=None):
    """Store a compact event snapshot.

    Position is logged for bias diagnostics but the supervised preference model
    intentionally does not train on it.
    """
    ensure_session(state)
    context = dict(context or {})
    now = time.time()

    event = {
        "event": str(event_type),
        "title": str(title),
        "timestamp": now,
        "session_id": state.get("showroom_session_id"),
        "elapsed_seconds": max(
            0.0,
            now - float(state.get("showroom_session_start") or now),
        ),
        "row": context.get("row"),
        "position": context.get("position"),
        "match": context.get("match"),
        "model_score": context.get("model_score"),
        "decision_utility": context.get("decision_utility"),
        "genre_affinity": context.get("genre_affinity"),
        "trait_affinity": context.get("trait_affinity"),
        "semantic_similarity": context.get("semantic_similarity"),
        "quality_alignment": context.get("quality_alignment"),
        "discovery_alignment": context.get("discovery_alignment"),
        "priority_alignment": context.get("priority_alignment"),
        "availability_alignment": context.get("availability_alignment"),
        "vote_confidence": context.get("vote_confidence"),
        "profile_confidence": context.get("profile_confidence"),
        "cf_affinity": context.get("cf_affinity"),
        "candidate_source": context.get("candidate_source"),
        "model_version": context.get("model_version"),
    }

    events = list(state.get("analytics_events") or [])
    events.append(event)
    state["analytics_events"] = events[-MAX_EVENTS:]
    return event


def record_impressions(state, contexts):
    ensure_session(state)
    seen = set(state.get("showroom_impression_keys") or set())

    for title, context in (contexts or {}).items():
        key = (
            state.get("showroom_session_id"),
            title,
            context.get("row"),
            context.get("position"),
        )
        if key in seen:
            continue
        record_event(state, "impression", title, context)
        seen.add(key)

    state["showroom_impression_keys"] = seen


IDLE_GAP_SECONDS = 30 * 60


def _segment_keys(events):
    """Map event index -> (session_id, n): a new segment starts after 30 idle minutes."""
    order = sorted(range(len(events)), key=lambda i: float(events[i].get("timestamp") or 0))
    last, count, keys = {}, {}, {}
    for i in order:
        sid = events[i].get("session_id")
        if not sid:
            continue
        ts = float(events[i].get("timestamp") or 0)
        if sid not in last or ts - last[sid] > IDLE_GAP_SECONDS:
            count[sid] = count.get(sid, -1) + 1
        last[sid] = ts
        keys[i] = (sid, count[sid])
    return keys


def analytics_insights(events):
    """Return product metrics centered on decision efficiency."""
    events = list(events or [])
    saves = [e for e in events if e.get("event") == "save"]
    skips = [e for e in events if e.get("event") == "skip"]
    seen = [e for e in events if e.get("event") == "seen"]
    impressions = [e for e in events if e.get("event") == "impression"]

    # Sessionize with a 30-minute inactivity rule (standard in web analytics), so a tab
    # left open for hours doesn't count as hours of deciding. Works on existing history too.
    seg_of = _segment_keys(events)
    seg_start = {}
    for idx, e in enumerate(events):
        key = seg_of.get(idx)
        if key is not None:
            ts = float(e.get("timestamp") or 0)
            seg_start[key] = min(seg_start.get(key, ts), ts)

    first_save = {}  # segment -> timestamp of its first save
    for idx, e in enumerate(events):
        key = seg_of.get(idx)
        if e.get("event") == "save" and key is not None:
            ts = float(e.get("timestamp") or 0)
            first_save[key] = min(first_save.get(key, ts), ts)

    times = [first_save[k] - seg_start[k] for k in first_save if first_save[k] >= seg_start[k]]

    skips_before, impressions_before = [], []
    for key, t in first_save.items():
        skips_before.append(sum(1 for idx, e in enumerate(events)
                                if e.get("event") == "skip" and seg_of.get(idx) == key
                                and float(e.get("timestamp") or 0) <= t))
        impressions_before.append(len({e.get("title") for idx, e in enumerate(events)
                                        if e.get("event") == "impression" and seg_of.get(idx) == key
                                        and float(e.get("timestamp") or 0) <= t and e.get("title")}))
    first_save_time = first_save

    saved_titles = {e.get("title") for e in saves if e.get("title")}
    seen_after = {
        e.get("title")
        for e in seen
        if e.get("title") in saved_titles
    }

    exploratory_rows = {
        "Hidden Gems",
        "Something Different",
        "Critically Acclaimed",
    }
    exploratory_saves = [
        e for e in saves if e.get("row") in exploratory_rows
    ]

    unique_impressions = {
        (e.get("session_id"), e.get("title"))
        for e in impressions
        if e.get("session_id") and e.get("title")
    }
    unique_saves = {
        (e.get("session_id"), e.get("title"))
        for e in saves
        if e.get("session_id") and e.get("title")
    }

    sessions_with_impressions = {
        seg_of[idx] for idx, e in enumerate(events)
        if e.get("event") == "impression" and idx in seg_of
    }
    sessions_with_save = set(first_save_time)

    return {
        "time_to_match_seconds": median(times) if times else None,
        "avg_skips_before_save": (
            sum(skips_before) / len(skips_before)
            if skips_before
            else None
        ),
        "avg_recommendations_examined_before_save": (
            sum(impressions_before) / len(impressions_before)
            if impressions_before
            else None
        ),
        "saved_to_seen_rate": (
            len(seen_after) / len(saved_titles)
            if saved_titles
            else None
        ),
        "discovery_rate": (
            len(exploratory_saves) / len(saves)
            if saves
            else None
        ),
        "save_rate": (
            len(unique_saves) / len(unique_impressions)
            if unique_impressions
            else None
        ),
        "session_no_save_rate": (
            (len(sessions_with_impressions - sessions_with_save)
             / len(sessions_with_impressions))
            if sessions_with_impressions
            else None
        ),
        "decision_efficiency": (
            1.0 / (sum(impressions_before) / len(impressions_before))
            if impressions_before and sum(impressions_before) > 0
            else None
        ),
        "impressions": len(impressions),
        "saves": len(saves),
        "skips": len(skips),
        "seen_actions": len(seen),
        "sessions_with_match": len(first_save_time),
        "sessions_observed": len(sessions_with_impressions),
    }
