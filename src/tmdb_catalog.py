"""TMDB catalog access and multi-source candidate retrieval for iCinema.

The public function signatures are intentionally preserved so the finished UI does
not need to change. The main upgrade is retrieval: candidate generation is no
longer driven by one popularity-sorted stream. Instead, iCinema retrieves from
several complementary candidate sources before the existing recommender ranks and
reranks them.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import math
import time
from threading import Lock
from typing import Dict, Optional, Tuple

import requests
import streamlit as st

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
CACHE_SECONDS = 60 * 60 * 24 * 14
SEARCH_CACHE_SECONDS = 60 * 60 * 24
DISCOVERY_CACHE_SECONDS = 60 * 60 * 24

_DISCOVERY_PAGE_CACHE = {}
_DISCOVERY_PAGE_CACHE_LOCK = Lock()

GENRE_MAP = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Thriller",
    99: "Documentary",
    18: "Drama",
    10751: "Drama",
    14: "Fantasy",
    36: "Drama",
    27: "Horror",
    10402: "Drama",
    9648: "Mystery",
    10749: "Romance",
    878: "Sci-Fi",
    10770: "Drama",
    53: "Thriller",
    37: "Adventure",
    10752: "Drama",
}

OVERVIEW_TRAIT_KEYWORDS = {
    "Suspenseful": ("murder", "missing", "investigation", "danger", "threat", "crime", "hunt"),
    "Thought-provoking": ("identity", "society", "humanity", "meaning", "memory", "future", "ethics"),
    "Character-driven": ("family", "relationship", "friendship", "life", "journey", "struggles", "coming of age"),
    "Fast-paced": ("race", "escape", "mission", "chase", "rescue", "battle"),
    "Emotional": ("love", "loss", "grief", "family", "heart", "reunite"),
    "Dark": ("murder", "death", "revenge", "violent", "crime", "nightmare"),
    "Funny": ("comedy", "hilarious", "funny", "misadventure"),
    "Cerebral": ("mystery", "scientist", "experiment", "reality", "mind", "conspiracy"),
    "Unpredictable": ("secret", "twist", "mystery", "unexpected", "deception"),
    "Heartfelt": ("friendship", "family", "love", "bond", "home"),
    "Action-heavy": ("war", "battle", "assassin", "mission", "fight", "soldier"),
    "Slow-burn": ("quiet", "gradually", "years later", "isolated"),
    "Romantic": ("romance", "love", "couple", "relationship"),
    "Intense": ("survival", "danger", "desperate", "battle", "hostage"),
    "Lighthearted": ("fun", "adventure", "friendship", "holiday"),
    "Epic": ("kingdom", "empire", "world", "war", "destiny"),
    "Grounded": ("everyday", "ordinary", "family", "work", "community"),
    "Psychological": ("mind", "obsession", "trauma", "paranoia", "psychological"),
    "Adventurous": ("adventure", "journey", "quest", "expedition", "explore"),
    "Nostalgic": ("childhood", "memories", "reunion", "years later"),
    "Satirical": ("satire", "satirical", "society", "wealth", "media"),
    "Tense": ("hostage", "danger", "trapped", "threat", "race against"),
    "Moving": ("grief", "loss", "family", "love", "reunite"),
}


def _credentials():
    bearer = st.secrets.get("TMDB_BEARER_TOKEN", "") if hasattr(st, "secrets") else ""
    api_key = st.secrets.get("TMDB_API_KEY", "") if hasattr(st, "secrets") else ""
    return str(bearer).strip(), str(api_key).strip()


def tmdb_catalog_configured() -> bool:
    bearer, api_key = _credentials()
    return bool(bearer or api_key)


def _request(path: str, params: Optional[dict] = None) -> Optional[dict]:
    bearer, api_key = _credentials()
    if not bearer and not api_key:
        return None

    headers = {"accept": "application/json"}
    params = dict(params or {})
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    else:
        params["api_key"] = api_key

    try:
        response = requests.get(
            f"{TMDB_BASE}{path}",
            headers=headers,
            params=params,
            timeout=4.5,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def _poster_url(path):
    return f"{TMDB_IMAGE_BASE}{path}" if path else None


def _year(item):
    release = str(item.get("release_date", ""))
    return int(release[:4]) if len(release) >= 4 and release[:4].isdigit() else None


def _canonical_genre(item):
    genre_ids = item.get("genre_ids") or []
    mapped = [GENRE_MAP[g] for g in genre_ids if g in GENRE_MAP]
    if 16 in genre_ids and str(item.get("original_language", "")).lower() == "ja":
        return "Anime"
    return mapped[0] if mapped else "Drama"


def _overview_traits(text):
    text = " ".join(str(text or "").lower().split())
    if not text:
        return []

    out = []
    for trait, keywords in OVERVIEW_TRAIT_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            out.append(trait)
    return out[:5]


def _movie_tags(item):
    genre_ids = item.get("genre_ids") or []
    tags = []

    if 16 in genre_ids and str(item.get("original_language", "")).lower() == "ja":
        tags.extend(["Anime", "Animation"])

    for gid in genre_ids:
        genre = GENRE_MAP.get(gid)
        if genre and genre not in tags:
            tags.append(genre)

    if str(item.get("original_language", "")).lower() not in {"", "en"}:
        tags.append("International")

    year = _year(item)
    current_year = datetime.now().year
    if year and year >= current_year - 3:
        tags.append("Recent Release")
    if year and year <= 2000:
        tags.append("Classic")

    for trait in _overview_traits(item.get("overview")):
        if trait not in tags:
            tags.append(trait)

    return tags


def _to_icinema_movie(item, candidate_source=None):
    title = str(item.get("title") or item.get("original_title") or "Untitled").strip()
    year = _year(item) or 0
    overview = " ".join(str(item.get("overview") or "").split()).strip()

    movie = {
        "title": title,
        "year": year,
        "genre": _canonical_genre(item),
        "imdb": None,
        "rt": None,
        "tags": _movie_tags(item),
        "why": overview or "A movie selected from the full TMDB catalog.",
        "poster_url": _poster_url(item.get("poster_path")),
        "tmdb_id": item.get("id"),
        "original_language": item.get("original_language"),
        "tmdb_vote": item.get("vote_average"),
        "tmdb_vote_count": item.get("vote_count"),
        "popularity": item.get("popularity"),
        "external": True,
    }
    if candidate_source:
        movie["candidate_source"] = str(candidate_source)
    return movie


@st.cache_data(ttl=SEARCH_CACHE_SECONDS, show_spinner=False)
def search_movies(query: str, limit: int = 8):
    query = " ".join(str(query).split()).strip()
    if len(query) < 2 or not tmdb_catalog_configured():
        return []

    payload = _request(
        "/search/movie",
        {
            "query": query,
            "include_adult": "false",
            "language": "en-US",
            "page": 1,
        },
    )
    if not payload:
        return []

    results = []
    for item in payload.get("results", []):
        if not item.get("title"):
            continue
        results.append(_to_icinema_movie(item, "search"))
        if len(results) >= limit:
            break
    return results


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def find_movie(title: str, year: int = 0):
    if not tmdb_catalog_configured():
        return None

    params = {
        "query": title,
        "include_adult": "false",
        "language": "en-US",
    }
    if year:
        params["year"] = int(year)

    payload = _request("/search/movie", params)
    results = (payload or {}).get("results", [])

    if not results and year:
        payload = _request(
            "/search/movie",
            {
                "query": title,
                "include_adult": "false",
                "language": "en-US",
            },
        )
        results = (payload or {}).get("results", [])

    if not results:
        return None

    title_folded = str(title).casefold()
    for item in results:
        if (
            str(item.get("title", "")).casefold() == title_folded
            and (_year(item) or 0) == int(year or 0)
        ):
            return _to_icinema_movie(item, "search")

    for item in results:
        if str(item.get("title", "")).casefold() == title_folded:
            return _to_icinema_movie(item, "search")

    return _to_icinema_movie(results[0], "search")


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_poster_batch(movies: Tuple[Tuple[str, int], ...]) -> Dict[str, Optional[str]]:
    if not movies or not tmdb_catalog_configured():
        return {}

    result: Dict[str, Optional[str]] = {}
    workers = min(8, max(1, len(movies)))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(find_movie, title, year): title
            for title, year in movies
        }
        for future in as_completed(futures):
            title = futures[future]
            try:
                movie = future.result()
                result[title] = movie.get("poster_url") if movie else None
            except Exception:
                result[title] = None
    return result


def _discovery_strategies():
    """Complementary retrieval channels.

    The existing ranker still decides what is shown. These strategies only make
    sure the ranker receives a less popularity-biased candidate set.
    """
    current_year = datetime.now().year
    return [
        (
            "popular",
            {
                "sort_by": "popularity.desc",
                "vote_count.gte": 80,
            },
        ),
        (
            "quality",
            {
                "sort_by": "vote_average.desc",
                "vote_count.gte": 500,
            },
        ),
        (
            "hidden_gem",
            {
                "sort_by": "vote_average.desc",
                "vote_count.gte": 100,
                "vote_count.lte": 5000,
                "vote_average.gte": 6.7,
            },
        ),
        (
            "recent",
            {
                "sort_by": "popularity.desc",
                "vote_count.gte": 40,
                "primary_release_date.gte": f"{current_year - 2}-01-01",
            },
        ),
        (
            "international_ko",
            {
                "sort_by": "popularity.desc",
                "vote_count.gte": 60,
                "with_original_language": "ko",
            },
        ),
        (
            "international_ja",
            {
                "sort_by": "popularity.desc",
                "vote_count.gte": 60,
                "with_original_language": "ja",
            },
        ),
        (
            "international_fr_es",
            {
                "sort_by": "vote_average.desc",
                "vote_count.gte": 80,
                "with_original_language": "fr|es",
            },
        ),
        (
            "classic",
            {
                "sort_by": "vote_average.desc",
                "vote_count.gte": 300,
                "primary_release_date.lte": "2005-12-31",
            },
        ),
    ]


def _fetch_discovery_page(source_name, source_params, page_number):
    cache_key = (
        source_name,
        int(page_number),
        tuple(sorted((str(k), str(v)) for k, v in source_params.items())),
    )
    now = time.time()

    with _DISCOVERY_PAGE_CACHE_LOCK:
        cached = _DISCOVERY_PAGE_CACHE.get(cache_key)
        if cached and now - cached[0] < DISCOVERY_CACHE_SECONDS:
            return source_name, page_number, cached[1]

    params = {
        "include_adult": "false",
        "include_video": "false",
        "language": "en-US",
        "page": int(page_number),
        **source_params,
    }
    payload = _request("/discover/movie", params)
    items = (payload or {}).get("results", [])

    if items:
        with _DISCOVERY_PAGE_CACHE_LOCK:
            _DISCOVERY_PAGE_CACHE[cache_key] = (now, items)

    return source_name, page_number, items


# The app's genre labels -> TMDB discover filters. "Anime" is Japanese-language animation.
TMDB_GENRE_FILTERS = {
    "Action": {"with_genres": "28"}, "Adventure": {"with_genres": "12"},
    "Anime": {"with_genres": "16", "with_original_language": "ja"}, "Animation": {"with_genres": "16"},
    "Comedy": {"with_genres": "35"}, "Documentary": {"with_genres": "99"}, "Drama": {"with_genres": "18"},
    "Fantasy": {"with_genres": "14"}, "Horror": {"with_genres": "27"}, "Mystery": {"with_genres": "9648"},
    "Romance": {"with_genres": "10749"}, "Sci-Fi": {"with_genres": "878"}, "Thriller": {"with_genres": "53"},
}


def _taste_strategies(focus_genres):
    """Two extra channels per top genre: its most popular and its best-rated titles."""
    channels = []
    for genre in list(focus_genres or [])[:2]:
        filters = TMDB_GENRE_FILTERS.get(str(genre))
        if not filters:
            continue
        slug = str(genre).lower().replace(" ", "_").replace("-", "_")
        channels.append((f"genre_{slug}_popular", {**filters, "sort_by": "popularity.desc", "vote_count.gte": 40}))
        channels.append((f"genre_{slug}_best", {**filters, "sort_by": "vote_average.desc", "vote_count.gte": 150}))
    return channels


def discover_movies(limit: int = 120, start_page: int = 1, *_, focus_genres=None, **__):
    """Return a diversified TMDB retrieval pool.

    Compatibility is preserved with the existing app:
        discover_movies(limit)
        discover_movies(limit, start_page)

    start_page still rotates into deeper inventory as a user accumulates Skips,
    but each retrieval channel now advances independently.
    """
    if not tmdb_catalog_configured() or limit <= 0:
        return []

    # General channels plus channels for the viewer's own top genres.
    strategies = _discovery_strategies() + _taste_strategies(focus_genres)
    per_page = 20
    pages_per_strategy = max(
        1,
        int(math.ceil(float(limit) / (per_page * len(strategies)))) + 1,
    )

    # The app advances start_page in larger jumps. Compress that into a safe
    # per-strategy page offset so all retrieval channels keep rotating without
    # racing toward TMDB's 500-page ceiling.
    rotation = max(0, int(start_page or 1) - 1)
    base_page = 1 + (rotation % 80)

    tasks = []
    for source_name, source_params in strategies:
        for offset in range(pages_per_strategy):
            page = min(500, base_page + offset)
            tasks.append((source_name, source_params, page))

    fetched = {}
    workers = min(8, max(1, len(tasks)))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _fetch_discovery_page,
                source_name,
                source_params,
                page,
            )
            for source_name, source_params, page in tasks
        ]
        for future in as_completed(futures):
            try:
                source_name, page, items = future.result()
                fetched[(source_name, page)] = items
            except Exception:
                continue

    # Round-robin the sources instead of letting one source fill the entire pool.
    queues = {}
    for source_name, _ in strategies:
        combined = []
        for offset in range(pages_per_strategy):
            page = min(500, base_page + offset)
            combined.extend(fetched.get((source_name, page), []))
        queues[source_name] = combined

    results = []
    seen = set()
    source_order = [name for name, _ in strategies]
    cursor = {name: 0 for name in source_order}

    while len(results) < int(limit):
        added_this_round = False

        for source_name in source_order:
            items = queues.get(source_name, [])
            while cursor[source_name] < len(items):
                item = items[cursor[source_name]]
                cursor[source_name] += 1

                movie = _to_icinema_movie(item, source_name)
                key = (
                    movie["title"].casefold(),
                    int(movie.get("year") or 0),
                )
                if key in seen:
                    continue

                seen.add(key)
                results.append(movie)
                added_this_round = True
                break

            if len(results) >= int(limit):
                break

        if not added_this_round:
            break

    return results


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_movie_identity(title: str, year: int = 0, tmdb_id: int = 0):
    """Resolve canonical TMDB display metadata + stable IMDb ID."""
    if not tmdb_catalog_configured():
        return None

    resolved_id = int(tmdb_id or 0)
    if not resolved_id:
        resolved = find_movie(title, int(year or 0))
        if not resolved:
            return None

        resolved_id = int(resolved.get("tmdb_id") or 0)
        if not resolved_id:
            return {
                "display_title": resolved.get("title") or title,
                "year": int(resolved.get("year") or year or 0),
                "poster_url": resolved.get("poster_url"),
                "tmdb_id": None,
                "imdb_id": None,
            }

    payload = _request(f"/movie/{resolved_id}", {"language": "en-US"})
    if not payload:
        return None

    canonical_title = str(
        payload.get("title") or payload.get("original_title") or title
    ).strip()
    release = str(payload.get("release_date") or "")
    canonical_year = (
        int(release[:4])
        if len(release) >= 4 and release[:4].isdigit()
        else int(year or 0)
    )

    return {
        "display_title": canonical_title,
        "year": canonical_year,
        "poster_url": _poster_url(payload.get("poster_path")),
        "tmdb_id": resolved_id,
        "imdb_id": payload.get("imdb_id") or None,
    }


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_movie_identity_batch(
    movies: Tuple[Tuple[str, int, int], ...]
) -> Dict[str, dict]:
    """Resolve visible movies concurrently without changing internal keys."""
    if not movies or not tmdb_catalog_configured():
        return {}

    result: Dict[str, dict] = {}
    workers = min(8, max(1, len(movies)))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                get_movie_identity,
                title,
                int(year or 0),
                int(tmdb_id or 0),
            ): title
            for title, year, tmdb_id in movies
        }
        for future in as_completed(futures):
            internal_title = futures[future]
            try:
                identity = future.result()
            except Exception:
                identity = None
            if identity:
                result[internal_title] = identity

    return result


# --- Landscape artwork for the Step 1 shelf -------------------------------------------
TMDB_BACKDROP_BASE = "https://image.tmdb.org/t/p/w780"


def _best_landscape(images):
    """Prefer titled English landscape key art, then the best textless still."""
    backdrops = list((images or {}).get("backdrops") or [])
    if not backdrops:
        return None

    def rank(img):
        return (float(img.get("vote_average") or 0), int(img.get("vote_count") or 0))

    titled = [b for b in backdrops if b.get("iso_639_1") == "en"]
    textless = [b for b in backdrops if not b.get("iso_639_1")]
    pool = titled or textless or backdrops
    best = max(pool, key=rank)
    path = best.get("file_path")
    return f"{TMDB_BACKDROP_BASE}{path}" if path else None


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_landscape_art(title: str, year: int = 0, tmdb_id: int = 0) -> Optional[str]:
    """Landscape (16:9) artwork for one movie, or None so the UI can fall back to the poster."""
    if not tmdb_catalog_configured():
        return None
    movie_id = int(tmdb_id or 0)
    if not movie_id:
        found = find_movie(title, int(year or 0))
        movie_id = int((found or {}).get("tmdb_id") or 0)
    if not movie_id:
        return None
    images = _request(f"/movie/{movie_id}/images", {"include_image_language": "en,null"})
    return _best_landscape(images)


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_landscape_batch(movies: Tuple[Tuple[str, int, int], ...]) -> Dict[str, Optional[str]]:
    """{title: landscape_url_or_None} for (title, year, tmdb_id) tuples, fetched concurrently."""
    if not movies or not tmdb_catalog_configured():
        return {}
    result: Dict[str, Optional[str]] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(movies))) as pool:
        futures = {
            pool.submit(get_landscape_art, title, int(year or 0), int(tmdb_id or 0)): title
            for title, year, tmdb_id in movies
        }
        for future in as_completed(futures):
            try:
                result[futures[future]] = future.result()
            except Exception:
                result[futures[future]] = None
    return result
