"""Session helpers: browser save/restore, tap guards, tab version marks, friendly errors."""
import streamlit as st
from src.recommender import get_movie


def restore_profile(data):
    if not isinstance(data, dict):
        return False
    try:
        st.session_state.likes = set(data.get("likes") or [])
        st.session_state.favorites = set(data.get("favorites") or [])
        st.session_state.review_priority = int(data.get("review_priority", 50))
        st.session_state.genres = list(data.get("genres") or [])
        st.session_state.adventure = int(data.get("adventure", 50))
        st.session_state.more_of = list(data.get("more_of") or [])
        st.session_state.saved = set(data.get("saved") or [])
        st.session_state.seen = set(data.get("seen") or [])
        st.session_state.dismissed = set(data.get("dismissed") or [])
        st.session_state.disliked = set(data.get("disliked") or [])
        st.session_state.seen_from_saved = set(data.get("seen_from_saved") or [])
        st.session_state.seen_rating = {str(k): int(v) for k, v in (data.get("seen_rating") or {}).items() if v in (1, -1)}
        if data.get("anon_id"):
            st.session_state.anon_id = str(data["anon_id"])
        st.session_state.analytics_opt_out = bool(data.get("analytics_opt_out"))
        st.session_state.prev_visit = data.get("last_visit")
        st.session_state.prev_shown = list(data.get("last_shown") or [])
        st.session_state.last_shown = list(data.get("last_shown") or [])
        st.session_state.taste_reset_at = data.get("taste_reset_at")
        st.session_state.selection_order = list(data.get("selection_order") or [])
        st.session_state.imported_titles = set(data.get("imported_titles") or [])
        st.session_state.imported_seen = set(data.get("imported_seen") or [])
        st.session_state.imported_disliked = set(data.get("imported_disliked") or [])
        st.session_state.external_movies = dict(data.get("external_movies") or {})
        st.session_state.analytics_events = list(data.get("analytics_events") or [])[-2000:]
        st.session_state.streaming_services = list(data.get("streaming_services") or [])
        # A reload opens your normal Showroom: a search is for this visit only, never restored.
        st.session_state.mood_active = ""
        st.session_state.pop("mood_input", None)
        st.session_state.onboarding_complete = bool(data.get("onboarding_complete", False))
        if st.session_state.onboarding_complete:
            st.session_state.screen = "showroom"
        return True
    except (TypeError, ValueError):
        return False


def _compact_events(events, keep_actions=1500, keep_impressions=300):
    """What this browser keeps: every recent choice, the latest impressions, numbers rounded to 4 places.
    Impressions are 16 per page view, so keeping all of them made every save slow to write."""
    events = list(events or [])
    imp_idx = [i for i, e in enumerate(events) if e.get("event") == "impression"][-keep_impressions:]
    act_idx = [i for i, e in enumerate(events) if e.get("event") != "impression"][-keep_actions:]
    out = []
    for i in sorted(set(imp_idx) | set(act_idx)):
        e = dict(events[i])
        if isinstance(e.get("context"), dict):
            e["context"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in e["context"].items()}
        out.append({k: (round(v, 4) if isinstance(v, float) and k != "timestamp" else v) for k, v in e.items()})
    return out


def queue_profile_save():
    """Queue persistence without forcing an extra rerun.

    Every Streamlit widget interaction already causes one normal app rerun.
    Profile changes are written to localStorage during that same rerun, so we
    never trigger a second rerun just to persist state. This keeps selections
    visually stable and prevents the brief black/blank transition that can
    happen when explicit reruns are stacked on top of widget reruns.
    """
    st.session_state._pending_profile_save = True
    st.session_state._state_ver = int(st.session_state.get("_state_ver") or 0) + 1


def _too_soon(slot_key, gap=0.4):
    """A second tap on the same card within a moment is a double tap: ignore it so one tap = one action."""
    import time as _t
    now = _t.monotonic()
    last = dict(st.session_state.get("_last_slot_tap") or {})
    if now - last.get(slot_key, 0.0) < gap:
        return True
    last[slot_key] = now
    st.session_state._last_slot_tap = last
    return False


def _ver_mark(tab=None):
    """Hidden marker of how current this part of the page is. Opening a tab refreshes it only if
    something changed since it was drawn, so switching tabs is instant when nothing did."""
    v = int(st.session_state.get("_state_ver") or 0)
    cls = f'tv-mark" data-tab="{tab}' if tab is not None else "sv-cur"
    st.markdown(f'<span class="{cls}" data-v="{v}"></span>', unsafe_allow_html=True)


def _lib_mark(showroom=False):
    """Hidden marker for the library counter. The Showroom's copy says which library state it was ranked with."""
    v = int(st.session_state.get("_lib_ver") or 0)
    cls = 'lib-mark" data-tab="0' if showroom else "lib-cur"
    st.markdown(f'<span class="{cls}" data-v="{v}"></span>', unsafe_allow_html=True)


def _friendly_error(exc):
    """Log the real error for the server logs; show the viewer a calm message instead of a traceback."""
    if type(exc).__name__ in {"RerunException", "StopException"}:
        raise exc
    import sys
    import traceback
    print("iCinema error:", "".join(traceback.format_exception(exc)), file=sys.stderr, flush=True)
    st.markdown('<div class="friendly-error">This part didn’t load. Refresh the page to try again. '
                'Your picks, saves, and settings are kept.</div>', unsafe_allow_html=True)


def _timing_on():
    """Set ICINEMA_TIMING = true in Streamlit secrets to log where time goes (Manage app → Logs)."""
    import os
    if os.environ.get("ICINEMA_TIMING"):
        return True
    try:
        return bool(st.secrets.get("ICINEMA_TIMING", False))
    except Exception:
        return False


def _format_seconds(value):
    if value is None:
        return "Learning"
    value=max(0,int(round(value)))
    if value<60:
        return f"{value}s"
    return f"{value//60}m {value%60:02d}s"


def _remember_movie(movie):
    if not movie or not isinstance(movie, dict):
        return
    title = movie.get("title")
    if not title:
        return
    if movie.get("external") or not get_movie(title, {}):
        st.session_state.external_movies[title] = dict(movie)


def _drop_last_event(title, event_type):
    """Remove the most recent event of a type for a title (used by Undo)."""
    events = list(st.session_state.get("analytics_events") or [])
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("event") == event_type and events[i].get("title") == title:
            del events[i]
            break
    st.session_state.analytics_events = events
