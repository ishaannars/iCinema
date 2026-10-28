
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
from src.tmdb_catalog import search_movies, get_poster_batch, get_landscape_batch, get_movie_identity_batch, tmdb_catalog_configured, discover_movies
from src.live_ratings import get_live_ratings_batch, omdb_configured
from src.browser_storage import browser_storage
from src.scroll_keeper import scroll_keeper
from src.cf_model import user_vector, cf_affinity, closest_liked, item_similarity, fan_percentile, preferred_title
from src.recommender import _calibrated_match_percent

st.set_page_config(page_title="iCinema", page_icon="🎬", layout="wide", initial_sidebar_state="collapsed")

from src.ui import app_css
from src.love import love_line, fit_floor
from src.ui.watch import (STREAMING_SERVICES, PROVIDER_LINKS, _provider_key, _on_service, provider_watch_url,
                          watch_options, watch_line_html, concise_availability_text, movie_on_services)

st.markdown("<style>" + app_css() + "</style>", unsafe_allow_html=True)

defaults={
    "screen":"welcome","onboarding_complete":False,"likes":set(),"favorites":set(),"review_priority":50,
    "genres":[],"adventure":50,"more_of":[],"saved":set(),"seen":set(),"dismissed":set(),"disliked":set(),"seen_from_saved":set(),"seen_rating":{},"selection_order":[],
    "custom_like":None,"search_selected_title":None,"search_selected_movie":None,"external_movies":{},
    "shelf_movies":[],"shelf_replacement_pool":[],"shelf_seen_titles":set(),
    "shelf_pool_initialized":False,"shelf_tmdb_loaded":False,
    "analytics_events":[],"showroom_session_id":None,"showroom_session_start":None,
    "showroom_impression_keys":set(),"recommendation_context":{},
    "showroom_slots":{},"showroom_payloads":{},"showroom_row_queues":{},
    "showroom_identity_cache":{},"showroom_watch_cache":{},"showroom_rating_cache":{},
    "streaming_services":[]
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
        "external_movies": st.session_state.external_movies,
        "analytics_events": list(st.session_state.get("analytics_events", []))[-2000:],
        "streaming_services": list(st.session_state.get("streaming_services") or []),
    }

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
        st.session_state.external_movies = dict(data.get("external_movies") or {})
        st.session_state.analytics_events = list(data.get("analytics_events") or [])[-2000:]
        st.session_state.streaming_services = list(data.get("streaming_services") or [])
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
    st.session_state._last_persisted_profile = json.dumps(profile_snapshot(), sort_keys=True, default=str) if restored else None

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

def _snapshot_signature(snapshot):
    return json.dumps(snapshot, sort_keys=True, default=str)

def persist_profile_if_needed():
    if not st.session_state.get("_storage_hydrated", False):
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
    st.session_state._pending_profile_save = profile_snapshot()

RECOGNIZABLE_SHELF_TITLES = [
    "Dune: Part Two", "Blade Runner 2049", "The Prestige", "Prisoners",
    "Nightcrawler", "The Truman Show", "The Grand Budapest Hotel",
    "No Country for Old Men", "Before Sunrise", "Train to Busan",
    "Your Name", "Princess Mononoke", "Akira", "Ex Machina",
    "Past Lives", "The Holdovers", "The Wailing", "The Handmaiden",
    "Memories of Murder", "The Worst Person in the World",
]

def _shelf_key(movie):
    return (str(movie.get("title", "")).casefold(), int(movie.get("year") or 0))

def _seed_local_shelf_pool():
    if st.session_state.shelf_pool_initialized:
        return
    selected = st.session_state.likes | st.session_state.favorites
    pool = []
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
        st.session_state.shelf_movies = [dict(m) for m in STARTER_MOVIES if m.get("title") not in selected]
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


def card_ratings(movie, live_rating):
    """The one set of ratings a card shows and its explanations cite.

    Live OMDb scores first, then the scores stored with the movie. TMDB's viewer
    score is used only when neither IMDb nor Rotten Tomatoes is available.
    """
    movie, live = movie or {}, live_rating or {}
    def pick(key):
        for source in (live, movie):
            value = source.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        return None
    imdb, rt = pick("imdb"), pick("rt")
    tmdb = None if imdb else pick("tmdb_vote")  # viewer score stands in only when IMDb is missing
    return {"imdb": imdb, "rt": rt, "tmdb_vote": tmdb}


def ratings_text(ratings):
    """'IMDb 7.1 · RT 88%', 'IMDb 7.1 · No RT', or 'Viewers 7.9/10 · No RT'."""
    audience = (f"IMDb {ratings['imdb']:.1f}" if ratings.get("imdb") else
                (f"Viewers {ratings['tmdb_vote']:.1f}/10" if ratings.get("tmdb_vote") else None))
    critics = f"RT {int(ratings['rt'])}%" if ratings.get("rt") else "No RT"
    if not audience and critics == "No RT":
        return []  # nothing to show; the card says "Ratings unavailable"
    return [x for x in (audience, critics) if x]


def with_live_ratings(movie, live_rating):
    """Copy of the movie carrying exactly the ratings shown on its card."""
    movie = dict(movie or {})
    ratings = card_ratings(movie, live_rating)
    for key in ("imdb", "rt"):
        if ratings[key]:
            movie[key] = ratings[key]
        else:
            movie.pop(key, None)
    if ratings["tmdb_vote"]:
        movie["tmdb_vote"] = ratings["tmdb_vote"]
    else:
        movie.pop("tmdb_vote", None)  # explanations cite only what the card shows
    return movie


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
        else:
            reason = {"label": "Loved by viewers like you",
                      "text": "Viewers who liked the movies you liked tend to love this too."}
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
_PILL_SHORT = {
    "Feels like your favorites": "Like your favorites",
    "Feels like your pick": "Like your pick",
    "Storytelling you like": "Your kind of story",
    "Critically acclaimed": "Critics' pick",
    "Easy to watch tonight": "Streaming now",
    "International pick": "International",
    "Loved by viewers like you": "Fans like you",
}
PILL_BUDGET = 25  # characters, including "80% · ", that fit a card pill without clipping


