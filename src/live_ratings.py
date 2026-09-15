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
def get_live_ratings(title: str, year: int = 0, imdb_id: str = "") -> Optional[dict]:
    """Fetch IMDb + Rotten Tomatoes from OMDb.

    Stable IMDb-ID lookup is preferred. Title/year is only a fallback, which
    avoids failures caused by regional title spellings or alternate titles.
    """
    key = _api_key()
    if not key:
        return None

    imdb_id = str(imdb_id or "").strip()
    if imdb_id:
        params = {
            "apikey": key,
            "i": imdb_id,
            "type": "movie",
            "r": "json",
            "plot": "short",
        }
    else:
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

    # If an ID lookup somehow fails, retry by title/year. If title/year is too
    # strict, retry once more by title only.
    if str(payload.get("Response", "False")).lower() != "true" and imdb_id:
        fallback = {"apikey": key, "t": str(title).strip(), "type": "movie", "r": "json", "plot": "short"}
        if year:
            fallback["y"] = int(year)
        try:
            response = requests.get(OMDB_BASE, params=fallback, timeout=4.5)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return None

    if str(payload.get("Response", "False")).lower() != "true" and year:
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
        "omdb_title": payload.get("Title"),
        "source": "OMDb",
    }


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def get_live_ratings_batch(movies: Tuple[Tuple, ...]) -> Dict[str, dict]:
    """Fetch ratings concurrently for visible movie cards.

    Supports tuples of (title, year) and (title, year, imdb_id), preserving
    backward compatibility with older calls.
    """
    if not movies or not omdb_configured():
        return {}

    normalized = []
    for item in movies:
        title = item[0]
        year = int(item[1] or 0) if len(item) > 1 else 0
        imdb_id = str(item[2] or "") if len(item) > 2 else ""
        normalized.append((title, year, imdb_id))

    result: Dict[str, dict] = {}
    workers = min(8, max(1, len(normalized)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(get_live_ratings, title, year, imdb_id): title
            for title, year, imdb_id in normalized
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
