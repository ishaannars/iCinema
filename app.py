
import time as _time
_BOOT = _time.perf_counter()
import html
from pathlib import Path
from urllib.parse import quote_plus
import json
import re
import streamlit as st
from src.recommender import (
    STARTER_MOVIES, GENRES, MORE_OF_OPTIONS, searchable_titles, get_movie,
    build_profile, score_movie, recommend, rank_movies, score_movie_components, CATALOG,
    recommendation_explanation, profile_confidence_label, mmr_rerank, availability_utility,
    semantic_similarity_scores
)
from src.analytics import ensure_session, start_new_session, record_event, record_impressions, analytics_insights
from src.ml_engine import train_learning_model, predict_success, ranking_metrics, calibration_metrics
from src.watch_providers import get_watch_availability_batch, tmdb_configured
from src.tmdb_catalog import search_movies, get_poster_batch, get_landscape_batch, get_landscape_art, get_movie_identity_batch, tmdb_catalog_configured, discover_movies
from src.live_ratings import get_live_ratings_batch, omdb_configured
from src.browser_storage import browser_storage
from src.scroll_keeper import scroll_keeper
from src.cf_model import user_vector, cf_affinity, closest_liked, item_similarity, fan_percentile, preferred_title, interleave_eligible
from src.interleave import team_draft, TARGET_DECIDED
from src.recommender import _calibrated_match_percent

def _timing_on():
    """Set ICINEMA_TIMING = true in Streamlit secrets to log where time goes (Manage app → Logs)."""
    import os
    if os.environ.get("ICINEMA_TIMING"):
        return True
    try:
        return bool(st.secrets.get("ICINEMA_TIMING", False))
    except Exception:
        return False


def _log_time(label, start):
    if _timing_on():
        import sys
        print(f"[timing] {label}: {(_time.perf_counter() - start) * 1000:.0f} ms", file=sys.stderr, flush=True)


_log_time("imports", _BOOT)
st.set_page_config(page_title="iCinema", page_icon=str(Path(__file__).parent / "assets" / "favicon.png"), layout="wide", initial_sidebar_state="collapsed")

from src.ui import app_css
from src.love import love_line, fit_floor, test_viewers as love_test_viewers
from src.ui.cards import (  # card and popup text, unit-tested in tests/test_cards.py
    PILL_BUDGET,
    _PILL_SHORT,
    _short_reason,
    _short_title,
    card_desc_html,
    card_html,
    ratings_reason,
    score_mix,
    meta_html,
    card_ratings,
    card_reason_line,
    concise_description,
    fit_head,
    fit_label,
    genre_pair,
    library_lines_html,
    library_ratings_html,
    library_text_html,
    match_label,
    match_pill,
    plain_premise,
    premise_panel,
    profile_analysis_html,
    profile_chip_html,
    ratings_text,
    why_models,
    why_rows,
    why_sentences,
    with_live_ratings,
)
from src.ui.watch import (STREAMING_SERVICES, PROVIDER_LINKS, _provider_key, _on_service, provider_watch_url,
                          watch_options, watch_line_html, concise_availability_text, movie_on_services)

st.markdown("<style>" + app_css() + "</style>", unsafe_allow_html=True)

defaults={
    "screen":"welcome","onboarding_complete":False,"likes":set(),"favorites":set(),"review_priority":50,
    "genres":[],"adventure":50,"more_of":[],"saved":set(),"seen":set(),"dismissed":set(),"disliked":set(),"seen_from_saved":set(),"seen_rating":{},"selection_order":[],"imported_titles":set(),"imported_seen":set(),"imported_disliked":set(),"import_summary":None,
    "custom_like":None,"search_selected_title":None,"search_selected_movie":None,"external_movies":{},
    "shelf_movies":[],"shelf_replacement_pool":[],"shelf_seen_titles":set(),
    "shelf_pool_initialized":False,"shelf_tmdb_loaded":False,
    "analytics_events":[],"showroom_session_id":None,"showroom_session_start":None,
    "showroom_impression_keys":set(),"recommendation_context":{},
    "showroom_slots":{},"showroom_payloads":{},"showroom_row_queues":{},
    "showroom_identity_cache":{},"showroom_watch_cache":{},"showroom_rating_cache":{},
    "streaming_services":[],"mood_active":""
}
# Always mounted at the same spot so its iframe (and listeners) persist across reruns.
scroll_keeper()

# Module-level code runs only on full page runs, never on fragment-only reruns.
st.session_state._in_full_run = True
for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k]=v.copy() if isinstance(v,(set,dict)) else (list(v) if isinstance(v,list) else v)

PROFILE_STORAGE_KEY = "icinema_profile_v1"

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


def profile_snapshot():
    return {
        "version": 1,
        "onboarding_complete": bool(st.session_state.onboarding_complete),
        "likes": sorted(st.session_state.likes),
        "favorites": sorted(st.session_state.favorites),
        "review_priority": st.session_state.review_priority,
        "genres": list(st.session_state.genres),
        "adventure": st.session_state.adventure,
        "more_of": list(st.session_state.more_of),
        "saved": sorted(st.session_state.saved),
        "seen": sorted(st.session_state.seen),
        "dismissed": sorted(st.session_state.dismissed),
        "disliked": sorted(st.session_state.get("disliked") or set()),
        "seen_from_saved": sorted(st.session_state.get("seen_from_saved") or set()),
        "seen_rating": dict(st.session_state.get("seen_rating") or {}),
        "anon_id": st.session_state.get("anon_id"),
        "analytics_opt_out": bool(st.session_state.get("analytics_opt_out")),
        "last_visit": st.session_state.get("last_visit"),
        "last_shown": list(st.session_state.get("last_shown") or [])[:40],
        "taste_reset_at": st.session_state.get("taste_reset_at"),
        "selection_order": list(st.session_state.get("selection_order", [])),
        "imported_titles": sorted(st.session_state.get("imported_titles") or set()),
        "imported_seen": sorted(st.session_state.get("imported_seen") or set()),
        "imported_disliked": sorted(st.session_state.get("imported_disliked") or set()),
        "external_movies": st.session_state.external_movies,
        "analytics_events": _compact_events(st.session_state.get("analytics_events", [])),
        "streaming_services": list(st.session_state.get("streaming_services") or []),
        "mood_active": str(st.session_state.get("mood_active") or "")[:120],
    }

def _snapshot_signature(snapshot):
    import hashlib
    return hashlib.md5(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()


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
        st.session_state.mood_active = str(data.get("mood_active") or "")[:120]
        st.session_state.pop("mood_input", None)
        st.session_state.onboarding_complete = bool(data.get("onboarding_complete", False))
        if st.session_state.onboarding_complete:
            st.session_state.screen = "showroom"
        return True
    except (TypeError, ValueError):
        return False

# Hydrate once per browser session before rendering the product. The component stores
# only recommendation/profile state in this browser's localStorage.
if not st.session_state.get("_storage_hydrated", False):
    _stored = browser_storage("get", PROFILE_STORAGE_KEY, key="icinema_profile_loader")
    if not (isinstance(_stored, dict) and _stored.get("loaded") is True):
        logo_placeholder = '<div class="icinema-logo">iCinema</div><div class="icinema-boot-loader" aria-label="Loading"></div>'
        st.markdown(logo_placeholder, unsafe_allow_html=True)
        st.session_state._in_full_run = False
        st.stop()
    restored = restore_profile(_stored.get("value")) if _stored.get("value") else False
    st.session_state._storage_hydrated = True
    st.session_state._fade_in_once = True
    st.session_state._last_persisted_profile = _snapshot_signature(profile_snapshot()) if restored else None

# Move my profile: a link from another device asks before replacing this browser's profile.
from src.profile_link import decode as _decode_profile_link, encode as _encode_profile_link
_incoming = st.query_params.get("p")
if _incoming and st.session_state.get("_link_handled") != _incoming:
    _data = _decode_profile_link(_incoming)
    if _data is None:
        st.session_state._link_handled = _incoming
    else:
        st.markdown('<div class="link-banner">Load your iCinema profile from this link? '
                    'It replaces the profile saved in this browser.</div>', unsafe_allow_html=True)
        _a, _b, _ = st.columns([1.2, 1, 5], gap="small")
        with _a:
            if st.button("Load My Profile", type="primary", key="link_load"):
                restore_profile({**profile_snapshot(), **_data, "external_movies": {**st.session_state.external_movies,
                                                                                    **(_data.get("external_movies") or {})}})
                st.session_state._link_handled = _incoming
                st.query_params.clear()
                st.session_state._last_persisted_profile = None    # the end of the next run saves it to this browser
                st.rerun()
        with _b:
            if st.button("Not Now", key="link_skip"):
                st.session_state._link_handled = _incoming
                st.query_params.clear()
                st.rerun()

# Profile-changing actions queue a snapshot, but we deliberately do NOT mount
# the browser-storage component before the destination page renders. Mounting
# that component at the top of a page transition can briefly expose its iframe
# background as a black strip. The normal persist_profile_if_needed() call at
# the end of the render writes the exact same snapshot silently.
# Always emit this one style element, so every run has the same layout above the page.
# If it appeared only on the first run, the next run's elements would shift by one slot and
# the previous copy of the header and tabs could show as a faded duplicate while it loads.
_first_paint = st.session_state.pop("_fade_in_once", False)
st.markdown('<style>' + ('.stApp [data-testid="stMainBlockContainer"], .stApp .block-container'
                         '{animation:icn-appear .25s ease both}.stApp [data-stale="true"]{display:none !important}'
                         if _first_paint else '') + '</style>', unsafe_allow_html=True)

_pending_profile = st.session_state.get("_pending_profile_save")

def persist_profile_if_needed():
    """Write the profile to this browser only after something the viewer did changed it.

    Building and comparing the full snapshot on every render (including every card rerun)
    used to cost more than the click itself, so it now runs only when a change is queued.
    """
    if not st.session_state.get("_storage_hydrated", False):
        return
    if not st.session_state.get("_pending_profile_save") and st.session_state.get("_last_persisted_profile") is not None:
        return
    snapshot = profile_snapshot()
    serialized = _snapshot_signature(snapshot)
    if serialized != st.session_state.get("_last_persisted_profile"):
        # Stable component key lets the browser acknowledge the write without
        # creating a new component instance on every ordinary render.
        browser_storage("set_silent", PROFILE_STORAGE_KEY, value=snapshot, key="icinema_profile_saver")
        st.session_state._last_persisted_profile = serialized
    st.session_state._pending_profile_save = None

def persist_from_fragment():
    """Save only during fragment-only reruns (e.g. Skip).

    On a full page run the single save at the end of the script handles it, so the
    hidden saver never appears mid-page and shifts the layout between runs.
    """
    if not st.session_state.get("_in_full_run"):
        persist_profile_if_needed()


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


def _lib_bump():
    """A choice made on Saved or Seen (thumbs, Mark Seen, Remove): the Showroom re-ranks when you go back to it."""
    st.session_state._lib_ver = int(st.session_state.get("_lib_ver") or 0) + 1


def _saved_to_seen(title, movie):
    mark_movie_seen(title, movie)
    _lib_bump()


def _lib_mark(showroom=False):
    """Hidden marker for the library counter. The Showroom's copy says which library state it was ranked with."""
    v = int(st.session_state.get("_lib_ver") or 0)
    cls = 'lib-mark" data-tab="0' if showroom else "lib-cur"
    st.markdown(f'<span class="{cls}" data-v="{v}"></span>', unsafe_allow_html=True)


def _ver_mark(tab=None):
    """Hidden marker of how current this part of the page is. Opening a tab refreshes it only if
    something changed since it was drawn, so switching tabs is instant when nothing did."""
    v = int(st.session_state.get("_state_ver") or 0)
    cls = f'tv-mark" data-tab="{tab}' if tab is not None else "sv-cur"
    st.markdown(f'<span class="{cls}" data-v="{v}"></span>', unsafe_allow_html=True)

RECOGNIZABLE_SHELF_TITLES = [
    "Dune: Part Two", "Blade Runner 2049", "The Prestige", "Prisoners",
    "Nightcrawler", "The Truman Show", "The Grand Budapest Hotel",
    "No Country for Old Men", "Before Sunrise", "Train to Busan",
    "Your Name", "Princess Mononoke", "Akira", "Ex Machina",
    "Past Lives", "The Holdovers", "The Wailing", "The Handmaiden",
    "Memories of Murder", "The Worst Person in the World",
]

def _tested_shelf():
    """Step 1 shelf picked by training/confirm_shelf_and_imports.py, or [] if that test didn't pass."""
    try:
        rows = json.loads((Path(__file__).resolve().parent / "data" / "shelf_titles.json").read_text())["titles"]
    except Exception:
        return []
    out = []
    for r in rows:
        m = get_movie(r["title"])
        out.append(dict(m) if m else {"title": r["title"], "year": int(r.get("year") or 0),
                                      "tmdb_id": int(r.get("tmdb_id") or 0), "external": True,
                                      "candidate_source": "shelf"})
    return out


def _current_hits(k, skip):
    """The k most popular recent movies on TMDB right now (released in the last 3 years)."""
    if not tmdb_catalog_configured():
        return []
    try:
        import datetime
        recent = datetime.date.today().year - 3
        cands = [dict(m) for m in discover_movies(100) if m.get("poster_url") and int(m.get("year") or 0) >= recent]
    except Exception:
        return []
    cands.sort(key=lambda m: float(m.get("popularity") or 0), reverse=True)
    out = []
    for m in cands:
        if _shelf_key(m) in skip or (str(m.get("title", "")).casefold(), 0) in skip:
            continue
        out.append(m)
        if len(out) >= k:
            break
    return out


def _shelf_key(movie):
    return (str(movie.get("title", "")).casefold(), int(movie.get("year") or 0))

def _seed_local_shelf_pool():
    if st.session_state.shelf_pool_initialized:
        return
    selected = st.session_state.likes | st.session_state.favorites
    visible = {_shelf_key(m) for m in st.session_state.shelf_movies}
    pool = [m for m in _tested_shelf() if m.get("title") not in selected and _shelf_key(m) not in visible]
    for title in RECOGNIZABLE_SHELF_TITLES:
        movie = get_movie(title)
        if not movie or movie.get("title") in selected:
            continue
        pool.append(dict(movie))
    st.session_state.shelf_replacement_pool = pool
    st.session_state.shelf_pool_initialized = True

def _load_tmdb_shelf_pool():
    if st.session_state.shelf_tmdb_loaded or not tmdb_catalog_configured():
        return
    try:
        candidates = discover_movies(300)
    except Exception:
        candidates = []
    # Keep the shelf broadly recognizable: prioritize popularity and substantial voting.
    candidates = [
        dict(m) for m in candidates
        if m.get("poster_url")
        and (float(m.get("popularity") or 0) >= 25 or int(m.get("tmdb_vote_count") or 0) >= 750)
    ]
    candidates.sort(
        key=lambda m: (float(m.get("popularity") or 0), int(m.get("tmdb_vote_count") or 0)),
        reverse=True,
    )
    existing = {_shelf_key(m) for m in st.session_state.shelf_replacement_pool}
    existing |= {_shelf_key(m) for m in st.session_state.shelf_movies}
    existing |= {(str(t).casefold(), 0) for t in (st.session_state.likes | st.session_state.favorites)}
    for movie in candidates:
        key = _shelf_key(movie)
        if key in existing or movie.get("title") in st.session_state.likes or movie.get("title") in st.session_state.favorites:
            continue
        st.session_state.shelf_replacement_pool.append(movie)
        existing.add(key)
    st.session_state.shelf_tmdb_loaded = True

def _next_shelf_movie():
    _seed_local_shelf_pool()
    visible_keys = {_shelf_key(m) for m in st.session_state.shelf_movies}
    selected = st.session_state.likes | st.session_state.favorites

    def pop_valid():
        while st.session_state.shelf_replacement_pool:
            movie = st.session_state.shelf_replacement_pool.pop(0)
            if movie.get("title") in selected:
                continue
            key = _shelf_key(movie)
            if key in visible_keys or key in st.session_state.shelf_seen_titles:
                continue
            return movie
        return None

    movie = pop_valid()
    if movie is None:
        _load_tmdb_shelf_pool()
        movie = pop_valid()
    return movie

def ensure_rotating_shelf():
    selected = st.session_state.likes | st.session_state.favorites
    if not st.session_state.shelf_movies:
        tested = _tested_shelf()
        first = tested or [dict(m) for m in STARTER_MOVIES]
        first = [m for m in first if m.get("title") not in selected]
        if tested:
            # The tested order fills the first two rows. The third row is this year's biggest movies,
            # so the shelf feels current; the test didn't score them, it only adds more to like.
            hits = _current_hits(5, {_shelf_key(m) for m in first[:10]} | {(str(t).casefold(), 0) for t in selected})
            first = first[:10] + hits + first[10:]
        st.session_state.shelf_movies = first[:15]
        st.session_state.shelf_seen_titles.update(_shelf_key(m) for m in st.session_state.shelf_movies)
    else:
        st.session_state.shelf_movies = [m for m in st.session_state.shelf_movies if m.get("title") not in selected]

    while len(st.session_state.shelf_movies) < 15:
        replacement = _next_shelf_movie()
        if not replacement:
            break
        st.session_state.shelf_movies.append(replacement)
        st.session_state.shelf_seen_titles.add(_shelf_key(replacement))

def skip_shelf_movie(slot_index):
    """Swap one shelf card for the next recognizable title. Not a dislike, so nothing is logged."""
    replacement = _next_shelf_movie()
    if 0 <= slot_index < len(st.session_state.shelf_movies):
        if replacement:
            st.session_state.shelf_movies[slot_index] = replacement
            st.session_state.shelf_seen_titles.add(_shelf_key(replacement))
        else:
            st.session_state.shelf_movies.pop(slot_index)


def rate_shelf_movie(movie, kind, slot_index):
    movie = dict(movie)
    title = movie.get("title")
    if not title:
        return
    # TMDB replacement movies carry rich metadata. Persist that metadata so every
    # available feature (genre, semantic traits, popularity, quality, language, era)
    # enters the same recommendation model immediately after Like/Favorite.
    if movie.get("external") or movie.get("tmdb_id"):
        st.session_state.external_movies[title] = movie

    st.session_state.likes.add(title)
    if title not in st.session_state.selection_order:
        st.session_state.selection_order.append(title)
    if kind == "favorite":
        st.session_state.favorites.add(title)
    else:
        st.session_state.favorites.discard(title)

    replacement = _next_shelf_movie()
    if 0 <= slot_index < len(st.session_state.shelf_movies):
        if replacement:
            st.session_state.shelf_movies[slot_index] = replacement
            st.session_state.shelf_seen_titles.add(_shelf_key(replacement))
        else:
            st.session_state.shelf_movies.pop(slot_index)
    queue_profile_save()

def add_search_choice(kind):
    movie = st.session_state.get("search_selected_movie")
    if not movie:
        return
    title = movie["title"]
    if movie.get("external"):
        st.session_state.external_movies[title] = movie
    st.session_state.likes.add(title)
    if title not in st.session_state.selection_order:
        st.session_state.selection_order.append(title)
    if kind == "favorite":
        st.session_state.favorites.add(title)
    else:
        st.session_state.favorites.discard(title)
    st.session_state.search_selected_movie = None
    st.session_state.search_selected_title = None
    queue_profile_save()

def live_search_box():
    """Results update as you type (debounced ~0.3s), like a search engine.
    Falls back to the standard text box if the keyup component is unavailable."""
    try:
        from st_keyup import st_keyup
        return st_keyup("Search movies", placeholder="Search by title", debounce=300,
                        label_visibility="collapsed", key="movie_search_live") or ""
    except Exception:
        return st.text_input("Search movies", placeholder="Search by title",
                             label_visibility="collapsed", key="movie_search_query")


def _import_flags():
    """Which extra imported signals passed their offline test (data/shelf_import_confirm.json)."""
    try:
        d = json.loads((Path(__file__).resolve().parent / "data" / "shelf_import_confirm.json").read_text())["imports"]
        return bool(d["low_ratings_as_not_for_me"]["use"]), bool(d["middling_ratings_as_seen"]["use"])
    except Exception:
        return False, False


def import_letterboxd():
    """Read an uploaded Letterboxd or IMDb export and add its ratings as signals."""
    from src.cf_model import lookup
    from src.letterboxd import read_ratings, to_choices
    up = st.session_state.get("lb_upload")
    if up is None:
        return
    use_low, use_mid = _import_flags()
    try:
        choices, summary = to_choices(read_ratings(up.getvalue()), lookup, use_low, use_mid)
    except Exception:
        st.session_state.import_summary = {"error": True}
        return
    imported = set(st.session_state.get("imported_titles") or set())
    imp_seen = set(st.session_state.get("imported_seen") or set())
    imp_dis = set(st.session_state.get("imported_disliked") or set())
    for movie, kind in choices:
        title = movie["title"]
        if title in st.session_state.likes:
            continue                      # keep what the viewer already chose by hand
        if kind in ("seen", "dislike"):
            if not get_movie(title):
                st.session_state.external_movies[title] = movie
            (imp_seen if kind == "seen" else imp_dis).add(title)
            continue
        if not get_movie(title):          # catalog movies keep their richer catalog details
            st.session_state.external_movies[title] = movie
        st.session_state.likes.add(title)
        if kind == "favorite":
            st.session_state.favorites.add(title)
        imported.add(title)
    st.session_state.imported_titles = imported
    st.session_state.imported_seen = imp_seen
    st.session_state.imported_disliked = imp_dis
    st.session_state.import_summary = summary
    queue_profile_save()


def undo_letterboxd_import():
    for title in st.session_state.get("imported_titles") or set():
        st.session_state.likes.discard(title)
        st.session_state.favorites.discard(title)
    st.session_state.imported_titles = set()
    st.session_state.imported_seen = set()
    st.session_state.imported_disliked = set()
    st.session_state.import_summary = None
    queue_profile_save()


def remove_step1_selection(title):
    """Remove a Like/Favorite signal from Step 1 and persist the updated profile."""
    st.session_state.likes.discard(title)
    st.session_state.favorites.discard(title)
    st.session_state.selection_order = [
        item for item in st.session_state.get("selection_order", [])
        if item != title
    ]
    queue_profile_save()

def go(screen):
    """Navigate using the widget's normal single rerun.

    Ordinary onboarding page navigation does not change the learned profile, so
    it should not invoke the localStorage bridge. Only entering the Showroom
    changes the persisted onboarding-complete state. Avoiding that unnecessary
    write also prevents a transient dark component strip during Start
    Personalizing -> Step 1.
    """
    st.session_state.screen = screen
    if screen == "showroom":
        st.session_state.onboarding_complete = True
        start_new_session(st.session_state)
        queue_profile_save()

def go_from_fragment(screen):
    """Leave a fragment with one intentional page-level transition.

    Do not synchronously write browser storage before navigating. The next page
    render persists the queued snapshot, which avoids making Step 1 → 2 → 3 →
    Profile → Showroom transitions wait on the browser component first.
    """
    go(screen)
    st.session_state._app_rerun = True

def select_search_result(movie):
    st.session_state.search_selected_movie = movie
    st.session_state.search_selected_title = movie.get("title")

def set_review_priority(value):
    st.session_state.review_priority = value
    queue_profile_save()

def toggle_genre_choice(genre):
    selected = set(st.session_state.genres)
    if genre in selected:
        selected.discard(genre)
    elif len(selected) < 5:
        selected.add(genre)
    st.session_state.genres = list(selected)
    queue_profile_save()

def set_adventure_level(value):
    st.session_state.adventure = value
    queue_profile_save()




_NON_TONE_TAGS = {g.casefold() for g in GENRES} | {
    "animation", "anime", "international", "critically acclaimed", "hidden gem", "hidden gems",
    "classic", "classics", "recent", "recent release", "recent releases", "documentary", "documentaries",
}


def _tone_tags(movie):
    return [t for t in ((movie or {}).get("tags") or []) if str(t).strip() and str(t).casefold() not in _NON_TONE_TAGS]


def with_tone_detail(reasons, movie, avoid=None):
    """Make the tone reason concrete: which tones it shares, and with which liked movie."""
    liked = [m for m, action in _cf_signals() if action in ("favorite", "like", "save")
             and m.get("title") != (movie or {}).get("title")]
    tones = {t.casefold(): t for t in _tone_tags(movie)}
    best, shared, best_key = None, [], None
    for other in liked:
        overlap = [tones[t.casefold()] for t in _tone_tags(other) if t.casefold() in tones]
        if not overlap:
            continue
        sim = item_similarity(movie, other) or 0.0
        key = (len(overlap), other.get("title") != avoid, sim)   # most shared tones, then a different movie, then closest fans
        if best_key is None or key > best_key:
            best, shared, best_key = other.get("title"), overlap, key
    if not best or not shared:
        return reasons
    words = [t.lower() if t[:1].isupper() and not t.isupper() else t for t in shared[:2]]
    phrase = " and ".join(words)
    detail = f"{phrase[:1].upper() + phrase[1:]}, like “{best}”."
    out = []
    for reason in reasons or []:
        if reason.get("label") in ("Feels like your favorites", "Feels like your pick", "Storytelling you like"):
            reason = {**reason, "text": detail}
        out.append(reason)
    return out


FATIGUE_STEP = 0.04     # objective penalty per earlier visit a title was shown and ignored
FATIGUE_CAP = 5         # stop penalizing after five ignored visits
VARIETY_SPREAD = 0.03   # per-visit shuffle among near-ties (stable within a visit)


def impression_fatigue():
    """Earlier visits in which each title was shown but got no Save, Seen, or Skip.

    Impression discounting: returning viewers see fresh options instead of the
    same ignored cards, which shortens the path to something worth watching.
    """
    events = st.session_state.get("analytics_events") or []
    current = st.session_state.get("showroom_session_id")
    acted = {e.get("title") for e in events if e.get("event") in ("save", "seen", "skip", "dislike")}
    visits = {}
    for e in events:
        if e.get("event") != "impression":
            continue
        sid, title = e.get("session_id"), e.get("title")
        if sid and title and sid != current and title not in acted:
            visits.setdefault(title, set()).add(sid)
    return {title: len(sids) for title, sids in visits.items()}


def visit_variety(title):
    """Deterministic value in [-0.5, 0.5] for this visit and title."""
    import hashlib
    key = f"{st.session_state.get('showroom_session_id')}::{title}".encode()
    return int(hashlib.md5(key).hexdigest()[:8], 16) / 0xFFFFFFFF - 0.5








def with_cf_reason(reasons, payload, limit=3):
    """Surface the collaborative-filtering signal, naming the viewer's closest liked movie."""
    cf = (payload or {}).get("cf")
    anchor = (closest_liked((payload or {}).get("movie"), _cf_signals())
              if isinstance(cf, (int, float)) and cf >= 0.65 else None)
    reasons = with_tone_detail(list(reasons or []), (payload or {}).get("movie"), avoid=anchor)
    if isinstance(cf, (int, float)) and cf >= 0.65:
        if anchor:
            # High similarity means the same MovieLens viewers loved both movies.
            reason = {"label": f"Loved by fans of “{anchor}”",
                      "text": f"Viewers who loved “{anchor}” tend to love this too."}
        elif fan_percentile((payload or {}).get("movie")) is None:
            # A new release: no fans yet, so the score comes from its makers and style (new_releases.py).
            reason = {"label": "New, and close to what you like",
                      "text": "Its director, cast, and studio point to the movies you liked."}
        else:
            reason = {"label": "Loved by viewers like you",
                      "text": "Viewers who liked the movies you liked tend to love this too."}
        if anchor:   # one line per movie: fold a tone line about the same movie into this one
            key = re.sub(r"[^\w]", "", anchor.casefold())
            same = [r for r in reasons if r.get("label") in ("Feels like your favorites", "Feels like your pick", "Storytelling you like")
                    and key in re.sub(r"[^\w]", "", str(r.get("text", "")).casefold())]
            if same:
                reasons = [r for r in reasons if r not in same]
                reason["text"] = f"Viewers who loved “{anchor}” tend to love this too, and it has a similar tone."
        reasons = [reason] + reasons
    return reasons[:limit]

def _tag_overlap(a, b):
    ta = {str(t).casefold() for t in (a or {}).get("tags") or []}
    tb = {str(t).casefold() for t in (b or {}).get("tags") or []}
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def whats_next_ranking(source, payloads, blocked):
    """Candidates ranked by how well they follow `source`, the movie just watched.

    A tested mix of similarity to that movie and the viewer's own personalized match, so each
    pick follows what they watched AND fits their taste. Similarity comes from the
    MovieLens item-kNN model (the same viewers loved both movies). When the watched movie
    is in MovieLens, only candidates in MovieLens are compared, so CF and content
    scores are never mixed; otherwise genre and tag overlap stand in.
    Returns [(title, used_cf), ...], best first.
    """
    scored = []
    for t, payload in (payloads or {}).items():
        movie = (payload or {}).get("movie")
        if not movie or t in blocked or t == (source or {}).get("title"):
            continue
        sim = item_similarity(movie, source)
        used_cf = sim is not None
        if sim is None:
            same_genre = 1.0 if movie.get("genre") and movie.get("genre") == (source or {}).get("genre") else 0.0
            sim = 0.5 * same_genre + 0.5 * _tag_overlap(movie, source)
        score = WHATS_NEXT_SIM * sim + (1 - WHATS_NEXT_SIM) * (float(payload.get("match") or 0) / 100.0)
        scored.append((score, t, used_cf))
    if any(cf for _, _, cf in scored):
        scored = [x for x in scored if x[2]]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(t, cf) for _, t, cf in scored]


