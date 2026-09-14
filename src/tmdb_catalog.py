from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Optional, Tuple

import requests
import streamlit as st

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
CACHE_SECONDS = 60 * 60 * 24 * 14
SEARCH_CACHE_SECONDS = 60 * 60 * 24
DISCOVERY_CACHE_SECONDS = 60 * 60 * 24

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
        response = requests.get(f"{TMDB_BASE}{path}", headers=headers, params=params, timeout=4.5)
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

def _overview_traits(text):
    text = " ".join(str(text or "").lower().split())
    if not text:
        return []
    out=[]
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


def _to_icinema_movie(item):
    title = str(item.get("title") or item.get("original_title") or "Untitled").strip()
    year = _year(item) or 0
    overview = " ".join(str(item.get("overview") or "").split()).strip()
    return {
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


@st.cache_data(ttl=SEARCH_CACHE_SECONDS, show_spinner=False)
def search_movies(query: str, limit: int = 8):
    query = " ".join(str(query).split()).strip()
    if len(query) < 2 or not tmdb_catalog_configured():
        return []
    payload = _request(
        "/search/movie",
        {"query": query, "include_adult": "false", "language": "en-US", "page": 1},
    )
    if not payload:
        return []
    results = []
    for item in payload.get("results", []):
        if not item.get("title"):
            continue
        results.append(_to_icinema_movie(item))
        if len(results) >= limit:
            break
    return results


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def find_movie(title: str, year: int = 0):
    if not tmdb_catalog_configured():
        return None
    params = {"query": title, "include_adult": "false", "language": "en-US"}
    if year:
        params["year"] = int(year)
    payload = _request("/search/movie", params)
    results = (payload or {}).get("results", [])
    if not results and year:
        payload = _request("/search/movie", {"query": title, "include_adult": "false", "language": "en-US"})
        results = (payload or {}).get("results", [])
    if not results:
        return None
    title_folded = str(title).casefold()
    for item in results:
        if str(item.get("title", "")).casefold() == title_folded and (_year(item) or 0) == int(year or 0):
            return _to_icinema_movie(item)
    for item in results:
        if str(item.get("title", "")).casefold() == title_folded:
            return _to_icinema_movie(item)
    return _to_icinema_movie(results[0])


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_poster_batch(movies: Tuple[Tuple[str, int], ...]) -> Dict[str, Optional[str]]:
    if not movies or not tmdb_catalog_configured():
        return {}
    result: Dict[str, Optional[str]] = {}
    workers = min(8, max(1, len(movies)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(find_movie, title, year): title for title, year in movies}
        for future in as_completed(futures):
            title = futures[future]
            try:
                movie = future.result()
                result[title] = movie.get("poster_url") if movie else None
            except Exception:
                result[title] = None
    return result


@st.cache_data(ttl=DISCOVERY_CACHE_SECONDS, show_spinner=False)
def discover_movies(limit: int = 120):
    """Return a broad TMDB candidate pool for resilient recommendation replenishment."""
    if not tmdb_catalog_configured() or limit <= 0:
        return []

    results = []
    seen = set()
    page = 1
    max_pages = min(8, max(1, (int(limit) + 19) // 20 + 1))
    while page <= max_pages and len(results) < limit:
        payload = _request(
            "/discover/movie",
            {
                "include_adult": "false",
                "include_video": "false",
                "language": "en-US",
                "page": page,
                "sort_by": "popularity.desc",
                "vote_count.gte": 80,
            },
        )
        if not payload:
            break
        items = payload.get("results", [])
        if not items:
            break
        for item in items:
            movie = _to_icinema_movie(item)
            key = (movie["title"].casefold(), int(movie.get("year") or 0))
            if key in seen:
                continue
            seen.add(key)
            results.append(movie)
            if len(results) >= limit:
                break
        page += 1
    return results