def _short_reason(reason, room):
    """Pill-sized version of a reason label, or None if it can't fit without cutting."""
    label = str((reason or {}).get("label") or "").strip()
    if label.startswith("Loved by fans of "):
        fans = "Fans of " + label[len("Loved by fans of "):]
        label = fans if len(fans) <= room else "Fans like you"
    label = _PILL_SHORT.get(label, label)
    if label.startswith("Your kind of ") and len(label) > room:
        label = label[len("Your kind of "):].strip().capitalize() + " pick"
    return label if label and len(label) <= room else None


def fit_head(payload, match):
    """Rank-based fit: where this movie ranks among every movie iCinema scored for you.

    Accurate by construction (it is a rank, not a probability), and it spreads out
    even when the raw scores of top picks sit close together.
    """
    top = (payload or {}).get("fit_top_pct")
    return f"Top {int(top)}%" if isinstance(top, (int, float)) else f"{int(match or 0)}%"


def fit_label(payload, match):
    top = (payload or {}).get("fit_top_pct")
    if not isinstance(top, (int, float)):
        return match_label(match)
    return "Made for you" if top <= 2 else "Strong match" if top <= 10 else "Good match" if top <= 25 else "Worth a look"


def match_pill(match, reasons, limit=None, taken=(), head=None):
    """Percent plus this movie's strongest reason not already shown in its row.

    Returns (pill_text, label_used). Skipping labels other cards in the row already
    use keeps a row varied, e.g. one "Fans of “Spirited Away”" instead of four.
    """
    match = int(match or 0)
    head = head or f"{match}%"
    room = (limit if limit is not None else PILL_BUDGET) - len(f"{head} · ")
    for reason in reasons or []:
        label = _short_reason(reason, room)
        if label and label not in taken:
            return f"{head} · {label}", label
    return f"{head} for you", None


def match_label(match):
    """Plain-language fit instead of a bare percentage; the % stays in the explanation."""
    match = int(match or 0)
    if match >= 70:
        return "Made for you"
    if match >= 55:
        return "Strong match"
    if match >= 42:
        return "Good match"
    return "Worth a look"


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
    st.session_state.seen.discard(title)
    st.session_state.seen_rating = {k: v for k, v in (st.session_state.get("seen_rating") or {}).items() if k != title}
    from_saved = set(st.session_state.get("seen_from_saved") or set())
    if title in from_saved:
        from_saved.discard(title)
        st.session_state.seen_from_saved = from_saved
        st.session_state.saved.add(title)
    _drop_last_event(title, "seen")
    queue_profile_save()


def library_ratings_html(movie, identity, live_map):
    """Same ratings line as the Showroom cards (IMDb · RT, 'No RT', or viewer score)."""
    parts = ratings_text(card_ratings(movie, (live_map or {}).get(movie["title"]) or {}))
    return (f'<div class="ratings library-ratings">{" · ".join(parts)}</div>' if parts
            else '<div class="ratings library-ratings muted">Ratings unavailable</div>')


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
    for key in ("tonight_services_picker", "tonight_last_skip", "tonight_pool", "showroom_undo", "showroom_pill_labels"):
        st.session_state.pop(key, None)
    queue_profile_save()

def reset_profile_from_fragment():
    reset_profile_state()
    st.session_state._app_rerun = True

def logo():
    st.markdown('<div class="icinema-logo">iCinema</div>',unsafe_allow_html=True)

def movie_thumb(movie, poster_url=None, compact=False, library_mode=None):
    title = html.escape(str(movie.get("title", "")))
    year = html.escape(str(movie.get("year", "")))
    poster_url = poster_url or movie.get("poster_url")
    if poster_url and not str(poster_url).lower().startswith(("https://", "http://")):
        poster_url = None   # only web image links reach the page
    if poster_url:
        safe_url = html.escape(str(poster_url), quote=True)
        poster_html = f'<div class="poster has-image"><img src="{safe_url}" alt="Poster for {title}"></div>'
    else:
        poster_html = '<div class="poster"><div class="poster-placeholder-mark">iCINEMA</div></div>'

    year_html = f'<div class="poster-caption-year">{year}</div>' if year else ''
    
    if library_mode == "saved":
        caption_class = "poster-caption library-poster-caption saved-poster-caption"
    elif library_mode == "seen":
        caption_class = "poster-caption library-poster-caption seen-poster-caption"
    else:
        caption_class = 'poster-caption library-poster-caption' if compact else 'poster-caption'
    st.markdown(
        poster_html
        + f'<div class="{caption_class}"><div class="poster-caption-title" title="{title}">{title}</div>{year_html}</div>',
        unsafe_allow_html=True
    )

def current_profile():
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
    queue_profile_save()

def concise_description(text, limit=138):
    """Return a compact *complete-sounding* description for aligned movie cards.

    Prefer a full first sentence. If the source is longer, shorten on a natural
    phrase boundary and never leave dangling filler words such as "a" or "the".
    """
    text = " ".join(str(text or "").split()).strip()
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text)
    first_sentence = sentences[0].strip() if sentences else text
    if len(first_sentence) <= limit:
        return first_sentence if first_sentence.endswith((".", "!", "?")) else first_sentence + "."

    candidate = first_sentence
    # Prefer a natural clause boundary before falling back to a word boundary.
    boundaries = [m.end() for m in re.finditer(r"[,;:]\s+|\s+[–—-]\s+", candidate[:limit + 1])]
    if boundaries:
        candidate = candidate[:boundaries[-1]].rstrip(" ,;:–—-")
    else:
        candidate = candidate[:limit].rsplit(" ", 1)[0].rstrip(" ,;:–—-")

    dangling = {"a", "an", "the", "and", "or", "but", "with", "to", "of", "in", "for", "from", "by"}
    words = candidate.split()
    while words and words[-1].casefold().strip(".,;:") in dangling:
        words.pop()
    candidate = " ".join(words).rstrip(" ,;:.…")
    return candidate + "." if candidate else first_sentence