def whats_next_another(source_title):
    offsets = dict(st.session_state.get("whats_next_offset") or {})
    offsets[source_title] = int(offsets.get(source_title, 0)) + 1
    st.session_state.whats_next_offset = offsets


def service_availability_utility(availability):
    """Availability value that respects the viewer's chosen services.

    A title streaming only on a service the viewer doesn't have is treated like a
    paid rental: still watchable, but less convenient tonight.
    """
    availability = availability or {}
    status = availability.get("status")
    services = list(st.session_state.get("streaming_services") or [])
    if services and status == "streaming" and not movie_on_services(availability, services):
        return availability_utility("rent")
    return availability_utility(status)





# Pill-sized forms of long reason labels; the full wording stays in the popover.












def toggle_streaming_service(name):
    services = list(st.session_state.get("streaming_services") or [])
    if name in services:
        services.remove(name)
    else:
        services.append(name)
    st.session_state.streaming_services = services
    queue_profile_save()

def toggle_priority_choice(option):
    selected = set(st.session_state.more_of)
    if option in selected:
        selected.discard(option)
    else:
        selected.add(option)
    st.session_state.more_of = list(selected)
    queue_profile_save()

def _remember_movie(movie):
    if not movie or not isinstance(movie, dict):
        return
    title = movie.get("title")
    if not title:
        return
    if movie.get("external") or not get_movie(title, {}):
        st.session_state.external_movies[title] = dict(movie)

def _current_recommendation_context(title):
    return dict((st.session_state.get("recommendation_context") or {}).get(title) or {})

def skip_movie(title, movie=None):
    _remember_movie(movie)
    record_event(st.session_state, "skip", title, _current_recommendation_context(title))
    st.session_state.dismissed.add(title)
    st.session_state.saved.discard(title)
    queue_profile_save()

def save_movie(title, movie=None):
    _remember_movie(movie)
    record_event(st.session_state, "save", title, _current_recommendation_context(title))
    st.session_state.saved.add(title)
    st.session_state.seen.discard(title)
    st.session_state.dismissed.discard(title)
    queue_profile_save()

def remove_saved_movie(title):
    _lib_bump()
    st.session_state.saved.discard(title)
    queue_profile_save()

def mark_movie_seen(title, movie=None):
    _remember_movie(movie)
    record_event(st.session_state, "seen", title, _current_recommendation_context(title))
    if title in st.session_state.saved:
        from_saved = set(st.session_state.get("seen_from_saved") or set())
        from_saved.add(title)
        st.session_state.seen_from_saved = from_saved
    st.session_state.seen.add(title)
    st.session_state.saved.discard(title)
    st.session_state.dismissed.discard(title)
    queue_profile_save()

def remove_from_seen(title):
    _lib_bump()
    """Undo an accidental Seen: drop it and its model signal; restore it to Saved if it came from there."""
    st.session_state.seen.discard(title)
    st.session_state.seen_rating = {k: v for k, v in (st.session_state.get("seen_rating") or {}).items() if k != title}
    from_saved = set(st.session_state.get("seen_from_saved") or set())
    if title in from_saved:
        from_saved.discard(title)
        st.session_state.seen_from_saved = from_saved
        st.session_state.saved.add(title)
    _drop_last_event(title, "seen")
    queue_profile_save()












def resolve_history_movie(title):
    movie = get_movie(title, st.session_state.external_movies)
    if movie:
        return movie
    if tmdb_catalog_configured():
        try:
            matches = search_movies(title, 1)
            movie = matches[0] if matches else None
        except Exception:
            movie = None
        if movie:
            st.session_state.external_movies[title] = movie
            queue_profile_save()
            return movie
    return None

def reset_profile_state():
    for k, v in defaults.items():
        st.session_state[k] = v.copy() if isinstance(v, (set, dict)) else (list(v) if isinstance(v, list) else v)
    st.session_state._last_persisted_profile = None
    for key in ("tonight_services_picker", "tonight_last_skip", "tonight_pool", "showroom_undo", "showroom_pill_labels", "mood_input"):
        st.session_state.pop(key, None)
    queue_profile_save()

def reset_profile_from_fragment():
    reset_profile_state()
    st.session_state._app_rerun = True

def logo():
    st.markdown('<div class="icinema-logo">iCinema</div>',unsafe_allow_html=True)

def movie_thumb(movie, poster_url=None, compact=False, library_mode=None, landscape=False, toggle_id=None, return_html=False):
    title = html.escape(str(movie.get("title", "")))
    year = html.escape(str(movie.get("year", "")))
    poster_url = poster_url or movie.get("poster_url")
    if poster_url and not str(poster_url).lower().startswith(("https://", "http://")):
        poster_url = None   # only web image links reach the page
    logo_url = None
    if poster_url and "#logo=" in str(poster_url):
        poster_url, logo_url = str(poster_url).split("#logo=", 1)
    if poster_url:
        safe_url = html.escape(str(poster_url), quote=True)
        portrait = landscape and "/w780" not in str(poster_url)       # no 16:9 art: fit the poster inside the frame
        logo_html = (f'<img class="art-logo" src="{html.escape(logo_url, quote=True)}" alt="">' if logo_url else
                     (f'<div class="art-title-text">{title}</div>' if landscape and not str(poster_url).endswith("#titled") else ""))
        poster_html = (f'<div class="poster has-image{" landscape" if landscape else ""}{" fallback" if portrait else ""}">'
                       f'<img src="{safe_url}" alt="Poster for {title}">{logo_html}</div>')
    elif landscape:
        poster_html = f'<div class="poster landscape"><div class="art-title-text">{title}</div></div>'
    else:
        poster_html = '<div class="poster"><div class="poster-placeholder-mark">iCINEMA</div></div>'

    year_html = f'<div class="poster-caption-year">{year}</div>' if year else ''
    # Key art that already shows the title gets no text title (like streaming apps); others keep it.
    art_has_title = bool(logo_url) or landscape or (bool(poster_url) and str(poster_url).endswith("#titled"))
    title_html = "" if art_has_title else f'<div class="poster-caption-title" title="{title}">{title}</div>'
    
    if library_mode == "saved":
        caption_class = "poster-caption library-poster-caption saved-poster-caption"
    elif library_mode == "seen":
        caption_class = "poster-caption library-poster-caption seen-poster-caption"
    else:
        caption_class = 'poster-caption library-poster-caption' if compact else 'poster-caption'
    if return_html:      # the caller puts the art in the same block as the card's text (one block, even spacing)
        return poster_html
    if toggle_id:
        poster_html = f'<label class="art-toggle" for="{toggle_id}" aria-label="Show the story">{poster_html}</label>'
    st.markdown(
        poster_html
        + f'<div class="{caption_class}{" art-titled" if art_has_title else ""}">{title_html}{year_html}</div>',
        unsafe_allow_html=True
    )

def current_profile():
    """The viewer's profile, rebuilt only when something it depends on changed (not once per card)."""
    ss = st.session_state
    sig = (tuple(sorted(ss.likes)), tuple(sorted(ss.favorites)), tuple(ss.genres), ss.review_priority,
           tuple(ss.more_of), len(ss.saved), len(ss.dismissed), ss.adventure, len(ss.seen),
           len(ss.get("disliked") or ()), len(ss.external_movies), len(ss.get("analytics_events") or ()))
    memo = ss.get("_profile_memo")
    if memo and memo[0] == sig:
        return memo[1]
    prof = _build_current_profile()
    ss._profile_memo = (sig, prof)
    return prof


def _build_current_profile():
    return build_profile(
        st.session_state.likes, st.session_state.favorites, st.session_state.genres,
        st.session_state.review_priority, st.session_state.more_of,
        st.session_state.saved, st.session_state.dismissed, st.session_state.adventure,
        st.session_state.external_movies, st.session_state.seen,
        disliked_titles=st.session_state.get("disliked") or set(),
    )

def _cf_signals():
    """Collect browser-local actions for the MovieLens-pretrained CF layer."""
    ext = st.session_state.external_movies
    out = []
    for t in st.session_state.likes:
        m = get_movie(t, ext)
        if m: out.append((m, "favorite" if t in st.session_state.favorites else "like"))
    rated = st.session_state.get("seen_rating") or {}
    cutoff = st.session_state.get("taste_reset_at")
    last_act = {}
    if cutoff:
        for e in st.session_state.get("analytics_events") or []:
            last_act[e.get("title")] = max(last_act.get(e.get("title"), 0), float(e.get("timestamp") or 0))
    for key, action in (("saved", "save"), ("seen", "seen"), ("dismissed", "skip"), ("disliked", "dislike")):
        for t in st.session_state.get(key) or set():
            m = get_movie(t, ext)
            if not m:
                continue
            if cutoff and key != "disliked" and last_act.get(t, 0) < float(cutoff):
                continue   # "My taste changed": older saves, Seen and skips stop shaping picks
            if key == "seen" and rated.get(t) in (1, -1):
                action = "like" if rated[t] == 1 else "dislike"   # a rated Seen is a real signal
            elif key == "seen" and t in (st.session_state.get("seen_from_saved") or set()):
                action = "save"    # saved, then watched: it keeps the positive signal it had in Saved
            out.append((m, action))
    for key, action in (("imported_seen", "seen"), ("imported_disliked", "dislike")):
        for t in st.session_state.get(key) or set():   # only filled if that signal passed its test
            if t in st.session_state.likes:
                continue
            m = get_movie(t, ext)
            if m:
                out.append((m, action))
    return out


def _set_opt_out():
    st.session_state.analytics_opt_out = not st.session_state.get("_share_counts", True)
    queue_profile_save()


def taste_changed():
    """Keep your likes, favorites and "Not for me"s; older saves, Seen and skips stop counting."""
    import time as _t
    st.session_state.taste_reset_at = _t.time()
    queue_profile_save()


def taste_undo():
    st.session_state.taste_reset_at = None
    queue_profile_save()


def lately_genres(limit=3):
    """Genres of what you saved or loved most recently (last 10), for the Profile."""
    ext = st.session_state.external_movies
    recent = [e.get("title") for e in reversed(st.session_state.get("analytics_events") or [])
              if e.get("event") == "save"][:10]
    recent += [t for t, v in (st.session_state.get("seen_rating") or {}).items() if v == 1][:5]
    from collections import Counter
    c = Counter(g for t in recent if (m := get_movie(t, ext)) and (g := m.get("genre")))
    return [g for g, _ in c.most_common(limit)]


def rate_seen(title, value):
    """Thumbs on a Seen movie: tap again to clear."""
    rated = dict(st.session_state.get("seen_rating") or {})
    rated[title] = 0 if rated.get(title) == value else value
    rated = {k: v for k, v in rated.items() if v}
    st.session_state.seen_rating = rated
    _lib_bump()
    queue_profile_save()


from src.descriptions import card_description, expanded_card_description, quick_card_description, tonight_description  # card text rules (unit-tested)





def _format_seconds(value):
    if value is None:
        return "Learning"
    value=max(0,int(round(value)))
    if value<60:
        return f"{value}s"
    return f"{value//60}m {value%60:02d}s"


def cached_semantic_scores(movies, profile):
    """Content-model theme similarity, recomputed only when inputs change."""
    signals = tuple((s.get("title"), s.get("weight")) for s in (profile.get("semantic_signals") or []))
    titles = tuple(m.get("title") for m in movies)
    key = (signals, titles)
    cache = st.session_state.get("_semantic_cache")
    if cache and cache[0] == key:
        by_title = cache[1]
    else:
        scores = semantic_similarity_scores(movies, profile)
        by_title = {m.get("title"): scores.get(id(m), 0.5) for m in movies}
        st.session_state._semantic_cache = (key, by_title)
    return {id(m): by_title.get(m.get("title"), 0.5) for m in movies}


def _cached_insights(events):
    """Profile stats, recomputed only when a new event arrives (not on every rerun)."""
    labels = [e for e in events if e.get("event") != "impression"]
    key = (len(labels), float((labels[-1] if labels else {}).get("timestamp") or 0))
    memo = st.session_state.get("_insights_memo")
    if memo and memo[0] == key:
        return memo[1]
    out = analytics_insights(events)
    st.session_state._insights_memo = (key, out)
    return out


def learning_model_for(events):
    """Train the Save/Skip model only when feedback changed since the last run."""
    events = list(events or [])
    # Only choices change the model. Impressions arrive on every page view, so keying on all
    # events used to retrain it (gradient boosting included) on nearly every click.
    labels = [e for e in events if e.get("event") not in ("impression",)]
    signature = (len(labels), labels[-1].get("timestamp") if labels else None)
    cache = st.session_state.get("_learning_model_cache")
    if cache and cache[0] == signature:
        return cache[1]
    result = train_learning_model(events)
    st.session_state._learning_model_cache = (signature, result)
    return result


def _personal_need(learned, decisions):
    """What the personal model still needs: 50 decisions and at least 12 saves and 12 skips."""
    saves, skips = int(getattr(learned, "positives", 0) or 0), int(getattr(learned, "negatives", 0) or 0)
    n = int(getattr(learned, "samples", 0) or decisions)
    if n < 50:
        return f"{n} of 50 saves and skips"
    if saves < 12:
        return f"Needs 12 saves to start ({saves} so far). Skips alone can’t show what you like."
    if skips < 12:
        return f"Needs 12 skips to start ({skips} so far)."
    return "Starting with your next visit"


def training_scale():
    """Human-readable MovieLens training size, read from the results file when available."""
    data = load_offline_results() or {}
    def fmt(n, fallback):
        if isinstance(n, int):
            return f"{n / 1e6:.1f} million" if n >= 1_000_000 else f"{n:,}"
        return fallback
    return {
        "users": fmt(data.get("train_users"), None),
        "movies": fmt(data.get("train_movies"), None),
        "positives": fmt(data.get("train_positives"), None),
    }


def _tested_blend_weights():
    """Blend weights picked on held-out MovieLens viewers (training/evaluate_blends.py)."""
    try:
        d = json.loads((Path(__file__).resolve().parent / "data" / "blend_results.json").read_text())
        return float(d["content_blend"]["best_weight"]), float(d["whats_next"]["best_weight"])
    except Exception:
        return 0.65, 0.6


# Content vs "viewers like you" in every row, and similarity vs personal match in What's next.
CONTENT_WEIGHT, WHATS_NEXT_SIM = _tested_blend_weights()


@st.cache_data(show_spinner=False)
def load_offline_results():
    """MovieLens evaluation written by training/train_cf.py (data/cf_results.json)."""
    try:
        path = Path(__file__).resolve().parent / "data" / "cf_results.json"
        return json.loads(path.read_text())
    except Exception:
        return None


