"""One search field for mood and time: the time words become a runtime filter, the rest is the mood."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.ui.mood_time import fits, parse  # noqa: E402


def test_parse_mood_and_time():
    p = parse("funny, under 2 hours")
    assert p["mood"] == "funny" and p["max"] == 120 and p["label"] == "under 120 min"
    assert parse("dark thriller under 90 min")["max"] == 90
    assert parse("something long")["min"] == 150 and parse("something long")["mood"] == ""
    assert parse("anime short episodes")["episodes"] == 35 and parse("anime short episodes")["mood"] == "anime"
    assert parse("feel-good") == {**parse("feel-good"), "max": None, "min": None, "label": ""}


def test_fits():
    spec = parse("under 2 hours")
    assert fits(110, spec) and not fits(130, spec) and not fits(None, spec)
    assert fits(None, parse("funny"))                      # no time limit: everything passes
    assert fits(25, parse("short episodes"), show=True) and not fits(60, parse("short episodes"), show=True)


def test_bare_length_is_a_time_limit():
    assert parse("2 hours")["max"] == 120 and parse("2 hours")["mood"] == ""
    assert parse("90-minute comedy")["max"] == 90 and parse("90-minute comedy")["mood"] == "comedy"
    assert parse("2h 30m")["max"] == 150 and parse("an hour")["max"] == 60
    assert parse("funny movie around 2 hours")["mood"] == "funny"


def test_chips_remove_one_part_at_a_time():
    from src.ui.mood_time import chips
    labels = dict(chips("funny, under 2 hours"))
    assert set(labels) == {"funny", "Under 120 min"}
    assert parse(labels["funny"])["max"] == 120 and parse(labels["funny"])["mood"] == ""
    assert parse(labels["Under 120 min"])["mood"] == "funny" and parse(labels["Under 120 min"])["max"] is None
    assert chips("") == []


def test_search_understands_movies_like():
    from src.ui.mood_time import chips
    p = parse("funny, under 2 hours, like The Office")
    assert p["like"] == "The Office" and p["mood"] == "funny" and p["max"] == 120
    labels = dict(chips("funny, like Inception"))
    assert parse(labels["Like Inception"])["like"] is None and parse(labels["funny"])["like"] == "Inception"
    assert parse("movies like Se7en")["like"] == "Se7en" and parse("movies like Se7en")["mood"] == ""
    assert parse("like")["mood"] == ""
