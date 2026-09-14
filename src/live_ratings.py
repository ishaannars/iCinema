from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Tuple

import requests
import streamlit as st

OMDB_BASE = "https://www.omdbapi.com/"
CACHE_SECONDS = 60 * 60 * 24 * 14


def _api_key() -> str:
    try:
        return str(st.secrets.get("OMDB_API_KEY", "")).strip()
    except Exception:
        return ""


def omdb_configured() -> bool:
    return bool(_api_key())


def _parse_float(value) -> Optional[float]:
    try:
        text = str(value).strip()
        if not text or text.upper() == "N/A":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _parse_percent(value) -> Optional[int]:
    try:
        text = str(value).strip().replace("%", "")
        if not text or text.upper() == "N/A":
            return None
        return int(round(float(text)))
    except (TypeError, ValueError):
        return None


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_live_ratings(title: str, year: int = 0) -> Optional[dict]:
    """Fetch IMDb + Rotten Tomatoes ratings from OMDb for one movie.

    Returns None when OMDb is not configured, the title cannot be resolved,
    or the request fails. Results are cached for 14 days.
    """
    key = _api_key()
    if not key:
        return None

    params = {
        "apikey": key,
        "t": str(title).strip(),
        "type": "movie",
        "r": "json",
        "plot": "short",
    }
    if year:
        params["y"] = int(year)

    try:
        response = requests.get(OMDB_BASE, params=params, timeout=4.5)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    if str(payload.get("Response", "False")).lower() != "true":
        # Year matching can occasionally be too strict. Retry once by title only.
        if year:
            try:
                response = requests.get(
                    OMDB_BASE,
                    params={"apikey": key, "t": str(title).strip(), "type": "movie", "r": "json", "plot": "short"},
                    timeout=4.5,
                )
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError):
                return None
        if str(payload.get("Response", "False")).lower() != "true":
            return None

    imdb = _parse_float(payload.get("imdbRating"))
    rt = None
    for rating in payload.get("Ratings", []) or []:
        if str(rating.get("Source", "")).strip().lower() == "rotten tomatoes":
            rt = _parse_percent(rating.get("Value"))
            break

    return {
        "imdb": imdb,
        "rt": rt,
        "imdb_id": payload.get("imdbID"),
        "source": "OMDb",
    }


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_live_ratings_batch(movies: Tuple[Tuple[str, int], ...]) -> Dict[str, dict]:
    """Fetch ratings concurrently for a small set of visible movie cards."""
    if not movies or not omdb_configured():
        return {}

    result: Dict[str, dict] = {}
    workers = min(8, max(1, len(movies)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(get_live_ratings, title, int(year or 0)): title
            for title, year in movies
        }
        for future in as_completed(futures):
            title = futures[future]
            try:
                data = future.result()
            except Exception:
                data = None
            if data:
                result[title] = data
    return result