def render_cinema_profile(p, include_insights=False, show_heading=True, tab_heading=False):
    # Plain-language labels; "Your mix" drops lines that repeat "How you choose".
    matters_text = " ".join(p["matters"]).casefold()
    mix = [b for b in p["balance"] if not ("review" in b.casefold() and "review" in matters_text)]
    _n = int(p.get("movies_used") or 0)
    _early = (f'<span class="pf-empty">Like or save {3 - _n} more movie{"s" if 3 - _n != 1 else ""} to see your tone and patterns</span>'
              if _n < 3 else "")
    sections = [
        ("You enjoy" if p["traits"] else "Your tone", profile_chip_html(p["traits"]) or _early, "profile-chip-wrap"),
        ("Top genres", profile_chip_html(p["genres"]), "profile-chip-wrap"),
        ("How you choose", profile_chip_html(p["matters"]), "profile-chip-wrap"),
        ("Show me more", profile_chip_html(p["priorities"]), "profile-chip-wrap"),
        ("Your patterns", profile_chip_html(p["patterns"]), "profile-chip-wrap"),
        ("Your mix", profile_chip_html(mix), "profile-chip-wrap"),
    ]
    sections = [s for s in sections if s[1]]
    section_html = "".join(
        f'<div class="profile-block full"><div class="profile-label">{label}</div><div class="{wrapper_class}">{content}</div></div>'
        for label, content, wrapper_class in sections
    )
    events=list(st.session_state.get("analytics_events") or [])
    insights=_cached_insights(events)
    learned=learning_model_for(events)
    conf=profile_confidence_label(p)
    signals=sum((p.get("behavior_counts") or {}).values()) + len((p.get("controls") or {}).get("selected_genres",[]) or []) + len((p.get("controls") or {}).get("priorities",[]) or [])
    _bc = p.get("behavior_counts") or {}
    _ctl = p.get("controls") or {}
    _parts = [(_bc.get("liked", 0) + _bc.get("favorited", 0), "like"), (_bc.get("saved", 0), "save"),
              (_bc.get("seen", 0), "seen"), (_bc.get("skipped", 0), "skip"), (_bc.get("disliked", 0), "not for me"),
              (len(_ctl.get("selected_genres") or []), "genre pick"), (len(_ctl.get("priorities") or []), "row preference")]
    signal_parts = " · ".join(f"{n} {lbl}{'' if n == 1 or lbl in ('seen', 'not for me') else 's'}" for n, lbl in _parts if n)
    scale = training_scale()
    # What is actually running right now. Collaborative filtering and the content
    # model work from the first like; the personal model needs 50 Save/Skip labels.
    decisions = int(insights.get("saves") or 0) + int(insights.get("skips") or 0)
    if learned.ready:
        personal_html = (f'<div class="model-row"><span class="model-dot on"></span>'
                         f'<span class="model-name">Your personal model</span>'
                         f'<span class="model-note">Active · {html.escape(learned.model_name)} trained on {learned.samples} of your decisions</span></div>')
    else:
        pct = min(100, round(decisions / 50 * 100))
        personal_html = (f'<div class="model-row"><span class="model-dot"></span>'
                         f'<span class="model-name">Your personal model</span>'
                         f'<span class="model-note">{html.escape(_personal_need(learned, decisions))}</span>'
                         f'<span class="model-progress"><span style="width:{pct}%"></span></span></div>')
    # What's shaping your picks: each model, whether it's on, and its real share of the score.
    from src import cf_model as _cfm
    from src.new_releases import available as _nr_on
    from src.tv import available as _tv_on
    _sig = _cf_signals()
    _full_m, _ = _cfm._history_cut()
    _rk = _cfm._ranker_for(_sig) if _sig else None
    _cf_name = ("EASE (you’ve rated a lot)" if _full_m is not None and _rk is _full_m else
                "RP3beta (less mainstream likes)" if _rk is not None and _rk is _cfm._load_rank() and _rk is not _cfm._load() else
                "item-kNN")
    _p_share = 0.22 if learned.ready else 0.0
    _fans = round((1 - CONTENT_WEIGHT) * (1 - _p_share) * 100)
    _cont = round(CONTENT_WEIGHT * (1 - _p_share) * 100)
    _mood_on = bool(_mood_spec().get("mood"))
    _short_cf = _cf_name.split(" (")[0]
    _why_cf = {"EASE": "you’ve rated a lot, and EASE won the test for long histories",
               "RP3beta": "your likes are less mainstream, and RP3beta won that test",
               "item-kNN": "item-kNN won the benchmark from just a few likes"}.get(_short_cf, "")
    from src import ltr as _ltr_mod
    _ltr_on = _ltr_mod.available()
    _names = {"routed": _short_cf, "item_knn": "item-kNN", "rp3beta": "RP3beta", "ease": "EASE",
              "content": "content", "popularity": "popularity"}
    _shares = ", ".join(f"{_names.get(k, k)} {v:.0%}" for k, v in
                        sorted((_ltr_mod.result().get("feature_shares") or {}).items(), key=lambda kv: -kv[1]) if v > 0.005)
    # Each row: plain name, the technique underneath, its weight in your score, and its job.
    if _ltr_on:
        first = (True, "Best-of-all ranker", "Learned ranker · gradient boosting", f"{_fans}%",
                 "Combines the three fan models below, the content model, and popularity, weighted by what predicted 3,000 test viewers best.")
    else:
        first = (True, "Fans like you", f"Collaborative filtering · {_short_cf}", f"{_fans}%",
                 f"Finds {scale['users'] or 'MovieLens'} movie fans who loved what you loved.")
    _mq = _mood_spec()["mood"] if _mood_on else ""
    # The ranker's three fan models, shown on their own lines so every model doing work is visible.
    _fans_n = f"{scale['users']:,}" if isinstance(scale.get("users"), int) else (scale.get("users") or "MovieLens")
    _inside = ([(True, "  · Fans like you", "item-kNN", "", f"Movies the same {_fans_n} fans loved together."),
                (True, "  · Fans with less mainstream likes", "RP3beta", "", "A random-walk model that finds less obvious fan favorites."),
                (True, "  · Fans with long histories", "EASE", "", "Learns from viewers who rated many movies, for detailed profiles.")]
               if _ltr_on else [])
    items = [
        first,
        *_inside,
        (True, "What each movie is like", "Content model · TF-IDF + SVD", f"{_cont}%",
         "Matches your answers to each movie’s genres and fan tags."),
        (learned.ready, "Your own choices", f"Personal model · {(learned.model_name if learned.ready else 'logistic regression').lower()}",
         f"{round(_p_share * 100)}%" if learned.ready else "",
         "Trained on your saves and skips, and retrained after each new one." if learned.ready else _personal_need(learned, decisions)),
        (_nr_on(), "New releases", "Cold-start model · ridge regression", "",
         "Places brand-new movies by their director, cast, and studio."),
        (_tv_on(), "Shows", "TV model · item-kNN + popularity", "",
         "Finds shows loved by fans of your movies."),
        (_mood_on, "Mood search", "Fan-tag TF-IDF", "",
         (f"Using “{_mq[:30]}” right now." if _mq else "Off: your search is a title, not a mood.") if _mood_on
         else "Off until you type a mood in the Showroom."),
    ]
    _foot = "Weights were set in tests on movie fans the models never saw."
    if _ltr_on:
        _d = _ltr_mod.result() or {}
        if isinstance(_d.get("ndcg_learned"), (int, float)) and isinstance(_d.get("ndcg_current_blend"), (int, float)):
            _foot += (f" The ranker beat a fixed mix on those viewers "
                      f"(NDCG@10 {_d['ndcg_learned']:.3f} vs {_d['ndcg_current_blend']:.3f}).")
    models_html = (
        '<div class="pf-section"><div class="pf-title">What’s choosing your picks</div>'
        '<div class="pf-sub">A filled dot means running for you now. The percent is each model’s weight in your picks.</div>'
        '<div class="pf-models">'
        + "".join(f'<div class="pf-model"><span class="pf-dot{" on" if on else ""}"></span>'
                  f'<div class="pf-model-main"><div class="pf-model-name">{html.escape(name)}</div>'
                  f'<div class="pf-model-tech">{html.escape(tech)}</div></div>'
                  f'<div class="pf-model-share">{share}</div>'
                  f'<div class="pf-model-note">{html.escape(note)}</div></div>' for on, name, tech, share, note in items)
        + f'</div><div class="pf-foot">{html.escape(_foot)}</div></div>'
    )

    def _stat(value, title, note):
        return (f'<div class="insight-card"><div class="insight-value">{html.escape(str(value))}</div>'
                f'<div class="insight-title">{html.escape(title)}</div>'
                f'<div class="insight-label">{html.escape(note)}</div></div>')

    def _or_learning(key, fmt):
        v = insights.get(key)
        return "Learning" if v is None else fmt(v)

    insight_cards = [
        _stat(_format_seconds(insights.get("time_to_match_seconds")), "Time to your first save",
              "Typical visit, from opening iCinema to your first save."),
        _stat(_or_learning("avg_skips_before_save", lambda v: f"{v:.1f}"), "Skips before a save",
              "Lower means the first picks land."),
        _stat(_or_learning("saved_to_seen_rate", lambda v: f"{v*100:.0f}%"), "Saves you watched",
              "Saved movies you later marked Seen."),
        _stat(_or_learning("discovery_rate", lambda v: f"{v*100:.0f}%"), "Saves beyond Top Picks",
              "Found in More to explore or Shows for You."),
    ]
    # Only stats with real values; "Learning" placeholders repeated six times read as noise.
    insight_cards = [c for c in insight_cards if '>Learning<' not in c]
    insight_html = "".join(insight_cards)

    lm=learned.metrics or {}
    offline=load_offline_results()

    def _fmt(v, pct=False):
        if v is None:
            return "Learning"
        return f"{v*100:.0f}%" if pct else f"{v:.2f}"

    def _card(value, label):
        return (f'<div class="insight-card"><div class="insight-value">{html.escape(str(value))}</div>'
                f'<div class="insight-label">{html.escape(label)}</div></div>')

    scale = training_scale()
    # Consumer-facing: what it does and whether it works. Full detail lives in MODEL_CARD.md.
    proof_html = ""
    if offline:
        pop = (offline.get("full") or {}).get("popularity") or {}
        cf3 = (offline.get("three_likes") or {}).get("cf") or {}
        stored = offline.get("lifts_three_likes_vs_popularity") or {}
        def _lift(key):
            # Prefer the lift saved by training, so the app matches the README exactly.
            if isinstance(stored.get(key), (int, float)):
                return int(stored[key])
            a, b = cf3.get(key), pop.get(key)
            return round((a / b - 1) * 100) if a and b else None
        pick_lift, ndcg_lift, recall_lift = _lift("hit@1"), _lift("ndcg@10"), _lift("recall@10")
        users = offline.get("held_out_users")
        # Only claim significance the bootstrap actually found (read from the results file).
        sig = {b.get("metric"): bool(b.get("significant")) for b in offline.get("bootstrap_three_likes_vs_popularity") or []}
        if sig.get("Hit@1") and sig.get("Recall@10"):
            significance_note = "Both results are statistically significant (bootstrap test)."
        elif any(sig.values()):
            significance_note = "Some results are statistically significant; see the model card for details."
        else:
            significance_note = "See the model card for confidence intervals."
        cards = []
        if pick_lift is not None:
            cf_hit, pop_hit = cf3.get("hit@1"), pop.get("hit@1")
            hit_note = (f"Its one pick was a movie the viewer rated 4+ stars {cf_hit:.2%} of the time, vs. {pop_hit:.2%} for the most popular pick."
                        if isinstance(cf_hit, (int, float)) and isinstance(pop_hit, (int, float))
                        else "Its one pick is a movie you'll love more often than the most popular pick.")
            cards.append(_stat(f"+{pick_lift}%", "More hits for Tonight’s Show", hit_note))
        if ndcg_lift is not None and recall_lift is not None:
            lo, hi = sorted((ndcg_lift, recall_lift))
            cards.append(_stat(f"+{lo}–{hi}%", "Better Showroom rows",
                               f"More movies you’d love in the top 10 (+{recall_lift}%, Recall@10), ranked closer to the top (+{ndcg_lift}%, NDCG@10)."))
        hit_boot = next((b for b in offline.get("bootstrap_three_likes_vs_popularity") or []
                         if b.get("metric") == "Hit@1"), {})
        share = hit_boot.get("cf_win_share")
        if isinstance(share, (int, float)):
            # Share of bootstrap resamples where iCinema wins -> one-sided bootstrap p-value.
            n_win = int(round(share * 2000))
            cards.append(_stat(f"{n_win:,} / 2,000", "Not a fluke",
                               "Bootstrap resamples of the 3,000 test viewers in which iCinema beat the popularity pick."))
        full_note = (" It was chosen over SVD, implicit ALS, and EASE in a head-to-head benchmark on the same viewers, "
                     "and it does better than item-kNN for viewers with less mainstream likes.")
        if pick_lift is not None and isinstance(users, int):
            cf_hit, pop_hit = cf3.get("hit@1"), pop.get("hit@1")
            rows_part = (f", and its rows put {recall_lift}% more movies you’d love in the top 10"
                         if recall_lift is not None else "")
            hits_part = (f" ({cf_hit:.1%} vs {pop_hit:.1%})" if isinstance(cf_hit, (int, float)) and isinstance(pop_hit, (int, float)) else "")
            cards_p = [(f"+{pick_lift}%", "Better first pick",
                        f"Tonight’s Show vs. the most popular movie{hits_part}: share of test viewers who rated it 4+ stars.")]
            if recall_lift is not None:
                cards_p.append((f"+{recall_lift}%", "Better rows", "More 4+ star movies in each row’s top 10 than a most-popular list."))
            cards_p.append((f"{users:,}", "Test viewers", "Never seen by the models. Each started from just 3 likes."))
            proof_html = (
                '<div class="pf-subtitle">Tested before launch</div>'
                '<div class="pf-stats pf-proof">' + "".join(_stat(v, t, n) for v, t, n in cards_p) + '</div>'
                f'<div class="pf-foot">{html.escape(significance_note)}</div>'
            )

    live_html = ""
    if learned.ready:
        auc, n_test = lm.get("auc"), int(lm.get("test_samples") or 0)
        if isinstance(auc, (int, float)) and n_test >= 30:
            live_html = (f'<div class="pf-note">On your newest {n_test} choices, your own model predicted your saves '
                         f'well above chance (AUC {auc:.2f}).</div>')

    from src.new_releases import available as _nr_ready
    from src.mood import available as _mood_on
    from src.cf_model import _history_cut
    _ease_on = _history_cut()[0] is not None
    _fans = scale["users"] or "MovieLens"
    _n_movies = scale["movies"] or "thousands of"
    _personal_state = (f"Your own model is on, learned from {learned.samples} of your saves and skips."
                       if learned.ready else f"Your own model starts after 50 saves and skips ({min(decisions, 50)} so far).")
    steps = [
        ("Data", "What it learns from",
         f"Ratings from {_fans} movie fans, and the genres and fan tags of {_n_movies} movies"
         + (", plus director, cast, and studio for new releases." if _nr_ready() else "."),
         "MovieLens 32M · Wikidata · TMDB for posters only"),
        ("Models", "How it scores each movie",
         "Fan models find people who loved what you loved. A content model reads what each movie is like. "
         "A learned ranker weighs them, and after 50 choices your own model joins in.",
         "item-kNN · RP3beta · EASE · TF-IDF + SVD · gradient boosting · logistic regression"),
        ("Testing", "How it was checked",
         "Before launch, every model was scored on movie fans it had never seen, starting from just 3 likes each. "
         "A model only ships if it beats the simpler option.",
         "held-out viewers · NDCG@10 · Recall@10 · bootstrap significance"),
        ("Showroom", "What you see",
         "Each row has one job, there’s one movie per series, and “chance you’ll love it” is calibrated on test "
         "viewers and rounded down.",
         "calibration error under 1% · mood and time filters"),
    ]
    methodology_html = (
        '<div class="pf-section"><div class="pf-title">How iCinema works</div>'
        '<div class="pf-sub">From raw data to the four movies in each row.</div>'
        '<div class="pf-steps">'
        + "".join(f'<div class="pf-step"><div class="pf-step-n">{i}</div><div class="pf-step-body">'
                  f'<div class="pf-step-k">{html.escape(k)}</div><div class="pf-step-title">{html.escape(t)}</div>'
                  f'<div class="pf-step-copy">{html.escape(c)}</div><div class="pf-step-data">{html.escape(d)}</div></div></div>'
                  for i, (k, t, c, d) in enumerate(steps, 1))
        + '</div>'
        + f'{proof_html}{live_html}'
        + '<div class="pf-foot">IMDb and Rotten Tomatoes scores come from OMDb. Movies you pass over step back each visit, '
        'so new picks keep surfacing.</div></div>'
    )

    insights_section = (
        ('<div class="pf-section"><div class="pf-title">Your stats</div>'
         + (f'<div class="pf-stats">{insight_html}</div>' if insight_html else
            '<div class="pf-sub">They appear after your first few saves.</div>')
         + '</div>')
        + methodology_html
        if include_insights else ""
    )

    heading_class = "tab-primary-heading profile-heading-aligned" if tab_heading else "profile-heading"
    profile_heading_html = f'<div class="{heading_class}">Your Cinema Profile</div>' if show_heading else ""

    # A live readout of what the models are computing from: each onboarding step, then every choice since.
    _ss = st.session_state
    _g, _r = len(_ss.get("genres") or []), len(_ss.get("more_of") or [])
    # Counts match what the viewer sees: the Saved and Seen tabs, and movies skipped or marked Not for me.
    _dl = len(_ss.get("disliked") or ())
    _sv, _sn = len(_ss.get("saved") or ()), len(_ss.get("seen") or ())
    _sk = len(set(_ss.get("dismissed") or ()) - set(_ss.get("disliked") or ()))
    _lk = len(set(_ss.get("likes") or ()) | set(_ss.get("favorites") or ()))
    _inputs = [(_lk, "movie liked", "movies liked"), (_g, "genre", "genres"), (2, "slider", "sliders"),
               (_r, "row pick", "row picks"), (_sv, "saved", "saved"), (_sn, "seen", "seen"),
               (_sk, "skipped", "skipped"), (_dl, "not for me", "not for me")]
    _parts = [f"{n} {one if n == 1 else many}" for n, one, many in _inputs if n]
    _summary = (
        '<div class="pf-readout"><span class="pf-dot on"></span>'
        f'<span class="pf-readout-k">Computed from</span><span class="pf-readout-v">{html.escape(" · ".join(_parts))}</span></div>'
    ) if _parts else ""
    _page = (
        f'<div class="profile-wrap pf">'
        f'{profile_heading_html}{_summary}'
        f'{models_html}'
        f'<div class="pf-section"><div class="pf-title">What you like</div><div class="pf-taste">{section_html}</div></div>'
        f'{insights_section}'
        f'</div>'
    )
    st.markdown(re.sub(r"\s*\n\s*", " ", _page), unsafe_allow_html=True)



import functools as _functools


def _friendly_error(exc):
    """Log the real error for the server logs; show the viewer a calm message instead of a traceback."""
    if type(exc).__name__ in {"RerunException", "StopException"}:
        raise exc
    import sys
    import traceback
    print("iCinema error:", "".join(traceback.format_exception(exc)), file=sys.stderr, flush=True)
    st.markdown('<div class="friendly-error">This part didn’t load. Refresh the page to try again. '
                'Your picks, saves, and settings are kept.</div>', unsafe_allow_html=True)


def _with_app_rerun(fn):
    """Run a full-app rerun requested by a button callback (callbacks themselves can't)."""
    @_functools.wraps(fn)
    def inner(*args, **kwargs):
        if st.session_state.pop("_app_rerun", False):
            st.rerun(scope="app")
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            _friendly_error(exc)
    return inner


@st.fragment
@_with_app_rerun
def render_live_profile():
    """Profile tab, refreshed every few seconds.

    Showroom cards rerun on their own (so Skip/Save stay fast), which used to leave this
    tab showing counts from when the Showroom was built. Rebuilding it from current state
    keeps the signals and the "x of 50" progress matching what you just did.
    """
    st.button("Refresh", key="refresh_profile")     # hidden; clicked when the Profile tab opens and is out of date
    _ver_mark(3)
    render_cinema_profile(current_profile(), include_insights=True, show_heading=True, tab_heading=True)


