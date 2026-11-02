"""TV shows: who'd love which show, from real fan ratings, plus the show's details from TMDB.

data/tv_knn.npz is built by training/confirm_tv_blend.py only if it beat "most popular shows" on
held-out people (Amazon Reviews 2023, Movies & TV). For each MovieLens movie it holds the shows its
fans loved most. A viewer's loved movies add up to a score per show; the score is blended with
show popularity at the weight the test picked (fans like you 80%, popularity 20%).
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
import streamlit as st

from src import cf_model

DATA = Path(__file__).resolve().parent.parent / "data"
FAN_ACTIONS = {"favorite": 2.0, "like": 1.0, "save": 1.0, "seen_loved": 1.0}
TV_GENRES = {10759: "Action", 16: "Animation", 35: "Comedy", 80: "Crime", 99: "Documentary", 18: "Drama",
             10751: "Family", 10762: "Kids", 9648: "Mystery", 10764: "Reality", 10765: "Sci-Fi", 10766: "Drama",
             10768: "Drama", 37: "Western"}


@lru_cache(maxsize=1)
def _load():
    path = DATA / "tv_knn.npz"
    if not path.exists():
        return None
    d = np.load(path)
    row_of = {int(r): i for i, r in enumerate(d["movie_rows"])}
    fans = d["show_fans"].astype(float)
    order = np.argsort(fans, kind="stable")
    pop = np.empty(len(fans))
    pop[order] = np.arange(len(fans)) / max(len(fans) - 1, 1)
    w = float(d["popularity_weight"]) if "popularity_weight" in d.files else 0.2
    return [str(x) for x in d["show_names"]], row_of, d["movie_nbr"], d["movie_w"].astype(np.float32), pop, w


def available():
    return _load() is not None


def viewer_shows(signals, exclude=()):
    """Shows ranked for this viewer: list of (name, score 0-1, rank, total, anchor movie title)."""
    d = _load()
    if d is None:
        return []
    names, row_of, nbr, w, pop, a = d
    s = np.zeros(len(names))
    best = {}
    for movie, action in signals or []:
        weight = FAN_ACTIONS.get(action, 0.0)
        idx = cf_model._index(movie)
        r = row_of.get(idx) if idx is not None else None
        if not weight or r is None:
            continue
        for j, v in zip(nbr[r], w[r]):
            if j < 0:
                continue
            s[j] += weight * v
            if v > best.get(j, (0, None))[0]:
                best[int(j)] = (float(v), movie.get("title"))
    if not s.any():
        return []
    order = np.argsort(s, kind="stable")
    fan_pct = np.empty(len(s))
    fan_pct[order] = np.arange(len(s)) / max(len(s) - 1, 1)
    blend = (1 - a) * fan_pct + a * pop
    ranked = [int(j) for j in np.argsort(-blend)]
    skip = {str(x).casefold() for x in exclude}
    out = []
    for rank, j in enumerate(ranked, start=1):
        if names[j].casefold() in skip:
            continue
        out.append((names[j], float(blend[j]), rank, len(ranked), (best.get(j) or (0, None))[1]))
        if len(out) >= 40:
            break
    return out


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def show_details(name):
    """TMDB details for a show by name: title, year, genres, overview, art, rating, where to watch."""
    from src.tmdb_catalog import _request, _best_landscape, TMDB_IMAGE_BASE
    found = (_request("/search/tv", {"query": name, "include_adult": "false"}) or {}).get("results") or []
    if not found:
        return None
    item = max(found[:5], key=lambda x: (str(x.get("name", "")).casefold() == name.casefold(), x.get("popularity") or 0))
    sid = int(item["id"])
    genres = [TV_GENRES[g] for g in item.get("genre_ids") or [] if g in TV_GENRES]
    art = _best_landscape(_request(f"/tv/{sid}/images", {"include_image_language": "en,null"}))
    poster = f"{TMDB_IMAGE_BASE}{item['poster_path']}" if item.get("poster_path") else None
    details = _request(f"/tv/{sid}", {"append_to_response": "external_ids,keywords"}) or {}
    runs = [int(x) for x in details.get("episode_run_time") or [] if x]
    keywords = [k.get("name", "") for k in ((details.get("keywords") or {}).get("results") or [])]
    return {"title": item.get("name") or name, "year": int(str(item.get("first_air_date") or "0")[:4] or 0),
            "tmdb_id": sid, "media": "tv", "external": True, "genre": genres[0] if genres else "Drama",
            "tags": list(dict.fromkeys(genres)), "overview": item.get("overview") or "", "poster_url": poster,
            "backdrop_url": art, "tmdb_vote": item.get("vote_average"), "tmdb_vote_count": item.get("vote_count"),
            "episode_runtime": min(runs) if runs else None, "imdb_id": (details.get("external_ids") or {}).get("imdb_id"),
            "keywords": keywords[:20], "origin": list(item.get("origin_country") or [])}


def matches_mood(show, words):
    """Shows aren't in the tested mood model, so a mood matches their genres, keywords, and summary words."""
    if not words:
        return True
    text = " ".join([show.get("title", ""), " ".join(show.get("tags") or []), " ".join(show.get("keywords") or []),
                     show.get("overview") or ""]).lower()
    if "anime" in words and "JP" in (show.get("origin") or []) and "Animation" in (show.get("tags") or []):
        return True
    return any(w in text for w in words.split())


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def show_watch(tmdb_id, region="US"):
    """Where to watch a show, in the same shape the movie cards use."""
    from src.tmdb_catalog import _request
    from src.watch_providers import _provider_names
    region_data = ((_request(f"/tv/{int(tmdb_id)}/watch/providers") or {}).get("results") or {}).get(region) or {}
    flat = (region_data.get("flatrate") or []) + (region_data.get("free") or []) + (region_data.get("ads") or [])
    streaming = _provider_names(flat)
    if streaming:
        return {"status": "streaming", "text": "Streaming: " + " · ".join(streaming), "url": region_data.get("link"),
                "providers": _provider_names(flat, limit=50), "rent_providers": []}
    buy = _provider_names(region_data.get("buy"))
    if buy:
        return {"status": "buy", "text": "Buy: " + " · ".join(buy), "url": region_data.get("link")}
    return {"status": "unavailable", "text": "Not currently available on major streaming services", "url": region_data.get("link")}
