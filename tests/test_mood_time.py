"""One search field for mood and time: the time words become a runtime filter, the rest is the mood."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.ui.mood_time import fits, parse  # noqa: E402


def test_parse_mood_and_time():
    p = parse("funny, under 2 hours")
    assert p["mood"] == "funny" and p["max"] == 120 and p["label"] == "under 2h"
    assert parse("dark thriller under 90 min")["max"] == 90
    assert parse("something long")["min"] == 150 and parse("something long")["mood"] == ""
    assert parse("anime short episodes")["episodes"] == 35 and parse("anime short episodes")["mood"] == "anime"
    assert parse("feel-good") == {**parse("feel-good"), "max": None, "min": None, "label": ""}


def test_fits():
    spec = parse("under 2 hours")
    assert fits(110, spec) and not fits(130, spec) and not fits(None, spec)
    assert fits(None, parse("funny"))                      # no time limit: everything passes
    assert fits(25, parse("short episodes"), show=True) and not fits(60, parse("short episodes"), show=True)