@st.fragment
@_with_app_rerun
def render_shelf_fragment():
    logo()
    st.markdown(
        '<div class="page-top-heading">Step 1 of 3 — Rate the Shelf</div>'
        '<div class="page-top-subtitle">Choose a few titles you already like. Skip any you don’t know, or search for one you enjoy.</div>',
        unsafe_allow_html=True,
    )

    ensure_rotating_shelf()
    shelf_movies = list(st.session_state.shelf_movies)
    missing_posters = tuple(
        (m["title"], int(m.get("year") or 0))
        for m in shelf_movies if not m.get("poster_url")
    )
    shelf_poster_map = get_poster_batch(missing_posters) if missing_posters else {}
    # Landscape key art fits the short shelf cards without cropping; posters are the fallback.
    shelf_landscape_map = get_landscape_batch(tuple(
        (m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in shelf_movies
    ))
    shelf_box = st.container(key="step1_shelf")
    cols=shelf_box.columns(5, gap="small")
    for i,movie in enumerate(shelf_movies):
        title=movie["title"]
        with cols[i%5]:
            with st.container(key=f"shelf_card_{i}"):
                # Skip is a small × on the artwork, so each card has just two actions underneath.
                st.button(
                    "×",
                    key=f"shelfskip_{i}_{movie.get('tmdb_id') or title}",
                    help="Haven’t seen it? Show another.",
                    on_click=skip_shelf_movie,
                    args=(i,),
                )
                movie_thumb(movie, shelf_landscape_map.get(title) or movie.get("poster_url") or shelf_poster_map.get(title))
                b1,b2=st.columns(2, gap="small")
                with b1:
                    st.button(
                        "Like",
                        key=f"like_{i}_{movie.get('tmdb_id') or title}",
                        use_container_width=True,
                        on_click=rate_shelf_movie,
                        args=(movie, "like", i),
                    )
                with b2:
                    st.button(
                        "Favorite",
                        key=f"fav_{i}_{movie.get('tmdb_id') or title}",
                        use_container_width=True,
                        on_click=rate_shelf_movie,
                        args=(movie, "favorite", i),
                    )

    with st.container(key="step1_search"):
        st.markdown(
            '<div class="search-shell">'
            '<div class="search-shell-title">Don’t see one you like?</div>'
            '<div class="search-shell-copy">Search for a movie you already enjoy.</div>'
            '</div>',
            unsafe_allow_html=True
        )

        search_query = live_search_box()

        matches = []
        already_selected_matches = []
        did_you_mean = False
        if search_query.strip():
            from src.cf_model import fan_percentile, fuzzy_titles
            from src.search_rank import rerank
            if tmdb_catalog_configured():
                matches = search_movies(search_query.strip(), 20)
            else:
                q = search_query.strip().lower()
                local_titles = [title for title in searchable_titles() if q in title.lower()][:20]
                matches = [get_movie(title) for title in local_titles if get_movie(title)]
            # Exact titles first, best-known breaks ties (search_rank.py); a typo falls back to close spellings.
            matches = rerank(search_query, matches, known=lambda m: fan_percentile(m) is not None)[:12]
            if not matches:
                matches = fuzzy_titles(search_query)
                did_you_mean = bool(matches)

            selected_titles = st.session_state.likes | st.session_state.favorites
            already_selected_matches = [m for m in matches if m["title"] in selected_titles]
            matches = [m for m in matches if m["title"] not in selected_titles]

        selected_movie = st.session_state.search_selected_movie
        valid_ids = {m.get("tmdb_id") for m in matches if m.get("tmdb_id") is not None}
        valid_titles = {m["title"] for m in matches}
        if selected_movie:
            selected_valid = (selected_movie.get("tmdb_id") in valid_ids) if selected_movie.get("tmdb_id") is not None else (selected_movie.get("title") in valid_titles)
            if not selected_valid:
                st.session_state.search_selected_movie = None
                st.session_state.search_selected_title = None

        if search_query.strip():
            if matches:
                st.markdown(f'<div class="search-results-label">{"Did you mean" if did_you_mean else "Matching titles"}</div>', unsafe_allow_html=True)
                result_cols = st.columns(2)
                for j, movie in enumerate(matches):
                    title = movie["title"]
                    year_label = f" ({movie['year']})" if movie.get("year") else ""
                    selected_movie = st.session_state.search_selected_movie
                    selected = bool(selected_movie and selected_movie.get("tmdb_id") == movie.get("tmdb_id") and movie.get("tmdb_id") is not None)
                    with result_cols[j % 2]:
                        st.button(
                            f"{title}{year_label}",
                            key=f"search_result_{j}_{movie.get('tmdb_id') or title}",
                            type="primary" if selected else "secondary",
                            use_container_width=True,
                            on_click=select_search_result,
                            args=(movie,),
                        )

            if already_selected_matches:
                selected_name = already_selected_matches[0]["title"]
                state = "Favorite" if selected_name in st.session_state.favorites else "Liked"
                st.markdown(
                    f'<div class="search-already-selected">'
                    f'<strong>{html.escape(selected_name)}</strong> is already in your selections as {state.lower()}'
                    f'</div>',
                    unsafe_allow_html=True
                )

            if not matches and not already_selected_matches:
                if tmdb_catalog_configured():
                    st.caption("No matches yet. Try another spelling or a shorter title.")
                else:
                    st.caption("Search is offline for a moment, so these matches come from iCinema’s own catalog.")

        choice_movie = st.session_state.search_selected_movie
        if choice_movie:
            choice = choice_movie["title"]
            st.markdown(
                f'<div class="search-selected-card">'
                f'<div class="search-selected-kicker">Selected title</div>'
                f'<div class="search-selected-title">{html.escape(choice)}{html.escape(" (" + str(choice_movie.get("year")) + ")") if choice_movie.get("year") else ""}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            preview_cols = st.columns([1, 3])
            with preview_cols[0]:
                movie_thumb(choice_movie)
            with preview_cols[1]:
                a,b=st.columns([1,1])
                with a:
                    st.button(
                        "Add as Like",
                        key="search_add_like",
                        use_container_width=True,
                        on_click=add_search_choice,
                        args=("like",),
                    )
                with b:
                    st.button(
                        "Add as Favorite",
                        key="search_add_favorite",
                        use_container_width=True,
                        on_click=add_search_choice,
                        args=("favorite",),
                    )

    with st.container(key="step1_letterboxd"):
        # Optional, so it stays one quiet line under search (progressive disclosure): no new box or button.
        with st.expander("Or import your ratings from Letterboxd or IMDb"):
            st.caption("Upload the ZIP from Letterboxd or the ratings file from IMDb. Your file stays in this browser.")
            st.file_uploader("Letterboxd export (ZIP or ratings.csv) or IMDb ratings.csv", type=["zip", "csv"], key="lb_upload",
                             label_visibility="collapsed", on_change=import_letterboxd)
        _imp = st.session_state.get("import_summary")
        _n_imp = len(st.session_state.get("imported_titles") or set())
        if _imp and _imp.get("error"):
            st.caption("That file couldn’t be read. Upload the ZIP from Letterboxd, its ratings.csv, or IMDb’s ratings export.")
        elif _n_imp:
            note = f"{_n_imp} loved movie{'s' if _n_imp != 1 else ''} imported"
            if _imp and _imp.get("not_found"):
                note += f" ({_imp['not_found']} couldn’t be matched)"
            c1, c2 = st.columns([5, 1], gap="small")
            with c1:
                st.caption(note)
            with c2:
                st.button("Undo Import", key="undo_import", on_click=undo_letterboxd_import, use_container_width=True)

    with st.container(key="step1_selections"):
        _selected_set = st.session_state.likes | st.session_state.favorites
        _imported = set(st.session_state.get("imported_titles") or set())
        chosen_titles = [t for t in st.session_state.get("selection_order", []) if t in _selected_set and t not in _imported]
        chosen_titles += sorted(_selected_set - set(chosen_titles) - _imported)
        chosen_count = len(_selected_set)

        if chosen_titles:
            st.markdown(
                '<div class="selection-area-heading">'
                '<div class="selection-heading">Your selections</div>'
                '</div>',
                unsafe_allow_html=True,
            )

            # Keep the familiar compact chip layout while making every item removable.
            selection_cols = st.columns(min(4, len(chosen_titles)), gap="small")
            for idx, title in enumerate(chosen_titles):
                state = "Favorite" if title in st.session_state.favorites else "Liked"
                with selection_cols[idx % len(selection_cols)]:
                    with st.container(key=f"selection_card_{idx}"):
                        st.markdown(
                            f'<div class="selection-card-copy">'
                            f'<div class="selection-title">{html.escape(title)}</div>'
                            f'<div class="selection-state">{html.escape(state)}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        st.button(
                            "×",
                            key=f"remove_selection_{idx}",
                            help=f"Remove {title}",
                            on_click=remove_step1_selection,
                            args=(title,),
                        )

        st.caption(f"{chosen_count} title{'s' if chosen_count!=1 else ''} selected")
    with st.container(key="nav_row_rate"):
        cont, _ = st.columns([1.25, 6], gap="small")
        with cont:
            st.button("Continue →", type="primary", disabled=chosen_count==0, key="continue_rate", use_container_width=True, on_click=go_from_fragment, args=("taste",))


    persist_from_fragment()

@st.fragment
@_with_app_rerun
def render_taste_fragment():
    logo()
    st.markdown(
        '<div class="step2-header">'
        '<div class="step2-title">Step 2 of 3 — Tailor Your Preferences</div>'
        '<div class="step2-subtitle">Choose what matters most when you pick something to watch.</div>'
        '</div>'
        '<div class="step2-question">Which matters more?</div>',
        unsafe_allow_html=True,
    )

    review_scale_map = [15, 32, 50, 68, 85]
    review_idx = min(range(5), key=lambda i: abs(review_scale_map[i] - st.session_state.review_priority))

    review_label = [
        "Leaning strongly toward reviews",
        "Leaning toward reviews",
        "Balanced",
        "Leaning toward entertainment",
        "Leaning strongly toward entertainment",
    ][review_idx]

    st.markdown(
        '<div class="pref-scale-wrap">'
        '<div class="pref-scale-ends"><span>Great reviews</span><span>Easy to enjoy</span></div>'
        '</div>',
        unsafe_allow_html=True
    )

    review_button_labels = ["Reviews first", "Lean reviews", "Balanced", "Lean enjoyment", "Enjoyment first"]
    st.markdown('<div class="pref-scale-clicks">', unsafe_allow_html=True)
    review_cols = st.columns(5, gap="small")
    for i, value in enumerate(review_scale_map):
        with review_cols[i]:
            st.button(
                review_button_labels[i],
                key=f"review_scale_{i}",
                type="primary" if i == review_idx else "secondary",
                use_container_width=True,
                on_click=set_review_priority,
                args=(value,),
            )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="step2-question step2-question-next">What do you like to watch?</div>', unsafe_allow_html=True)
    st.markdown('<div class="genre-helper">Select up to five genres.</div>', unsafe_allow_html=True)
    selected=set(st.session_state.genres)
    genre_cols=st.columns(7, gap="small")
    for i,genre in enumerate(GENRES):
        with genre_cols[i%7]:
            active=genre in selected
            st.button(
                genre,
                key=f"genre_{i}",
                type="primary" if active else "secondary",
                use_container_width=True,
                on_click=toggle_genre_choice,
                args=(genre,),
            )

    st.markdown('<div class="step2-question step2-question-next">How open are you to something different?</div>', unsafe_allow_html=True)

    adventure_scale_map = [15, 32, 50, 68, 85]
    adventure_idx = min(range(5), key=lambda i: abs(adventure_scale_map[i] - st.session_state.adventure))

    adventure_label = [
        "Stay very close to what I like",
        "Stay mostly familiar",
        "Balanced",
        "Explore a little more",
        "Show me something different",
    ][adventure_idx]

    st.markdown(
        '<div class="pref-scale-wrap">'
        '<div class="pref-scale-ends"><span>Stay close to what I like</span><span>Show me something different</span></div>'
        '</div>',
        unsafe_allow_html=True
    )

    adventure_button_labels = ["Very familiar", "Mostly familiar", "Balanced", "More discovery", "Very different"]
    st.markdown('<div class="pref-scale-clicks">', unsafe_allow_html=True)
    adventure_cols = st.columns(5, gap="small")
    for i, value in enumerate(adventure_scale_map):
        with adventure_cols[i]:
            st.button(
                adventure_button_labels[i],
                key=f"adventure_scale_{i}",
                type="primary" if i == adventure_idx else "secondary",
                use_container_width=True,
                on_click=set_adventure_level,
                args=(value,),
            )
    with st.container(key="nav_row_taste"):
        back, cont, _ = st.columns([1, 1.25, 5], gap="small")
        with back:
            st.button("← Back", key="back_taste", use_container_width=True, on_click=go_from_fragment, args=("shelf",))
        with cont:
            st.button("Continue →", type="primary", key="continue_taste", use_container_width=True, on_click=go_from_fragment, args=("more",))


    persist_from_fragment()

@st.fragment
@_with_app_rerun
def render_more_fragment():
    logo()
    st.markdown(
        '<div class="page-top-heading">Step 3 of 3 — Shape Your Showroom</div>'
        '<div class="page-top-subtitle step3-subtitle">What should iCinema lean toward? Choose any you’d like to see more often.</div>',
        unsafe_allow_html=True,
    )

    descriptions = {
        "Hidden Gems": "Less-known titles that still fit what you like",
        "Critically Acclaimed": "Rotten Tomatoes 75%+ and IMDb 7.5+",
        "Recent Releases": "Newer films and recent additions",
        "International Films": "Stories and filmmakers from around the world",
        "Classics": "Established favorites across earlier eras",
        "Documentaries": "Nonfiction stories matched to your interests",
    }

    selected = set(st.session_state.more_of)
    left, right = st.columns(2, gap="large")

    for i, option in enumerate(MORE_OF_OPTIONS):
        with (left if i % 2 == 0 else right):
            active = option in selected
            st.button(
                f"**{option}**  \n{descriptions[option]}",
                key=f"priority_card_{'active_' if active else ''}{i}",
                use_container_width=True,
                type="secondary",
                on_click=toggle_priority_choice,
                args=(option,),
            )

    st.session_state.more_of = list(selected)

    with st.container(key="nav_row_more"):
        back, cont, _ = st.columns([1, 2.2, 4], gap="small")
        with back:
            st.button("← Back", key="back_more", use_container_width=True, on_click=go_from_fragment, args=("taste",))
        with cont:
            st.button("Build My Cinema Profile →", type="primary", key="build_profile", use_container_width=True, on_click=go_from_fragment, args=("profile",))

    # Step 3 selections are queued in session state and persisted on the page-level
    # transition to Profile. Avoid rendering the localStorage bridge inside this
    # fragment, which could briefly surface as a dark strip after a card click.


# The fourth Showroom row follows your Step 3 picks that have no row of their own;
# with none picked it stays Something Different. Always four rows at most.
_THIS_YEAR = __import__("datetime").date.today().year
ADAPTIVE_ROWS = {
    "Recent Releases for You": lambda m: int(m.get("year") or 0) >= _THIS_YEAR - 2,
    "Classics for You": lambda m: 0 < int(m.get("year") or 0) <= 1995,
    "Documentaries for You": lambda m: m.get("genre") == "Documentary" or "Documentary" in (m.get("tags") or []),
    "International Films for You": lambda m: str(m.get("original_language") or "en").lower() not in ("", "en"),
}
ADAPTIVE_NOTES = {
    "Recent Releases for You": "From the last two years, ranked for you",
    "Classics for You": "Older favorites that match what you like",
    "Documentaries for You": "Nonfiction picked for you",
    "International Films for You": "Films from around the world that match what you like",
}
_ADAPTIVE_FROM_STEP3 = {"Recent Releases": "Recent Releases for You", "Classics": "Classics for You",
                        "Documentaries": "Documentaries for You", "International Films": "International Films for You"}


def _title_of(item):
    """Row entries are (match, movie) pairs on a full build; after a Save they can be placeholders."""
    if isinstance(item, (tuple, list)) and len(item) == 2 and isinstance(item[1], dict):
        return item[1].get("title")
    if isinstance(item, dict):
        return item.get("title")
    return None


def _new_picks_note(choices):
    """'3 new picks since your last visit' for returning viewers; otherwise the usual note."""
    import time as _t
    prev, shown = st.session_state.get("prev_visit"), set(st.session_state.get("prev_shown") or [])
    titles = [t for t in (_title_of(c) for c in (choices or [])) if t]
    fresh = [t for t in titles if t not in shown]
    if prev and shown and _t.time() - float(prev) > 6 * 3600 and fresh:
        n = len(fresh)
        return f"{n} new pick{'s' if n != 1 else ''} since your last visit"
    return "Your best fits right now"


def _remember_shown(row_choices):
    import time as _t
    shown = [t for name in (row_choices or {}) for t in (_title_of(c) for c in (row_choices[name] or [])) if t]
    if shown:
        st.session_state.last_shown = shown[:40]
    st.session_state.last_visit = _t.time()


def fourth_row_name():
    for pick in st.session_state.get("more_of") or []:
        if pick in _ADAPTIVE_FROM_STEP3:
            return _ADAPTIVE_FROM_STEP3[pick]
    return "Something Different"


def _interleave_session():
    """Random ID for this visit's live test. A new Showroom visit gets a new one."""
    sid = st.session_state.get("showroom_session_id")
    if st.session_state.get("_il_for") != sid or not st.session_state.get("_il_session"):
        import uuid
        st.session_state._il_for = sid
        st.session_state._il_session = uuid.uuid4().hex[:12]
    return st.session_state._il_session


def _interleave_fields(row_name, title):
    """Team and visit ID for a Top Matches card during the live test, else nothing."""
    team = (st.session_state.get("interleave_teams") or {}).get(title)
    if row_name != "Top Matches for You" or not team:
        return {}
    return {"il_team": team, "il_session": _interleave_session()}


def live_test_line():
    """One plain line about the live interleaving test, read from data/interleave_results.json."""
    try:
        r = json.loads((Path(__file__).resolve().parent / "data" / "interleave_results.json").read_text())
    except Exception:
        return None
    target = int(r.get("target_decided_visits") or TARGET_DECIDED)
    if r.get("status") != "finished":
        return (f"Live test running: {int(r.get('decided_visits') or 0)} of {target}. For viewers with less mainstream likes, "
                "Top Matches mixes picks from two ranking methods and counts which one gets more saves.")
    if not r.get("significant"):
        return f"Live test finished ({target} visits): no detectable difference between the two ranking methods."
    lead = "the less-mainstream method" if r.get("leader") == "routed" else "the standard method"
    return f"Live test finished ({target} visits): {lead} won {max(r['routed_wins'], r['knn_wins'])} of {target}."


from src.dedupe import MAKING_OF as _MAKING_OF, franchise as _franchise


def _clean_ranked(ranked, excluded):
    """Drop anything the viewer already chose under another title, duplicate copies of one movie,
    and making-of specials. Liked "Star Wars: Episode IV - A New Hope" also blocks TMDB's "Star Wars"."""
    from src.cf_model import _index as _cf_index
    ext = st.session_state.external_movies
    blk_t, blk_c = set(), set()
    for t in excluded:
        m = get_movie(t, ext) or {"title": t}
        if int(m.get("tmdb_id") or 0):
            blk_t.add(int(m["tmdb_id"]))
        c = _cf_index(m)
        if c is not None:
            blk_c.add(c)
    seen_t, seen_c, out = set(), set(), []
    for item in ranked:
        m = item[1]
        tid, c = int(m.get("tmdb_id") or 0), _cf_index(m)
        if (tid and (tid in blk_t or tid in seen_t)) or (c is not None and (c in blk_c or c in seen_c)):
            continue
        if _MAKING_OF.search(str(m.get("title", ""))):
            continue
        if tid:
            seen_t.add(tid)
        if c is not None:
            seen_c.add(c)
        out.append(item)
    return out














def _mood_text():
    """The mood search the viewer applied. It stays until they clear it, across pages and visits."""
    return " ".join(str(st.session_state.get("mood_active") or "").split())


def _apply_mood():
    """Enter in the search field: the typed words become the active search, tidied the way a person
    would read it back: typos in mood words fixed ("dakr" -> "dark"), chat words dropped ("I want a"),
    and "I haven't seen yet" understood (every pick is already something you haven't marked Seen)."""
    from src.ui.mood_time import parse, compose
    raw = " ".join(str(st.session_state.get("mood_input") or "").split())[:120]
    spec = parse(raw)
    try:
        from src.mood import correct
        mood = correct(spec["mood"]) if spec["mood"] else ""
    except Exception:
        mood = spec["mood"]
    like = spec.get("like")
    if raw and mood and not like:
        hit = _lookup_title(mood)
        if hit:
            mood = hit["title"]          # a title search keeps the title as typed-and-found ("Hokum")
    tidy = compose(mood, spec["max"], spec["min"], spec["episodes"], like) if raw else ""
    st.session_state.mood_active = tidy
    st.session_state.mood_input = tidy
    queue_profile_save()


def _set_mood(text):
    """Chip ×, Clear, or an edit: rewrite the active mood and the field together."""
    text = " ".join(str(text or "").split())[:120]
    st.session_state.mood_active = text
    st.session_state.mood_input = text
    queue_profile_save()


def _lookup_title(words):
    """The movie a search names when its words aren't moods ("Hokum", "The Prestige"), else None.
    Remembered per query, so the lookup never repeats on every tap."""
    from src.mood import is_mood_word
    q = " ".join(str(words or "").split())
    if not q or all(is_mood_word(w) for w in q.split()):
        return None
    memo = dict(st.session_state.get("_lookup_memo") or {})
    if q.casefold() not in memo:
        memo[q.casefold()] = _strong_title(q)
        st.session_state._lookup_memo = memo
    return memo[q.casefold()]


def _mood_spec():
    """The search field split into a mood (for the mood model), a time limit (a runtime filter), and a
    movie: "like X" (reshape the Showroom around X) or a plain title (find it, plus one row like it)."""
    from src.ui.mood_time import parse
    spec = parse(_mood_text())
    spec["lookup"] = False
    if spec.get("mood") and not spec.get("like"):
        hit = _lookup_title(spec["mood"])
        if hit:
            spec.update(like=hit["title"], mood="", lookup=True)
    return spec


def _time_filter(items, spec, cap=80):
    """Keep (match, movie) items whose runtime fits the time limit; the models' order is unchanged."""
    from src.ui.mood_time import fits
    if not (spec.get("max") or spec.get("min")) or not items:
        return items
    head = items[:cap]
    ids = get_movie_identity_batch(tuple((m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for _, m in head))
    return [it for it in head if fits((ids.get(it[1]["title"]) or {}).get("runtime"), spec)]


def mood_reason(movie):
    """'Fits your mood' when this movie is among the closest 10% to the words, else None."""
    from src.mood import scores
    from src.cf_model import _index
    q = _mood_spec()["mood"]
    sc = scores(q) if q else None
    i = _index(movie) if sc is not None else None
    import numpy as np
    if i is None or sc[i] <= 0 or sc[i] < float(np.quantile(sc[sc > 0], 0.9)):
        return None
    return {"label": "Fits your mood", "text": f"Fans describe it the way you did: “{q[:40]}”."}


def _like_source():
    """The movie behind "like X" in the search, resolved once: catalog, then the viewer's own titles, then TMDB."""
    q = (_mood_spec().get("like") or "").strip()
    if not q:
        return None
    memo = dict(st.session_state.get("_like_memo") or {})
    if q.casefold() in memo:
        return memo[q.casefold()]
    ext = st.session_state.external_movies
    found = get_movie(q, ext)
    if not found:
        pool = list(CATALOG) + list(ext.values())
        qq = q.casefold()
        hits = [m for m in pool if qq in str(m.get("title", "")).casefold()]
        found = min(hits, key=lambda m: len(str(m.get("title", "")))) if hits else None
    if not found:
        try:
            from src.cf_model import fuzzy_titles
            close = fuzzy_titles(q, n=1, cutoff=0.85)   # a typo in the title ("se7ven") still finds the movie
            found = close[0] if close else None
        except Exception:
            found = None
    if not found and tmdb_catalog_configured():
        try:
            res = search_movies(q, 1)
            found = res[0] if res else None
        except Exception:
            found = None
    memo[q.casefold()] = found
    st.session_state._like_memo = memo
    return found


def _strong_title(q):
    """The movie a short query clearly names, or None. Only near-exact names count, so a mood never
    turns into a random title."""
    import difflib
    q = " ".join(str(q).split())
    if not q or len(q) > 60:
        return None
    m = get_movie(q, st.session_state.external_movies)
    if m:
        return m
    pool = list(CATALOG) + list(st.session_state.external_movies.values())
    exact = [x for x in pool if str(x.get("title", "")).casefold() == q.casefold()]
    if exact:
        return exact[0]
    if tmdb_catalog_configured():
        try:
            res = search_movies(q, 3) or []
        except Exception:
            res = []
        for r in res:
            t = str(r.get("title", ""))
            if difflib.SequenceMatcher(None, t.casefold(), q.casefold()).ratio() >= 0.85:
                return r
    return None


def render_search_card():
    """The movie your search names, drawn exactly like a Top Picks card (art, fit, year · genres ·
    minutes, ratings, where to stream, tap the art for the story, Save / Seen), under a row title:
    "Top result" for a title search, "Based on" for "like X"."""
    src = _like_source()
    if not src:
        return
    title, year, tid = src.get("title", ""), int(src.get("year") or 0), int(src.get("tmdb_id") or 0)
    ident = (get_movie_identity_batch(((title, year, tid),)) or {}).get(title) or {}
    art = (get_landscape_batch(((title, year, tid),)) or {}).get(title) or ident.get("poster_url") or src.get("poster_url")
    live = (get_live_ratings_batch(((title, int(ident.get("year") or year), ident.get("imdb_id") or ""),)) or {}).get(title) or {}
    watch = (get_watch_availability_batch(((title, int(ident.get("year") or year)),), "US") or {}).get(title)
    runtime = int(ident.get("runtime") or src.get("runtime") or 0)
    movie = dict(src, overview=src.get("overview") or ident.get("overview"), tagline=ident.get("tagline"))
    meta = [str(ident.get("year") or year or ""), genre_pair(movie) or movie.get("genre") or "", f"{runtime} min" if runtime else ""]
    ratings = " · ".join(ratings_text(card_ratings(movie, live))) or "Ratings unavailable"
    fit = ""
    cf = cf_affinity(movie, user_vector(_cf_signals()))
    if isinstance(cf, float) and cf > 0.5:
        fit = f"Top {max(1, round((1 - (cf - 0.5) * 2) * 100))}% for you"
    lookup = _mood_spec().get("lookup")
    note = ("The movie you searched for" if lookup else "The movie your search is built around")
    st.markdown('<div class="showroom-row showroom-row-header"><div class="showroom-row-title">'
                f'{"Top result" if lookup else "Based on"}</div><div class="row-model-note">{note}</div></div>',
                unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]:
        if fit:
            st.markdown(f'<div class="search-fit-pill">{html.escape(fit)}</div>', unsafe_allow_html=True)
        art_html = movie_thumb(dict(movie, year=""), art, landscape=True, return_html=True)
        st.markdown(card_html("search-premise", art_html, ident.get("display_title") or title, movie, ident,
                              f'<div class="poster-caption-year card-year">{meta_html([x for x in meta if x])}</div>'
                              f'<div class="ratings">{html.escape(ratings)}</div>'
                              f'<div class="watch-availability">{watch_line_html(watch, title, st.session_state.get("streaming_services"))}</div>'),
                    unsafe_allow_html=True)
        state = "Saved" if title in st.session_state.saved else "Seen" if title in st.session_state.seen else ""
        with st.container(key="movie_actions_search"):
            if state:
                st.markdown(f'<div class="search-state">In {state}</div>', unsafe_allow_html=True)
            else:
                a, b = st.columns(2, gap="small")
                with a:
                    st.button("Save", key="search_card_save", use_container_width=True, on_click=save_movie, args=(title, movie))
                with b:
                    st.button("Seen", key="search_card_seen", use_container_width=True, on_click=mark_movie_seen, args=(title, movie))


def _like_sims(source):
    """How close every known movie is to `source`, once per search: {catalog index: 0-1}.
    Known movies use the fans-like-you neighbors; a new release fans haven't rated yet uses the
    new-release model's placement (director, cast, studio) to find its closest known movies."""
    key = (str(source.get("title")), int(source.get("tmdb_id") or 0))
    memo = st.session_state.get("_like_sims_memo")
    if memo and memo[0] == key:
        return memo[1]
    from src.cf_model import neighbors as _nb, _index as _ix
    sims = {}
    if _ix(source) is not None:
        # Fans' 100 closest movies, re-ranked: half how strongly the same fans loved both, half how alike the
        # movies are (genres and fan tags), minus a light discount for the most popular titles. Fans alone
        # drift to famous crowd-pleasers; tags alone drift to oddities; together they stay on target.
        import numpy as _np
        from src import content_model as _cm
        from src.cf_model import _load as _cfl
        i = _ix(source)
        near = _nb(source, 100)
        fan_rank = 1 - _np.arange(len(near)) / max(len(near), 1)
        vecs, pop = _cm._load(), _cfl().fan_pct
        if vecs is not None and len(near):
            E, has = vecs
            v = E[i]
            if has[i] and float(_np.linalg.norm(v)) > 0:
                cos = (E[near] @ v) / _np.maximum(_np.linalg.norm(E[near], axis=1) * _np.linalg.norm(v), 1e-9)
                tag_rank = 1 - _np.argsort(_np.argsort(-cos)) / len(near)
                score = 0.5 * fan_rank + 0.5 * tag_rank - 0.15 * pop[near]
            else:
                score = fan_rank - 0.15 * pop[near]
        else:
            score = fan_rank
        order = _np.argsort(-score)
        sims = {int(near[k]): 0.5 + 0.5 * (1 - r / max(len(near), 1)) for r, k in enumerate(order)}
    else:
        from src.new_releases import nearest as _nr_near
        sims = dict(_nr_near(source, 100))
    st.session_state._like_sims_memo = (key, sims)
    return sims


def _like_score(movie, source):
    """0-1: how close a movie is to the one you searched for."""
    from src.cf_model import _index as _ix
    sims = _like_sims(source)
    i = _ix(movie)
    if sims and i is not None:
        return sims.get(i, 0.5)          # 0.5 = no closer than any other movie
    sim = item_similarity(movie, source)
    if sim is None:
        same_genre = 1.0 if movie.get("genre") and movie.get("genre") == source.get("genre") else 0.0
        sim = 0.5 * same_genre + 0.5 * _tag_overlap(movie, source)
    return sim


def _mood_line():
    """Row note while a mood is set, or "" (only if the words matched something)."""
    from src.mood import scores
    spec = _mood_spec()
    q, t = spec["mood"], spec["label"]
    src = _like_source()
    if src:
        t = " · ".join(x for x in t.split(" · ") if not x.startswith("like "))
        head = (f"More like {src['title']}" + (f", for “{q[:30]}”" if q and scores(q) is not None else ""))
        return f"{head} · {t}" if t else head
    head = f"Your best fits for “{q[:40]}”" if q and scores(q) is not None else ("Your best fits" if t else "")
    return f"{head} · {t}" if head and t else head


def render_mood_chips():
    """What the search understood, as chips with ×. Each chip removes one part; Clear removes all."""
    from src.ui.mood_time import chips
    from src.mood import scores
    active = _mood_text()
    parts = chips(active)
    _sp = _mood_spec()
    if _sp.get("lookup") and _sp.get("like"):
        parts = [(_sp["like"], "")]
    if not parts:
        return
    try:
        row = st.container(key="mood_chip_row", horizontal=True, gap="small")
    except TypeError:          # older Streamlit: chips stack instead of sitting in one line
        row = st.container(key="mood_chip_row")
    with row:
        for i, (label, rest) in enumerate(parts):
            st.button(f"{label}  ×", key=f"mood_chip_{i}", help=f"Remove {label}",
                      on_click=_set_mood_live, args=(rest,))
        st.button("Clear", key="mood_reset", on_click=_set_mood_live, args=("",))
    mood = _mood_spec()["mood"]
    if mood and scores(mood) is None:
        st.markdown(
            f'<div class="mood-hint">No movies are described as “{html.escape(mood[:40])}” yet. '
            'Try words like feel-good, mind-bending, or slow burn.</div>',
            unsafe_allow_html=True,
        )


_MOOD_PRESETS = [("Feel-good", "feel-good"), ("Mind-bending", "mind-bending"), ("Funny", "funny"),
                 ("Dark and tense", "dark tense"), ("Thought-provoking", "thought-provoking"),
                 ("Under 2 hours", "under 2 hours"), ("Like your last save", None)]


def render_mood_suggestions():
    """One-tap starting points under the empty search field. A mood preset shows only if fans actually
    use those words, so every chip changes the picks; "Like your last save" follows the movie you saved last."""
    from src.mood import scores
    opts = []
    for label, text in _MOOD_PRESETS:
        if text is None:
            last = next((e.get("title") for e in reversed(st.session_state.get("analytics_events") or [])
                         if e.get("event") == "save" and e.get("title")), None)
            if last:
                opts.append((f"Like {last[:28]}", f"like {last}"))
        elif text.startswith("under") or scores(text) is not None:
            opts.append((label, text))
    if not opts:
        return
    try:
        row = st.container(key="mood_suggest_row", horizontal=True, gap="small")
    except TypeError:
        row = st.container(key="mood_suggest_row")
    with row:
        for i, (label, text) in enumerate(opts):
            st.button(label, key=f"mood_suggest_{i}", on_click=_set_mood_live, args=(text,))


_BUILD_KEYS = ("showroom_slots", "showroom_payloads", "showroom_row_queues", "recommendation_context",
               "tonight_pool", "tonight_deep_pool", "interleave_teams")


def _build_key():
    """Everything a Showroom build depends on. Any choice changes it, so a reused build is never stale."""
    ss = st.session_state
    return (_mood_text(), tuple(sorted(ss.likes)), tuple(sorted(ss.favorites)), tuple(ss.genres),
            ss.review_priority, ss.adventure, tuple(ss.more_of), len(ss.saved), len(ss.seen), len(ss.dismissed),
            len(ss.get("disliked") or ()), tuple(ss.get("streaming_services") or ()),
            len([e for e in (ss.get("analytics_events") or []) if e.get("event") != "impression"]))


def _commit_search(text):
    """Run a search from the live field or a suggestion, then rebuild the Showroom around it."""
    st.session_state.mood_input = " ".join(str(text or "").split())[:120]
    _apply_mood()
    st.session_state._mood_ver = int(st.session_state.get("_mood_ver") or 0) + 1   # the field shows the tidy text
    st.session_state._app_rerun = True


def _set_mood_live(text):
    """A chip, Clear, or a starting point tapped inside the search box: change the search, rebuild the Showroom."""
    _set_mood(text)
    st.session_state._mood_ver = int(st.session_state.get("_mood_ver") or 0) + 1
    st.session_state._app_rerun = True


@st.fragment
@_with_app_rerun
def render_search_box():
    """One search field that answers as you type, like the Apple TV app. Typing reruns only this box:
    a "Search for …" line plus matching movies with their posters appear under it. Tap one (or the
    Search line) to apply it; until then the Showroom underneath stays put."""
    with st.container(key="mood_box"):
        live = None
        try:
            from st_keyup import st_keyup
            live = st_keyup("Search by mood, time, or a movie", value=_mood_text(), debounce=300,
                            key=f"mood_live_{int(st.session_state.get('_mood_ver') or 0)}",
                            placeholder="A mood, a time, or a movie you loved", label_visibility="collapsed")
        except Exception:
            if "mood_input" not in st.session_state:
                st.session_state.mood_input = _mood_text()
            st.text_input("Search by mood, time, or a movie", key="mood_input", label_visibility="collapsed",
                          placeholder="A mood, a time, or a movie you loved", on_change=_apply_mood)
        typed = " ".join(str(live or "").split())
        with st.container(key="mood_under"):
            if live is not None and typed and typed != _mood_text():
                _render_live_suggestions(typed)
            elif _mood_text():
                render_mood_chips()
            else:
                render_mood_suggestions()


def _render_live_suggestions(typed):
    """Under the field while typing: "Search for …" first, then up to four movies with posters."""
    st.button(f"Search for “{typed[:60]}”", key="live_search_go", on_click=_commit_search, args=(typed,))
    from src.ui.mood_time import parse
    spec = parse(typed)
    q = spec.get("like") or spec.get("mood") or ""
    hits = []
    if len(q) >= 2 and tmdb_catalog_configured():
        try:
            hits = [m for m in (search_movies(q, 6) or []) if m.get("poster_url")][:4]
        except Exception:
            hits = []
    if not hits:
        return
    st.markdown('<div class="live-hits-label">Movies</div>', unsafe_allow_html=True)
    cols = st.columns(4, gap="small")
    for k, m in enumerate(hits):
        with cols[k]:
            st.markdown(f'<div class="live-hit"><img src="{html.escape(str(m["poster_url"]), quote=True)}" alt=""></div>',
                        unsafe_allow_html=True)
            label = f'{m["title"]}' + (f' ({m["year"]})' if m.get("year") else "")
            st.button(label[:42], key=f"live_hit_{k}", use_container_width=True, on_click=_commit_search,
                      args=(("like " + m["title"]) if spec.get("like") else m["title"],))


def _showroom_slot_key(row_name, slot_index):
    return f"{row_name}::{int(slot_index)}"

def _advance_showroom_slot(row_name, slot_index):
    """Replace only one visible showroom slot from its already-ranked queue."""
    slot_key = _showroom_slot_key(row_name, slot_index)
    slots = dict(st.session_state.get("showroom_slots") or {})
    queues = st.session_state.get("showroom_row_queues") or {}
    payloads = st.session_state.get("showroom_payloads") or {}
    current_titles = {title for title in slots.values() if title}
    excluded = (
        set(st.session_state.saved)
        | set(st.session_state.seen)
        | set(st.session_state.dismissed)
        | set(st.session_state.get("disliked") or set())
        | set(st.session_state.likes) | set(st.session_state.favorites)  # tabs9
    )

    replacement = None
    current_series = {_franchise(t) for t in current_titles}
    for title in queues.get(row_name, []):
        if not title or title in current_titles or title in excluded or _franchise(title) in current_series:
            continue
        if title not in payloads:
            continue
        _top = (payloads.get(title) or {}).get("fit_top_pct")
        _fl = fit_floor()
        if row_name != "Top Matches for You" and _fl is not None and isinstance(_top, (int, float)) and _top > _fl:
            continue          # past the fit floor: less likely to be loved than an average movie
        if ((st.session_state.get("showroom_watch_cache") or {}).get(title) or {}).get("status") == "unavailable":
            continue
        replacement = title
        break

    if replacement:
        slots[slot_key] = replacement
    else:
        slots[slot_key] = None      # nothing strong left: the card simply goes away (no slow rebuild)
    st.session_state.showroom_slots = slots
    return True

def dislike_movie(title, movie=None):
    """Explicit negative feedback: stronger than Skip, and the title never returns."""
    _remember_movie(movie)
    record_event(st.session_state, "dislike", title, _current_recommendation_context(title))
    disliked = set(st.session_state.get("disliked") or set())
    disliked.add(title)
    st.session_state.disliked = disliked
    st.session_state.saved.discard(title)
    queue_profile_save()


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


def dislike_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    if _too_soon(slot_key):
        return
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    if title:
        dislike_movie(title, payload.get("movie"))
        undo = dict(st.session_state.get("showroom_undo") or {})
        undo[slot_key] = title
        st.session_state.showroom_undo = undo
    _advance_showroom_slot(row_name, slot_index)


def skip_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    if _too_soon(slot_key):
        return
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    movie = payload.get("movie")
    if title:
        skip_movie(title, movie)
        undo = dict(st.session_state.get("showroom_undo") or {})
        undo[slot_key] = title
        st.session_state.showroom_undo = undo
    if not _advance_showroom_slot(row_name, slot_index):
        st.session_state._app_rerun = True

def _mark_showroom_fast():
    st.session_state._showroom_fast = True


def save_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    if _too_soon(slot_key):
        return
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    movie = payload.get("movie")
    if title:
        save_movie(title, movie)
        undo = dict(st.session_state.get("showroom_undo") or {})
        undo.pop(slot_key, None)
        st.session_state.showroom_undo = undo
    if not _advance_showroom_slot(row_name, slot_index):
        st.session_state._app_rerun = True

def seen_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    if _too_soon(slot_key):
        return
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    movie = payload.get("movie")
    if title:
        mark_movie_seen(title, movie)
        undo = dict(st.session_state.get("showroom_undo") or {})
        undo.pop(slot_key, None)
        st.session_state.showroom_undo = undo
    if not _advance_showroom_slot(row_name, slot_index):
        st.session_state._app_rerun = True

def _showroom_cached_metadata(movie):
    """Use initial batch metadata; fetch only the replacement card on cache miss."""
    title = movie["title"]
    year = int(movie.get("year") or 0)
    tmdb_id = int(movie.get("tmdb_id") or 0)

    identity_cache = dict(st.session_state.get("showroom_identity_cache") or {})
    identity = identity_cache.get(title)
    if identity is None:
        identity = (get_movie_identity_batch(((title, year, tmdb_id),)).get(title) or {})
        identity_cache[title] = identity
        st.session_state.showroom_identity_cache = identity_cache

    watch_cache = dict(st.session_state.get("showroom_watch_cache") or {})
    availability = watch_cache.get(title)
    if availability is None:
        availability = (get_watch_availability_batch(((title, year),), "US").get(title) or {
            "status":"unknown",
            "text":"Where to watch: availability unavailable",
            "url":None,
        })
        watch_cache[title] = availability
        st.session_state.showroom_watch_cache = watch_cache

    rating_cache = dict(st.session_state.get("showroom_rating_cache") or {})
    live_rating = rating_cache.get(title)
    if live_rating is None:
        imdb_id = (identity or {}).get("imdb_id") or ""
        live_rating = (get_live_ratings_batch(((title, year, imdb_id),)).get(title) or {})
        rating_cache[title] = live_rating
        st.session_state.showroom_rating_cache = rating_cache

    return identity or {}, availability or {}, live_rating or {}

@st.fragment
@_with_app_rerun
def render_showroom_card_fragment(row_name, row_index, slot_index):
    """Render one independently-rerunnable card so Skip never refreshes its neighbors."""
    slot_key = _showroom_slot_key(row_name, slot_index)
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    acted = (set(st.session_state.saved) | set(st.session_state.seen) | set(st.session_state.dismissed)
             | set(st.session_state.get("disliked") or set()) | set(st.session_state.likes) | set(st.session_state.favorites))  # tabs9
    if title in acted and _advance_showroom_slot(row_name, slot_index):
        title = (st.session_state.get("showroom_slots") or {}).get(slot_key)  # never re-show an acted-on movie
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    movie = payload.get("movie")
    if not title or not movie or title in acted:
        return            # an emptied slot: nothing strong left for this spot

    match = int(payload.get("match") or 0)
    p = current_profile()
    identity, availability, live_rating = _showroom_cached_metadata(movie)
    availability_value = service_availability_utility(availability)
    comps = score_movie_components(
        movie, p, st.session_state.adventure, st.session_state.review_priority,
        semantic_similarity=float(payload.get("semantic_similarity", .5)),
        availability_score=availability_value,
    )
    context = {
        "row":row_name,
        "position":int(slot_index)+1,
        "match":int(payload.get("model_match") or match),
        "model_score":round(float(comps.get("raw_score",0)),6),
        "decision_utility":round(float(comps.get("decision_utility",comps.get("raw_score",0))),6),
        **{k:round(float(comps.get(k,.5)),6) for k in [
            "genre_affinity","trait_affinity","semantic_similarity","quality_alignment",
            "discovery_alignment","priority_alignment","availability_alignment",
            "vote_confidence","profile_confidence"
        ]},
        "cf_affinity":round(float(payload.get("cf") if payload.get("cf") is not None else 0.5),6),
        "candidate_source":movie.get("candidate_source"),
        "model_version":"v5.191",
        **_interleave_fields(row_name, title),
    }
    recommendation_context = dict(st.session_state.get("recommendation_context") or {})
    recommendation_context[title] = context
    st.session_state.recommendation_context = recommendation_context
    record_impressions(st.session_state, {title: context})

    with st.container(key=f"showroom_controls_{row_index}_{slot_index}_{title}"):
        undo_title = (st.session_state.get("showroom_undo") or {}).get(slot_key)
        if undo_title:
            match_col, undo_col, skip_col = st.columns([2.75,0.62,0.90], gap="small")
            with undo_col:
                st.button(
                    ":material/undo:",
                    key=f"undo_{row_name}_{slot_index}_{title}",
                    help=f"Undo skip · bring back {undo_title}",
                    use_container_width=True,
                    on_click=undo_showroom_slot,
                    args=(row_name, slot_index),
                )
        else:
            match_col, skip_col = st.columns([3.35,0.90], gap="small")
        reasons = with_cf_reason(recommendation_explanation(
            with_live_ratings(movie, live_rating),p,st.session_state.adventure,st.session_state.review_priority,
            semantic_similarity=context.get("semantic_similarity"),
            availability_score=context.get("availability_alignment",0.5),
            components=context,
        ), payload)
        if (_mr := mood_reason(movie)):
            reasons = [_mr] + reasons
        pill_labels = dict(st.session_state.get("showroom_pill_labels") or {})
        row_taken = {label for key, label in pill_labels.items()
                     if key.startswith(f"{row_name}::") and key != slot_key and label}
        pill_text, pill_label = match_pill(match, reasons, taken=row_taken, head=fit_head(payload, match),
                                           limit=19 if undo_title else None)
        pill_text = fit_head(payload, match)     # the why is shown in words under the title
        pill_labels[slot_key] = pill_label
        st.session_state.showroom_pill_labels = pill_labels
        with match_col:
            with st.popover(pill_text, use_container_width=True):
                _love = love_line(payload.get("fit_top_pct"))
                _odds = _love.replace("If you watch it: about ", "About ").replace(" chance you'll love it", " chance you’ll love it") if _love else ""
                # One compact block: each model's share of this movie's score, with what it saw right under it.
                _rows = dict(why_rows(reasons, movie, live_rating, payload, row_name))
                _detail = {"Fans like you": _rows.get("Fans like you") or _rows.get("All models"),
                           "New releases": _rows.get("New release"),
                           "What it’s like": _rows.get("Tone"),
                           "Your choices": _rows.get("Your choices")}
                _mix = score_mix(payload, CONTENT_WEIGHT)
                _mix_html = "".join(
                    f'<div class="mix-row"><div class="mix-name">{html.escape(n)}<span>{html.escape(t)}</span></div>'
                    f'<div class="mix-track"><div class="mix-fill" style="width:{max(3, round(sh * 100))}%"></div></div>'
                    f'<div class="mix-pct">{round(sh * 100)}%</div></div>'
                    + (f'<div class="mix-detail">{html.escape(_detail[n])}</div>' if _detail.get(n) else "")
                    for n, t, sh in _mix)
                if _rows.get("Mood"):
                    _mix_html += f'<div class="mix-detail mix-extra">Mood: {html.escape(_rows["Mood"])}</div>'
                if (_rr := ratings_reason(_rows.get("Ratings"), st.session_state.get("review_priority"))):
                    _mix_html += f'<div class="mix-detail mix-extra">Ratings: {html.escape(_rr)}</div>'
                _rank, _pool = payload.get("fit_rank"), payload.get("fit_pool")
                _head = fit_head(payload, match) + (f" · #{_rank} of {_pool:,}" if isinstance(_rank, int) and isinstance(_pool, int) else "")
                st.markdown(
                    '<div class="why-pop-kicker">Why it’s here</div>'
                    f'<div class="why-pop-head">{html.escape(_head)}</div>'
                    + (f'<div class="why-pop-odds">{html.escape(_odds)} if you watch it</div>' if _odds else "")
                    + (f'<div class="mix">{_mix_html}</div>' if _mix_html else "")
                    + '<div class="why-pop-foot">Every number is from this movie’s own scores. The models and the chance '
                    'were tested on movie fans they never saw.</div>',
                    unsafe_allow_html=True,
                )
                st.button(
                    ":material/thumb_down:",
                    key=f"dislike_{row_name}_{slot_index}_{title}",
                    help="Not for me: hide it and show fewer like it. Undo brings it back.",
                    on_click=dislike_showroom_slot,
                    args=(row_name, slot_index),
                )
        with skip_col:
            st.button(
                "Skip",
                key=f"skip_{row_name}_{slot_index}_{title}",
                use_container_width=True,
                on_click=skip_showroom_slot,
                args=(row_name, slot_index),
            )

    display_movie = dict(movie)
    display_movie["title"] = preferred_title(movie, identity.get("display_title") or display_movie.get("title", ""))
    if identity.get("year"):
        display_movie["year"] = identity["year"]
    _art = get_landscape_art(movie.get("title", ""), int(movie.get("year") or 0), int(movie.get("tmdb_id") or 0)) \
        if tmdb_catalog_configured() else None
    _year = display_movie.get("year")
    _sid = f"card-premise-{row_index}-{slot_index}"
    _art_html = movie_thumb(dict(display_movie, year=""), _art or identity.get("poster_url") or movie.get("poster_url"),
                            landscape=True, return_html=True)
    # Like streaming apps: art, then what you decide on (year, two genres), then ratings and where to watch.
    # Why it's here lives in the % pill, so the card stays two short lines.
    rating_parts = ratings_text(card_ratings(movie, live_rating))
    from src.ui.mood_time import fmt as _fmt_rt
    _label = {"Critically Acclaimed": "Critics’ pick", "Hidden Gems": "Hidden gem", "Recent Releases for You": "New release",
              "Classics for You": "Classic", "International Films for You": "International",
              "Documentaries for You": "Documentary", "Something Different": "Something new"}.get(row_name, "")
    meta = [str(x) for x in (_label if row_name != "Top Matches for You" else "", _year, genre_pair(movie),
                               _fmt_rt(identity.get("runtime"))) if x]
    availability_class = "watch-availability muted" if availability.get("status") in {"unknown", "not_configured", "unavailable"} else "watch-availability"
    watch_html = watch_line_html(availability, movie.get("title", ""), st.session_state.get("streaming_services"))
    if availability.get("status") in {"unknown", "unavailable"}:
        # Still in theaters? Show labeled estimates for when it reaches home (src/stream_when.py).
        from src.stream_when import line as _when
        _w = _when(identity.get("release_date"), identity.get("studios") or ())
        if _w:
            watch_html, availability_class = html.escape(_w), "watch-availability"
    st.markdown(card_html(_sid, _art_html, display_movie.get("title", ""), movie, identity,
        f'<div class="poster-caption-year card-year">{meta_html(meta)}</div>'
        f'<div class="ratings">{" · ".join(rating_parts) or "Ratings unavailable"}</div>'
        f'<div class="{availability_class}">{watch_html}</div>'), unsafe_allow_html=True)
    # Save / Seen live inside the card too, so every tap on a card reruns only that card. The Saved and
    # Seen tabs pick the change up when you open them (version check in src/scroll_keeper_component).
    render_card_actions(row_name, row_index, slot_index)
    # Persist Skip / Save / Seen / Undo during this card-only rerun without creating a visible loader.
    persist_from_fragment()
    _ver_mark()


def render_card_actions(row_name, row_index, slot_index):
    """Save / Seen sit outside the card fragment: a click runs the page once, directly,
    so the Saved / Seen tabs update without a second rerun triggered from a fragment."""
    if not (st.session_state.get("showroom_slots") or {}).get(_showroom_slot_key(row_name, slot_index)):
        return
    with st.container(key=f"movie_actions_{row_index}_{slot_index}"):
        a, b = st.columns(2, gap="small")
        with a:
            st.button("Save", key=f"save_{row_name}_{slot_index}", use_container_width=True,
                      on_click=save_showroom_slot, args=(row_name, slot_index))
        with b:
            st.button("Seen", key=f"seen_{row_name}_{slot_index}", use_container_width=True,
                      on_click=seen_showroom_slot, args=(row_name, slot_index))

def _drop_last_event(title, event_type):
    """Remove the most recent event of a type for a title (used by Undo)."""
    events = list(st.session_state.get("analytics_events") or [])
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("event") == event_type and events[i].get("title") == title:
            del events[i]
            break
    st.session_state.analytics_events = events


def undo_skip(title):
    """Reverse an accidental Skip or "Not for me" so it neither hides the movie nor trains the model."""
    if not title:
        return
    disliked = set(st.session_state.get("disliked") or set())
    if title in disliked:
        disliked.discard(title)
        st.session_state.disliked = disliked
        _drop_last_event(title, "dislike")
    else:
        st.session_state.dismissed.discard(title)
        _drop_last_event(title, "skip")
    queue_profile_save()


def undo_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    undo = dict(st.session_state.get("showroom_undo") or {})
    title = undo.pop(slot_key, None)
    st.session_state.showroom_undo = undo
    if not title:
        return
    undo_skip(title)
    slots = dict(st.session_state.get("showroom_slots") or {})
    slots[slot_key] = title
    st.session_state.showroom_slots = slots


def _sync_services_from_picker():
    st.session_state.streaming_services = list(st.session_state.get("tonight_services_picker") or [])
    queue_profile_save()


def tonight_skip(title, movie):
    if _too_soon(f"tonight_skip:{title}"):
        return
    skip_movie(title, movie)
    st.session_state.tonight_last_skip = title


def tonight_dislike(title, movie):
    if _too_soon(f"tonight_dislike:{title}"):
        return
    dislike_movie(title, movie)
    st.session_state.tonight_last_skip = title


def tonight_undo():
    undo_skip(st.session_state.get("tonight_last_skip"))
    st.session_state.tonight_last_skip = None


def _request_showroom_refresh():
    """Save/Seen change the Saved/Seen tabs and counts, which live outside the card."""
    st.session_state._showroom_refresh = True

def _refresh_if_requested():
    if st.session_state.pop("_showroom_refresh", False):
        st.rerun(scope="app")

def tonight_save(title, movie):
    if _too_soon(f"tonight_save:{title}"):
        return
    save_movie(title, movie)
    st.session_state.tonight_last_skip = None
    _mark_showroom_fast()
    _request_showroom_refresh()


def tonight_seen(title, movie):
    if _too_soon(f"tonight_seen:{title}"):
        return
    mark_movie_seen(title, movie)
    st.session_state.tonight_last_skip = None
    _mark_showroom_fast()
    _request_showroom_refresh()


def _render_services_picker(services):
    label = f"Your Services · {len(services)}" if services else "Choose Your Services"
    if "tonight_services_picker" not in st.session_state:
        st.session_state.tonight_services_picker = list(services)
    with st.container(key="services_picker"), st.popover(label, use_container_width=True):
        st.markdown('<div class="services-help">Pick what you subscribe to. Tonight’s Show updates as you tap.</div>',
                    unsafe_allow_html=True)
        options = list(STREAMING_SERVICES)
        if hasattr(st, "pills"):
            st.pills("Your services", options, selection_mode="multi", key="tonight_services_picker",
                     on_change=_sync_services_from_picker, label_visibility="collapsed")
        else:
            st.multiselect("Your services", options, key="tonight_services_picker",
                           on_change=_sync_services_from_picker, label_visibility="collapsed")


@st.fragment
@_with_app_rerun
def render_tonight_pick_fragment():
    """Compact single best match. Services, Skip, and Undo rerun only this card."""
    _refresh_if_requested()
    services = list(st.session_state.get("streaming_services") or [])
    payloads = st.session_state.get("showroom_payloads") or {}
    watch_cache = st.session_state.get("showroom_watch_cache") or {}
    blocked = (set(st.session_state.saved) | set(st.session_state.seen) | set(st.session_state.dismissed)
               | set(st.session_state.get("disliked") or set()) | set(st.session_state.likes) | set(st.session_state.favorites)  # tabs9
               | {t for t in (st.session_state.get("showroom_slots") or {}).values() if t})
    in_rows = {t for t in (st.session_state.get("showroom_slots") or {}).values() if t}
    acted = blocked - in_rows
    pool = [t for t in (st.session_state.get("tonight_pool") or []) if t in payloads and t not in blocked]
    fits = []
    if services:
        # Look through up to the top 120 ranked movies for ones on the viewer's services,
        # fetching any missing availability in one cached batch.
        deep = [t for t in (st.session_state.get("tonight_deep_pool") or st.session_state.get("tonight_pool") or [])
                if t in payloads and t not in acted]
        missing = [t for t in deep if t not in watch_cache]
        if missing:
            keys = tuple((t, int((payloads[t].get("movie") or {}).get("year") or 0)) for t in missing)
            try:
                fetched = get_watch_availability_batch(keys, "US") or {}
            except Exception:
                fetched = {}
            watch_cache = {**watch_cache, **fetched}
            st.session_state.showroom_watch_cache = watch_cache
        on_services = [t for t in deep if movie_on_services(watch_cache.get(t), services)]
        # Prefer a match not already shown in a row; a row duplicate beats a wrong pick.
        fits = [t for t in on_services if t not in in_rows] + [t for t in on_services if t in in_rows]
    ordered = fits + [t for t in pool if t not in fits]

    if services:
        shown = ", ".join(services[:2]) + (f" +{len(services) - 2}" if len(services) > 2 else "")
        note = (f"Your single best match right now on {shown}" if fits else
                f"None of your top matches stream on {shown} right now, so here’s your best overall match")
    else:
        note = "Your single best match right now"
    if _mood_line() and not _mood_spec().get("lookup"):
        note = _mood_line().replace("Your best fits for", "Your best match for")
    head, picker = st.columns([3.4, 1.1], gap="medium", vertical_alignment="bottom")
    with head:
        st.markdown(
            '<div class="showroom-row-header tonight-row-header">'
            '<div class="showroom-row-title">Tonight’s Show</div>'
            f'<div class="row-model-note">{html.escape(note)}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with picker:
        _render_services_picker(services)

    if not ordered:
        st.caption("No pick available right now. Try adding more services or refreshing.")
        return

    title = ordered[0]
    payload = payloads.get(title) or {}
    movie = payload.get("movie") or {}
    match = int(payload.get("match") or 0)
    p = current_profile()
    identity, availability, live_rating = _showroom_cached_metadata(movie)
    comps = score_movie_components(
        movie, p, st.session_state.adventure, st.session_state.review_priority,
        semantic_similarity=float(payload.get("semantic_similarity", .5)),
        availability_score=service_availability_utility(availability),
    )
    context = {
        "row": "Tonight's Show", "position": 1, "match": int(payload.get("model_match") or match),
        "model_score": round(float(comps.get("raw_score", 0)), 6),
        "decision_utility": round(float(comps.get("decision_utility", comps.get("raw_score", 0))), 6),
        **{k: round(float(comps.get(k, .5)), 6) for k in [
            "genre_affinity", "trait_affinity", "semantic_similarity", "quality_alignment",
            "discovery_alignment", "priority_alignment", "availability_alignment",
            "vote_confidence", "profile_confidence"
        ]},
        "cf_affinity": round(float(payload.get("cf") if payload.get("cf") is not None else 0.5), 6),
        "candidate_source": movie.get("candidate_source"),
        "model_version":"v5.191",
    }
    recommendation_context = dict(st.session_state.get("recommendation_context") or {})
    recommendation_context[title] = context
    st.session_state.recommendation_context = recommendation_context
    record_impressions(st.session_state, {title: context})

    display_title = preferred_title(movie, identity.get("display_title") or movie.get("title", ""))
    year = identity.get("year") or movie.get("year") or ""
    genre = movie.get("genre") or ""
    poster_url = identity.get("poster_url") or movie.get("poster_url")
    poster_html = (
        f'<div class="poster has-image"><img src="{html.escape(str(poster_url), quote=True)}" '
        f'alt="Poster for {html.escape(str(display_title))}"></div>'
        if poster_url else '<div class="poster"><div class="poster-placeholder-mark">iCINEMA</div></div>'
    )
    ratings = ratings_text(card_ratings(movie, live_rating))
    # Same line as every card: year · two genres · minutes, then ratings in their own casing (IMDb, RT).
    _rt_min = int((identity or {}).get("runtime") or movie.get("runtime") or 0)
    _meta_parts = [str(year) if year else "", genre_pair(movie) or genre, f"{_rt_min} min" if _rt_min else ""]
    meta_html_line = (meta_html([x for x in _meta_parts if x])
                      + (f' · <span class="no-caps">{html.escape(" · ".join(ratings))}</span>' if ratings else ""))

    watch_html = watch_line_html(availability, movie.get("title", ""), services)
    options = watch_options(availability, movie.get("title", ""), services, limit=1)
    fit = ""  # the streaming line already lists the viewer's services first

    reasons = with_cf_reason(recommendation_explanation(
        with_live_ratings(movie, live_rating), p, st.session_state.adventure, st.session_state.review_priority,
        semantic_similarity=context.get("semantic_similarity"),
        availability_score=context.get("availability_alignment", 0.5),
        components=context,
    ), payload, limit=2)
    def _why_text(r):
        # "Loved by fans of X" already says it; skip the sentence that repeats it.
        t = str(r.get("text") or "")
        if str(r.get("label", "")).startswith("Loved by fans") and "loved" in t.casefold():
            return " · similar tone too" if "similar tone" in t else ""
        return f" · {t}" if t else ""
    why_html = "".join(f'<div class="tonight-why"><strong>{html.escape(r["label"])}</strong>{html.escape(_why_text(r))}</div>'
                       for r in reasons)

    _love = love_line(payload.get("fit_top_pct"))
    _love_short = _love.replace("If you watch it: about ", "About ").replace(" chance you'll love it", " chance you’ll love it") if _love else ""
    tonight_badge = ((f"Best on your services · " if services else "")
                     + (_love_short or fit_head(payload, match)))
    with st.container(key=f"tonight_hero_{title}"):
        poster_col, info_col = st.columns([1, 6.2], gap="medium")
        with poster_col:
            st.markdown(poster_html, unsafe_allow_html=True)
        with info_col:
            st.markdown(
                '<div class="tonight-stack">'
                f'<div class="tonight-title">{html.escape(str(display_title))}</div>'
                f'<div class="tonight-meta">{meta_html_line}</div>'
                f'<div class="tonight-badges"><span class="tonight-match">{html.escape(tonight_badge)}</span>{fit}</div>'
                f'<div class="tonight-line">{watch_html}</div>'
                f'<div class="tonight-hook">{html.escape(card_description(dict(movie, tagline=identity.get("tagline"), overview=movie.get("overview") or identity.get("overview"))))}</div>'
                f'<div class="tonight-whys">{why_html}</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            last_skip = st.session_state.get("tonight_last_skip")
            with st.container(key=f"tonight_actions_{title}"):
                # Save · Seen · Skip · thumbs-down, then Undo when there is something to undo.
                cols = st.columns([1, 1, 1, 0.55, 1, 1.65], gap="small")
                with cols[0]:
                    st.button("Save", key=f"tonight_save_{title}", use_container_width=True,
                              on_click=tonight_save, args=(title, movie))
                with cols[1]:
                    st.button("Seen", key=f"tonight_seen_{title}", use_container_width=True,
                              on_click=tonight_seen, args=(title, movie))
                with cols[2]:
                    st.button("Skip", key=f"tonight_skip_{title}", use_container_width=True,
                              on_click=tonight_skip, args=(title, movie))
                with cols[3]:
                    st.button(":material/thumb_down:", key=f"tonight_dislike_{title}", use_container_width=True,
                              help="Not for me: hide it and show fewer like it.",
                              on_click=tonight_dislike, args=(title, movie))
                with cols[4]:
                    if last_skip:
                        st.button("Undo", key=f"tonight_undo_{title}", use_container_width=True,
                                  help=f"Bring back {last_skip}", on_click=tonight_undo)
    persist_from_fragment()
    _ver_mark()


def _library_counts():
    """Saved/Seen counts beside the fixed tab labels, refreshed inside each library fragment."""
    st.markdown(
        '<style>[data-testid="stTabs"] [role="tab"][id$="-tab-1"] p::after,'
        '[data-testid="stTabs"] [role="tablist"] > [role="tab"]:nth-of-type(2) p::after{content:" (%d)" !important}'
        '[data-testid="stTabs"] [role="tab"][id$="-tab-2"] p::after,'
        '[data-testid="stTabs"] [role="tablist"] > [role="tab"]:nth-of-type(3) p::after{content:" (%d)" !important}</style>'
        % (len(st.session_state.saved), len(st.session_state.seen)),
        unsafe_allow_html=True,
    )


@st.fragment
def _saved_tab():
    """Saved tab. A fragment, so its buttons rerun only this tab: the open tab never changes."""
    # Hidden refresh: switching to this tab clicks it (src/scroll_keeper_component), so a change made
    # on the other library tab shows up here without reloading the page.
    st.button("Refresh", key="refresh_saved")
    _ver_mark(1)
    _lib_mark()
    st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
    st.markdown('<div class=\"tab-primary-heading saved-tab-heading\">Saved</div>', unsafe_allow_html=True)
    movies=[m for t in _newest_first(st.session_state.saved, ("save",)) if (m := resolve_history_movie(t))]
    saved_identity_keys=tuple((m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in movies if m.get("media") != "tv")
    saved_identity_map = get_movie_identity_batch(saved_identity_keys)
    saved_poster_map = get_poster_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies))
    saved_art_map = get_landscape_batch(saved_identity_keys) if movies else {}
    saved_watch_map = get_watch_availability_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies if m.get("media") != "tv"), "US") if movies else {}
    from src.tv import show_watch as _show_watch
    for _m in movies:
        if _m.get("media") == "tv" and _m.get("tmdb_id"):
            saved_watch_map[_m["title"]] = _show_watch(int(_m["tmdb_id"]))
    saved_live_map = get_live_ratings_batch(tuple((m["title"], int(m.get("year") or 0),
                                                  (saved_identity_map.get(m["title"], {}) or {}).get("imdb_id") or "")
                                                 for m in movies)) if movies else {}
    if not movies:st.caption("Nothing saved yet. Tap Save on any movie in the Showroom and it waits here.")
    else:
        cols=st.columns(4, gap="medium")
        for i,m in enumerate(movies):
            with cols[i % 4]:
                with st.container(key=f"savedcard_{i}"):
                    identity = {} if m.get("media") == "tv" else (saved_identity_map.get(m["title"], {}) or {})
                    display_movie = dict(m)
                    display_movie["title"] = preferred_title(m, identity.get("display_title") or display_movie.get("title", ""))
                    if identity.get("year"):
                        display_movie["year"] = identity["year"]
                    _art = m.get("backdrop_url") if m.get("media") == "tv" else saved_art_map.get(m["title"])
                    _sid = f"saved-premise-{i}"
                    _art_html = movie_thumb(dict(display_movie, year=""), _art or identity.get("poster_url") or m.get("poster_url")
                                            or saved_poster_map.get(m["title"]), landscape=True, return_html=True)
                    st.markdown(card_html(_sid, _art_html, display_movie.get("title", ""), m, identity,
                                          library_lines_html(m, identity, saved_live_map,
                                                             watch_line_html(saved_watch_map.get(m["title"]), m["title"], st.session_state.get("streaming_services"))),
                                          lines_in_panel=True),   # just the art and two buttons; tap for details
                                unsafe_allow_html=True)
                    saved_actions = st.columns(2, gap="small")
                    with saved_actions[0]:
                        st.button("Seen", key=f"savedseen_{m['title']}", use_container_width=True,
                                  on_click=_saved_to_seen, args=(m["title"], m))
                    with saved_actions[1]:
                        st.button("Remove", key=f"unsave_{m['title']}", use_container_width=True,
                                  on_click=remove_saved_movie, args=(m["title"],))
    _library_counts()


def _whats_next_popover(i, m, pick, wn_payloads, wn_identity):
    """The What's next pick for one Seen movie, in a popover."""
    nt, used_cf = pick
    npay = wn_payloads.get(nt) or {}
    nmovie = npay.get("movie") or {}
    nid = wn_identity.get(nt) or {}
    nposter = nid.get("poster_url") or nmovie.get("poster_url")
    ntitle = preferred_title(nmovie, nid.get("display_title") or nmovie.get("title") or nt)
    nyear = nid.get("year") or nmovie.get("year") or ""
    why = (f"Viewers who loved “{m['title']}” tend to love this too."
           if used_cf else f"Shares the genre and tone of “{m['title']}”.")
    with st.container(key=f"whatsnext_{i}"):
        with st.popover("What’s Next", use_container_width=True):
            img = (f'<img src="{html.escape(str(nposter), quote=True)}" alt="">'
                   if nposter else '<div class="whatsnext-noimg">iCINEMA</div>')
            st.markdown(
                f'<div class="whatsnext-kicker">Watch next after “{html.escape(m["title"])}”</div>'
                f'<div class="whatsnext-pick"><div class="whatsnext-poster">{img}</div>'
                f'<div class="whatsnext-info">'
                f'<div class="whatsnext-title">{html.escape(str(ntitle))}</div>'
                f'<div class="whatsnext-meta">{html.escape(" · ".join(str(x) for x in [nyear, genre_pair(nmovie) or nmovie.get("genre")] if x))}'
                f' · {fit_head(npay, npay.get("match"))}</div>'
                f'<div class="whatsnext-why">{html.escape(why)}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            # Compact pills, about the poster's width, aligned under the poster.
            a, b, _ = st.columns([1, 1.7, 3.3], gap="small")
            with a:
                st.button("Save", key=f"whatsnext_save_{i}_{nt}", use_container_width=True,
                          on_click=save_movie, args=(nt, nmovie))
            with b:
                st.button("Another Pick", key=f"whatsnext_more_{i}_{nt}", use_container_width=True,
                          on_click=whats_next_another, args=(m["title"],))


def _newest_first(titles, kinds):
    """Saved and Seen in the order you did it, newest first (imported titles without a date go last)."""
    when = {}
    for e in st.session_state.get("analytics_events") or []:
        if e.get("event") in kinds and e.get("title") in titles:
            when[e["title"]] = max(when.get(e["title"], 0.0), float(e.get("timestamp") or 0))
    return sorted(titles, key=lambda t: (-when.get(t, 0.0), str(t).casefold()))


@st.fragment
def _seen_tab():
    """Seen tab. A fragment, so its buttons rerun only this tab: the open tab never changes."""
    # Hidden refresh: switching to this tab clicks it (src/scroll_keeper_component), so a change made
    # on the other library tab shows up here without reloading the page.
    st.button("Refresh", key="refresh_seen")
    _ver_mark(2)
    _lib_mark()
    st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
    st.markdown('<div class=\"tab-primary-heading\">Seen</div>', unsafe_allow_html=True)
    movies=[m for t in _newest_first(st.session_state.seen, ("seen",)) if (m := resolve_history_movie(t))]
    seen_identity_keys=tuple((m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in movies if m.get("media") != "tv")
    seen_identity_map = get_movie_identity_batch(seen_identity_keys)
    seen_poster_map = get_poster_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies))
    seen_art_map = get_landscape_batch(seen_identity_keys) if movies else {}
    seen_live_map = get_live_ratings_batch(tuple((m["title"], int(m.get("year") or 0),
                                                 (seen_identity_map.get(m["title"], {}) or {}).get("imdb_id") or "")
                                                for m in movies)) if movies else {}
    seen_watch_map = get_watch_availability_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies if m.get("media") != "tv"), "US") if movies else {}
    for _m in movies:
        if _m.get("media") == "tv" and _m.get("tmdb_id"):
            from src.tv import show_watch as _show_watch
            seen_watch_map[_m["title"]] = _show_watch(int(_m["tmdb_id"]))
    if not movies:st.caption("Nothing here yet. Tap Seen on a movie you’ve watched and it lands here, with a pick for what to watch next.")
    else:
        # What's next: one personalized follow-up per Seen movie, never the same pick
        # twice on this tab, never something already saved, seen, skipped or disliked.
        wn_payloads = st.session_state.get("showroom_payloads") or {}
        wn_blocked = (set(st.session_state.saved) | set(st.session_state.seen)
                      | set(st.session_state.dismissed) | set(st.session_state.get("disliked") or set()) | set(st.session_state.likes) | set(st.session_state.favorites))  # tabs9
        wn_offsets = st.session_state.get("whats_next_offset") or {}
        # What's next picks only change when the Seen list, the blocked set, or "Another pick" changes,
        # so a thumbs tap reuses them instead of re-ranking every candidate for every Seen movie.
        _wn_key = (tuple(m["title"] for m in movies), len(wn_blocked), hash(frozenset(wn_blocked)),
                   tuple(sorted(wn_offsets.items())), len(wn_payloads),
                   tuple(sorted((st.session_state.get("seen_rating") or {}).items())))
        _wn_memo = st.session_state.get("_whats_next_memo")
        if _wn_memo and _wn_memo[0] == _wn_key:
            wn_picks = dict(_wn_memo[1])
        else:
            wn_taken, wn_picks = set(), {}
            for m in movies:
                ranked = [(t, cf) for t, cf in whats_next_ranking(m, wn_payloads, wn_blocked) if t not in wn_taken]
                if ranked:
                    pick = ranked[int(wn_offsets.get(m["title"], 0)) % len(ranked)]
                    wn_picks[m["title"]] = pick
                    wn_taken.add(pick[0])
            st.session_state._whats_next_memo = (_wn_key, dict(wn_picks))
        wn_identity = st.session_state.get("showroom_identity_cache") or {}
        cols=st.columns(4, gap="medium")
        for i,m in enumerate(movies):
            with cols[i % 4]:
                with st.container(key=f"seencard_{i}"):
                    identity = {} if m.get("media") == "tv" else (seen_identity_map.get(m["title"], {}) or {})
                    display_movie = dict(m)
                    display_movie["title"] = preferred_title(m, identity.get("display_title") or display_movie.get("title", ""))
                    if identity.get("year"):
                        display_movie["year"] = identity["year"]
                    _art = m.get("backdrop_url") if m.get("media") == "tv" else seen_art_map.get(m["title"])
                    _sid = f"seen-premise-{i}"
                    _art_html = movie_thumb(dict(display_movie, year=""), _art or identity.get("poster_url") or m.get("poster_url")
                                            or seen_poster_map.get(m["title"]), landscape=True, return_html=True)
                    st.markdown(card_html(_sid, _art_html, display_movie.get("title", ""), m, identity,
                                          library_lines_html(m, identity, seen_live_map,
                                                             watch_line_html(seen_watch_map.get(m["title"]), m["title"], st.session_state.get("streaming_services"))),
                                          lines_in_panel=True),
                                unsafe_allow_html=True)
                    _r = (st.session_state.get("seen_rating") or {}).get(m["title"], 0)
                    pick = wn_picks.get(m["title"])
                    # One calm row: two icon toggles (loved it / not for me) and What's next.
                    # Two calm rows that fit any card width: the three icon pills, then What's Next.
                    with st.container(key=f"seenrow_{i}"):
                        up, down, rm = st.columns(3, gap="small", vertical_alignment="center")
                        with up:
                            st.button(":material/thumb_up:", key=f"seenup_{m['title']}", help="Loved it",
                                      type="primary" if _r == 1 else "secondary", use_container_width=True,
                                      on_click=rate_seen, args=(m["title"], 1))
                        with down:
                            st.button(":material/thumb_down:", key=f"seendown_{m['title']}", help="Not for me",
                                      type="primary" if _r == -1 else "secondary", use_container_width=True,
                                      on_click=rate_seen, args=(m["title"], -1))
                        with rm:
                            st.button(":material/close:", key=f"unseen_{m['title']}", help="Remove from Seen",
                                      use_container_width=True, on_click=remove_from_seen, args=(m["title"],))
                    if pick:
                        with st.container(key=f"seennext_{i}"):
                            _whats_next_popover(i, m, pick, wn_payloads, wn_identity)
    _library_counts()


