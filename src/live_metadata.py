
from __future__ import annotations

import re
from typing import Dict, Any

import requests
import streamlit as st

OMDB_URL = "https://www.omdbapi.com/"
CACHE_SECONDS = 14 * 24 * 60 * 60  # 14 days


def _get_api_key() -> str | None:
    try:
        return st.secrets.get("OMDB_API_KEY")
    except Exception:
        return None


@st.cache_data(ttl=CACHE_SECONDS, max_entries=500, show_spinner=False)
def fetch_omdb(title: str, year: int | str | None = None) -> Dict[str, Any]:
    """
    Fetch current movie metadata from OMDb.
    Cached for 14 days to keep ratings fresh while staying within API limits.
    """
    api_key = _get_api_key()
    if not api_key:
        return {"ok": False, "reason": "missing_api_key"}

    params = {
        "apikey": api_key,
        "t": title,
        "type": "movie",
        "plot": "short",
        "r": "json",
    }
    if year:
        params["y"] = str(year)

    try:
        response = requests.get(OMDB_URL, params=params, timeout=8)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return {"ok": False, "reason": "request_failed"}

    if data.get("Response") != "True":
        return {"ok": False, "reason": data.get("Error", "not_found")}

    ratings = {}
    for item in data.get("Ratings", []):
        source = item.get("Source", "")
        value = item.get("Value", "")
        if source and value:
            ratings[source] = value

    return {
        "ok": True,
        "title": data.get("Title") or title,
        "year": data.get("Year"),
        "genres": [g.strip() for g in (data.get("Genre") or "").split(",") if g.strip()],
        "plot": data.get("Plot") if data.get("Plot") not in (None, "", "N/A") else None,
        "imdb_rating": data.get("imdbRating") if data.get("imdbRating") not in (None, "", "N/A") else None,
        "imdb_id": data.get("imdbID"),
        "rt_score": ratings.get("Rotten Tomatoes"),
        "rated": data.get("Rated") if data.get("Rated") not in (None, "", "N/A") else None,
        "runtime": data.get("Runtime") if data.get("Runtime") not in (None, "", "N/A") else None,
    }


def _first_sentence(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    match = re.match(r"(.+?[.!?])(?:\s|$)", text)
    sentence = match.group(1) if match else text
    return sentence.rstrip(".!?").strip()


def _style_phrase(movie: Dict[str, Any]) -> str:
    tags = set(movie.get("tags", []))
    genre = movie.get("genre", "")

    if "Anime" in tags or genre == "Anime":
        return "expressive animation and purposeful visual design"
    if genre == "Documentary" or "Documentary" in tags:
        return "immersive nonfiction filmmaking"
    if "Atmospheric" in tags:
        return "an atmospheric, carefully composed visual style"
    if "Dark" in tags and "Intense" in tags:
        return "a dark visual tone and sustained tension"
    if "Dark" in tags:
        return "a dark, controlled visual tone"
    if "Intense" in tags:
        return "tight pacing and visually controlled tension"
    if "Emotional" in tags:
        return "restrained, character-focused filmmaking"
    if "Funny" in tags or genre == "Comedy":
        return "energetic, character-driven filmmaking"
    if "International" in tags:
        return "a distinct visual and cultural perspective"
    if "Critically Acclaimed" in tags:
        return "polished, deliberate filmmaking"
    return "clear, character-focused filmmaking"


def editorial_blurb(movie: Dict[str, Any], meta: Dict[str, Any]) -> str:
    """
    One concise sentence: factual plot context from live metadata plus
    a general cinematic/style observation.
    """
    plot = _first_sentence(meta.get("plot")) if meta.get("ok") else None
    style = _style_phrase(movie)

    if not plot:
        # Original editorial fallback, intentionally generic rather than inventing plot facts.
        return movie.get("why") or f"A {movie.get('genre', 'film')} presented with {style}."

    # Keep the final line compact on cards.
    if len(plot) > 150:
        plot = plot[:147].rsplit(" ", 1)[0] + "…"

    return f"{plot}, with {style}."


def display_metadata(movie: Dict[str, Any]) -> Dict[str, Any]:
    meta = fetch_omdb(movie["title"], movie.get("year"))

    if meta.get("ok"):
        genres = meta.get("genres") or [movie.get("genre")]
        return {
            "title": meta.get("title") or movie["title"],
            "year": meta.get("year") or movie.get("year"),
            "genres": genres,
            "imdb": meta.get("imdb_rating"),
            "rt": meta.get("rt_score"),
            "runtime": meta.get("runtime"),
            "blurb": editorial_blurb(movie, meta),
            "live": True,
        }

    # Do not pretend static scores are current if the live provider is unavailable.
    return {
        "title": movie["title"],
        "year": movie.get("year"),
        "genres": [movie.get("genre")] if movie.get("genre") else [],
        "imdb": None,
        "rt": None,
        "runtime": None,
        "blurb": movie.get("why", ""),
        "live": False,
    }
