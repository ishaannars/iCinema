
import time as _time
_BOOT = _time.perf_counter()
import html
from pathlib import Path
from urllib.parse import quote_plus
import json
import re
import streamlit as st
from src.app_state import (  # session helpers, split out of app.py
    restore_profile,
    _compact_events,
    queue_profile_save,
    _too_soon,
    _ver_mark,
    _lib_mark,
    _friendly_error,
    _timing_on,
    _format_seconds,
    _remember_movie,
    _drop_last_event,
)
from src.tested_settings import (  # tuned numbers from data/ test results
    _tested_blend_weights,
    _tested_knobs,
    _tested_shelf,
    _like_rerank_ships,
    load_offline_results,
    _similar_weights,
)
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


def _log_time(label, start):
    if _timing_on():
        import sys
        print(f"[timing] {label}: {(_time.perf_counter() - start) * 1000:.0f} ms", file=sys.stderr, flush=True)


_log_time("imports", _BOOT)
st.set_page_config(page_title="iCinema", page_icon=str(Path(__file__).parent / "assets" / "favicon.png"), layout="wide", initial_sidebar_state="collapsed")

from src.ui import app_css, css_chunks
from src.screens.home import render_home
from src.screens.ready import render_ready_summary
from src.love import love_line, love_chance, fit_floor, test_viewers as love_test_viewers
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
from src.model_names import MODELS_TOTAL, odds_model_on
from src.ui.watch import (STREAMING_SERVICES, PROVIDER_LINKS, _provider_key, _on_service, provider_watch_url,
                          watch_options, watch_line_html, concise_availability_text, movie_on_services)

# The stylesheet goes out in a few <style> blocks under 60k characters each: one ~200k block was being cut
# off in the browser, silently dropping every rule past that point (Batches 56-60's newest rules).
for _css_part in css_chunks(app_css()):
    st.markdown("<style>" + _css_part + "</style>", unsafe_allow_html=True)

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
    }

