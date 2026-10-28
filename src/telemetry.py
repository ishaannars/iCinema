"""Anonymous usage counts, sent to PostHog only when a key is configured.

What is sent: a random browser ID, the event type (visit, save, skip, seen, not_for_me), the row,
the card position, the love-chance band, and the model version. Never titles, names, emails, or
IP-based location. Viewers can turn it off in their Profile. Without POSTHOG_KEY in Streamlit
secrets nothing is sent and nothing breaks.
"""
import uuid
from functools import lru_cache

from src.secrets_util import safe_secret

ALLOWED = {"visit", "save", "skip", "seen", "not_for_me", "seen_loved", "seen_not_for_me"}


@lru_cache(maxsize=1)
def _client():
    key = str(safe_secret("POSTHOG_KEY", "") or "").strip()
    if not key:
        return None
    try:
        from posthog import Posthog
    except ImportError:
        return None
    host = str(safe_secret("POSTHOG_HOST", "https://us.i.posthog.com") or "https://us.i.posthog.com")
    return Posthog(key, host=host, disable_geoip=True)


def anon_id(state):
    if not state.get("anon_id"):
        state["anon_id"] = uuid.uuid4().hex
    return state["anon_id"]


def track(state, event, row=None, position=None, top_pct=None, model_version=None):
    """Fire-and-forget. Any failure is swallowed, so analytics can never break the app."""
    if event not in ALLOWED or state.get("analytics_opt_out"):
        return
    client = _client()
    if client is None:
        return
    band = None
    if isinstance(top_pct, (int, float)):
        band = "top 1%" if top_pct <= 1 else "top 5%" if top_pct <= 5 else "top 20%" if top_pct <= 20 else "below top 20%"
    try:
        client.capture(distinct_id=anon_id(state), event=event,
                       properties={"row": row, "position": position, "fit_band": band,
                                   "model_version": model_version, "$process_person_profile": False})
    except Exception:
        pass