from src.descriptions import expanded_card_description, quick_card_description, tonight_description  # card text rules (unit-tested)



def profile_chip_html(items):
    return "".join(f'<span class="profile-chip">{item}</span>' for item in items)

def profile_analysis_html(items):
    return "".join(f'<div class="profile-analysis-row">{item}</div>' for item in items)

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


def learning_model_for(events):
    """Train the Save/Skip model only when feedback changed since the last run."""
    events = list(events or [])
    signature = (len(events), events[-1].get("timestamp") if events else None)
    cache = st.session_state.get("_learning_model_cache")
    if cache and cache[0] == signature:
        return cache[1]
    result = train_learning_model(events)
    st.session_state._learning_model_cache = (signature, result)
    return result


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
    _early = (f'<span class="profile-chip profile-chip-muted">Like or save {3 - _n} more movie{"s" if 3 - _n != 1 else ""} to see your tone and patterns</span>'
              if _n < 3 else "")
    sections = [
        (f"You tend to enjoy · from {_n} movies" if p["traits"] else "Your tone", profile_chip_html(p["traits"]) or _early, "profile-chip-wrap"),
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
    insights=analytics_insights(events)
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
                         f'<span class="model-note">Learns from your saves and skips: {min(decisions, 50)} of 50 · '
                         f'{int(insights.get("saves") or 0)} saves, {int(insights.get("skips") or 0)} skips (needs 12+ of each; Seen doesn\'t count)</span>'
                         f'<span class="model-progress"><span style="width:{pct}%"></span></span></div>')
    models_html = (
        '<div class="model-status-panel">'
        '<div class="model-row"><span class="model-dot on"></span>'
        '<span class="model-name">Active now</span>'
        f'<span class="model-note">Viewers like you ({(scale["users"] + " ") if scale["users"] else ""}MovieLens fans) and the content model, '
        f'using your {signals} signal{"s" if signals != 1 else ""}'
        + (f' ({html.escape(signal_parts)})' if signal_parts else '')
        + '. Every save, skip, and Seen updates it.</span></div>'
        f'{personal_html}'
        '</div>'
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
              "Median per visit. A visit ends after 30 idle minutes."),
        _stat(_or_learning("avg_skips_before_save", lambda v: f"{v:.1f}"), "Skips before a save",
              "Lower means the first picks are landing."),
        _stat(_or_learning("avg_recommendations_examined_before_save", lambda v: f"{v:.0f}"), "Movies shown before a save",
              "How many picks it took to find one you wanted."),
        _stat(_or_learning("saved_to_seen_rate", lambda v: f"{v*100:.0f}%"), "Saved, then watched",
              "Share of your saves you later marked Seen."),
        _stat(_or_learning("discovery_rate", lambda v: f"{v*100:.0f}%"), "Saves beyond Top Matches",
              "Finds from Critically Acclaimed, Hidden Gems, and Something Different."),
        _stat(conf, "Profile strength", "Grows with every like, save, and skip."),
    ]
    insight_html = "".join(insight_cards)

    ranking=ranking_metrics(events)
    calib=calibration_metrics(events)
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
        if sig.get("Hit@1") and sig.get("NDCG@10") and sig.get("Recall@10"):
            significance_note = "All three results are statistically significant."
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
                     "and it does better than item-kNN for viewers with less mainstream taste.")
        if cards and isinstance(users, int):
            proof_html = (
                '<div class="profile-methodology">'
                f'<div class="profile-insights-title">Tested on {users:,} real viewers</div>'
                f'<div class="profile-insights-copy">iCinema saw only 3 random movies each MovieLens viewer liked, then predicted the films '
                'they’d rate 4+ stars later, compared with simply recommending what’s popular. '
                f'{significance_note}{full_note}</div>'
                f'<div class="insight-grid proof-grid">{"".join(cards)}</div>'
                '</div>'
            )

    live_html = ""
    if learned.ready:
        auc = lm.get("auc")
        live_html = (
            '<div class="profile-insights-copy live-model-copy">'
            f'Your personal model is active: {html.escape(learned.model_name)}, trained on {learned.samples} of your choices'
            + (f', and it predicts your saves well above chance (AUC {auc:.2f}).' if isinstance(auc, (int, float)) else '.')
            + '</div>'
        )

    methodology_html = (
        '<div class="profile-methodology">'
        '<div class="profile-insights-title">How iCinema works</div>'
        '<div class="methodology-grid how-grid">'
        '<div class="methodology-card">'
        f'<div class="methodology-value">Starts with {scale["users"] or "MovieLens"} movie fans</div>'
        f'<div class="methodology-label">A model trained on how they rated {scale["movies"] or "thousands of"} movies compares your first likes with theirs, '
        'so your first picks are already personal. If your likes are less mainstream, a ranking method tested for that takes over.</div>'
        '</div>'
        '<div class="methodology-card">'
        '<div class="methodology-value">Understands every movie</div>'
        '<div class="methodology-label">A second model compares movies by their genres and the tags MovieLens fans gave them, and weighs them by your setup answers.</div>'
        '</div>'
        '<div class="methodology-card">'
        '<div class="methodology-value">Gives every row a job</div>'
        '<div class="methodology-label">Best fit, critics’ favorites, hidden gems, or something new, and no movie appears twice. '
        'Each row was tested: within its kind, it finds movies you’ll love more often than the most popular ones.</div>'
        '</div>'
        '<div class="methodology-card">'
        '<div class="methodology-value">Learns you over time</div>'
        '<div class="methodology-label">After 50 saves and skips, a third model trained only on your choices joins in. Undo keeps accidental taps out.</div>'
        '</div>'
        '</div>'
        '<div class="profile-insights-copy ratings-note">About ratings: IMDb and Rotten Tomatoes scores come from OMDb. '
        'When IMDb has no score, iCinema shows the viewer rating from TMDB, a large community movie database. '
        '“No RT” means Rotten Tomatoes hasn’t reviewed the movie.</div>'
        '<div class="profile-insights-copy ratings-note">Fresh every visit: movies you passed over step back, and iCinema '
        'searches deeper into your favorite genres, so new picks keep surfacing.</div>'
        f'{live_html}'
        '</div>'
        f'{proof_html}'
    )

    insights_section = (
        f'<div class="profile-insights"><div class="profile-insights-title">iCinema’s Insights</div>'
        f'<div class="profile-insights-copy">How fast iCinema gets you from browsing to a movie worth watching.</div>'
        f'<div class="insight-grid stats-grid">{insight_html}</div></div>'
        f'{methodology_html}'
        if include_insights else ""
    )

    heading_class = "tab-primary-heading profile-heading-aligned" if tab_heading else "profile-heading"
    profile_heading_html = f'<div class="{heading_class}">Your Cinema Profile</div>' if show_heading else ""

    st.markdown(
        f'<div class="profile-wrap">'
        f'{profile_heading_html}'
        f'<div class="profile-heading-gap"></div>'
        f'{models_html}'
        f'<div class="profile-grid">{section_html}</div>'
        f'<div class="profile-summary">{p["summary"]}</div>'
        f'{insights_section}'
        f'</div>', unsafe_allow_html=True
    )



