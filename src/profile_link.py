"""Move my profile: carry a profile to another device in one link, with no accounts.

The link holds a compressed copy of the choices that shape picks (likes, saves, answers, and so on),
never analytics or anything personal. Opening it on another device asks before replacing that
browser's profile.
"""
import base64
import json
import zlib

KEYS = ("onboarding_complete", "likes", "favorites", "review_priority", "genres", "adventure", "more_of",
        "saved", "seen", "dismissed", "disliked", "seen_rating", "streaming_services", "imported_titles")
MOVIE_FIELDS = ("title", "year", "tmdb_id", "genre", "tags", "external")


def encode(snapshot):
    data = {k: snapshot.get(k) for k in KEYS if snapshot.get(k) not in (None, [], {}, "")}
    used = set(data.get("likes") or []) | set(data.get("saved") or []) | set(data.get("seen") or [])
    ext = snapshot.get("external_movies") or {}
    data["external_movies"] = {t: {f: m.get(f) for f in MOVIE_FIELDS if m.get(f) is not None}
                               for t, m in ext.items() if t in used}
    raw = zlib.compress(json.dumps(data, separators=(",", ":")).encode(), 9)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode(token):
    """Profile dict from a link token, or None if it isn't a valid iCinema link."""
    try:
        pad = "=" * (-len(token) % 4)
        data = json.loads(zlib.decompress(base64.urlsafe_b64decode(str(token) + pad)).decode())
    except Exception:
        return None
    return data if isinstance(data, dict) and ("likes" in data or "saved" in data) else None