def render_showroom_fragment(p):
    _t = _time.perf_counter()
    try:
        _render_showroom(p)
    finally:
        _log_time("showroom (fast path)" if st.session_state.get("_timing_fast") else "showroom (full build)", _t)


def _render_showroom(p):
    # Not a fragment: nesting card fragments inside a Showroom fragment let Streamlit
    # briefly draw the tabs twice after an app rerun.
    ensure_session(st.session_state)
    if not st.session_state.get("_visit_tracked"):
        from src.telemetry import track
        track(st.session_state, "visit")
        st.session_state._visit_tracked = True
    tabs = st.tabs(["Showroom", "Saved", "Seen", "Profile"])  # tabs8: fixed labels keep the open tab

    # Save / Seen reuse the current ranking: the page reruns so the Saved / Seen tabs
    # update, but the heavy rebuild (candidate fetch, scoring ~700 movies, ranking every
    # row) is skipped. The next navigation or visit re-ranks with the new feedback.
    # Changing or clearing the search goes back to a Showroom built a moment ago instead of re-ranking
    # ~700 movies again: the last few builds are kept, keyed by everything that shapes them.
    _bk = _build_key()
    _hit = (st.session_state.get("_build_cache") or {}).get(_bk)
    if _hit and not st.session_state.get("_showroom_fast"):
        for _k, _v in _hit.items():
            st.session_state[_k] = _v
        st.session_state._showroom_fast = True
    fast = st.session_state.pop("_showroom_fast", False) and bool(st.session_state.get("showroom_slots"))
    st.session_state._timing_fast = fast
    if fast:
        row_choices = {}
        for key in (st.session_state.get("showroom_slots") or {}):
            row, _, idx = key.rpartition("::")
            row_choices.setdefault(row, [])
            while len(row_choices[row]) <= int(idx):
                row_choices[row].append(None)
    else:
        excluded=st.session_state.saved|st.session_state.seen|st.session_state.dismissed|set(st.session_state.get("disliked") or set())|set(st.session_state.likes)|set(st.session_state.favorites)  # tabs9

        # Build a deep candidate pool, then rank every candidate with the same iCinema
        # personalization algorithm. TMDB discovery acts only as replenishment: it does not
        # bypass the user's profile, and excluded Save/Seen/Skip titles stay excluded.
        # Rotate deeper into TMDB as a user skips more titles, so the showroom keeps
        # replenishing instead of exhausting one fixed discovery slice.
        # Each return visit starts a little deeper, so the candidate pool keeps changing.
        _events = st.session_state.get("analytics_events") or []
        _current = st.session_state.get("showroom_session_id")
        past_visits = len({e.get("session_id") for e in _events if e.get("event") == "impression"
                           and e.get("session_id") and e.get("session_id") != _current})
        discovery_start_page = 1 + (len(st.session_state.dismissed) // 80) * 8 + (past_visits % 12) * 2
        focus_genres = tuple((p.get("genres") or [])[:2])
        external_pool = []
        if tmdb_catalog_configured():
            try:
                external_pool = discover_movies(640, discovery_start_page, focus_genres=focus_genres)
            except TypeError:
                # Backward-compatible fallback if Streamlit is briefly serving an
                # older cached module during a deployment. Never take down Showroom.
                try:
                    external_pool = discover_movies(640)
                except Exception:
                    external_pool = []
            except Exception:
                external_pool = []
        candidate_pool = list(CATALOG) + list(st.session_state.external_movies.values()) + external_pool
        _mq = _mood_spec()["mood"]
        if _mq:
            from src.mood import top_rows as _mood_rows
            from src.cf_model import movie_at as _movie_at
            _have = {str(m.get("title", "")).casefold() for m in candidate_pool}
            _mood_genre = next((g for g in GENRES if g.casefold() in _mq.casefold()), None)
            for _r in _mood_rows(_mq, 150):
                _m = _movie_at(_r)
                if _m and _mood_genre:
                    _m["genre"] = _mood_genre
                    _m["tags"] = [_mood_genre]
                if _m and _m["title"] and _m["title"].casefold() not in _have:
                    candidate_pool.append(_m)
                    _have.add(_m["title"].casefold())
        # Retrieval from the whole catalog: the fans-like-you model's own top 150 for this viewer, and for
        # "like X" the 100 movies fans link most closely to X, join the pool before ranking. Without this,
        # the true best matches could be missing simply because TMDB's pages didn't include them.
        from src.cf_model import top_indices as _cf_top, neighbors as _cf_nbrs, movie_at as _movie_at2
        _have2 = {str(m.get("title", "")).casefold() for m in candidate_pool}
        _extra_idx = _cf_top(user_vector(_cf_signals()), 150)
        _src0 = _like_source()
        if _src0:
            _extra_idx = list(_like_sims(_src0).keys())[:60] + _extra_idx   # the 60 closest are plenty for 4 picks
        for _r in _extra_idx:
            _m = _movie_at2(_r)
            if _m and _m["title"] and _m["title"].casefold() not in _have2:
                _m["candidate_source"] = "catalog"
                candidate_pool.append(_m)
                _have2.add(_m["title"].casefold())
        ranked = rank_movies(
            candidate_pool,
            p,
            st.session_state.adventure,
            st.session_state.review_priority,
            excluded,
            None,
        )
        ranked = _clean_ranked(ranked, excluded)
        learning_result=learning_model_for(st.session_state.get("analytics_events", []))
        ranked_movies=[movie for _,movie in ranked]
        semantic_by_id=cached_semantic_scores(ranked_movies,p)
        _signals=_cf_signals()
        cf_user=user_vector(_signals)
        # Live interleaving test: only viewers routed to RP3beta get two different rankings.
        il_on=interleave_eligible(_signals)
        from src.mood import scores as _mood_scores
        _tspec=_mood_spec()
        _mood_q=_tspec["mood"]
        _mood=_mood_scores(_mood_q) if _mood_q else None
        if _mood is not None:
            il_on=False      # a mood changes Top Matches on purpose, so the live test sits it out
        cf_user_knn=user_vector(_signals,force_knn=True) if il_on else None

        def _mood_first(items):
            """Movies fans describe the way the viewer did move to the front; the row keeps its own rules."""
            if _mood is None or not items:
                return items
            import numpy as _np
            _pos=_mood[_mood>0]
            if not len(_pos):
                return items
            _thr=float(_np.quantile(_pos,0.8))
            hit=[it for it in items if (i:=_cf_idx(it[1])) is not None and _mood[i]>=_thr]
            hit_ids={id(it) for it in hit}
            return hit+[it for it in items if id(it) not in hit_ids]
        content_memo={}
        # Recent movies MovieLens fans haven't rated: placed by the new-release model (if it passed).
        from src.new_releases import viewer as _nr_viewer, affinity as _nr_affinity
        from src.cf_model import _index as _cf_idx
        nr_view=_nr_viewer(_signals,_cf_idx)
        # Learned ranker (shipped only if it beat the fixed mix): one score from all six models.
        from src import ltr as _ltr
        ltr_aff=_ltr.viewer_scores(_signals) if _ltr.available() else None
        cf_by_title={}
        personal_by_title={}
        cf_source_by_title={}
        model_match_by_title={}

        def _safe_num(value, default=0):
            try:
                return float(value) if value is not None else default
            except (TypeError, ValueError):
                return default

        def _row_signal(row_name, movie):
            """Section-specific signal layered on the same learned iCinema profile."""
            tags=set(movie.get("tags", []))
            popularity=max(0.0, _safe_num(movie.get("popularity"), 0.0))
            rt=_safe_num(movie.get("rt"), -1.0)
            imdb=_safe_num(movie.get("imdb"), -1.0)
            tmdb_vote=_safe_num(movie.get("tmdb_vote"), -1.0)
            year=int(_safe_num(movie.get("year"), 0))

            if row_name=="Critically Acclaimed":
                critic=(rt/100.0) if rt>=0 else 0.5
                audience_vals=[]
                if imdb>=0: audience_vals.append(imdb/10.0)
                if tmdb_vote>=0: audience_vals.append(tmdb_vote/10.0)
                audience=sum(audience_vals)/len(audience_vals) if audience_vals else 0.5
                tagged=1.0 if "Critically Acclaimed" in tags else 0.0
                return max(0.0,min(1.0,0.50*critic+0.35*audience+0.15*tagged))

            if row_name=="Hidden Gems":
                # Prefer lower-popularity titles with discovery-oriented metadata, while
                # keeping enough quality evidence to avoid rewarding obscurity by itself.
                obscurity=1.0/(1.0+popularity/28.0) if popularity else 0.58
                hidden=1.0 if "Hidden Gem" in tags else 0.0
                discovery_tags={"International","Offbeat","Slow-burn","Psychological","Documentary","Grounded","Cerebral"}
                discovery=min(1.0,len(discovery_tags.intersection(tags))/2.0)
                quality=max(0.0,min(1.0,((rt/100.0) if rt>=0 else ((imdb/10.0) if imdb>=0 else 0.55))))
                return max(0.0,min(1.0,0.42*obscurity+0.24*hidden+0.18*discovery+0.16*quality))

            if row_name=="Something Different":
                preferred=set(p.get("genres", []))
                genre_novelty=0.0 if movie.get("genre") in preferred else 1.0
                language_novelty=1.0 if str(movie.get("original_language") or "en").lower() not in {"", "en"} else 0.0
                era_novelty=1.0 if year and (year<=2005 or year>=2023) else 0.35
                obscurity=1.0/(1.0+popularity/40.0) if popularity else 0.45
                votes=_safe_num(movie.get("tmdb_vote_count"), -1.0)
                if votes>=0:
                    import math
                    # ~25k votes (a blockbuster) scores near 0; a few hundred scores high.
                    obscurity=0.5*obscurity+0.5*max(0.0,1.0-math.log10(votes+1.0)/4.5)
                return max(0.0,min(1.0,0.40*genre_novelty+0.18*language_novelty+0.10*era_novelty+0.32*obscurity))

            return 1.0

        base_memo={}
        fatigue=impression_fatigue()

        # Popularity right now, as a 0-1 percentile within this candidate pool.
        _pops=sorted(_safe_num(m.get("popularity"),0.0) for _,m in ranked)
        def _pop_now(movie):
            if not _pops:
                return 0.0
            import bisect
            return bisect.bisect_left(_pops,_safe_num(movie.get("popularity"),0.0))/max(1,len(_pops)-1)

        def _qualifies(row_name, movie):
            """Hard rule each section must meet before personal fit ranks it (true to its name)."""
            rt=_safe_num(movie.get("rt"),-1.0); imdb=_safe_num(movie.get("imdb"),-1.0)
            tv=_safe_num(movie.get("tmdb_vote"),-1.0); votes=_safe_num(movie.get("tmdb_vote_count"),-1.0)
            tags=set(movie.get("tags",[]))
            if row_name=="Critically Acclaimed":
                # Critics and audiences both agree: Rotten Tomatoes 75%+ (its own bar for its best-reviewed
                # films) and IMDb 7.5+. A missing score can't vouch for a movie, so the known one must clear its bar.
                critics_ok = rt>=75 if rt>=0 else None
                viewers_ok = imdb>=7.5 if imdb>=0 else ((tv>=7.5 and votes>=1500) if tv>=0 else None)
                if critics_ok is None and viewers_ok is None:
                    return "Critically Acclaimed" in tags
                return critics_ok is not False and viewers_ok is not False
            if row_name=="Hidden Gems":
                quality=rt>=75 or imdb>=7.0 or (tv>=7.0 and votes>=150) or "Hidden Gem" in tags
                # Little known: under 4,000 TMDB votes; if votes are missing, outside the 20% most-loved
                # MovieLens movies; if neither is known, TMDB popularity. Unknown never counts as hidden.
                fans=fan_percentile(movie)
                if votes>=0:
                    little_known=votes<4000
                elif fans is not None:
                    little_known=fans<0.80
                else:
                    little_known=_safe_num(movie.get("popularity"),0.0)>0 and _pop_now(movie)<0.35
                little_known=little_known or "Hidden Gem" in tags
                return quality and little_known
            if row_name=="Something Different":
                return movie.get("genre") not in set(p.get("genres",[]))
            if row_name in ADAPTIVE_ROWS:
                return ADAPTIVE_ROWS[row_name](movie)
            return True


        def _row_candidates(row_name, already_used):
            available=[item for item in ranked if item[1]["title"] not in already_used]
            scored=[]
            for display_match,movie in available:
                memo=base_memo.get(id(movie))
                if memo is not None:
                    # Same personalized score in every row; only the row objective differs.
                    base,display_match=memo
                else:
                    components=score_movie_components(movie,p,st.session_state.adventure,st.session_state.review_priority,semantic_similarity=semantic_by_id.get(id(movie),0.5))
                    base=components["raw_score"]
                    # Supervised features stay exactly as logged at training time (pre-CF),
                    # so the Save/Skip model never sees train/serve skew.
                    model_match_by_title[movie["title"]]=display_match
                    ml_context=dict(components)
                    ml_context.update({"model_score":base,"decision_utility":components.get("decision_utility",base),"match":display_match,"position":2})
                    content_memo[id(movie)]=(base,dict(ml_context))
                    _ci=_cf_idx(movie) if ltr_aff is not None else None
                    cf=float(ltr_aff[_ci]) if _ci is not None else cf_affinity(movie,cf_user)
                    cf_source_by_title[movie["title"]]="ranker" if _ci is not None else "fans"
                    if cf is None:
                        cf=_nr_affinity(movie,nr_view)
                        cf_source_by_title[movie["title"]]="new" if cf is not None else None
                    ml_context["cf_affinity"]=cf if cf is not None else 0.5
                    if cf is not None:
                        base=CONTENT_WEIGHT*base+(1-CONTENT_WEIGHT)*cf
                        cf_by_title[movie["title"]]=cf
                    learned_probability=predict_success(learning_result,ml_context)
                    if learned_probability is not None:
                        base=0.78*base+0.22*learned_probability
                        personal_by_title[movie["title"]]=float(learned_probability)
                    # The % shown to users reflects the final blended ranking score.
                    display_match=_calibrated_match_percent(base,p)
                    base_memo[id(movie)]=(base,display_match)
                section=_row_signal(row_name,movie)
                # The learned profile remains dominant in every row. The section signal
                # changes the objective, not the underlying personalization system.
                if row_name=="Top Matches for You":
                    objective=base+0.06*_pop_now(movie)   # current movies surface; fit still dominates
                elif row_name=="Critically Acclaimed":
                    objective=0.70*base+0.30*section
                elif row_name=="Hidden Gems":
                    objective=0.72*base+0.28*section
                elif row_name in ADAPTIVE_ROWS:
                    # The row's kind is the hard filter; within it, your personal fit decides.
                    objective=base+(0.06*_pop_now(movie) if row_name=="Recent Releases for You" else 0.0)
                else:  # Something Different: serendipity = fans-like-you love it, but it's unlike your usual picks
                    cf_v=cf_by_title.get(movie["title"])
                    sem=semantic_by_id.get(id(movie),0.5)
                    seren=max(0.0,min(1.0,((cf_v if cf_v is not None else 0.5)-sem+1.0)/2.0))
                    objective=0.55*base+0.25*seren+0.20*section
                # Freshness for returning viewers: discount ignored repeats, lightly vary near-ties.
                objective-=FATIGUE_STEP*min(fatigue.get(movie["title"],0),FATIGUE_CAP)
                objective+=VARIETY_SPREAD*visit_variety(movie["title"])
                scored.append((objective,base,display_match,movie))

            # Section objective chooses membership. Within that objective, stronger core
            # personalized fit breaks ties, so every row remains grounded in the same model.
            # Qualifying movies always come first, so each section is true to its name;
            # non-qualifiers only backfill if the section would otherwise be empty.
            scored.sort(key=lambda x:(_qualifies(row_name,x[3]),x[0],x[1]),reverse=True)
            n_ok=sum(1 for x in scored if _qualifies(row_name,x[3]))
            if n_ok>=4 or row_name in ADAPTIVE_ROWS:
                scored=[x for x in scored if _qualifies(row_name,x[3])]   # adaptive rows never borrow other kinds
            if row_name=="Top Matches for You":
                # Top Matches is exactly your best fits, in order, so no later row can hold a better match.
                return [(display_match,movie) for _,_,display_match,movie in scored]
            diversified=mmr_rerank(scored,limit=min(12,len(scored)),relevance_lambda=0.74)
            chosen={item[3]["title"] for item in diversified}
            ordered=diversified+[item for item in scored if item[3]["title"] not in chosen]
            return [(display_match,movie) for _,_,display_match,movie in ordered]

        # Reserve distinct movies for each row before rendering. This prevents a title from
        # migrating into another section during the same refresh and keeps every row populated.
        row_order=["Top Matches for You","Critically Acclaimed","Hidden Gems",fourth_row_name()]
        row_choices={name: [] for name in row_order}
        row_candidate_queues={name: [] for name in row_order}

        # Tonight's Pick: the single best personalized match, preferring the viewer's
        # own streaming services and falling back to any service when none are chosen.
        top_all=_row_candidates("Top Matches for You",set())
        if _mood is not None and top_all:
            # A mood re-orders Top Matches: half how well each movie fits you, half how well it fits the words.
            import numpy as _np
            _n=len(top_all)
            _ms=[float(_mood[i]) if (i:=_cf_idx(m)) is not None else 0.0 for _,m in top_all]
            _pos=_mood[_mood>0]
            _thr=float(_np.quantile(_pos,0.95)) if len(_pos) else 1.0
            _hit=[j for j in range(_n) if _ms[j]>=_thr]          # movies fans really describe that way
            if len(_hit)>=4:
                _mrank={j:r for r,j in enumerate(sorted(_hit,key=lambda j:-_ms[j]))}
                _frank={j:r for r,j in enumerate(_hit)}
                _first=sorted(_hit,key=lambda j:0.5*_frank[j]+0.5*_mrank[j])
                _hs=set(_hit)
                top_all=[top_all[j] for j in _first]   # only movies that fit the mood, even after many Skips
        _src=_like_source()
        _lookup=_mood_spec().get("lookup")
        _personal_top=list(top_all)          # a title lookup leaves Tonight's Show as your personal best
        if _src and top_all:
            # "like X": Top Picks re-ranks by the What's next blend (fans who loved X, plus your own match).
            _sk=_src.get("title")
            top_all=[x for x in top_all if x[1].get("title")!=_sk]
            _scored=[(_like_score(x[1],_src),x) for x in top_all]
            _close=[(v,x) for v,x in _scored if v>0.5 and float(x[0] or 0)>=45]   # close AND a real fit for you
            if len(_close)>=4:
                _scored=_close
            # 80% how close it is, 20% how well it fits you: the What's Next blend that beat every lower
            # similarity weight on held-out viewers, so tonight's search leads and your profile still counts.
            top_all=[x for _,x in sorted(_scored,key=lambda t:-(WHATS_NEXT_SIM*t[0]+(1-WHATS_NEXT_SIM)*float(t[1][0] or 0)/100.0))]
            # Shorts (under 40 minutes) can sit close to a movie in fan data but aren't what "like X" means.
            _ids12=get_movie_identity_batch(tuple((m["title"],int(m.get("year") or 0),int(m.get("tmdb_id") or 0)) for _,m in top_all[:16]))
            top_all=[x for x in top_all[:16] if int((_ids12.get(x[1]["title"]) or {}).get("runtime") or 999)>=40]+top_all[16:]
        top_all=_time_filter(top_all,_tspec)
        tonight_pool=top_all[:40]       # any search (mood, time, a title, "like X") reaches Tonight's Show too
        tonight_watch=get_watch_availability_batch(
            tuple((m["title"],int(m.get("year") or 0)) for _,m in tonight_pool),"US"
        ) if tonight_pool else {}
        my_services=list(st.session_state.get("streaming_services") or [])
        fits=[item for item in tonight_pool if movie_on_services(tonight_watch.get(item[1]["title"]),my_services)]
        fit_titles={m["title"] for _,m in fits}
        tonight_queue=fits+[item for item in tonight_pool if item[1]["title"] not in fit_titles]
        reserved={tonight_queue[0][1]["title"]} if tonight_queue else set()
        reserved_series={_franchise(t) for t in reserved}

        # Team-draft interleave routed vs item-kNN-only for Top Matches (rule in src/interleave.py).
        # Tonight's Show and the other rows always use the routed ranking.
        top_matches_ordered=[item for item in top_all if item[1]["title"] not in reserved]
        il_teams, il_override = {}, {}
        if il_on and cf_user_knn is not None:
            import random as _random
            import bisect as _bisect
            b_scored=[]
            for _,movie in top_all:
                memo=content_memo.get(id(movie))
                if memo is None:
                    continue
                b_base,b_ctx=memo[0],dict(memo[1])
                cf_b=cf_affinity(movie,cf_user_knn)
                b_ctx["cf_affinity"]=cf_b if cf_b is not None else 0.5
                if cf_b is not None:
                    b_base=CONTENT_WEIGHT*b_base+(1-CONTENT_WEIGHT)*cf_b
                b_learned=predict_success(learning_result,b_ctx)
                if b_learned is not None:
                    b_base=0.78*b_base+0.22*b_learned
                t=movie["title"]
                b_obj=(b_base+0.06*_pop_now(movie)-FATIGUE_STEP*min(fatigue.get(t,0),FATIGUE_CAP)
                       +VARIETY_SPREAD*visit_variety(t))
                b_scored.append((b_obj,b_base,cf_b,movie))
            b_scored.sort(key=lambda x:(x[0],x[1]),reverse=True)
            a_map={m["title"]:(dm,m) for dm,m in top_all}
            a_ids=[m["title"] for _,m in top_matches_ordered][:60]
            b_ids=[x[3]["title"] for x in b_scored if x[3]["title"] not in reserved][:60]
            merged,il_teams=team_draft(a_ids,b_ids,_random.Random(),limit=40)
            # Cards picked by item-kNN show item-kNN's own score and love chance, so neither side looks better.
            b_asc=sorted(x[1] for x in b_scored)
            b_info={x[3]["title"]:x for x in b_scored}
            for t in merged:
                if il_teams.get(t)=="knn" and t in b_info:
                    _,b_base,cf_b,_m=b_info[t]
                    above=len(b_asc)-_bisect.bisect_right(b_asc,b_base)
                    il_override[t]={"match":_calibrated_match_percent(b_base,p),"cf":cf_b,
                                    "top_pct":max(1,-(-100*(above+1)//max(1,len(b_asc))))}
            top_matches_ordered=[(il_override.get(t,{}).get("match",a_map[t][0]),a_map[t][1]) for t in merged if t in a_map]
        st.session_state.interleave_teams=il_teams
        if il_teams:
            from src.telemetry import track
            _il=_interleave_session()
            if st.session_state.get("_il_shown")!=_il:
                track(st.session_state,"interleave_shown",il_session=_il)
                st.session_state._il_shown=_il

        # Pass 1: category-specific ordering with strict cross-row de-duplication.
        # Keep the remaining ranked candidates as a replacement queue so one card can
        # advance without rebuilding the entire Showroom.
        for row_name in row_order:
            if row_name=="Top Matches for You":
                ordered=list(top_matches_ordered)
            else:
                ordered=_row_candidates(row_name,reserved)
            ordered=_time_filter(ordered,_tspec)    # "under 2 hours": a filter; order stays the models'
            if row_name!="Top Matches for You":
                ordered=_mood_first(ordered)        # a mood reaches every row, not only Top Picks
                if _src:
                    # "like X" reaches every row too: the closest fifth moves up, each row keeps its own rules.
                    _sims=[(_like_score(m,_src),k) for k,(_,m) in enumerate(ordered) if m.get("title")!=_src.get("title")]
                    if _sims:
                        import numpy as _np
                        _cut=float(_np.quantile([v for v,_ in _sims],0.8))
                        _close={k for v,k in _sims if v>=_cut}
                        ordered=[ordered[k] for k in sorted(_close)]+[it for k,it in enumerate(ordered) if k not in _close and it[1].get("title")!=_src.get("title")]
            # One movie per series across the Showroom, so rows don't fill up with sequels.
            picks=[]
            for item in ordered:
                if len(picks)>=4:
                    break
                if item[1]["title"] in reserved or _franchise(item[1]["title"]) in reserved_series:
                    continue
                picks.append(item)
                reserved_series.add(_franchise(item[1]["title"]))
            row_choices[row_name].extend(picks)
            row_candidate_queues[row_name].extend(ordered)
            reserved.update(movie["title"] for _,movie in picks)

        # Pass 2: if any category pool is thin, fill it with the next-best personalized
        # candidates that have not appeared elsewhere. This keeps every section alive.
        for row_name in row_order:
            need=4-len(row_choices[row_name])
            if need<=0 or row_name in ADAPTIVE_ROWS:
                continue
            fallback=_time_filter([item for item in ranked if item[1]["title"] not in reserved
                                   and _franchise(item[1]["title"]) not in reserved_series],_tspec)
            extra=fallback[:need]
            reserved_series.update(_franchise(m["title"]) for _,m in extra)
            row_choices[row_name].extend(extra)
            reserved.update(movie["title"] for _,movie in extra)

        visible_movies=[movie for row_name in row_order for _,movie in row_choices.get(row_name,[])]
        visible_titles={movie["title"] for movie in visible_movies}
        warm_backups=[]
        for row_name in row_order:
            for _,candidate in row_candidate_queues.get(row_name,[]):
                if candidate["title"] not in visible_titles:
                    warm_backups.append(candidate)
                    break
        metadata_movies=visible_movies+warm_backups
        # Deduplicate while preserving the ranked order.
        metadata_movies=list({m["title"]:m for m in metadata_movies}.values())
        visible_movie_keys=tuple((movie["title"], int(movie.get("year") or 0)) for movie in metadata_movies)
        visible_identity_keys=tuple((movie["title"], int(movie.get("year") or 0), int(movie.get("tmdb_id") or 0)) for movie in metadata_movies)
        watch_by_title=get_watch_availability_batch(visible_movie_keys,"US")
        for row_name in row_order:
            if il_teams and row_name=="Top Matches for You":
                continue   # interleaved order is shown as drafted, so neither ranker gets the top spots
            row_choices[row_name].sort(key=lambda item:0.91*(item[0]/100.0)+0.09*service_availability_utility(watch_by_title.get(item[1]["title"])),reverse=True)

        recommendation_context={}
        for row_name in row_order:
            for position,(match,movie) in enumerate(row_choices.get(row_name,[]),start=1):
                availability_value=service_availability_utility(watch_by_title.get(movie["title"]))
                comps=score_movie_components(
                    movie,p,st.session_state.adventure,st.session_state.review_priority,
                    semantic_similarity=semantic_by_id.get(id(movie),0.5),
                    availability_score=availability_value,
                )
                recommendation_context[movie["title"]]={
                    "row":row_name,"position":position,"match":model_match_by_title.get(movie["title"],match),
                    "model_score":round(float(comps.get("raw_score",0)),6),
                    "decision_utility":round(float(comps.get("decision_utility",comps.get("raw_score",0))),6),
                    **{k:round(float(comps.get(k,.5)),6) for k in ["genre_affinity","trait_affinity","semantic_similarity","quality_alignment","discovery_alignment","priority_alignment","availability_alignment","vote_confidence","profile_confidence"]},
                    "cf_affinity":round(float(cf_by_title.get(movie["title"],0.5)),6),
                    "candidate_source":movie.get("candidate_source"),
                    "model_version":"v5.191",
                    **_interleave_fields(row_name,movie["title"]),
                }
        st.session_state.recommendation_context=recommendation_context
        record_impressions(st.session_state,recommendation_context)
        identity_by_title=get_movie_identity_batch(visible_identity_keys)
        get_landscape_batch(visible_identity_keys)   # warms the cache so each card's 16:9 art loads at once
        showroom_poster_map={title: data.get("poster_url") for title, data in identity_by_title.items()}
        live_rating_keys=tuple((movie["title"], int(movie.get("year") or 0), (identity_by_title.get(movie["title"], {}) or {}).get("imdb_id") or "") for movie in metadata_movies)
        live_ratings_by_title=get_live_ratings_batch(live_rating_keys)

        # Persist the ranked queues and current slots. Card fragments use these to
        # replace exactly one movie without rerunning the four-row Showroom.
        payloads={}
        queues={}
        for row_name in row_order:
            queue_titles=[]
            for match,movie in row_candidate_queues.get(row_name,[])[:80]:
                title=movie["title"]
                queue_titles.append(title)
                payloads.setdefault(title,{
                    "match":match,
                    "movie":movie,
                    "semantic_similarity":semantic_by_id.get(id(movie),.5),
                    "cf":cf_by_title.get(movie["title"]),
                    "model_match":model_match_by_title.get(movie["title"],match),
                })
            queues[row_name]=queue_titles
        slots={}
        for row_name in row_order:
            for slot_index,(match,movie) in enumerate(row_choices.get(row_name,[])):
                title=movie["title"]
                slots[_showroom_slot_key(row_name,slot_index)]=title
                payloads.setdefault(title,{
                    "match":match,
                    "movie":movie,
                    "semantic_similarity":semantic_by_id.get(id(movie),.5),
                    "cf":cf_by_title.get(movie["title"]),
                    "model_match":model_match_by_title.get(movie["title"],match),
                })
        st.session_state.tonight_pool=[m["title"] for _,m in tonight_queue]
        # Deeper ranked list so a service filter (e.g. Netflix only) can reach past the top 40.
        deep=top_all[:120]
        st.session_state.tonight_deep_pool=[m["title"] for _,m in deep]
        for match,movie in deep:
            payloads.setdefault(movie["title"],{
                "match":match,
                "movie":movie,
                "semantic_similarity":semantic_by_id.get(id(movie),.5),
                "cf":cf_by_title.get(movie["title"]),
                "model_match":model_match_by_title.get(movie["title"],match),
            })
        st.session_state.showroom_undo={}
        st.session_state.showroom_pill_labels={}
        if tonight_queue:
            for match,movie in tonight_queue:
                payloads.setdefault(movie["title"],{
                    "match":match,
                    "movie":movie,
                    "semantic_similarity":semantic_by_id.get(id(movie),.5),
                    "cf":cf_by_title.get(movie["title"]),
                    "model_match":model_match_by_title.get(movie["title"],match),
                })
        # Rank every scored movie by its final blended score, so "Top N%" is exact.
        _bases = sorted((b for b, _ in base_memo.values()), reverse=True)
        _pool = len(_bases)
        if _pool:
            import bisect
            _asc = sorted(_bases)
            for _pl in payloads.values():
                _memo = base_memo.get(id(_pl.get("movie")))
                if _memo is None:
                    continue
                _above = _pool - bisect.bisect_right(_asc, _memo[0])   # movies scored strictly higher
                _pl["fit_top_pct"] = max(1, -(-100 * (_above + 1) // _pool))
                _pl["fit_rank"] = int(_above + 1)
                _pl["fit_pool"] = _pool
        # What each model said about each movie, for the "why it's here" popup.
        from src import cf_model as _cfm2
        _full2, _ = _cfm2._history_cut()
        _rk2 = _cfm2._ranker_for(_signals) if _signals else None
        _cf_name = ("EASE" if _full2 is not None and _rk2 is _full2 else
                    "RP3beta" if _rk2 is not None and _rk2 is _cfm2._load_rank() and _rk2 is not _cfm2._load() else "item-kNN")
        _sems = sorted(v for v in semantic_by_id.values() if isinstance(v, (int, float)))
        import bisect as _bis
        for _t, _pl in payloads.items():
            _pl["personal"] = personal_by_title.get(_t)
            _cm = content_memo.get(id(_pl.get("movie")))
            _pl["content"] = float(_cm[0]) if _cm else None
            _pl["cf_source"] = cf_source_by_title.get(_t)
            _pl["cf_name"] = _cf_name
            _pl["personal_n"] = int(learning_result.samples or 0) if getattr(learning_result, "ready", False) else 0
            _sv = _pl.get("semantic_similarity")
            if _sems and isinstance(_sv, (int, float)):
                _pl["tone_pct"] = int(round(100 * _bis.bisect_left(_sems, _sv) / len(_sems)))
        for _t, _ov in il_override.items():
            if _t in payloads:
                payloads[_t].update({"match": _ov["match"], "cf": _ov["cf"], "fit_top_pct": _ov["top_pct"]})
        st.session_state.showroom_payloads=payloads
        st.session_state.showroom_row_queues=queues
        st.session_state.showroom_slots=slots
        _cache = dict(st.session_state.get("_build_cache") or {})
        _cache[_bk] = {k: st.session_state.get(k) for k in _BUILD_KEYS}
        st.session_state._build_cache = dict(list(_cache.items())[-4:])     # the last 4 builds
        identity_cache=dict(st.session_state.get("showroom_identity_cache") or {})
        identity_cache.update(identity_by_title)
        st.session_state.showroom_identity_cache=identity_cache
        watch_cache=dict(st.session_state.get("showroom_watch_cache") or {})
        watch_cache.update(tonight_watch)
        watch_cache.update(watch_by_title)
        st.session_state.showroom_watch_cache=watch_cache
        rating_cache=dict(st.session_state.get("showroom_rating_cache") or {})
        rating_cache.update(live_ratings_by_title)
        st.session_state.showroom_rating_cache=rating_cache

    # Step 3 answers decide which section comes right after Top Matches. Display order only:
    # which movie lands in which row is unchanged, so this never costs accuracy.
    _asked = list(st.session_state.get("more_of") or [])
    _middle = sorted(["Critically Acclaimed","Hidden Gems"], key=lambda r: (r not in _asked, _asked.index(r) if r in _asked else 0))
    row_specs=["Top Matches for You"] + _middle + [fourth_row_name()]

    with tabs[0]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        st.button("Refresh", key="refresh_showroom")   # hidden; clicked when you return here after rating on Saved/Seen
        _lib_mark(showroom=True)
        # The search sits inside the Showroom tab: it only changes Showroom rows, so Saved, Seen and
        # Profile stay clean. One keyed slot holds chips or suggestions, so the layout never shifts.
        from src.mood import available as _mood_ready
        if _mood_ready():
            render_search_box()
            if _mood_text():
                render_search_card()
        # One unified guide, like the Apple TV app's Home: no toggles. Tonight's Show, Top Picks,
        # Shows for You, and More to explore (critics' picks, hidden gems and your fourth row mixed in
        # one row, each card labeled), so there are never more than three rows under the hero.
        from src import tv as _tv
        render_tonight_pick_fragment()
        row_notes={
            "Top Matches for You":_new_picks_note(row_choices.get("Top Matches for You", [])),
            "Critically Acclaimed":"Highly rated movies that still fit what you like",
            "Hidden Gems":"Less-known movies you’re likely to love",
            "Something Different":"Outside your usual genres, but still likely to click",
            **{name: note for name, note in ADAPTIVE_NOTES.items()},
        }
        _floor = fit_floor()

        def _strong_slots(row_name, n):
            """Slots in a row worth showing; weak picks are swapped for the next strong one first."""
            pays = st.session_state.get("showroom_payloads") or {}
            def ok(i):
                slots = st.session_state.get("showroom_slots") or {}
                pay = pays.get(slots.get(_showroom_slot_key(row_name, i))) or {}
                top = pay.get("fit_top_pct")
                return row_name == "Top Matches for You" or _floor is None or not isinstance(top, (int, float)) or top <= _floor
            for i in range(n):
                if not ok(i):
                    _advance_showroom_slot(row_name, i)
            slots = st.session_state.get("showroom_slots") or {}
            return [i for i in range(n) if ok(i) and slots.get(_showroom_slot_key(row_name, i))]

        def _header(title, note):
            st.markdown(f'<div class="showroom-row showroom-row-header"><div class="showroom-row-title">{title}</div>'
                        f'<div class="row-model-note">{html.escape(note)}</div></div>', unsafe_allow_html=True)

        def _draw_cards(key, cells):
            with st.container(key=f"showroom_swipe_{key}"):
                cols = st.columns(4)
                for c, (rname, rindex, slot) in enumerate(cells[:4]):
                    with cols[c]:
                        render_showroom_card_fragment(rname, rindex, slot)

        top_name = row_specs[0]
        _header("Top Picks for You", _mood_line() or row_notes[top_name])
        top_slots = _strong_slots(top_name, len(row_choices.get(top_name, [])))
        if top_slots:
            _draw_cards(0, [(top_name, 0, i) for i in top_slots])
        else:
            st.caption("Refreshing personalized matches…")

        if _tv.available():
            from src.ui.shows import render_shows
            render_shows({"movie_thumb": movie_thumb, "card_html": card_html, "watch_line_html": watch_line_html,
                          "record_event": record_event, "queue_profile_save": queue_profile_save, "signals": _cf_signals,
                          "spec": _mood_spec()}, 4)

        explore = [(r, row_specs.index(r)) for r in row_specs[1:]]
        pools = {r: _strong_slots(r, len(row_choices.get(r, []))) for r, _ in explore}
        cells, depth = [], 0
        while len(cells) < 4 and any(len(v) > depth for v in pools.values()):
            for r, idx in explore:
                if len(pools[r]) > depth and len(cells) < 4:
                    cells.append((r, idx, pools[r][depth]))
            depth += 1
        if cells:
            _header("More to explore", "Critics’ picks, hidden gems, and something new, all chosen for you")
            _draw_cards("explore", cells)
        _remember_shown(row_choices)
        rating_note = "" if omdb_configured() else " IMDb and Rotten Tomatoes ratings require OMDB_API_KEY in Streamlit Secrets."
        st.markdown(
            '<div class="watch-attribution">Streaming availability for the United States. Data by JustWatch via TMDB. '
            'IMDb and Rotten Tomatoes ratings are retrieved through OMDb and cached for 14 days. '
            'This product uses the TMDB API but is not endorsed or certified by TMDB.' + rating_note + '</div>',
            unsafe_allow_html=True
        )

    with tabs[1]:
        _saved_tab()

    with tabs[2]:
        _seen_tab()

    with tabs[3]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        render_live_profile()
        st.markdown('<div class="profile-tab-reset"></div>', unsafe_allow_html=True)
        _lately = lately_genres()
        if _lately:
            _l = list(_lately)
            _lst = _l[0] if len(_l) == 1 else (" and ".join(_l) if len(_l) == 2 else ", ".join(_l[:-1]) + ", and " + _l[-1])
            st.markdown(f'<div class="privacy-note">Lately you’ve been saving {html.escape(_lst)} movies.</div>',
                        unsafe_allow_html=True)
        # One row of three matching pills.
        edit, reset, _ = st.columns([1.5, 1.3, 3.7], gap="small")
        with edit:
            # Revisit Steps 1-3 with every choice filled in; the models use the new answers on return.
            st.button("Edit My Answers", key="edit_preferences", use_container_width=True, on_click=go, args=("shelf",),
                      help="Change your likes, genres, and other setup answers.")
        with reset:
            if st.button("Reset Profile", key="reset_profile_tab", use_container_width=True,
                         help="Start over: clears your likes, saves, and answers in this browser."):
                reset_profile_state()
                st.rerun(scope="app")
        st.toggle("Share anonymous usage counts", value=not st.session_state.get("analytics_opt_out", False),
                  key="_share_counts", on_change=_set_opt_out,
                  help="Counts like visits and saves, tied to a random ID. Never movie titles, names, emails, or location.")
        st.markdown('<div class="privacy-note">Your profile stays in this browser. iCinema has no accounts '
                    'and never sells your data.</div>', unsafe_allow_html=True)
        # A utility, not a profile action: a quiet link under the privacy line.
        with st.container(key="move_profile_link"):
            with st.popover("Move to Another Device"):
                try:
                    _host = st.context.headers.get("host") or "icinema.streamlit.app"
                except Exception:
                    _host = "icinema.streamlit.app"
                st.markdown('<div class="why-pop-head" style="font-size:1rem">Open this link on your other device</div>'
                            '<div class="why-pop-line">It carries your likes, saves, and answers. No account, nothing personal. '
                            'Anyone with the link can load this profile.</div>', unsafe_allow_html=True)
                st.code(f"https://{_host}/?p={_encode_profile_link(profile_snapshot())}", language=None)



    # tabs9: counts beside the fixed tab labels, found by tab id (labels never change, so
    # the open tab stays), and a short fade so switching tabs feels smooth.
    st.markdown(
        '<style>'
        '[data-testid="stTabs"] [role="tab"][id$="-tab-1"] p::after,'
        '[data-testid="stTabs"] [role="tablist"] > [role="tab"]:nth-of-type(2) p::after{content:" (%d)"}'
        '[data-testid="stTabs"] [role="tab"][id$="-tab-2"] p::after,'
        '[data-testid="stTabs"] [role="tablist"] > [role="tab"]:nth-of-type(3) p::after{content:" (%d)"}'
        '[data-testid="stTabs"] [role="tabpanel"]{animation:icn-appear .18s ease both}'
        '</style>'
        % (len(st.session_state.saved), len(st.session_state.seen)),
        unsafe_allow_html=True,
    )

    pass  # saved once at the end of the full run

screen=st.session_state.screen
try:

    if screen=="welcome":
        logo()
        st.markdown('<div class="hero-title">Always something great to watch.</div>',unsafe_allow_html=True)
        st.markdown('<div class="hero-subtitle">Less scrolling, more watching. Nine models learn what you love and find your next movie or show, where to stream it, and how likely you are to love it, getting sharper every time you use it.</div>',unsafe_allow_html=True)
        st.button("Start Personalizing →", type="primary", key="start_personalizing", on_click=go, args=("shelf",))
        st.markdown('<div class="home-start-note">Like a few movies and answer a few quick questions.</div>', unsafe_allow_html=True)

        # Show the product: what's big right now, the kind of movie iCinema finds for you.
        _hits = _current_hits(6, set())
        if len(_hits) >= 4:
            st.markdown(
                '<div class="home-strip">' + "".join(
                    f'<img src="{html.escape(str(m["poster_url"]), quote=True)}" alt="{html.escape(str(m.get("title", "")))}">'
                    for m in _hits if str(m.get("poster_url", "")).startswith("https://")) + '</div>',
                unsafe_allow_html=True)

        # Proof, read from the results file so it always matches the README.
        _off = load_offline_results() or {}
        _lift = (_off.get("lifts_three_likes_vs_popularity") or {}).get("hit@1")
        _tested = _off.get("held_out_users")
        if isinstance(_lift, (int, float)):
            st.markdown(
                '<div class="home-proof">'
                f'<div class="home-proof-num">+{int(_lift)}%</div>'
                f'<div class="home-proof-text"><strong>More first picks you’ll love than going with what’s popular.</strong>'
                + (f'<span>Tested on {_tested:,} movie fans iCinema had never seen.</span>' if isinstance(_tested, int) else '')
                + '</div></div>', unsafe_allow_html=True)

    elif screen=="shelf":
        render_shelf_fragment()

    elif screen=="taste":
        render_taste_fragment()

    elif screen=="more":
        render_more_fragment()

    elif screen=="profile":
        logo()
        p=current_profile()
        render_cinema_profile(p)

        with st.container(key="nav_row_profile"):
            back, cont, _ = st.columns([1, 2, 4], gap="small")
            with back:
                st.button("← Back", key="back_profile", use_container_width=True, on_click=go, args=("more",))
            with cont:
                st.button("Enter My Showroom →", type="primary", key="enter_showroom", use_container_width=True, on_click=go, args=("showroom",))

    elif screen=="showroom":
        logo()
        p=current_profile()
        from src.mood import available as _mood_ready
        # Header and search live in one fixed container: whatever the search shows (chips or suggestions),
        # the tabs below never change position, so a rerun never leaves a faded copy of them behind.
        with st.container(key="showroom_top"):
          st.markdown(
            '<div class="showroom-header">'
            '<div class="showroom-heading">Your Showroom</div>'
            '<div class="showroom-intro">Picked for you, and sharper with every choice you make.</div>'
            '</div>',
            unsafe_allow_html=True
          )

        with st.container(key="showroom_body"):
            render_showroom_fragment(p)
except Exception as _exc:
    _friendly_error(_exc)

# Persist the latest profile/history after the page has processed this run.
persist_profile_if_needed()
_ver_mark()
st.session_state._in_full_run = False

# V5.90 is implemented through CSS overrides injected above in the main style block.

# V5.99 tab content alignment polish injected via CSS override.