import functools as _functools


def _with_app_rerun(fn):
    """Run a full-app rerun requested by a button callback (callbacks themselves can't)."""
    @_functools.wraps(fn)
    def inner(*args, **kwargs):
        if st.session_state.pop("_app_rerun", False):
            st.rerun(scope="app")
        return fn(*args, **kwargs)
    return inner


@st.fragment(run_every="4s")
@_with_app_rerun
def render_live_profile():
    """Profile tab, refreshed every few seconds.

    Showroom cards rerun on their own (so Skip/Save stay fast), which used to leave this
    tab showing counts from when the Showroom was built. Rebuilding it from current state
    keeps the signals and the "x of 50" progress matching what you just did.
    """
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
            movie_thumb(movie, shelf_landscape_map.get(title) or movie.get("poster_url") or shelf_poster_map.get(title))
            b1,b2,b3=st.columns([1,1.3,1], gap="small")
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
            with b3:
                st.button(
                    "Skip",
                    key=f"shelfskip_{i}_{movie.get('tmdb_id') or title}",
                    use_container_width=True,
                    on_click=skip_shelf_movie,
                    args=(i,),
                )

    with st.container(key="step1_search"):
        st.markdown(
            '<div class="search-shell">'
            '<div class="search-shell-title">Don’t see one you like?</div>'
            '<div class="search-shell-copy">Search for a movie you already enjoy</div>'
            '</div>',
            unsafe_allow_html=True
        )

        search_query = live_search_box()

        matches = []
        already_selected_matches = []
        if search_query.strip():
            if tmdb_catalog_configured():
                matches = search_movies(search_query.strip(), 8)
            else:
                q = search_query.strip().lower()
                local_titles = [title for title in searchable_titles() if q in title.lower()][:8]
                matches = [get_movie(title) for title in local_titles if get_movie(title)]

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
                st.markdown('<div class="search-results-label">Matching titles</div>', unsafe_allow_html=True)
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
                    st.caption("No movie matches found")
                else:
                    st.caption("TMDB search is unavailable, showing matches from the current iCinema catalog only")

        choice_movie = st.session_state.search_selected_movie
        if choice_movie:
            choice = choice_movie["title"]
            st.markdown(
                f'<div class="search-selected-card">'
                f'<div class="search-selected-kicker">Selected title</div>'
                f'<div class="search-selected-title">{html.escape(choice)}{html.escape(f" ({choice_movie.get('year')})") if choice_movie.get("year") else ""}</div>'
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

    with st.container(key="step1_selections"):
        _selected_set = st.session_state.likes | st.session_state.favorites
        chosen_titles = [t for t in st.session_state.get("selection_order", []) if t in _selected_set]
        chosen_titles += sorted(_selected_set - set(chosen_titles))
        chosen_count = len(chosen_titles)

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
        '<div class="step2-subtitle">Choose what matters most when deciding what to watch</div>'
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
        f'<div class="pref-scale-helper">{review_label}</div>'
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
    st.markdown('<div class="genre-helper">Select up to five genres</div>', unsafe_allow_html=True)
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
        f'<div class="pref-scale-helper">{adventure_label}</div>'
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
        '<div class="page-top-subtitle step3-subtitle">What should iCinema lean toward? Choose any that you want to see more often</div>',
        unsafe_allow_html=True,
    )

    descriptions = {
        "Hidden Gems": "Less obvious titles that still fit what you like",
        "Critically Acclaimed": "Titles with especially strong critical reception",
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
    for title in queues.get(row_name, []):
        if not title or title in current_titles or title in excluded:
            continue
        if title not in payloads:
            continue
        replacement = title
        break

    if replacement:
        slots[slot_key] = replacement
        st.session_state.showroom_slots = slots
        return True
    return False

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
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    movie = payload.get("movie")
    if title:
        save_movie(title, movie)
        undo = dict(st.session_state.get("showroom_undo") or {})
        undo.pop(slot_key, None)
        st.session_state.showroom_undo = undo
    _advance_showroom_slot(row_name, slot_index)
    _mark_showroom_fast()

def seen_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    movie = payload.get("movie")
    if title:
        mark_movie_seen(title, movie)
        undo = dict(st.session_state.get("showroom_undo") or {})
        undo.pop(slot_key, None)
        st.session_state.showroom_undo = undo
    _advance_showroom_slot(row_name, slot_index)
    _mark_showroom_fast()

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
        st.caption("Refreshing match…")
        return

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
                    "↶",
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
        pill_labels = dict(st.session_state.get("showroom_pill_labels") or {})
        row_taken = {label for key, label in pill_labels.items()
                     if key.startswith(f"{row_name}::") and key != slot_key and label}
        pill_text, pill_label = match_pill(match, reasons, taken=row_taken, head=fit_head(payload, match),
                                           limit=19 if undo_title else None)
        pill_labels[slot_key] = pill_label
        st.session_state.showroom_pill_labels = pill_labels
        with match_col:
            with st.popover(pill_text, use_container_width=True):
                st.markdown(
                    f'<div class="match-score"><span class="match-score-value">{fit_head(payload, match)}</span>'
                    f'<span class="match-score-label">· {html.escape(fit_label(payload, match))}</span></div>'
                    + (f'<div class="match-rank-note">{html.escape(love_line(payload.get("fit_top_pct")))}</div>'
                       if love_line(payload.get("fit_top_pct")) else "") +
                    '<div class="match-explain-title">Why this matches you</div>',
                    unsafe_allow_html=True,
                )
                for reason in reasons:
                    st.markdown(
                        f'<div class="match-reason">'
                        f'<div class="match-reason-label">{html.escape(reason["label"])}</div>'
                        f'<div class="match-reason-copy">{html.escape(reason["text"])}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    '<div class="match-model-note">The strongest reasons behind this pick.</div>',
                    unsafe_allow_html=True,
                )
                st.button(
                    "Not for me",
                    key=f"dislike_{row_name}_{slot_index}_{title}",
                    help="Hide this movie and show fewer like it. Undo brings it back.",
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
    movie_thumb(display_movie, identity.get("poster_url") or movie.get("poster_url"))

    rating_parts = ratings_text(card_ratings(movie, live_rating))
    rating_class = "ratings" if rating_parts else "ratings muted"
    rating_text = " · ".join(rating_parts) or "Ratings unavailable"
    st.markdown(f'<div class="{rating_class}">{rating_text}</div>',unsafe_allow_html=True)

    availability_class = "watch-availability muted" if availability.get("status") in {"unknown", "not_configured", "unavailable"} else "watch-availability"
    watch_html = watch_line_html(availability, movie.get("title", ""), st.session_state.get("streaming_services"))
    st.markdown(f'<div class="{availability_class}">{watch_html}</div>', unsafe_allow_html=True)

    quick_desc = quick_card_description(dict(movie, tagline=identity.get("tagline")), limit=92)
    expanded_desc = expanded_card_description(movie)
    summary_id = f"movie-summary-{row_index}-{slot_index}"
    st.markdown(
        f'<div class="movie-summary-toggle">'
        f'<input class="movie-summary-checkbox" type="checkbox" id="{summary_id}">'
        f'<label class="movie-summary-label" for="{summary_id}">{html.escape(quick_desc)}</label>'
        f'<div class="movie-full-description">'
        f'<div class="movie-synopsis-label">Premise</div>'
        f'<div class="movie-synopsis-copy">{html.escape(expanded_desc)}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    # Persist Skip / Undo during this card-only rerun without creating a visible loader.
    persist_from_fragment()


def render_card_actions(row_name, row_index, slot_index):
    """Save / Seen sit outside the card fragment: a click runs the page once, directly,
    so the Saved / Seen tabs update without a second rerun triggered from a fragment."""
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
    skip_movie(title, movie)
    st.session_state.tonight_last_skip = title


def tonight_dislike(title, movie):
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
    save_movie(title, movie)
    st.session_state.tonight_last_skip = None
    _mark_showroom_fast()
    _request_showroom_refresh()


def tonight_seen(title, movie):
    mark_movie_seen(title, movie)
    st.session_state.tonight_last_skip = None
    _mark_showroom_fast()
    _request_showroom_refresh()


def _render_services_picker(services):
    label = f"Your services · {len(services)}" if services else "Choose your services"
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
    meta = " · ".join(str(x) for x in [year, genre] + ratings if x)

    watch_html = watch_line_html(availability, movie.get("title", ""), services)
    options = watch_options(availability, movie.get("title", ""), services, limit=1)
    fit = ""  # the streaming line already lists the viewer's services first

    reasons = with_cf_reason(recommendation_explanation(
        with_live_ratings(movie, live_rating), p, st.session_state.adventure, st.session_state.review_priority,
        semantic_similarity=context.get("semantic_similarity"),
        availability_score=context.get("availability_alignment", 0.5),
        components=context,
    ), payload, limit=2)
    why_html = "".join(f'<div class="tonight-why"><strong>{html.escape(r["label"])}</strong> · {html.escape(r["text"])}</div>'
                       for r in reasons)

    _love = love_line(payload.get("fit_top_pct"))
    _love_short = _love.replace("If you watch it: about ", "About ").replace(" chance you'll love it", " chance you’ll love it") if _love else ""
    tonight_badge = ((f"Best on your services · " if services else "")
                     + (_love_short or f"{fit_head(payload, match)} for you"))
    with st.container(key=f"tonight_hero_{title}"):
        poster_col, info_col = st.columns([1, 6.2], gap="medium")
        with poster_col:
            st.markdown(poster_html, unsafe_allow_html=True)
        with info_col:
            st.markdown(
                '<div class="tonight-stack">'
                f'<div class="tonight-title">{html.escape(str(display_title))}</div>'
                f'<div class="tonight-meta">{html.escape(meta)}</div>'
                f'<div class="tonight-badges"><span class="tonight-match">{html.escape(tonight_badge)}</span>{fit}</div>'
                f'<div class="tonight-line">{watch_html}</div>'
                f'<div class="tonight-hook">{html.escape(tonight_description(dict(movie, tagline=identity.get("tagline")), limit=160))}</div>'
                f'<div class="tonight-whys">{why_html}</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            last_skip = st.session_state.get("tonight_last_skip")
            with st.container(key=f"tonight_actions_{title}"):
                # Save · Seen · Skip · thumbs-down, then Undo when there is something to undo.
                cols = st.columns([1, 1, 1, 0.42, 1, 1.78], gap="small")
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
                    st.button("Not for me", key=f"tonight_dislike_{title}",
                              help="Not for me: hide this movie and show fewer like it.",
                              on_click=tonight_dislike, args=(title, movie))
                with cols[4]:
                    if last_skip:
                        st.button("↶ Undo", key=f"tonight_undo_{title}", use_container_width=True,
                                  help=f"Bring back {last_skip}", on_click=tonight_undo)
    persist_from_fragment()


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
    st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
    st.markdown('<div class=\"tab-primary-heading saved-tab-heading\">Saved</div>', unsafe_allow_html=True)
    movies=[m for t in st.session_state.saved if (m := resolve_history_movie(t))]
    saved_identity_keys=tuple((m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in movies)
    saved_identity_map = get_movie_identity_batch(saved_identity_keys)
    saved_poster_map = get_poster_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies))
    saved_watch_map = get_watch_availability_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies), "US") if movies else {}
    saved_live_map = get_live_ratings_batch(tuple((m["title"], int(m.get("year") or 0),
                                                  (saved_identity_map.get(m["title"], {}) or {}).get("imdb_id") or "")
                                                 for m in movies)) if movies else {}
    if not movies:st.caption("Nothing saved yet.")
    else:
        cols=st.columns(4, gap="medium")
        for i,m in enumerate(movies):
            with cols[i % 4]:
                with st.container(key=f"savedcard_{i}"):
                    identity = saved_identity_map.get(m["title"], {}) or {}
                    display_movie = dict(m)
                    display_movie["title"] = preferred_title(m, identity.get("display_title") or display_movie.get("title", ""))
                    if identity.get("year"):
                        display_movie["year"] = identity["year"]
                    movie_thumb(display_movie, identity.get("poster_url") or m.get("poster_url") or saved_poster_map.get(m["title"]), compact=True, library_mode="saved")
                    st.markdown(library_ratings_html(m, identity, saved_live_map), unsafe_allow_html=True)
                    st.markdown(f'<div class="watch-availability saved-watch">{watch_line_html(saved_watch_map.get(m["title"]), m["title"], st.session_state.get("streaming_services"))}</div>', unsafe_allow_html=True)
                    saved_actions = st.columns(2, gap="small")
                    with saved_actions[0]:
                        st.button("Mark Seen", key=f"savedseen_{m['title']}", use_container_width=True,
                                  on_click=mark_movie_seen, args=(m["title"], m))
                    with saved_actions[1]:
                        st.button("Remove", key=f"unsave_{m['title']}", use_container_width=True,
                                  on_click=remove_saved_movie, args=(m["title"],))
    _library_counts()


@st.fragment
def _seen_tab():
    """Seen tab. A fragment, so its buttons rerun only this tab: the open tab never changes."""
    # Hidden refresh: switching to this tab clicks it (src/scroll_keeper_component), so a change made
    # on the other library tab shows up here without reloading the page.
    st.button("Refresh", key="refresh_seen")
    st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
    st.markdown('<div class=\"tab-primary-heading\">Seen</div>', unsafe_allow_html=True)
    movies=[m for t in st.session_state.seen if (m := resolve_history_movie(t))]
    seen_identity_keys=tuple((m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in movies)
    seen_identity_map = get_movie_identity_batch(seen_identity_keys)
    seen_poster_map = get_poster_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies))
    seen_live_map = get_live_ratings_batch(tuple((m["title"], int(m.get("year") or 0),
                                                 (seen_identity_map.get(m["title"], {}) or {}).get("imdb_id") or "")
                                                for m in movies)) if movies else {}
    if not movies:st.caption("Nothing marked as seen yet.")
    else:
        # What's next: one personalized follow-up per Seen movie, never the same pick
        # twice on this tab, never something already saved, seen, skipped or disliked.
        wn_payloads = st.session_state.get("showroom_payloads") or {}
        wn_blocked = (set(st.session_state.saved) | set(st.session_state.seen)
                      | set(st.session_state.dismissed) | set(st.session_state.get("disliked") or set()) | set(st.session_state.likes) | set(st.session_state.favorites))  # tabs9
        wn_offsets = st.session_state.get("whats_next_offset") or {}
        wn_taken, wn_picks = set(), {}
        for m in movies:
            ranked = [(t, cf) for t, cf in whats_next_ranking(m, wn_payloads, wn_blocked) if t not in wn_taken]
            if ranked:
                pick = ranked[int(wn_offsets.get(m["title"], 0)) % len(ranked)]
                wn_picks[m["title"]] = pick
                wn_taken.add(pick[0])
        wn_identity = st.session_state.get("showroom_identity_cache") or {}
        cols=st.columns(4, gap="medium")
        for i,m in enumerate(movies):
            with cols[i % 4]:
                with st.container(key=f"seencard_{i}"):
                    identity = seen_identity_map.get(m["title"], {}) or {}
                    display_movie = dict(m)
                    display_movie["title"] = preferred_title(m, identity.get("display_title") or display_movie.get("title", ""))
                    if identity.get("year"):
                        display_movie["year"] = identity["year"]
                    movie_thumb(display_movie, identity.get("poster_url") or m.get("poster_url") or seen_poster_map.get(m["title"]), compact=True, library_mode="seen")
                    st.markdown(library_ratings_html(m, identity, seen_live_map), unsafe_allow_html=True)
                    # Hover × in the poster's top-right corner: remove an accidental Seen.
                    st.button("✕", key=f"unseen_{m['title']}", help="Remove from Seen",
                              on_click=remove_from_seen, args=(m["title"],))
                    _r = (st.session_state.get("seen_rating") or {}).get(m["title"], 0)
                    with st.container(key=f"seenrate_{i}"):
                        up, down = st.columns(2, gap="small")
                        with up:
                            st.button("Loved it", key=f"seenup_{m['title']}",
                                      type="primary" if _r == 1 else "secondary", use_container_width=True,
                                      on_click=rate_seen, args=(m["title"], 1))
                        with down:
                            st.button("Not for me", key=f"seendown_{m['title']}",
                                      type="primary" if _r == -1 else "secondary", use_container_width=True,
                                      on_click=rate_seen, args=(m["title"], -1))
                    pick = wn_picks.get(m["title"])
                    if pick:
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
                            with st.popover("What’s next", use_container_width=True):
                                img = (f'<img src="{html.escape(str(nposter), quote=True)}" alt="">'
                                       if nposter else '<div class="whatsnext-noimg">iCINEMA</div>')
                                st.markdown(
                                    f'<div class="whatsnext-kicker">Watch next after “{html.escape(m["title"])}”</div>'
                                    f'<div class="whatsnext-pick"><div class="whatsnext-poster">{img}</div>'
                                    f'<div class="whatsnext-info">'
                                    f'<div class="whatsnext-title">{html.escape(str(ntitle))}</div>'
                                    f'<div class="whatsnext-meta">{html.escape(" · ".join(str(x) for x in [nyear, nmovie.get("genre")] if x))}'
                                    f' · {fit_head(npay, npay.get("match"))} for you</div>'
                                    f'<div class="whatsnext-why">{html.escape(why)}</div>'
                                    f'</div></div>',
                                    unsafe_allow_html=True,
                                )
                                # Compact pills, about the poster's width, aligned under the poster.
                                a, b, _ = st.columns([1, 1.35, 4.2], gap="small")
                                with a:
                                    st.button("Save", key=f"whatsnext_save_{i}_{nt}", use_container_width=True,
                                              on_click=save_movie, args=(nt, nmovie))
                                with b:
                                    st.button("Another pick", key=f"whatsnext_more_{i}_{nt}", use_container_width=True,
                                              on_click=whats_next_another, args=(m["title"],))
    _library_counts()


