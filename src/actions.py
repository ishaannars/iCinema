"""What happens when you tap: likes, saves, skips, Seen, services, navigation, and profile state.

Moved out of app.py unchanged (behavior-preserving restructure). Each function reads and writes
st.session_state exactly as it did before."""
import streamlit as st
from src.app_state import queue_profile_save, _too_soon, _remember_movie, _drop_last_event
from src.tested_settings import _tested_shelf
from src.recommender import get_movie, build_profile, availability_utility, semantic_similarity_scores
from src.analytics import start_new_session, record_event, analytics_insights
from src.ml_engine import train_learning_model
from src.watch_providers import get_watch_availability_batch
from src.tmdb_catalog import search_movies, get_movie_identity_batch, tmdb_catalog_configured, discover_movies
from src.live_ratings import get_live_ratings_batch
from src.ui.watch import movie_on_services


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


PROFILE_STORAGE_KEY = "icinema_profile_v1"


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


def _tag_overlap(a, b):
    ta = {str(t).casefold() for t in (a or {}).get("tags") or []}
    tb = {str(t).casefold() for t in (b or {}).get("tags") or []}
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


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


def taste_undo():
    st.session_state.taste_reset_at = None
    queue_profile_save()


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


def _set_profile_section(name):
    st.session_state.pf_section_v = name


def _remove_like_from_profile(title):
    """× on a like in Profile: remove it and rebuild the whole Showroom so every row stops using it."""
    remove_step1_selection(title)
    st.session_state._app_rerun = True


_MORE_DESCRIPTIONS = {
    "Hidden Gems": "Less known, still your taste",
    "Critically Acclaimed": "RT 75%+ and IMDb 7.5+",
    "Recent Releases": "Released 2023 or later",
    "International Films": "From around the world",
    "Classics": "Favorites from earlier eras",
    "Documentaries": "True stories, your interests",
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


def fourth_row_name():
    for pick in st.session_state.get("more_of") or []:
        if pick in _ADAPTIVE_FROM_STEP3:
            return _ADAPTIVE_FROM_STEP3[pick]
    return "Something Different"


def _mood_text():
    """The mood search the viewer applied. It stays until they clear it, across pages and visits."""
    return " ".join(str(st.session_state.get("mood_active") or "").split())


def _set_mood(text):
    """Chip ×, Clear, or an edit: rewrite the active mood and the field together."""
    text = " ".join(str(text or "").split())[:120]
    st.session_state.mood_active = text
    st.session_state.mood_input = text
    queue_profile_save()


# Words fans use for the things a viewer can ask to avoid (MovieLens tags), used by the avoid filter
# for movies and, with the show's own keywords and rating, for shows.
AVOID_TERMS = {
    "violent": ["violent", "violence", "brutal", "brutality", "gore", "gory", "bloody", "graphic violence",
                "zombies", "zombie", "slasher", "war", "torture", "serial killer"],
    "scary": ["scary", "horror", "creepy", "disturbing", "terrifying", "gore"],
    "sad": ["sad", "depressing", "tearjerker", "bleak"],
    "gory": ["gore", "gory", "bloody", "violence"],
}


def _love_pct(payload):
    """The rank the love-chance table reads: on its test's footing when known, else the overall rank."""
    payload = payload or {}
    v = payload.get("love_top_pct")
    return v if isinstance(v, (int, float)) else payload.get("fit_top_pct")


def _fork_seen(title):
    """'I've Seen It' on the searched movie: ask how it was, right where the buttons were."""
    fork = dict(st.session_state.get("search_fork") or {})
    fork[title] = "rate"
    st.session_state.search_fork = fork


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


_BUILD_KEYS = ("showroom_slots", "showroom_payloads", "showroom_row_queues", "recommendation_context",
               "tonight_pool", "tonight_deep_pool", "interleave_teams")


def _build_key():
    """Everything a Showroom build depends on. Any choice changes it, so a reused build is never stale."""
    ss = st.session_state
    return (_mood_text(), tuple(sorted(ss.likes)), tuple(sorted(ss.favorites)), tuple(ss.genres),
            ss.review_priority, ss.adventure, tuple(ss.more_of), len(ss.saved), len(ss.seen), len(ss.dismissed),
            len(ss.get("disliked") or ()), tuple(sorted(ss.get("streaming_services") or ())),
            bool(ss.get("only_mine")),                                  # "Only show movies on my services" rebuilds the rows
            tuple(sorted((ss.get("seen_rating") or {}).items())),      # a thumbs on Seen re-ranks the Showroom
            len([e for e in (ss.get("analytics_events") or []) if e.get("event") != "impression"]))


def _edit_token(rest, text):
    """Tap a token's words: they open in the field to edit, and Search puts the edit back in place of it.
    Only the search box reruns; the Showroom stays as it is until Search."""
    ver = int(st.session_state.get("_mood_ver") or 0) + 1
    st.session_state._mood_ver = ver
    st.session_state._edit_rest = rest
    st.session_state._mood_prefill = (ver, " ".join(str(text or "").split())[:120])


def _set_mood_live(text):
    """A chip, Clear, or a starting point tapped inside the search box: change the search, rebuild the Showroom."""
    st.session_state.pop("_edit_rest", None)      # any token edit in progress is replaced by this change
    _set_mood(text)
    st.session_state._mood_ver = int(st.session_state.get("_mood_ver") or 0) + 1
    st.session_state._app_rerun = True


def _showroom_slot_key(row_name, slot_index):
    return f"{row_name}::{int(slot_index)}"


def _mark_showroom_fast():
    st.session_state._showroom_fast = True


def _answer_seen(slot_key, title, value):
    """Thumbs on the "liked it?" prompt after Seen: same effect as the thumbs on the Seen tab."""
    ask = dict(st.session_state.get("showroom_rate_ask") or {})
    ask.pop(slot_key, None)
    st.session_state.showroom_rate_ask = ask
    if value:
        rate_seen(title, value)


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


_SERVICE_SHORT = {"Free (Tubi, Pluto & more)": "Free with ads", "Max": "HBO Max", "Apple TV+": "Apple TV"}   # 2026 names


def _services_done():
    """Done: the whole Showroom redraws once, so every card's streaming line puts your services first.
    Tapping tiles reruns only Tonight's Show, which re-picks instantly; the rows reuse the current build."""
    st.session_state._app_rerun = True


def _library_counts(which):
    """The count beside one library tab, written by that tab's own fragment so neither can go stale over the other."""
    n = len(st.session_state.saved) if which == "saved" else len(st.session_state.seen)
    k = 1 if which == "saved" else 2
    st.markdown(
        f'<style>[data-testid="stTabs"] [role="tab"][id$="-tab-{k}"] p::after,'
        f'[data-testid="stTabs"] [role="tablist"] > [role="tab"]:nth-of-type({k + 1}) p::after{{content:" ({n})" !important}}</style>',
        unsafe_allow_html=True,
    )


def _newest_first(titles, kinds):
    """Saved and Seen in the order you did it, newest first (imported titles without a date go last)."""
    when = {}
    for e in st.session_state.get("analytics_events") or []:
        if e.get("event") in kinds and e.get("title") in titles:
            when[e["title"]] = max(when.get(e["title"], 0.0), float(e.get("timestamp") or 0))
    return sorted(titles, key=lambda t: (-when.get(t, 0.0), str(t).casefold()))
