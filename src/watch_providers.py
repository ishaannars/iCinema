from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, Optional, Tuple

import requests
import streamlit as st

TMDB_BASE = "https://api.themoviedb.org/3"
CACHE_SECONDS = 60 * 60 * 24 * 14  # 14 days


def _credentials():
    """Return TMDB authentication without exposing secrets to the UI."""
    bearer = st.secrets.get("TMDB_BEARER_TOKEN", "") if hasattr(st, "secrets") else ""
    api_key = st.secrets.get("TMDB_API_KEY", "") if hasattr(st, "secrets") else ""
    bearer = str(bearer).strip() if bearer else ""
    api_key = str(api_key).strip() if api_key else ""
    return bearer, api_key


def tmdb_configured() -> bool:
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


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def _find_tmdb_movie_id(title: str, year: int) -> Optional[int]:
    payload = _request(
        "/search/movie",
        {"query": title, "year": year, "include_adult": "false", "language": "en-US"},
    )
    if not payload:
        return None

    results = payload.get("results", [])
    if not results:
        # Some international films have a release-year mismatch in regional data.
        payload = _request(
            "/search/movie",
            {"query": title, "include_adult": "false", "language": "en-US"},
        )
        results = (payload or {}).get("results", [])

    if not results:
        return None

    # Prefer exact title/year matches, then exact title, then TMDB's first result.
    title_folded = title.casefold()
    for item in results:
        release_year = str(item.get("release_date", ""))[:4]
        if str(item.get("title", "")).casefold() == title_folded and release_year == str(year):
            return item.get("id")
    for item in results:
        if str(item.get("title", "")).casefold() == title_folded:
            return item.get("id")
    return results[0].get("id")


def _provider_names(items, limit=3):
    names = []
    for item in items or []:
        name = str(item.get("provider_name", "")).strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_watch_availability(title: str, year: int, region: str = "US") -> dict:
    """Return a compact, display-ready watch availability summary for one movie."""
    if not tmdb_configured():
        return {"status": "not_configured", "text": "Where to watch: availability not configured", "url": None}

    movie_id = _find_tmdb_movie_id(title, year)
    if not movie_id:
        return {"status": "unknown", "text": "Where to watch: availability unavailable", "url": None}

    payload = _request(f"/movie/{movie_id}/watch/providers")
    if payload is None:
        return {"status": "unknown", "text": "Where to watch: availability unavailable", "url": None}

    region_data = payload.get("results", {}).get(region, {})
    tmdb_url = region_data.get("link")

    streaming = _provider_names(
        (region_data.get("flatrate") or []) + (region_data.get("free") or []) + (region_data.get("ads") or [])
    )
    if streaming:
        return {
            "status": "streaming",
            "text": "Streaming: " + " · ".join(streaming),
            "url": tmdb_url,
        }

    rent = _provider_names(region_data.get("rent"))
    if rent:
        return {
            "status": "rent",
            "text": "Rent: " + " · ".join(rent),
            "url": tmdb_url,
        }

    buy = _provider_names(region_data.get("buy"))
    if buy:
        return {
            "status": "buy",
            "text": "Buy: " + " · ".join(buy),
            "url": tmdb_url,
        }

    return {
        "status": "unavailable",
        "text": "Not currently available on major streaming services",
        "url": tmdb_url,
    }


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_watch_availability_batch(movies: Tuple[Tuple[str, int], ...], region: str = "US") -> Dict[str, dict]:
    """Fetch currently visible cards concurrently so the first render stays responsive."""
    if not movies:
        return {}
    if not tmdb_configured():
        return {
            title: {"status": "not_configured", "text": "Where to watch: availability not configured", "url": None}
            for title, _ in movies
        }

    results: Dict[str, dict] = {}
    workers = min(8, max(1, len(movies)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(get_watch_availability, title, year, region): title
            for title, year in movies
        }
        for future in as_completed(futures):
            title = futures[future]
            try:
                results[title] = future.result()
            except Exception:
                results[title] = {"status": "unknown", "text": "Where to watch: availability unavailable", "url": None}
    return results