def render_showroom_fragment(p):
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
    fast = st.session_state.pop("_showroom_fast", False) and bool(st.session_state.get("showroom_slots"))
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
        ranked = rank_movies(
            candidate_pool,
            p,
            st.session_state.adventure,
            st.session_state.review_priority,
            excluded,
            None,
        )
        learning_result=learning_model_for(st.session_state.get("analytics_events", []))
        ranked_movies=[movie for _,movie in ranked]
        semantic_by_id=cached_semantic_scores(ranked_movies,p)
        cf_user=user_vector(_cf_signals())
        cf_by_title={}
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
                return rt>=85 or imdb>=7.8 or (tv>=7.6 and votes>=1500) or "Critically Acclaimed" in tags
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
                    cf=cf_affinity(movie,cf_user)
                    ml_context["cf_affinity"]=cf if cf is not None else 0.5
                    if cf is not None:
                        base=CONTENT_WEIGHT*base+(1-CONTENT_WEIGHT)*cf
                        cf_by_title[movie["title"]]=cf
                    learned_probability=predict_success(learning_result,ml_context)
                    if learned_probability is not None:
                        base=0.78*base+0.22*learned_probability
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
        tonight_pool=top_all[:40]
        tonight_watch=get_watch_availability_batch(
            tuple((m["title"],int(m.get("year") or 0)) for _,m in tonight_pool),"US"
        ) if tonight_pool else {}
        my_services=list(st.session_state.get("streaming_services") or [])
        fits=[item for item in tonight_pool if movie_on_services(tonight_watch.get(item[1]["title"]),my_services)]
        fit_titles={m["title"] for _,m in fits}
        tonight_queue=fits+[item for item in tonight_pool if item[1]["title"] not in fit_titles]
        reserved={tonight_queue[0][1]["title"]} if tonight_queue else set()

        # Pass 1: category-specific ordering with strict cross-row de-duplication.
        # Keep the remaining ranked candidates as a replacement queue so one card can
        # advance without rebuilding the entire Showroom.
        for row_name in row_order:
            if row_name=="Top Matches for You":
                ordered=[item for item in top_all if item[1]["title"] not in reserved]
            else:
                ordered=_row_candidates(row_name,reserved)
            picks=ordered[:4]
            row_choices[row_name].extend(picks)
            row_candidate_queues[row_name].extend(ordered)
            reserved.update(movie["title"] for _,movie in picks)

        # Pass 2: if any category pool is thin, fill it with the next-best personalized
        # candidates that have not appeared elsewhere. This keeps every section alive.
        for row_name in row_order:
            need=4-len(row_choices[row_name])
            if need<=0 or row_name in ADAPTIVE_ROWS:
                continue
            fallback=[item for item in ranked if item[1]["title"] not in reserved]
            extra=fallback[:need]
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
                }
        st.session_state.recommendation_context=recommendation_context
        record_impressions(st.session_state,recommendation_context)
        identity_by_title=get_movie_identity_batch(visible_identity_keys)
        showroom_poster_map={title: data.get("poster_url") for title, data in identity_by_title.items()}
        live_rating_keys=tuple((movie["title"], int(movie.get("year") or 0), (identity_by_title.get(movie["title"], {}) or {}).get("imdb_id") or "") for movie in metadata_movies)
        live_ratings_by_title=get_live_ratings_batch(live_rating_keys)

        # Persist the ranked queues and current slots. Card fragments use these to
        # replace exactly one movie without rerunning the four-row Showroom.
        payloads={}
        queues={}
        for row_name in row_order:
            queue_titles=[]
            for match,movie in row_candidate_queues.get(row_name,[])[:40]:
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
                _pl["fit_pool"] = _pool
        st.session_state.showroom_payloads=payloads
        st.session_state.showroom_row_queues=queues
        st.session_state.showroom_slots=slots
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
        render_tonight_pick_fragment()
        for row_index,row_name in enumerate(row_specs):
            choices=row_choices.get(row_name,[])
            row_class = "showroom-row first" if row_index == 0 else "showroom-row"
            row_notes={
                "Top Matches for You":_new_picks_note(row_choices.get("Top Matches for You", [])),
                "Critically Acclaimed":"Highly rated movies that still match your taste",
                "Hidden Gems":"Less-known movies you’re likely to love",
                "Something Different":"Outside your usual genres, but still likely to click",
                **{name: note for name, note in ADAPTIVE_NOTES.items()},
            }
            st.markdown(
                f'<div class="{row_class} showroom-row-header">'
                f'<div class="showroom-row-title">{row_name}</div>'
                f'<div class="row-model-note">{row_notes[row_name]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if not choices:
                st.caption("Refreshing personalized matches…")
                continue
            # Fit floor: past this rank a movie is less likely to be loved than an average one,
            # so the row shows fewer cards instead of padding (Top Matches is always shown).
            _floor = fit_floor()
            _pays = st.session_state.get("showroom_payloads") or {}
            _slots = st.session_state.get("showroom_slots") or {}
            def _strong(i):
                pay = _pays.get(_slots.get(_showroom_slot_key(row_name, i))) or {}
                top = pay.get("fit_top_pct")
                # Rows with their own within-kind test (Top Matches, Critically Acclaimed, Hidden Gems,
                # Something Different) show their best fits. Untested adaptive rows show only strong fits.
                return row_name not in ADAPTIVE_ROWS or _floor is None or not isinstance(top, (int, float)) or top <= _floor
            kept = [i for i in range(len(choices)) if _strong(i)]
            if not kept:
                st.caption("No strong fits here yet. Like or save a few more movies and this row fills in.")
                continue
            with st.container(key=f"showroom_swipe_{row_index}"):
                cols=st.columns(4)
                for c, i in enumerate(kept[:4]):
                    with cols[c]:
                        render_showroom_card_fragment(row_name,row_index,i)
                        render_card_actions(row_name,row_index,i)
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
        edit, reset, _ = st.columns([1.5, 1.2, 4], gap="small")
        with edit:
            # Revisit Steps 1-3 with every choice filled in; the models use the new answers on return.
            st.button("Edit my preferences", key="edit_preferences", use_container_width=True, on_click=go, args=("shelf",))
        with reset:
            if st.button("Reset Profile", key="reset_profile_tab", use_container_width=True):
                reset_profile_state()
                st.rerun(scope="app")
        _lately = lately_genres()
        if _lately:
            st.markdown(f'<div class="privacy-note">Lately you’ve been saving {html.escape(", ".join(_lately))} movies.</div>',
                        unsafe_allow_html=True)
        if st.session_state.get("taste_reset_at"):
            st.button("Undo “My taste changed”", key="taste_undo", on_click=taste_undo)
        else:
            st.button("My taste changed", key="taste_changed", on_click=taste_changed,
                      help="Keeps your likes, favorites and Not for me. Older saves, Seen and skips stop shaping your picks.")
        st.toggle("Share anonymous usage counts", value=not st.session_state.get("analytics_opt_out", False),
                  key="_share_counts", on_change=_set_opt_out,
                  help="Counts like visits and saves, tied to a random ID. Never movie titles, names, emails, or location.")
        st.markdown('<div class="privacy-note">Your profile stays in this browser. iCinema has no accounts '
                    'and never sells your data.</div>', unsafe_allow_html=True)


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

if screen=="welcome":
    logo()
    st.markdown('<div class="hero-title">Always find your next great watch.</div>',unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Like a few movies and answer a few quick questions. iCinema picks what you’ll love, shows where to watch it tonight, and gets better the more you use it.</div>',unsafe_allow_html=True)

    # Proof, read from the results file so it always matches the README.
    _off = load_offline_results() or {}
    _lift = (_off.get("lifts_three_likes_vs_popularity") or {}).get("hit@1")
    _tested = _off.get("held_out_users")
    if isinstance(_lift, (int, float)):
        st.markdown(
            '<div class="home-proof">'
            f'<div class="home-proof-num">+{int(_lift)}%</div>'
            f'<div class="home-proof-text"><strong>Your first pick is one you’ll love {int(_lift)}% more often than just going with what’s popular.</strong>'
            + (f'<span>Tested on {_tested:,} movie fans it had never seen.</span>' if isinstance(_tested, int) else '')
            + '</div></div>', unsafe_allow_html=True)

    steps=[
        ("1","Rate the Shelf","Like a few movies you enjoy."),
        ("2","Tailor Your Preferences","Tell iCinema what matters to you."),
        ("3","Shape Your Showroom","Choose what you want more of."),
    ]
    st.markdown(
        '<div class="home-steps-label">How it works</div><div class="home-steps">'
        + "".join(f'<div class="home-step"><div class="home-step-num">{n}</div><div class="home-step-title">{t}</div>'
                  f'<div class="home-step-body">{b}</div></div>' for n, t, b in steps)
        + '</div>', unsafe_allow_html=True)
    st.button("Start Personalizing →", type="primary", key="start_personalizing", on_click=go, args=("shelf",))

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
    st.markdown(
        '<div class="showroom-header">'
        '<div class="showroom-heading">Your Showroom of Movies</div>'
        '<div class="showroom-intro">Picked for you, and sharper with every choice you make</div>'
        '</div>',
        unsafe_allow_html=True
    )

    render_showroom_fragment(p)

# Persist the latest profile/history after the page has processed this run.
persist_profile_if_needed()
st.session_state._in_full_run = False

# V5.90 is implemented through CSS overrides injected above in the main style block.

# V5.99 tab content alignment polish injected via CSS override.

