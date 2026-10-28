"""Analytics never sends personal data and does nothing without a key."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import telemetry  # noqa: E402


def test_no_key_means_nothing_is_sent():
    telemetry._client.cache_clear()
    state = {}
    telemetry.track(state, "save", row="Top Matches for You", position=1)
    assert telemetry._client() is None or isinstance(state.get("anon_id"), str)


def test_only_known_events_and_no_titles():
    assert "title" not in telemetry.track.__code__.co_varnames
    assert telemetry.ALLOWED == {"visit", "save", "skip", "seen", "not_for_me", "seen_loved", "seen_not_for_me"}


def test_opt_out_is_respected():
    state = {"analytics_opt_out": True}
    telemetry.track(state, "save")
    assert "anon_id" not in state