def _snapshot_signature(snapshot):
    import hashlib
    return hashlib.md5(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()


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


def _lib_bump():
    """A choice made on Saved or Seen (thumbs, Mark Seen, Remove): the Showroom re-ranks when you go back to it."""
    st.session_state._lib_ver = int(st.session_state.get("_lib_ver") or 0) + 1


def _saved_to_seen(title, movie):
    mark_movie_seen(title, movie)
    _lib_bump()


RECOGNIZABLE_SHELF_TITLES = [
    "Dune: Part Two", "Blade Runner 2049", "The Prestige", "Prisoners",
    "Nightcrawler", "The Truman Show", "The Grand Budapest Hotel",
    "No Country for Old Men", "Before Sunrise", "Train to Busan",
    "Your Name", "Princess Mononoke", "Akira", "Ex Machina",
    "Past Lives", "The Holdovers", "The Wailing", "The Handmaiden",
    "Memories of Murder", "The Worst Person in the World",
]


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
    if st.session_state.get("_smoke_typed") is not None:     # tools/smoke_app.py types here (it can't type into st_keyup)
        return str(st.session_state._smoke_typed)
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


def like_search_result(movie):
    """Step 1 search: tapping a poster likes it right away (the same as Like on the shelf)."""
    movie = dict(movie or {})
    title = movie.get("title")
    if not title:
        return
    if movie.get("external") or movie.get("tmdb_id") or not get_movie(title):
        st.session_state.external_movies[title] = movie
    st.session_state.likes.add(title)
    st.session_state.favorites.discard(title)
    if title not in st.session_state.selection_order:
        st.session_state.selection_order.append(title)
    st.session_state.search_selected_movie = None
    st.session_state.search_selected_title = None
    queue_profile_save()

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
    """Undo an accidental Seen: drop it and its model signal; restore it to Saved if it came from there."""
    _lib_bump()
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
        titled = landscape and str(poster_url).endswith("#titled")     # the title is painted into the art
        poster_html = (f'<div class="poster has-image{" landscape" if landscape else ""}{" fallback" if portrait else ""}{" titled" if titled else ""}">'
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
    if rated.get(title) in (1, -1):
        # Logged like a Save or Skip, so the personal model can learn from it if its test passed
        # (training/confirm_seen_thumbs.py); otherwise the event is kept but not used for training.
        record_event(st.session_state, "seen_loved" if rated[title] == 1 else "seen_disliked", title,
                     _current_recommendation_context(title))
    _lib_bump()
    queue_profile_save()


from src.descriptions import card_description, expanded_card_description, quick_card_description, tonight_description  # card text rules (unit-tested)


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


# Content vs "viewers like you" in every row, and similarity vs personal match in What's next.
CONTENT_WEIGHT, WHATS_NEXT_SIM = _tested_blend_weights()


_KNOBS = _tested_knobs()


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
    _inside = ([(True, "Fans like you", "Inside the ranker · item-kNN", "", f"Movies the same {_fans_n} fans loved together."),
                (True, "Fans with less mainstream likes", "Inside the ranker · RP3beta", "", "A random-walk model that finds less obvious fan favorites."),
                (True, "Fans with long histories", "Inside the ranker · EASE", "", "Learns from viewers who rated many movies, for detailed profiles.")]
               if _ltr_on else [])
    from src import seq_model as _seqp
    _order_row = []
    if _seqp.main_available():
        _ord = round(_fans * _seqp.main_weight())
        _fans_left = _fans - _ord
        first = (first[0], first[1], first[2], f"{_fans_left}%", first[4])
        _order_row = [(True, "What you liked last", "Order model · Markov chain", f"{_ord}%",
                       "What people like next after your three most recent picks; it beat the fan ranking on held-out viewers.")]
    else:   # always listed, so the Profile shows all 11 models whether or not each is running
        _order_row = [(False, "What you liked last", "Order model · Markov chain", "",
                       "Off: its model file isn’t loaded right now.")]
    items = [
        first,
        *_inside,
        *_order_row,
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
        (odds_model_on(), "Your odds", "Calibration · isotonic regression", "",
         "Turns each score into a chance you’ll love it, checked against what test viewers did."),
    ]
    _running = sum(1 for it in items if it[0])      # each row is one model; the ranker's three fan models have their own rows
    _foot = "Weights were set in tests on movie fans the models never saw."
    if _ltr_on:
        _d = _ltr_mod.result() or {}
        if isinstance(_d.get("ndcg_learned"), (int, float)) and isinstance(_d.get("ndcg_current_blend"), (int, float)):
            _foot += (f" The ranker beat a fixed mix on those viewers "
                      f"(NDCG@10 {_d['ndcg_learned']:.3f} vs {_d['ndcg_current_blend']:.3f}).")
    models_html = (
        '<div class="pf-section"><div class="pf-title">What’s choosing your picks</div>'
        f'<div class="pf-sub">{MODELS_TOTAL} models: {MODELS_TOTAL - 1} pick, 1 sets the odds. {_running} are running for you now (filled dot). '
        'The percent is each model’s weight in your picks.</div>'
        '<div class="pf-models">'
        + "".join(f'<div class="pf-model"><span class="pf-dot{" on" if on else ""}"></span>'
                  f'<div class="pf-model-main"><div class="pf-model-name">{html.escape(name)}</div>'
                  f'<div class="pf-model-tech">{html.escape(tech)}</div></div>'
                  f'<div class="pf-model-share">{share}</div>'
                  f'<div class="pf-model-note">{html.escape(note)}</div></div>' for on, name, tech, share, note in items)
        + f'</div><div class="pf-foot">{html.escape(_foot)}</div></div>'
    )
    if not include_insights:
        # Before the Showroom, keep this page short: the model list opens on tap (it's always on the Profile tab).
        models_html = ('<details class="pf-collapse"><summary>See the models choosing your picks</summary>'
                       + models_html + '</details>')

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
                f'<div class="pf-pill-row"><span class="pf-pill">{html.escape(significance_note)}</span></div>'
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
        + '</div>'
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
    _inputs = [(_lk, "movie liked", "movies liked"), (_g, "genre", "genres"), (2, "preference", "preferences"),
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


def _remove_like_from_profile(title):
    """× on a like in Profile: remove it and rebuild the whole Showroom so every row stops using it."""
    remove_step1_selection(title)
    st.session_state._app_rerun = True


def _render_profile_likes():
    """Your likes, editable from the Showroom: small posters with ×, and a way to add more."""
    ss = st.session_state
    liked = [t for t in (ss.get("selection_order") or []) if t in ss.likes] + sorted(set(ss.likes) - set(ss.get("selection_order") or []))
    st.markdown('<div class="profile-likes-head">Your Likes</div>'
                '<div class="profile-likes-copy">Every pick starts from these. Tap × to remove one.</div>',
                unsafe_allow_html=True)
    if liked:
        ms = [get_movie(t, ss.external_movies) or {"title": t} for t in liked]
        need = tuple((m["title"], int(m.get("year") or 0)) for m in ms if not m.get("poster_url"))
        pm = get_poster_batch(need) if need else {}
        with st.container(key="profile_likes"):
            cols = st.columns(12, gap="small")
            for i, t in enumerate(liked):
                u = str(ms[i].get("poster_url") or pm.get(t) or "")
                with cols[i % 12]:
                    with st.container(key=f"selection_card_p{i}"):
                        st.markdown('<div class="sel-poster">'
                                    + (f'<img src="{html.escape(u, quote=True)}" alt="">' if u.startswith("https://")
                                       else f'<div class="live-hit-blank">{html.escape(t[:24])}</div>')
                                    + f'</div><div class="sel-cap"><span class="sel-state">{"Favorite" if t in ss.favorites else "Liked"}</span></div>',
                                    unsafe_allow_html=True)
                        if len(liked) > 1:   # × shows when you hover a poster (always on phones); the last like stays
                            st.button("×", key=f"remove_selection_p{i}", help=f"Remove {t}",
                                      on_click=_remove_like_from_profile, args=(t,))


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
        '<div class="page-top-heading">Step 1 of 2 — Rate the Shelf</div>'
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
    cols=None
    for i,movie in enumerate(shelf_movies):
        title=movie["title"]
        if i%5==0:
            cols=shelf_box.columns(5, gap="small")   # one row at a time: phones wrap it two across, in order
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
                # Own keyed box, so "stack Like over Favorite when the card is narrow" touches only these two.
                with st.container(key=f"shelf_actions_{i}_{movie.get('tmdb_id') or title}"):
                    # One action per movie: Like. "Loved it" comes later, after you've marked a movie Seen.
                    st.button(
                        "Like",
                        key=f"like_{i}_{movie.get('tmdb_id') or title}",
                        use_container_width=True,
                        on_click=rate_shelf_movie,
                        args=(movie, "like", i),
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
                # Same tiles as the Showroom search and cards: wide key art with the title in it; tap to pick.
                with st.container(key="step1_hits"):
                    # Tap a poster to like it. It moves to Your selections, where × takes it back.
                    _render_search_tiles(matches[:8], "search_result", lambda m: (m,), like_search_result)

            if already_selected_matches:
                selected_name = already_selected_matches[0]["title"]
                st.markdown(
                    f'<div class="search-already-selected">'
                    f'<strong>{html.escape(selected_name)}</strong> is already in your likes.'
                    f'</div>',
                    unsafe_allow_html=True
                )

            if not matches and not already_selected_matches:
                if tmdb_catalog_configured():
                    st.caption("No matches yet. Try another spelling or a shorter title.")
                else:
                    st.caption("Search is offline for a moment, so these matches come from iCinema’s own catalog.")

    with st.container(key="step1_letterboxd"):
        # One settings-style row, the same shape as the Privacy rows: a title, one line of why, and its
        # control on the right. The steps and the file picker open on tap, so the page stays calm.
        with st.container(key="import_card"):
            txt, ctl = st.columns([5, 1.3], vertical_alignment="center")
            with txt:
                st.markdown('<div class="imp-label">Import From Letterboxd or IMDb</div>'
                            '<div class="imp-note">Add every movie you’ve rated in one step.</div>', unsafe_allow_html=True)
            with ctl:
                with st.container(key="import_link"):
                    with st.popover("Import", use_container_width=True):
                        st.markdown('<div class="imp-pop-title">Import your ratings</div>'
                                    '<div class="imp-pop-row"><span>Letterboxd</span>Export your data from Settings, then upload the ZIP.</div>'
                                    '<div class="imp-pop-row"><span>IMDb</span>Export Your Ratings, then upload the CSV.</div>'
                                    '<div class="imp-pop-note">Movies you rated highly become likes. Your file stays in this browser.</div>',
                                    unsafe_allow_html=True)
                        st.file_uploader("Letterboxd export (ZIP or ratings.csv) or IMDb ratings.csv", type=["zip", "csv"],
                                         key="lb_upload", label_visibility="collapsed", on_change=import_letterboxd)
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

            # Your picks as small posters, like everywhere else movies appear; × on each removes it.
            _ms = [get_movie(t, st.session_state.external_movies) or {"title": t} for t in chosen_titles]
            _need = tuple((m["title"], int(m.get("year") or 0)) for m in _ms if not m.get("poster_url"))
            _pm = get_poster_batch(_need) if _need else {}
            selection_cols = st.columns(8, gap="small")
            for idx, title in enumerate(chosen_titles):
                _u = str(_ms[idx].get("poster_url") or _pm.get(title) or "")
                with selection_cols[idx % 8]:
                    with st.container(key=f"selection_card_{idx}"):
                        st.markdown(
                            '<div class="sel-poster">'
                            + (f'<img src="{html.escape(_u, quote=True)}" alt="">' if _u.startswith("https://")
                               else f'<div class="live-hit-blank">{html.escape(title[:24])}</div>')
                            + f'</div><div class="sel-cap"><span class="sel-title">{html.escape(title)}</span></div>',
                            unsafe_allow_html=True)
                        st.button("×", key=f"remove_selection_{idx}", help=f"Remove {title}",
                                  on_click=remove_step1_selection, args=(title,))

        st.caption(f"{chosen_count} title{'s' if chosen_count!=1 else ''} selected")
    with st.container(key="nav_row_rate"):
        cont, _ = st.columns([1.25, 6], gap="small")
        with cont:
            st.button("Continue →", type="primary", disabled=chosen_count==0, key="continue_rate", use_container_width=True, on_click=go_from_fragment, args=("taste",))


    persist_from_fragment()

@st.fragment
@_with_app_rerun
def render_taste_fragment():
    """Step 2 of 2: four short questions on one calm page, each the same shape: a question, one quiet
    helper line, then its control. The two scales are segmented controls (one track, one selected
    segment, like iOS); genres are chips that wrap; "show me more" is a two-column card grid."""
    logo()
    st.markdown('<div class="step2-header"><div class="step2-title">Step 2 of 2 — Tailor Your Showroom</div>'
                '<div class="step2-subtitle">Five quick answers. Change them anytime in Profile.</div></div>',
                unsafe_allow_html=True)

    def _question(title, left=None, right=None, helper=None):
        ends = (f'<div class="q-ends"><span>{html.escape(left)}</span><span>{html.escape(right)}</span></div>'
                if left and right else "")
        st.markdown(f'<div class="q-block"><div class="q-title">{html.escape(title)}</div>'
                    + (f'<div class="q-help">{html.escape(helper)}</div>' if helper else "") + ends + '</div>',
                    unsafe_allow_html=True)

    def _segmented(key, labels, values, current, on_click):
        idx = min(range(len(values)), key=lambda i: abs(values[i] - current))
        with st.container(key=key):
            cols = st.columns(len(values), gap="small")
            for i, value in enumerate(values):
                with cols[i]:
                    st.button(labels[i], key=f"{key}_{i}", type="primary" if i == idx else "secondary",
                              use_container_width=True, on_click=on_click, args=(value,))

    scale = [15, 32, 50, 68, 85]
    _question("Great reviews or easy to enjoy?")
    _segmented("review_scale", ["Reviews", "Lean reviews", "Balanced", "Lean easy", "Easy to enjoy"],
               scale, st.session_state.review_priority, set_review_priority)

    _question("Your genres", helper="Up to five.")
    selected = set(st.session_state.genres)
    try:
        chips = st.container(key="genre_chips", horizontal=True, gap="small")
    except TypeError:
        chips = st.container(key="genre_chips")
    with chips:
        for i, genre in enumerate(GENRES):
            st.button(genre, key=f"genre_{i}", type="primary" if genre in selected else "secondary",
                      on_click=toggle_genre_choice, args=(genre,))

    _question("How adventurous?")
    _segmented("adventure_scale", ["Familiar", "Mostly familiar", "Balanced", "More new", "Surprise me"],
               scale, st.session_state.adventure, set_adventure_level)

    _question("Show me more of", helper="Optional. Your first pick gets its own row.")
    _render_more_choices()

    # The promise is "tonight, on the services you pay for", so onboarding asks for them (optional).
    _question("Your streaming services", helper="Optional. Tonight's pick comes from these first.")
    with st.container(key="onb_services"):
        _render_services_grid(list(st.session_state.get("streaming_services") or []))

    with st.container(key="nav_row_taste"):
        back, cont, _ = st.columns([1, 2.2, 4], gap="small")
        with back:
            st.button("← Back", key="back_taste", use_container_width=True, on_click=go_from_fragment, args=("shelf",))
        with cont:
            st.button("Build My Cinema Profile →", type="primary", key="build_profile", use_container_width=True,
                      on_click=go_from_fragment, args=("profile",))
        with _:
            st.button("Skip, use my likes", key="skip_taste", on_click=go_from_fragment, args=("showroom",),
                      help="Go straight to your Showroom. You can answer these later in Profile.")
    persist_from_fragment()


_MORE_DESCRIPTIONS = {
    "Hidden Gems": "Less known, still your taste",
    "Critically Acclaimed": "RT 75%+ and IMDb 7.5+",
    "Recent Releases": "Released 2023 or later",
    "International Films": "From around the world",
    "Classics": "Favorites from earlier eras",
    "Documentaries": "True stories, your interests",
}


def _render_more_choices():
    """The six "show me more of" cards (formerly Step 3). Each card is drawn in HTML, so the title and line
    always start at the same left edge, with an invisible button over the whole card as the tap target."""
    selected = set(st.session_state.more_of)
    with st.container(key="step3_grid"):
        cols = st.columns(3, gap="small")
        for i, option in enumerate(MORE_OF_OPTIONS):
            with cols[i % 3]:
                active = option in selected
                with st.container(key=f"pcard_{'on_' if active else ''}{i}"):
                    st.markdown(f'<div class="pcard-title">{html.escape(option)}</div>'
                                f'<div class="pcard-desc">{html.escape(_MORE_DESCRIPTIONS[option])}</div>', unsafe_allow_html=True)
                    st.button(option, key=f"priority_card_{'active_' if active else ''}{i}", use_container_width=True,
                              type="secondary", help=("Remove " if active else "Add ") + option,
                              on_click=toggle_priority_choice, args=(option,))


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
    if r.get("status") != "finished" and not int(r.get("decided_visits") or 0):
        return ""                       # nothing decided yet: say nothing rather than "0 of 200"
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
    tidy = compose(mood, spec["max"], spec["min"], spec["episodes"], like, spec.get("avoid") or []) if raw else ""
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


# Words fans use for the things a viewer can ask to avoid (MovieLens tags), used by the avoid filter
# for movies and, with the show's own keywords and rating, for shows.
AVOID_TERMS = {
    "violent": ["violent", "violence", "brutal", "brutality", "gore", "gory", "bloody", "graphic violence"],
    "scary": ["scary", "horror", "creepy", "disturbing", "terrifying", "gore"],
    "sad": ["sad", "depressing", "tearjerker", "bleak"],
    "gory": ["gore", "gory", "bloody", "violence"],
}


def _avoid_filter(items, spec):
    """"not too violent", "nothing scary": drop movies fans describe that way (the closest fifth to those
    words, by the same tested mood model). Everything else keeps the models' order."""
    words = spec.get("avoid") or []
    if not words or not items:
        return items
    from src.mood import scores, correct
    from src.cf_model import _index as _ix
    import numpy as _np
    # Fans rarely write "violent"; they write "violence", "brutal", "gore". Every word fans use for the
    # thing you asked to avoid counts, and a movie leaves if any of them describes it strongly.
    sc = None
    for w in words:
        for term in AVOID_TERMS.get(w, [w]):
            s = scores(correct(term))
            if s is not None and float(s.max()) > 0:
                sc = s if sc is None else _np.maximum(sc, s)
    cut = float(_np.quantile(sc[sc > 0], 0.5)) if sc is not None else None   # the more strongly described half
    # Second, independent evidence: official rating-board descriptors (e.g. Kijkwijzer "violence") for the
    # movies near the top, so new films with few fan tags are covered too.
    try:
        from src.tmdb_catalog import flagged_by_rating_boards
        boards = flagged_by_rating_boards([it[1].get("tmdb_id") for it in items[:60]], words)
    except Exception:
        boards = {}
    kept = [it for it in items
            if not boards.get(int(it[1].get("tmdb_id") or 0))
            and (cut is None or (i := _ix(it[1])) is None or sc[i] < cut)]
    return kept if len(kept) >= 4 else items


def _time_filter(items, spec, cap=80):
    """Keep (match, movie) items whose runtime fits the time limit, minus anything you asked to avoid;
    the models' order is unchanged."""
    from src.ui.mood_time import fits
    items = _avoid_filter(items, spec)
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
    return {"label": "Fits your mood", "text": f"Among the 10% of movies fans tag closest to “{q[:30]}”."}


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


def _love_pct(payload):
    """The rank the love-chance table reads: on its test's footing when known, else the overall rank."""
    payload = payload or {}
    v = payload.get("love_top_pct")
    return v if isinstance(v, (int, float)) else payload.get("fit_top_pct")


def _strong_title(q):
    """The movie a short query clearly names, or None. Only near-exact names count, so a mood never
    turns into a random title."""
    import difflib
    q = " ".join(str(q).split())
    if not q or len(q) > 70:
        return None
    picked = (st.session_state.get("_exact_pick") or {}).get(q.casefold())
    if picked:
        return picked
    ym = re.match(r"^(.*?)\s*\((\d{4})\)$", q)
    if ym:
        t, y = ym.group(1).strip(), int(ym.group(2))
        pool = list(CATALOG) + list(st.session_state.external_movies.values())
        hit = [x for x in pool if str(x.get("title", "")).casefold() == t.casefold() and int(x.get("year") or 0) == y]
        if hit:
            return hit[0]
        if tmdb_catalog_configured():
            try:
                hit = [r for r in (search_movies(t, 8) or []) if int(r.get("year") or 0) == y]
            except Exception:
                hit = []
            if hit:
                return hit[0]
        q = t
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


def _fork_seen(title):
    """'I've Seen It' on the searched movie: ask how it was, right where the buttons were."""
    fork = dict(st.session_state.get("search_fork") or {})
    fork[title] = "rate"
    st.session_state.search_fork = fork


def _fork_answer(title, movie, value):
    """The answer to "How was it?": 1 loved it (a like, +1.0), -1 not for me (-0.8), 0 just seen (+0.5)."""
    mark_movie_seen(title, movie)
    rated = dict(st.session_state.get("seen_rating") or {})
    if value:
        rated[title] = value
        record_event(st.session_state, "seen_loved" if value == 1 else "seen_disliked", title,
                     _current_recommendation_context(title))
    st.session_state.seen_rating = rated
    if value != 1:
        st.session_state.likes.discard(title)             # changed from "Loved it": it stops counting as a like
    if value == 1:
        if movie and (movie.get("external") or movie.get("tmdb_id")) and not get_movie(title, {}):
            st.session_state.external_movies[title] = dict(movie)
        st.session_state.likes.add(title)
        if title not in st.session_state.selection_order:
            st.session_state.selection_order.append(title)
    fork = dict(st.session_state.get("search_fork") or {})
    fork.pop(title, None)
    st.session_state.search_fork = fork
    _lib_bump()
    queue_profile_save()
    st.session_state._app_rerun = True


def render_top_result(row_name=None, row_index=None, beside=None):
    """Movie search: the movie you searched, large, with the one question that tells two people apart.

    Someone who wants to watch it taps Save to Watch. Someone who just watched it taps I've Seen It,
    answers "How was it?", and the card shrinks to one line so "More Like ..." moves up, re-ranked
    with their answer. Anyone who already told the app (liked or seen) lands on that one line."""
    src = _like_source()
    if not src:
        return
    ss = st.session_state
    title, year, tid = src.get("title", ""), int(src.get("year") or 0), int(src.get("tmdb_id") or 0)
    ident = (get_movie_identity_batch(((title, year, tid),)) or {}).get(title) or {}
    live = (get_live_ratings_batch(((title, int(ident.get("year") or year), ident.get("imdb_id") or ""),)) or {}).get(title) or {}
    watch = (get_watch_availability_batch(((title, int(ident.get("year") or year)),), "US") or {}).get(title)
    runtime = int(ident.get("runtime") or src.get("runtime") or 0)
    movie = dict(src, overview=src.get("overview") or ident.get("overview"), tagline=ident.get("tagline"))
    meta = [str(ident.get("year") or year or ""), genre_pair(movie) or movie.get("genre") or ", ".join(ident.get("genres") or []),
            f"{runtime} min" if runtime else ""]
    ratings = " · ".join(ratings_text(card_ratings(movie, live)))
    poster = str(ident.get("poster_url") or src.get("poster_url") or "")
    pay = (ss.get("showroom_payloads") or {}).get(title) or {}
    rating = (ss.get("seen_rating") or {}).get(title)
    seen, liked, saved = title in ss.seen, title in ss.likes, title in ss.saved
    asking = (ss.get("search_fork") or {}).get(title) == "rate"
    name = html.escape(ident.get("display_title") or title)

    if (seen or liked) and not asking:
        # Already answered: one quiet line, so the matches below are the focus.
        state = ("Loved it" if (liked or rating == 1) else "Not for me" if rating == -1 else "Seen")
        thumb = f'<img src="{html.escape(poster, quote=True)}" alt="">' if poster.startswith("https://") else ""
        with st.container(key="shero_done_row"):
            st.markdown(f'<div class="shero-done">{thumb}<span class="shero-done-title">{name}</span>'
                        f'<span class="shero-done-state">{html.escape(state)}</span></div>', unsafe_allow_html=True)
            # Change your answer: the "How was it?" question comes back in place.
            st.button("Change", key="fork_change", help="Change your answer", on_click=_fork_seen, args=(title,))
        return

    with st.container(key="search_hero"):
        pcol, icol = st.columns([1, 4.2], gap="medium")
        with pcol:
            if poster.startswith("https://"):
                st.markdown(f'<div class="shero-poster"><img src="{html.escape(poster, quote=True)}" alt="Poster for {name}"></div>',
                            unsafe_allow_html=True)
        with icol:
            st.markdown(f'<div class="shero-title">{name}</div>'
                        f'<div class="shero-meta">{meta_html([x for x in meta if x])}</div>'
                        + (f'<div class="shero-line">{html.escape(ratings)}</div>' if ratings else "")
                        + f'<div class="shero-line">{watch_line_html(watch, title, ss.get("streaming_services"))}</div>'
                        f'<div class="shero-story">{html.escape(card_description(movie))}</div>', unsafe_allow_html=True)
            if pay:
                with st.container(key="search_hero_why"):
                    _love = love_line(_love_pct(pay))
                    _odds = (_love.replace("If you watch it: about ", "About ").replace(" chance you'll love it", " chance you’ll love it")
                             if _love else fit_head(pay, int(pay.get("match") or 0)))
                    with st.popover(_odds):
                        st.markdown(why_popup_html(pay, movie, [], live, watch or {}, int(pay.get("match") or 0), "Search"),
                                    unsafe_allow_html=True)
            with st.container(key="search_hero_actions"):
                if asking:
                    q, a, b, c = st.columns([1.3, 1, 1, 0.8], gap="small")
                    with q:
                        st.markdown('<div class="shero-ask">How was it?</div>', unsafe_allow_html=True)
                    with a:
                        st.button(":material/favorite: Loved it", key="fork_loved", use_container_width=True, on_click=_fork_answer, args=(title, movie, 1))
                    with b:
                        st.button("Not for me", key="fork_nope", use_container_width=True, on_click=_fork_answer, args=(title, movie, -1))
                    with c:
                        st.button("Skip", key="fork_skip", use_container_width=True, on_click=_fork_answer, args=(title, movie, 0))
                else:
                    a, b, _ = st.columns([1.2, 1.2, 2], gap="small")
                    with a:
                        st.button(":material/check: Saved" if saved else "Save to Watch", key="fork_save", type="primary", use_container_width=True,
                                  disabled=saved, on_click=save_movie, args=(title, movie))
                    with b:
                        st.button("I’ve Seen It", key="fork_seen", use_container_width=True, on_click=_fork_seen, args=(title,))


def _like_blend_weight():
    """The "More Like X" blend weight, only if its held-out test passed (data/like_blend_confirm.json).
    Until that file exists and says ship, the shelf stays closest first."""
    try:
        r = json.loads((Path(__file__).resolve().parent / "data" / "like_blend_confirm.json").read_text())
        return float(r["weight"]) if r.get("ship") else None
    except Exception:
        return None


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
        # Fans' 100 closest movies. A tag-based re-rank is applied only if training/confirm_like.py passed
        # (it lost: fans alone ranked better). The order model won a "like X" test too, but it measured
        # what fans liked next, not similarity, so it isn't used here (README, "A test it won that didn't ship").
        import numpy as _np
        from src import content_model as _cm
        from src.cf_model import _load as _cfl
        i = _ix(source)
        near = _nb(source, 100)
        fan_rank = 1 - _np.arange(len(near)) / max(len(near), 1)
        vecs, pop = _cm._load(), _cfl().fan_pct
        if not _like_rerank_ships():
            vecs = None          # the held-out test said fans alone rank better, so use fan order
        if vecs is not None and len(near):
            E, has = vecs
            v = E[i]
            if has[i] and float(_np.linalg.norm(v)) > 0:
                cos = (E[near] @ v) / _np.maximum(_np.linalg.norm(E[near], axis=1) * _np.linalg.norm(v), 1e-9)
                tag_rank = 1 - _np.argsort(_np.argsort(-cos)) / len(near)
                w, pdisc = _similar_weights()
                score = (1 - w) * fan_rank + w * tag_rank - pdisc * pop[near]
            else:
                score = fan_rank - _similar_weights()[1] * pop[near]
        else:
            score = fan_rank
        order = _np.argsort(-score)
        ranked_near = [int(near[k]) for k in order]
        from src import seq_model as _seq
        # A search for "like X" means similar to X, so it uses fans' closest movies to X alone.
        # The order model ("what people watch next") stays in the main ranking, where it won its test.
        sims = {j: 0.5 + 0.5 * (1 - r / max(len(ranked_near), 1)) for r, j in enumerate(ranked_near)}
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


def _active_chips():
    """The parts of the search shown as tokens: (label, search without this part, text to edit).
    Tap a token's words to edit them in the field; tap × to remove that part. Moods that are just the
    tapped presets show as filled presets instead, so nothing appears twice."""
    from src.ui.mood_time import chips, parse
    _sp = _mood_spec()
    raw_mood = parse(_mood_text())["mood"]
    preset_words = {w for _, t in _MOOD_PRESETS if t and not t.startswith(("under", "like ")) for w in t.split()}
    mood_now = (_sp.get("mood") or "").split()
    out = []
    for lab, rest in chips(_mood_text()):
        if _sp.get("lookup") and _sp.get("like") and raw_mood and lab.casefold() == raw_mood.casefold():
            out.append((re.sub(r"\s*\(\d{4}\)$", "", _sp['like']), rest, _sp["like"]))
        elif lab.startswith("More like "):
            out.append((re.sub(r"\s*\(\d{4}\)$", "", lab[len('More like '):]), rest, f"like {lab[len('More like '):]}"))
        elif mood_now and lab == " ".join(mood_now) and set(mood_now) <= preset_words:
            continue
        elif lab.startswith("Under ") and _sp.get("max") == 120:
            continue
        elif lab.startswith("Not ") and lab[4:] in {t[4:] for _, t in _MOOD_PRESETS if t.startswith("not ")}:
            continue
        else:
            out.append((lab[:1].upper() + lab[1:], rest, lab if lab == lab.lower() else lab[0].lower() + lab[1:]))
    return out


def render_mood_chips():
    """Kept for callers elsewhere: the single control row now shows chips, toggles and Clear together."""
    render_mood_suggestions()


_MOOD_PRESETS = [("Feel-good", "feel-good"), ("Funny", "funny"), ("Mind-bending", "mind-bending"),
                 ("Dark and tense", "dark tense"), ("Under 2 hours", "under 2 hours"), ("Nothing too violent", "not violent")]


# The search is one designed system. Four states, and one written rule for what every part of the
# Showroom shows in each. The page reads this table instead of deciding part by part.
#   none:  nothing typed or tapped.
#   mood:  a mood, a length, or something to avoid ("mind-bending", "under 2 hours", "not violent").
#   movie: a movie typed on its own ("Inception"): the movie first, then the closest matches.
#   like:  "like Inception" (or a movie plus a mood): the closest matches, without the movie itself.
# A mood or length added to a movie filters inside that movie's matches; it never changes the state.
# A movie search is one focused answer: the movie and its closest matches. Tonight's Show and Shows step aside
# (None below) because four rows all about the same movie repeated each other.
SEARCH_RULE = {
    "none":  {"tokens": "presets", "tonight": "Your single best match right now", "top_result": False,
              "top_picks": "personal ranking", "shows": "personal", "explore": True},
    "mood":  {"tokens": "editable, filled presets", "tonight": "Your best match for {search}", "top_result": False,
              "top_picks": "personal ranking, filtered and led by the mood", "shows": "personal, filtered", "explore": True},
    "movie": {"tokens": "X, editable", "tonight": None, "top_result": True,
              "top_picks": "fans' closest to X, two lines of four", "shows": None, "explore": False},
    "like":  {"tokens": "X + mood, editable", "tonight": None, "top_result": True,
              "top_picks": "fans' closest to X", "shows": None, "explore": False},
}


def _quality_strict():
    """The higher quality bar applies when you chose strong reviews in Step 2 or Critically Acclaimed in Step 3."""
    ss = st.session_state
    return int(ss.get("review_priority") or 50) < 41 or "Critically Acclaimed" in (ss.get("more_of") or [])


def _quality_ok(movie, strict=False):
    """A rule, not a model: is this movie good enough to lead a mood search? Uses every score known for it
    (IMDb, Rotten Tomatoes, TMDB with enough votes, then how many MovieLens fans loved it)."""
    live = (st.session_state.get("showroom_rating_cache") or {}).get(movie.get("title")) or {}
    def num(*vals):
        for v in vals:
            try:
                if v is not None and float(v) >= 0:
                    return float(v)
            except (TypeError, ValueError):
                pass
        return None
    imdb, rt = num(live.get("imdb"), movie.get("imdb")), num(live.get("rt"), movie.get("rt"))
    tv = num(movie.get("tmdb_vote")) if (num(movie.get("tmdb_vote_count")) or 0) >= 200 else None
    bars = {"imdb": 7.0 if strict else 6.3, "rt": 75 if strict else 55, "tv": 7.0 if strict else 6.3}
    known = [(v, bars[k]) for k, v in (("imdb", imdb), ("rt", rt), ("tv", tv)) if v is not None]
    if known:
        return all(v >= bar for v, bar in known)
    fans = fan_percentile(movie)
    return fans is None or fans >= (0.7 if strict else 0.55)


def _search_state():
    """Which of the four search states is on (see SEARCH_RULE)."""
    spec = _mood_spec()
    if spec.get("like") and (spec.get("lookup") or not spec.get("mood")):
        return "movie"            # "Inception" and "like Inception" are one search: the movie, then its closest matches
    if spec.get("like"):
        return "like"             # a movie plus a mood: closest matches to the movie that fit the mood
    if spec.get("mood") or spec.get("max") or spec.get("min") or spec.get("episodes") or spec.get("avoid"):
        return "mood"
    return "none"


def _search_words():
    """The search in a few readable words for row notes: “mind-bending” · under 2 hours · nothing violent."""
    sx = _mood_spec()
    bits = [f"“{sx['mood'][:30]}”" if sx.get("mood") else "",
            ("under 2 hours" if sx.get("max") == 120 else (f"under {sx['max']} min" if sx.get("max") else "")),
            (f"over {sx['min']} min" if sx.get("min") else ""),
            ("short episodes" if sx.get("episodes") else ""),
            ("nothing " + ", ".join(sx.get("avoid") or []) if sx.get("avoid") else "")]
    return " · ".join(b for b in bits if b)


def _fans_reason(movie=None):
    """The search's lead reason in the movie states: “Loved by fans of Inception”, with where this movie
    sits among the fans' 100 closest. None outside the movie states."""
    src = _like_source() if _search_state() in ("movie", "like") else None
    if not src:
        return None
    rank = None
    if movie is not None:
        from src.cf_model import _index as _ix
        sims = _like_sims(src)
        i = _ix(movie)
        if sims and i is not None and i in sims:
            rank = sorted(sims, key=lambda j: -sims[j]).index(i) + 1
    text = f"#{rank} of the 100 movies they love most alongside it" if rank else ""
    return {"label": f"Loved by fans of “{src['title']}”", "text": text, "rank": rank}


def _preset_active(text, spec):
    """Is this starting point already part of the search?"""
    if text.startswith("not "):
        return text[4:] in (spec.get("avoid") or [])
    if text.startswith("under"):
        return spec.get("max") == 120
    if text.startswith("like "):
        return (spec.get("like") or "").casefold() == text[5:].casefold()
    words = set((spec.get("mood") or "").split())
    return bool(words) and set(text.split()) <= words


def _toggle_preset(text):
    """Tap a starting point to add it to the search; tap it again to take it out. Other parts stay."""
    from src.ui.mood_time import parse, compose
    spec = parse(_mood_text())
    mood, mx, mn, ep, lk = spec["mood"], spec["max"], spec["min"], spec["episodes"], spec.get("like")
    av = list(spec.get("avoid") or [])
    on = _preset_active(text, spec)
    _sp = _mood_spec()
    if _sp.get("lookup") and _sp.get("like") and not text.startswith(("not ", "under", "like ")):
        # A movie search plus a mood: keep the movie as "like X" so the mood filters its matches,
        # instead of gluing the title onto the mood words ("inception (2010) funny").
        mood, lk = "", _sp["like"]
    if text.startswith("not "):
        w = text[4:]
        av = [x for x in av if x != w] if on else av + [w]
    elif text.startswith("under"):
        mx = None if on else 120
    elif text.startswith("like "):
        lk = None if on else text[5:]
    else:
        words = mood.split()
        if on:
            words = [w for w in words if w not in set(text.split())]
        else:
            words += [w for w in text.split() if w not in words]
        mood = " ".join(words)
    _set_mood_live(compose(mood, mx, mn, ep, lk, av))


def render_mood_suggestions():
    """One row under the search field: what's on (tap × to remove), then starting points (tap to add,
    tap again to remove; filled when on), then Clear when anything is on. Nothing moves around."""
    from src.mood import scores
    from src.ui.mood_time import parse
    spec = parse(_mood_text())
    spec["lookup"] = _mood_spec().get("lookup")
    opts = []
    for label, text in _MOOD_PRESETS:
        if text is None:
            if spec.get("like") or spec.get("lookup"):
                continue
            last = next((e.get("title") for e in reversed(st.session_state.get("analytics_events") or [])
                         if e.get("event") == "save" and e.get("title")), None)
            if last:
                opts.append((f"More like {last[:28]}", f"like {last}"))
        elif text.startswith(("under", "not ")) or scores(text) is not None:
            opts.append((label, text))
    chips_now = _active_chips() if _mood_text() else []
    try:
        row = st.container(key="mood_suggest_row", horizontal=True, gap="small")
    except TypeError:
        row = st.container(key="mood_suggest_row")
    with row:
        if _mood_text():
            st.button("Clear all", key="mood_reset", on_click=_set_mood_live, args=("",))
        for i, (label, rest, edit) in enumerate(chips_now):
            # One capsule, two taps: the words open the token in the field to edit; × removes it.
            try:
                tok = st.container(key=f"mood_tok_{i}", horizontal=True, gap="small")
            except TypeError:
                tok = st.container(key=f"mood_tok_{i}")
            with tok:
                st.button(label, key=f"mood_edit_{i}", help=f"Edit {label}", on_click=_edit_token, args=(rest, edit))
                st.button("×", key=f"mood_chip_{i}", help=f"Remove {label}", on_click=_set_mood_live, args=(rest,))
        for i, (label, text) in enumerate(opts):
            on = _preset_active(text, spec)
            st.button(label, key=f"mood_suggest_{'on_' if on else ''}{i}",
                      help=f"Remove {label}" if on else f"Add {label}", on_click=_toggle_preset, args=(text,))
    _spx = _mood_spec()
    mood = _spx["mood"]
    if mood and scores(mood) is None and not _spx.get("lookup"):
        # A likely typo of a title: offer "Did you mean …?" with the exact movie, one tap away.
        _dym = []
        try:
            from src.cf_model import fuzzy_titles
            _dym = [m for m in (fuzzy_titles(mood, n=3, cutoff=0.7) or []) if m.get("title")][:2]
        except Exception:
            _dym = []
        if _dym:
            st.markdown('<div class="mood-hint">Did you mean</div>', unsafe_allow_html=True)
            try:
                _drow = st.container(key="dym_row", horizontal=True, gap="small")
            except TypeError:
                _drow = st.container(key="dym_row")
            with _drow:
                for k, m in enumerate(_dym):
                    exact = f'{m["title"]} ({m["year"]})' if m.get("year") else m["title"]
                    st.button(exact[:48], key=f"dym_{k}", on_click=_commit_exact, args=(exact, m))
        else:
            st.markdown(f'<div class="mood-hint">No movie or mood matches “{html.escape(mood[:40])}”. '
                        'Try a movie title, or words like feel-good, mind-bending, or slow burn.</div>', unsafe_allow_html=True)


_BUILD_KEYS = ("showroom_slots", "showroom_payloads", "showroom_row_queues", "recommendation_context",
               "tonight_pool", "tonight_deep_pool", "interleave_teams")


def _build_key():
    """Everything a Showroom build depends on. Any choice changes it, so a reused build is never stale."""
    ss = st.session_state
    return (_mood_text(), tuple(sorted(ss.likes)), tuple(sorted(ss.favorites)), tuple(ss.genres),
            ss.review_priority, ss.adventure, tuple(ss.more_of), len(ss.saved), len(ss.seen), len(ss.dismissed),
            len(ss.get("disliked") or ()), tuple(sorted(ss.get("streaming_services") or ())),
            tuple(sorted((ss.get("seen_rating") or {}).items())),      # a thumbs on Seen re-ranks the Showroom
            len([e for e in (ss.get("analytics_events") or []) if e.get("event") != "impression"]))


def _merged_search(typed, exact_title=None):
    """What's typed, added to the search already on (or to the rest of a token being edited):
    moods and avoids add up, a new length or movie replaces the old one (src/ui/mood_time.merge)."""
    from src.ui.mood_time import merge, parse
    base = st.session_state.pop("_edit_rest", None)
    if base is None:
        base = _mood_text()
    typed = " ".join(str(typed or "").split())[:120]
    if not base:
        return typed
    bp, tp = parse(base), parse(typed)
    cur_title = None
    if bp["mood"] and not bp["like"]:
        cur_title = (_lookup_title(bp["mood"]) or {}).get("title")
    typed_title = exact_title
    if typed_title is None and tp["mood"] and not tp["like"]:
        typed_title = (_lookup_title(tp["mood"]) or {}).get("title")
    return merge(base, typed, current_title=cur_title, typed_title=typed_title)[:120]


def _edit_token(rest, text):
    """Tap a token's words: they open in the field to edit, and Search puts the edit back in place of it.
    Only the search box reruns; the Showroom stays as it is until Search."""
    ver = int(st.session_state.get("_mood_ver") or 0) + 1
    st.session_state._mood_ver = ver
    st.session_state._edit_rest = rest
    st.session_state._mood_prefill = (ver, " ".join(str(text or "").split())[:120])


def _commit_search(text):
    """Run a search from the live field or a suggestion, then rebuild the Showroom around it."""
    st.session_state.mood_input = _merged_search(text)
    _apply_mood()
    st.session_state._mood_ver = int(st.session_state.get("_mood_ver") or 0) + 1   # the field shows the tidy text
    st.session_state._app_rerun = True


def _commit_exact(text, movie=None):
    """A tapped poster: search for exactly that film (title and year), with no typo correction."""
    if movie and movie.get("title"):
        st.session_state.external_movies.setdefault(movie["title"], dict(movie))
        memo = dict(st.session_state.get("_exact_pick") or {})
        memo[text.replace("like ", "", 1).casefold()] = dict(movie)
        st.session_state._exact_pick = memo
    exact = None if text.startswith("like ") else text
    _set_mood_live(_merged_search(text, exact_title=exact))
    # Clear the half-typed text ("inters") so the live results close and the movie's page shows,
    # exactly like pressing Search. Without this the typed text kept the suggestions open.
    st.session_state._mood_ver = int(st.session_state.get("_mood_ver") or 0) + 1
    st.session_state._app_rerun = True


def _set_mood_live(text):
    """A chip, Clear, or a starting point tapped inside the search box: change the search, rebuild the Showroom."""
    st.session_state.pop("_edit_rest", None)      # any token edit in progress is replaced by this change
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
            _pre = st.session_state.get("_mood_prefill") or (None, "")
            _ver = int(st.session_state.get("_mood_ver") or 0)
            live = st_keyup("Search by mood, time, or a movie", value=(_pre[1] if _pre[0] == _ver else ""), debounce=300,
                            key=f"mood_live_{int(st.session_state.get('_mood_ver') or 0)}",
                            placeholder=("Add a Mood, Length, or Movie" if _mood_text() else "Movies, Moods, Lengths, and More"), label_visibility="collapsed")
        except Exception:
            if "mood_input" not in st.session_state:
                st.session_state.mood_input = _mood_text()
            st.text_input("Search by mood, time, or a movie", key="mood_input", label_visibility="collapsed",
                          placeholder=("Add a Mood, Length, or Movie" if _mood_text() else "Movies, Moods, Lengths, and More"), on_change=_apply_mood)
        if st.session_state.get("_smoke_typed") is not None:   # tools/smoke_app.py types here
            live = str(st.session_state._smoke_typed)
        typed = " ".join(str(live or "").split())
        if live is not None and not typed:
            st.session_state.pop("_edit_rest", None)   # the field was cleared: no token edit is pending
        with st.container(key="mood_under"):
            if live is not None and typed and typed != _mood_text():
                _render_live_suggestions(typed)
            else:
                render_mood_suggestions()
                if st.session_state.get("_search_status") and _mood_text():
                    st.markdown(f'<div class="search-status">{html.escape(st.session_state._search_status)}</div>',
                                unsafe_allow_html=True)


def _render_live_suggestions(typed):
    """Under the field while typing: "Search for …" first, then up to four movies with posters."""
    st.button(f"Search “{typed[:60]}”", key="live_search_go", type="primary", on_click=_commit_search, args=(typed,))
    from src.ui.mood_time import parse
    spec = parse(typed)
    q = spec.get("like") or spec.get("mood") or ""
    hits = []
    if len(q) >= 2 and tmdb_catalog_configured():
        try:
            hits = [m for m in (search_movies(q, 8) or []) if m.get("poster_url")][:6]
        except Exception:
            hits = []
    if not hits:
        return
    st.markdown(f'<div class="live-hits-label">Movies titled “{html.escape(q[:40])}”</div>', unsafe_allow_html=True)
    _render_search_tiles(hits[:4], "live_hit", lambda m: (("like " if spec.get("like") else "")
                         + (f'{m["title"]} ({m["year"]})' if m.get("year") else m["title"]), m), _commit_exact)


def _render_search_tiles(movies, key, args_for, on_click, selected_id=None):
    """Search results drawn exactly like Showroom cards: the same wide key art with the title in it,
    four across. The whole tile is the button (each tile is its own keyed box, so the tap area is exact)."""
    keys = tuple((m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in movies)
    art = get_landscape_batch(keys) if keys else {}
    cols = st.columns(4, gap="small")
    for k, m in enumerate(movies):
        with cols[k % 4]:
            with st.container(key=f"hit_tile_{key}_{k}"):
                on = selected_id is not None and m.get("tmdb_id") == selected_id
                # The year sits under the art, so two films with the same title (Oldboy 2003, Oldboy 2013) differ.
                st.markdown(f'<div class="hit-art{" on" if on else ""}">'
                            + movie_thumb(dict(m, year=""), art.get(m["title"]) or m.get("poster_url"), landscape=True, return_html=True)
                            + '</div>'
                            + (f'<div class="hit-year">{html.escape(str(m["year"]))}</div>' if m.get("year") else ""),
                            unsafe_allow_html=True)
                label = m["title"] + (f' ({m["year"]})' if m.get("year") else "")
                # No tooltip on this button: a tooltip wraps it in a box sized to its (invisible) label, which shrank
                # the tap area to a thin strip at the top of the tile. That is why poster taps did nothing.
                st.button(label[:60], key=f"{key}_{k}_{m.get('tmdb_id') or m['title']}",
                          use_container_width=True, on_click=on_click, args=args_for(m))


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
        | {st.session_state.get("tonight_current")}
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
    _advance_showroom_slot(row_name, slot_index)
    _mark_showroom_fast()                 # reuse the ranking, but refresh Saved / Seen and their counts now
    st.session_state._app_rerun = True

def _answer_seen(slot_key, title, value):
    """Thumbs on the "liked it?" prompt after Seen: same effect as the thumbs on the Seen tab."""
    ask = dict(st.session_state.get("showroom_rate_ask") or {})
    ask.pop(slot_key, None)
    st.session_state.showroom_rate_ask = ask
    if value:
        rate_seen(title, value)


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
        # Ask "liked it?" on the card that replaces it: a Seen with a thumbs teaches the fans model more
        # (+1.0 or -0.8) than a plain Seen (+0.5), which counts a movie you disliked as half a like.
        ask = dict(st.session_state.get("showroom_rate_ask") or {})
        ask[slot_key] = title
        st.session_state.showroom_rate_ask = ask
    _advance_showroom_slot(row_name, slot_index)
    _mark_showroom_fast()                 # reuse the ranking, but refresh Saved / Seen and their counts now
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

def why_popup_html(payload, movie, reasons, live_rating, availability, match, row_name, kind_tag="", fans_reason=None):
    """The "Why it's here" popup, shared by every card and Tonight's Show.

    1. The models' odds (calibrated on held-out viewers).
    2. The models behind this pick: each one that scored this movie, its share of the score, and this
       movie's own evidence from it (who loved it, how close its genres and tags are, who made it).
    3. One more reason only if it applies (your search, mood, services, or the reviews you asked for).
    Everything is this movie's own numbers; nothing generic."""
    love = love_line(_love_pct(payload))
    odds = (love.replace("If you watch it: about ", "About ").replace(" chance you'll love it", " chance you’ll love it")
            if love else fit_head(payload, match))
    rows = dict(why_rows(reasons, movie, live_rating, payload, row_name))
    anchor = next((r["label"] for r in reasons or [] if str(r.get("label", "")).startswith("Loved by fans of")), None)
    evidence = {
        "Fans like you": (anchor + " · " if anchor else "") + re.sub(r" · fans of .+ love it$", "",
                                                                   rows.get("Fans like you") or rows.get("All models") or "People with your taste loved it"),
        "New releases": rows.get("New release") or "Made by filmmakers close to your likes",
        "What it’s like": rows.get("Tone") or "Close to the genres and fan tags you like",
        "Your choices": rows.get("Your choices") or "Learned from your saves and skips",
        "What you liked last": "Fans who loved your most recent likes went on to love it",
        "Mood search": (f"Fans describe it as “{_mood_spec().get('mood')}” more than most movies"
                        if _mood_spec().get("mood") else "Fans tag it close to the words you searched"),
    }
    mix = [(n, t, sh) for n, t, sh in score_mix(payload, CONTENT_WEIGHT) if sh > 0.005]
    if any(r.get("label") == "Fits your mood" for r in reasons or []):
        # In a mood search, rows are ordered half by your fit and half by the mood model's match (tested blend).
        mix = [(n, t, sh * 0.5) for n, t, sh in mix] + [("Mood search", "fan-tag TF-IDF", 0.5)]
    mix.sort(key=lambda x: -x[2])
    # One sentence of evidence from the model that moved the score most; the rest as share bars.
    lead_line = evidence.get(mix[0][0], "") if mix else ""
    plain = {"Fans like you": "People with your taste", "What you liked last": "Your recent likes",
             "What it’s like": "Its story and style", "Mood search": "Your mood", "Your choices": "Your saves and skips",
             "New releases": "Its filmmakers"}
    models = "".join(
        f'<div class="why-model" title="{html.escape(n)} · {html.escape(t)}"><div class="why-model-top"><span class="why-model-name">{html.escape(plain.get(n, n))}</span>'
        f'<span class="why-model-pct">{round(sh * 100)}%</span></div>'
        f'<div class="why-model-bar"><span style="width:{max(4, round(sh * 100))}%"></span></div></div>'
        for n, t, sh in mix[:3])
    if len(mix) == 1 and mix[0][0] == "What it’s like":
        lead_line = "Too new or too rare for fan data yet, so it’s matched on genres and fan tags."
    # Which of the 11 models touched this pick: the bars, the models inside the ranker, and the odds model.
    _ids = {"calibration"}
    for n, _t, _sh in mix:
        _ids |= {"Fans like you": ({"ranker", "item-kNN", "RP3beta", "EASE"} if payload.get("cf_source") == "ranker" else {"item-kNN"}),
                 "What you liked last": {"markov"}, "What it’s like": {"content"}, "Your choices": {"personal"},
                 "New releases": {"ridge"}, "Mood search": {"mood"}}.get(n, set())
    used_line = (f"{len(_ids)} of {MODELS_TOTAL} models shaped this pick"
                 + (" (the fan ranker blends item-kNN, RP3beta and EASE)" if payload.get("cf_source") == "ranker" else "")
                 + ", and a calibration model turns the score into your odds.")
    extra = None
    if fans_reason:
        extra = (fans_reason["label"], fans_reason.get("text") or "")
    else:
        mood = next((r for r in reasons or [] if r.get("label") == "Fits your mood"), None)
        services = list(st.session_state.get("streaming_services") or [])
        rr = ratings_reason(rows.get("Ratings"), st.session_state.get("review_priority"))
        if mood:
            extra = ("Fits your mood", mood.get("text", ""))
        elif services and movie_on_services(availability, services):
            opt = watch_options(availability, movie.get("title", ""), services)
            extra = ("On your services", opt[0][1] if opt else "")
        elif rr:
            extra = ("Reviews", rr)
    return (f'<div class="why-pop-kicker">Why it’s here{html.escape(kind_tag)}</div>'
            f'<div class="why-pop-head">{html.escape(odds)}</div>'
            + (f'<div class="why-lead">{html.escape(lead_line)}</div>' if lead_line else "")
            + (f'<div class="why-models-label">What decided this pick</div><div class="why-models">{models}</div>' if models else "")
            + (f'<div class="why-extra" style="display:none"><strong>{html.escape(extra[0])}</strong>'
               + (f' · {html.escape(extra[1])}' if extra[1] else "") + '</div>' if extra else "")
            + f'<div class="why-more">{len(_ids)} of {MODELS_TOTAL} models · point at a bar for its method</div>')


def why_this_movie(reasons, rows, payload, movie, availability, fans_reason=None, limit=3):
    """The three most important reasons this one movie is here, each with its own number, strongest first.

    Order follows what moved its score most: the search, then the model with the biggest share of this
    movie's score (fans, the new-release model, or your own saves), then mood, tone, reviews you asked for,
    and whether it's on your services. Nothing generic: every line names this movie's own evidence."""
    out = []
    def add(k, v):
        if v and k not in {x[0] for x in out}:
            out.append((k, v[:1].upper() + v[1:]))
    if fans_reason:
        add(fans_reason["label"], fans_reason.get("text") or "")
    anchor = next((r["label"] for r in reasons or [] if str(r.get("label", "")).startswith("Loved by fans of")), None)
    mix = {n: sh for n, _t, sh in score_mix(payload, CONTENT_WEIGHT)}
    model_lines = []
    fans_text = rows.get("Fans like you") or rows.get("All models")
    if fans_text:
        model_lines.append((mix.get("Fans like you", 0), anchor or "Fans like you",
                            re.sub(r" · fans of .+ love it$", "", fans_text)))
    if rows.get("New release"):
        model_lines.append((mix.get("New releases", 0), "New, from filmmakers near your likes", rows["New release"]))
    if rows.get("Your choices"):
        model_lines.append((mix.get("Your choices", 0), "Your saves and skips", rows["Your choices"]))
    for _sh, k, v in sorted(model_lines, key=lambda x: -x[0]):
        add(k, v)
    mood = next((r for r in reasons or [] if r.get("label") == "Fits your mood"), None)
    if mood:
        add("Fits your mood", mood.get("text", ""))
    tone = next((r for r in reasons or [] if str(r.get("label", "")).startswith("Feels like")), None)
    if tone and rows.get("Tone"):
        add(tone["label"], rows["Tone"])
    rr = ratings_reason(rows.get("Ratings"), st.session_state.get("review_priority"))
    if rr:
        add("Reviews", rr)
    services = list(st.session_state.get("streaming_services") or [])
    if services and movie_on_services(availability, services):
        opt = watch_options(availability, movie.get("title", ""), services)
        add("On your services", opt[0][1] if opt else "")
    if rows.get("This row"):
        add("This row", rows["This row"])
    return out[:limit]


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
        "model_version":"v5.192",
        **_interleave_fields(row_name, title),
    }
    recommendation_context = dict(st.session_state.get("recommendation_context") or {})
    recommendation_context[title] = context
    st.session_state.recommendation_context = recommendation_context
    record_impressions(st.session_state, {title: context})

    undo_title = (st.session_state.get("showroom_undo") or {}).get(slot_key)
    ask_title = (st.session_state.get("showroom_rate_ask") or {}).get(slot_key)
    if ask_title and not undo_title:
        try:
            _ask_box = st.container(key=f"card_rate_{row_index}_{slot_index}", horizontal=True, gap="small")
        except TypeError:
            _ask_box = st.container(key=f"card_rate_{row_index}_{slot_index}")
        with _ask_box:
            st.markdown(f'<div class="rate-ask">Liked {html.escape(ask_title[:22])}?</div>', unsafe_allow_html=True)
            st.button(":material/thumb_up:", key=f"rate_up_{row_index}_{slot_index}", help="Liked it",
                      on_click=_answer_seen, args=(slot_key, ask_title, 1))
            st.button(":material/thumb_down:", key=f"rate_down_{row_index}_{slot_index}", help="Didn't like it",
                      on_click=_answer_seen, args=(slot_key, ask_title, -1))
            st.button(":material/close:", key=f"rate_x_{row_index}_{slot_index}", help="Not now",
                      on_click=_answer_seen, args=(slot_key, ask_title, 0))
    if undo_title:
        # Undo sits on the art's corner, not in the pill row, so the pill row is always match + Skip
        # and nothing in the row moves when it appears.
        st.button(":material/undo:", key=f"card_undo_{row_index}_{slot_index}_{title}",
                  help=f"Bring back {undo_title}", on_click=undo_showroom_slot, args=(row_name, slot_index))
    with st.container(key=f"showroom_controls_{row_index}_{slot_index}_{title}"):
        match_col, skip_col = st.columns([3.35,0.90], gap="small")
        reasons = with_cf_reason(recommendation_explanation(
            with_live_ratings(movie, live_rating),p,st.session_state.adventure,st.session_state.review_priority,
            semantic_similarity=context.get("semantic_similarity"),
            availability_score=context.get("availability_alignment",0.5),
            components=context,
        ), payload)
        if (_mr := mood_reason(movie)):
            reasons = [_mr] + reasons
        _fr = _fans_reason(movie)
        if _fr:
            reasons = [_fr] + [r for r in reasons if not str(r.get("label", "")).startswith("Loved by fans")]
        pill_labels = dict(st.session_state.get("showroom_pill_labels") or {})
        row_taken = {label for key, label in pill_labels.items()
                     if key.startswith(f"{row_name}::") and key != slot_key and label}
        _kind_tag = {"Critically Acclaimed": " · Critics’ pick", "Hidden Gems": " · Hidden gem",
                     "Recent Releases for You": " · New release", "Something Different": " · Something new",
                     "Classics for You": " · Classic", "International Films for You": " · International",
                     "Documentaries for You": " · Documentary"}.get(row_name, "")
        pill_text, pill_label = match_pill(match, reasons, taken=row_taken, head=fit_head(payload, match))
        pill_text = fit_head(payload, match)     # the why is shown in words under the title
        _lv = love_line(_love_pct(payload))
        _lvm = re.search(r"(\d+)%", _lv or "")
        if _lvm:
            pill_text = f"{_lvm.group(1)}% match"    # the calibrated chance you'll love it; the popup says so in full
        pill_labels[slot_key] = pill_label
        st.session_state.showroom_pill_labels = pill_labels
        with match_col:
            with st.popover(pill_text, use_container_width=True):
                st.markdown(why_popup_html(payload, movie, reasons, live_rating, availability, match, row_name,
                                           _kind_tag, _fr), unsafe_allow_html=True)
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
    meta = [str(x) for x in ("", _year, genre_pair(movie) or ", ".join(identity.get("genres") or []),
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


_SERVICE_SHORT = {"Free (Tubi, Pluto & more)": "Free with ads"}


def _services_done():
    """Done: the whole Showroom redraws once, so every card's streaming line puts your services first.
    Tapping tiles reruns only Tonight's Show, which re-picks instantly; the rows reuse the current build."""
    st.session_state._app_rerun = True


def _render_services_grid(services):
    """The services as their real logos (TMDB, JustWatch data); tap to turn one on or off.
    Used in Step 2 and inside Tonight's Show's "Your Services" popover."""
    from src.watch_providers import service_logos
    try:
        logos = service_logos() or {}
    except Exception:
        logos = {}
    try:
        grid = st.container(key="svc_grid", horizontal=True, gap="small")
    except TypeError:
        grid = st.container(key="svc_grid")
    with grid:
        for i, name in enumerate(STREAMING_SERVICES):
            on = name in services
            short = _SERVICE_SHORT.get(name, name)
            imgs = [u for u in (logos.get(name) or []) if str(u).startswith("https://")][:3]
            art = ("".join(f'<img src="{html.escape(u, quote=True)}" alt="">' for u in imgs) if imgs
                   else f'<span class="svc-word">{html.escape(short)}</span>')
            with st.container(key=f"svc_tile_{'on_' if on else ''}{i}"):
                st.markdown(f'<div class="svc-art{" multi" if len(imgs) > 1 else ""}">{art}</div>'
                            f'<div class="svc-name">{html.escape(short)}</div>', unsafe_allow_html=True)
                st.button(short, key=f"svc_btn_{i}", use_container_width=True,
                          on_click=toggle_streaming_service, args=(name,))


def _render_services_picker(services):
    """Your services as a grid of their real logos (from TMDB, which shows JustWatch's data); tap to turn one
    on or off. Tonight's Show re-picks on every tap. Names show if a logo can't load."""
    label = f"Your Services · {len(services)}" if services else "Choose Your Services"
    from src.watch_providers import service_logos
    try:
        logos = service_logos() or {}
    except Exception:
        logos = {}
    with st.container(key="services_picker"), st.popover(label, use_container_width=True):
        st.markdown('<div class="services-help">Tap the services you pay for.</div>',
                    unsafe_allow_html=True)
        try:
            grid = st.container(key="svc_grid", horizontal=True, gap="small")
        except TypeError:
            grid = st.container(key="svc_grid")
        with grid:
            for i, name in enumerate(STREAMING_SERVICES):
                on = name in services
                short = _SERVICE_SHORT.get(name, name)
                imgs = [u for u in (logos.get(name) or []) if str(u).startswith("https://")][:3]
                art = ("".join(f'<img src="{html.escape(u, quote=True)}" alt="">' for u in imgs) if imgs
                       else f'<span class="svc-word">{html.escape(short)}</span>')
                with st.container(key=f"svc_tile_{'on_' if on else ''}{i}"):
                    st.markdown(f'<div class="svc-art{" multi" if len(imgs) > 1 else ""}">{art}</div>'
                                f'<div class="svc-name">{html.escape(short)}</div>', unsafe_allow_html=True)
                    st.button(short, key=f"svc_btn_{i}", use_container_width=True,
                              on_click=toggle_streaming_service, args=(name,))
        st.button("Done", key="svc_done", type="primary", on_click=_services_done)
        st.markdown('<div class="services-credit">Availability and logos by JustWatch, via TMDB.</div>', unsafe_allow_html=True)


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

    # The note follows SEARCH_RULE: what the search is, then where it streams.
    _state = _search_state()
    _src = _like_source() if _state in ("movie", "like") else None
    _words = _search_words()
    if _src:
        base = f"Your best match like {_src['title']}"
    elif _state == "mood" and _words:
        base = f"Your best match for {_words}"
    else:
        base = SEARCH_RULE["none"]["tonight"]
    if services:
        shown = ", ".join(services[:2]) + (f" +{len(services) - 2}" if len(services) > 2 else "")
        note = (f"{base} on {shown}" if fits else
                f"Nothing {'like ' + _src['title'] if _src else 'in your top matches'} streams on {shown} right now, "
                "so here’s the best overall")
    else:
        note = base
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
    st.session_state.tonight_current = title     # a row card that moves on never lands on tonight's pick
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
        "model_version":"v5.192",
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
    # In a search, the lead reason names it: "Loved by fans of “Inception”", or the mood you typed.
    _lead = _fans_reason(movie) or mood_reason(movie)
    if _lead:
        reasons = [_lead] + [r for r in reasons if not str(r.get("label", "")).startswith("Loved by fans")]
    def _why_text(r):
        # "Loved by fans of X" already says it; skip the sentence that repeats it.
        t = str(r.get("text") or "")
        if str(r.get("label", "")).startswith("Loved by fans") and "loved" in t.casefold():
            return " · similar tone too" if "similar tone" in t else ""
        return f" · {t}" if t else ""
    why_html = "".join(f'<div class="tonight-why"><strong>{html.escape(r["label"])}</strong>{html.escape(_why_text(r))}</div>'
                       for r in reasons[:1])        # one reason keeps the card compact; the rest live in the popups

    _love = love_line(_love_pct(payload))
    _love_short = _love.replace("If you watch it: about ", "About ").replace(" chance you'll love it", " chance you’ll love it") if _love else ""
    tonight_badge = (("Best on your services · " if services and title in fits else "")
                     + (_love_short or fit_head(payload, match)))
    with st.container(key=f"tonight_hero_{title}"):
        poster_col, info_col = st.columns([1, 6.2], gap="medium")
        with poster_col:
            st.markdown(poster_html, unsafe_allow_html=True)
        with info_col:
            st.markdown(
                '<div class="tonight-stack">'
                f'<div class="tonight-title">{html.escape(str(display_title))}</div>'
                f'<div class="tonight-meta">{meta_html_line}</div></div>',
                unsafe_allow_html=True,
            )
            # The odds line opens the same "Why it's here" as every card.
            with st.container(key="tonight_why"):
                with st.popover(tonight_badge):
                    st.markdown(why_popup_html(payload, movie, reasons, live_rating, availability, match, "Tonight",
                                               "", _fans_reason(movie)), unsafe_allow_html=True)
            st.markdown(
                '<div class="tonight-stack">'
                + (f'<div class="tonight-badges">{fit}</div>' if fit else "")
                + f'<div class="tonight-line">{watch_html}</div>'
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


def _library_counts(which):
    """The count beside one library tab, written by that tab's own fragment so neither can go stale over the other."""
    n = len(st.session_state.saved) if which == "saved" else len(st.session_state.seen)
    k = 1 if which == "saved" else 2
    st.markdown(
        f'<style>[data-testid="stTabs"] [role="tab"][id$="-tab-{k}"] p::after,'
        f'[data-testid="stTabs"] [role="tablist"] > [role="tab"]:nth-of-type({k + 1}) p::after{{content:" ({n})" !important}}</style>',
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
    _library_counts("saved")
    persist_from_fragment()


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
    _library_counts("seen")
    # Thumbs, Remove and What's next run only this tab, so the change is written to this browser here;
    # before, it waited for a full page run and a reload in between lost it.
    persist_from_fragment()


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
        candidate_pool = [m for m in list(CATALOG) + list(st.session_state.external_movies.values()) + external_pool
                          if not str(m.get("title", "")).lower().startswith("untitled")]
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
            _extra_idx = list(_like_sims(_src0).keys())[:60] + _extra_idx   # the 60 closest are plenty for 7 picks
            if _search_state() in ("movie", "like") and str(_src0.get("title", "")).casefold() not in _have2:
                # The searched movie is scored like any other, so its pill is a real calibrated chance.
                candidate_pool.append(dict(_src0, candidate_source="search"))
                _have2.add(str(_src0.get("title", "")).casefold())
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
        ranked = [x for x in ranked if not str(x[1].get("title", "")).lower().startswith(("untitled", "tba ", "tbd "))]
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
        # What you liked most recently, in order: the order model (tested on the main ranking) uses the
        # last three to score what people like next. Step 1 picks come first, then saves by time.
        from src import seq_model as _seqm
        from src.cf_model import _index as _cfix
        _recent=[]
        if _seqm.main_available():
            _ev=sorted((e for e in (st.session_state.get("analytics_events") or []) if e.get("event")=="save"),
                       key=lambda e:float(e.get("timestamp") or 0))
            _titles=list(st.session_state.get("selection_order") or [])+[e.get("title") for e in _ev]
            for _t in _titles:
                _m=get_movie(_t, st.session_state.external_movies)
                _i=_cfix(_m) if _m else None
                if _i is not None:
                    _recent.append(_i)
        _seq_vec=_seqm.main_vector(_recent) if _recent else None
        _seq_w=_seqm.main_weight()
        cf_by_title={}
        personal_by_title={}
        cf_source_by_title={}
        seq_parts_by_title={}     # (fan ranking part, liked-next part) of each movie's fan score, for "Why it's here"
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
                        # Only movies MovieLens fans haven't rated get the new-release model, and only they say so.
                        cf=_nr_affinity(movie,nr_view)
                        cf_source_by_title[movie["title"]]="new" if cf is not None else None
                    if cf is not None and _seq_vec is not None:
                        _si=_ci if _ci is not None else _cfix(movie)
                        if _si is not None:
                            seq_parts_by_title[movie["title"]]=((1-_seq_w)*cf,_seq_w*float(_seq_vec[_si]))
                            cf=(1-_seq_w)*cf+_seq_w*float(_seq_vec[_si])   # tested blend: shipped ranking + liked-next
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
                    _w=_KNOBS["rows"].get("Critically Acclaimed",0.30)
                    objective=(1-_w)*base+_w*section
                elif row_name=="Hidden Gems":
                    _w=_KNOBS["rows"].get("Hidden Gems",0.28)
                    objective=(1-_w)*base+_w*section
                elif row_name in ADAPTIVE_ROWS:
                    # The row's kind is the hard filter; within it, your personal fit decides.
                    objective=base+(0.06*_pop_now(movie) if row_name=="Recent Releases for You" else 0.0)
                else:  # Something Different: serendipity = fans-like-you love it, but it's unlike your usual picks
                    cf_v=cf_by_title.get(movie["title"])
                    sem=semantic_by_id.get(id(movie),0.5)
                    seren=max(0.0,min(1.0,((cf_v if cf_v is not None else 0.5)-sem+1.0)/2.0))
                    _w=_KNOBS["rows"].get("Something Different",0.20)
                    objective=(0.75-_w)*base+0.25*seren+_w*section
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
            diversified=mmr_rerank(scored,limit=min(12,len(scored)),relevance_lambda=_KNOBS["variety"])
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
        if _mood is not None and top_all and not _like_source():
            # A mood re-orders Top Matches: half how well each movie fits you, half how well it fits the words.
            # (With a movie search on, the mood is applied inside that movie's matches instead; see below.)
            import numpy as _np
            _n=len(top_all)
            _ms=[float(_mood[i]) if (i:=_cf_idx(m)) is not None else 0.0 for _,m in top_all]
            _pos=_mood[_mood>0]
            _hit=[]
            for _q in (0.95,0.9,0.8,0.7):                         # strictest bar that still gives a full row
                _thr=float(_np.quantile(_pos,_q)) if len(_pos) else 1.0
                _hit=[j for j in range(_n) if _ms[j]>=_thr]       # movies fans really describe that way
                if len(_hit)>=4:
                    break
            # A mood narrows what kind of movie; it never lowers the bar on how good. Weak movies leave first,
            # by your Step 2/3 answers (strong reviews or Critically Acclaimed = the higher bar).
            for _strict in ((True, False) if _quality_strict() else (False,)):
                _good=[j for j in _hit if _quality_ok(top_all[j][1],_strict)]
                if len(_good)>=4:
                    _hit=_good
                    break
            if len(_hit)>=4:
                _mrank={j:r for r,j in enumerate(sorted(_hit,key=lambda j:-_ms[j]))}
                _frank={j:r for r,j in enumerate(_hit)}
                _first=sorted(_hit,key=lambda j:0.5*_frank[j]+0.5*_mrank[j])
                _hs=set(_hit)
                top_all=[top_all[j] for j in _first]   # only movies that fit the mood, even after many Skips
        _src=_like_source()
        _src_item=None
        _lookup=_mood_spec().get("lookup")
        _state=_search_state()
        _personal_top=list(top_all)          # a title lookup leaves Tonight's Show as your personal best
        if _src and top_all:
            # "like X": Top Picks re-ranks by the What's next blend (fans who loved X, plus your own match).
            _sk=_src.get("title")
            _src_item=next((x for x in top_all if x[1].get("title")==_sk),None)   # kept for the Top result pill
            top_all=[x for x in top_all if x[1].get("title")!=_sk]
            _scored=[(_like_score(x[1],_src),x) for x in top_all]
            _close=[(v,x) for v,x in _scored if v>0.5 and float(x[0] or 0)>=30]   # close, and not a poor fit for you
            if len(_close)>=4:
                _scored=_close
            # 80% how close it is, 20% how well it fits you: the What's Next blend that beat every lower
            # similarity weight on held-out viewers, so tonight's search leads and your profile still counts.
            # Closest to X first (similarity alone was the best weight on held-out viewers); your fit breaks ties.
            _lbw=_like_blend_weight()
            if _lbw is not None and len(_scored)>1:
                import numpy as np
                # The tested blend shipped (training/confirm_like_blend.py): closeness rank and your-fit rank, weighted.
                _cv=np.asarray([t[0] for t in _scored],dtype=float); _fv=np.asarray([float(t[1][0] or 0) for t in _scored])
                _cr=1-np.argsort(np.argsort(-_cv))/len(_cv); _fr=1-np.argsort(np.argsort(-_fv))/len(_fv)
                _bs=(1-_lbw)*_cr+_lbw*_fr
                top_all=[_scored[i][1] for i in np.argsort(-_bs)]
            else:
                top_all=[x for _,x in sorted(_scored,key=lambda t:(-round(t[0],3),-float(t[1][0] or 0)))]
            if _mood is not None and top_all:
                # Movie + mood ("Inception" + "Funny"): stay inside Inception's closest matches and order them
                # half by closeness, half by how strongly fans tag them with the mood. Never pull in movies
                # that aren't like the searched one.
                _cand=top_all[:60]
                _mv=[float(_mood[i]) if (i:=_cf_idx(m)) is not None else 0.0 for _,m in _cand]
                _fit=[j for j in range(len(_cand)) if _mv[j]>0]
                st.session_state._mood_thin=len(_fit)<4
                if len(_fit)>=4:
                    _mr={j:r for r,j in enumerate(sorted(_fit,key=lambda j:-_mv[j]))}
                    _cr={j:r for r,j in enumerate(_fit)}
                    top_all=[_cand[j] for j in sorted(_fit,key=lambda j:0.5*_cr[j]+0.5*_mr[j])]
            else:
                st.session_state._mood_thin=False
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
        # Tonight's Show keeps its pick out of the rows, except in a movie search, where Tonight's Show is hidden.
        reserved={tonight_queue[0][1]["title"]} if (tonight_queue and _state not in ("movie","like")) else set()
        if _src:
            reserved.add(_src.get("title"))      # the searched movie never repeats in a row below it
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
            # Movie state: Top Picks also fills the three places beside the Top result (SEARCH_RULE).
            _want=8 if (row_name=="Top Matches for You" and _state in ("movie","like")) else 4
            for item in ordered:
                if len(picks)>=_want:
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
            if row_name=="Top Matches for You" and _state!="none":
                continue   # a search sets this row's order (closest to X first, or mood-led); re-sorting by fit undid it
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
                    "model_version":"v5.192",
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
        st.session_state.showroom_rate_ask={}
        st.session_state.showroom_pill_labels={}
        if _src_item is not None:
            payloads.setdefault(_src_item[1]["title"],{
                "match":_src_item[0],
                "movie":_src_item[1],
                "semantic_similarity":semantic_by_id.get(id(_src_item[1]),.5),
                "cf":cf_by_title.get(_src_item[1]["title"]),
                "model_match":model_match_by_title.get(_src_item[1]["title"],_src_item[0]),
            })
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
            _pl["seq_parts"] = seq_parts_by_title.get(_t)
            _pl["cf_name"] = _cf_name
            _pl["personal_n"] = int(learning_result.samples or 0) if getattr(learning_result, "ready", False) else 0
            _sv = _pl.get("semantic_similarity")
            if _sems and isinstance(_sv, (int, float)):
                _pl["tone_pct"] = int(round(100 * _bis.bisect_left(_sems, _sv) / len(_sems)))
        # Love chance, on the same footing as its test: each movie's rank among the 600 most-loved movies
        # you haven't marked, by the routed fans-like-you score (training/evaluate_love_and_learning.py).
        # The blended rank above stays for "#N of M" in the popup; it isn't what the chance table was fit on.
        try:
            from src import cf_model as _cfL
            import numpy as _npL
            _mL = _cfL._load()
            if _mL is not None and cf_user is not None and len(cf_user.scores) == len(_mL.fan_pct):
                _seenL = {i for i in (_cfL._index(m) for m, _a in (_signals or [])) if i is not None}
                _poolL = [int(i) for i in _npL.argsort(-_mL.fan_pct) if int(i) not in _seenL][:600]
                _ps = _npL.sort(cf_user.scores[_poolL])
                for _t, _pl in payloads.items():
                    _i = _cfL._index(_pl.get("movie") or {})
                    if _i is None:
                        continue
                    _higher = len(_ps) - int(_npL.searchsorted(_ps, float(cf_user.scores[_i]), side="right"))
                    _pl["love_top_pct"] = round(100.0 * (_higher + 1) / len(_ps), 2)
        except Exception:
            pass
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
        _library_counts("saved"); _library_counts("seen")
        # The search sits inside the Showroom tab: it only changes Showroom rows, so Saved, Seen and
        # Profile stay clean. One keyed slot holds chips or suggestions, so the layout never shifts.
        from src.mood import available as _mood_ready
        _state = _search_state()
        _rule = SEARCH_RULE[_state]
        _src_now = _like_source() if _state in ("movie", "like") else None
        # One line says what the search changed, so nobody wonders why the rows moved.
        if _state != "none":
            _w = _search_words()
            _n_found = len(row_choices.get("Top Matches for You", []))
            if _src_now:
                # The large card and "More Like ..." already say what the page is; only a mood filter needs a line.
                _say = ((f"Few movies like {_src_now['title']} fit {_w}, so these are the closest that do." if st.session_state.get("_mood_thin")
                         else f"Matches narrowed to {_w}.") if _w else None)
            else:
                _say = f"Your picks, narrowed to {_w}. Clear the search to get your usual picks back."
            st.session_state._search_status = _say
        else:
            st.session_state._search_status = None
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
                top = _love_pct(pay)
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
        top_slots = _strong_slots(top_name, len(row_choices.get(top_name, [])))
        from src.mood import available as _mood_ready2
        if _mood_ready2():
            render_search_box()     # first on the page; the status line set above is drawn inside it, under the tokens
        _disliked_src = bool(_src_now and (st.session_state.get("seen_rating") or {}).get(_src_now.get("title")) == -1)
        if _rule["top_result"] and _src_now:
            # Movie state: the searched movie, large, with Save to Watch / I've Seen It. Its matches follow.
            render_top_result()
            if _disliked_src:
                st.markdown(f'<div class="search-status">Got it: fewer movies like {html.escape(_src_now["title"])}. '
                            'Clear the search to get your usual picks back.</div>', unsafe_allow_html=True)
                top_slots = []
        # One unified guide, like the Apple TV app's Home: no toggles. Tonight's Show, Top Picks,
        # Shows for You, and More to explore (critics' picks, hidden gems and your fourth row mixed in
        # one row, each card labeled), so there are never more than three rows under the hero.
        from src import tv as _tv
        if _rule["tonight"]:
            render_tonight_pick_fragment()
        else:
            st.session_state.tonight_current = None

        _words = _search_words()
        if _src_now:
            _top_note = f"More like {_src_now['title']}" + (f" · {_words}" if _words else "")
        else:
            _top_note = _mood_line() or row_notes[top_name]
        if top_slots:
            _header(f"More Like {_src_now['title']}" if _src_now else "Top Picks for You",
                    ("Closest first" + (f" · {_words}" if _words else "")) if _src_now else _top_note)
            _draw_cards(0, [(top_name, 0, i) for i in top_slots[:4]])
            if _src_now and len(top_slots) > 4:
                _draw_cards("more", [(top_name, 0, i) for i in top_slots[4:8]])   # a second line of matches
        elif _state == "none":
            _header(f"More like {_src_now['title']}" if _src_now else "Top Picks for You",
                    ("Closest first, kept to what fits you" + (f" · {_words}" if _words else "")) if _src_now else _top_note)
            st.caption("Refreshing personalized matches…")

        if _tv.available() and _rule["shows"]:
            from src.ui.shows import render_shows
            render_shows({"movie_thumb": movie_thumb, "card_html": card_html, "watch_line_html": watch_line_html,
                          "record_event": record_event, "queue_profile_save": queue_profile_save, "signals": _cf_signals,
                          "spec": _mood_spec(), "like_source": _src_now, "search_words": _words,
                          "avoid_terms": [t for w in (_mood_spec().get("avoid") or []) for t in AVOID_TERMS.get(w, [w])]}, 4)

        cells = []
        if _rule["explore"]:
            explore = [(r, row_specs.index(r)) for r in row_specs[1:]]
            pools = {r: _strong_slots(r, len(row_choices.get(r, []))) for r, _ in explore}
            depth = 0
            while len(cells) < 4 and any(len(v) > depth for v in pools.values()):
                for r, idx in explore:
                    if len(pools[r]) > depth and len(cells) < 4:
                        cells.append((r, idx, pools[r][depth]))
                depth += 1
        if cells:
            # Every row says when your search is shaping it.
            _header("More to explore", ("Critics’ picks, hidden gems, and something new, matching " + _words)
                    if _words else "Critics’ picks, hidden gems, and something new, all chosen for you")
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
            pass   # the profile above already shows what you like; no extra sentence here
        _render_profile_likes()
        # One row of three matching pills.
        likes_btn, edit, reset, _ = st.columns([1.4, 1.5, 1.3, 2.3], gap="small")
        with likes_btn:
            # Step 1 with your likes filled in: add, favorite, or remove (search there too).
            st.button("Edit My Likes", key="edit_likes", use_container_width=True, on_click=go, args=("shelf",),
                      help="Add or remove the movies every pick starts from.")
        with edit:
            # Step 2 with every answer filled in; the models use the new answers on return.
            st.button("Edit My Answers", key="edit_preferences", use_container_width=True, on_click=go, args=("taste",),
                      help="Change your genres, reviews, adventure, services, and more-of answers.")
        with reset:
            if st.button("Reset Profile", key="reset_profile_tab", use_container_width=True,
                         help="Start over: clears your likes, saves, and answers in this browser."):
                reset_profile_state()
                st.rerun(scope="app")
        # Privacy and moving devices: one quiet card, two rows, each a label, one line of why, and its control.
        try:
            _host = st.context.headers.get("host") or "icinema.streamlit.app"
        except Exception:
            _host = "icinema.streamlit.app"
        # Your data: drawn fresh with its own names, so none of the older card styles can reach it.
        # Hairlines are their own elements between rows, so they can never touch the text.
        st.markdown('<div class="pc-section">Privacy</div>', unsafe_allow_html=True)
        with st.container(key="privacy_card"):
            with st.container(key="privacy_row_share"):
                txt, ctl = st.columns([5, 1.3], vertical_alignment="center")
                with txt:
                    st.markdown('<div class="pc-label">Share Anonymous Usage Counts</div>', unsafe_allow_html=True)
                with ctl:
                    st.toggle("Share anonymous usage counts", value=not st.session_state.get("analytics_opt_out", False),
                              key="_share_counts", on_change=_set_opt_out, label_visibility="collapsed")
            st.markdown('<div class="pc-hr"></div>', unsafe_allow_html=True)
            with st.container(key="privacy_row_move"):
                txt, ctl = st.columns([5, 1.3], vertical_alignment="center")
                with txt:
                    st.markdown('<div class="pc-label">Move to Another Device</div>', unsafe_allow_html=True)
                with ctl:
                    with st.container(key="privacy_link"):
                        with st.popover("Get link", use_container_width=True):
                            st.markdown('<div class="why-pop-head" style="font-size:1rem">Open this link on your other device</div>'
                                        '<div class="why-pop-line">Anyone with the link can load this profile, so share it only with yourself.</div>',
                                        unsafe_allow_html=True)
                            st.code(f"https://{_host}/?p={_encode_profile_link(profile_snapshot())}", language=None)
        st.markdown('<div class="pc-footer">Everything stays in this browser. No account, nothing personal. Usage counts are visits '
                    'and saves with a random ID, never titles, names, email, or location. The link carries your likes, saves, '
                    'and answers, so keep it to yourself.</div>', unsafe_allow_html=True)


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
        render_home({"logo": logo, "go": go, "current_hits": _current_hits})

    elif screen=="shelf":
        render_shelf_fragment()

    elif screen=="taste":
        render_taste_fragment()

    elif screen=="more":        # Step 3 merged into Step 2; older saved sessions land on the merged page
        render_taste_fragment()

    elif screen=="profile":
        logo()
        render_ready_summary({"signals": _cf_signals, "learning_model_for": learning_model_for})
        with st.container(key="nav_row_profile"):
            back, cont, _ = st.columns([1, 2, 4], gap="small")
            with back:
                st.button("← Back", key="back_profile", use_container_width=True, on_click=go, args=("taste",))
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

