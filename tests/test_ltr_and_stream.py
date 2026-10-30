"""The learned ranker is used only if its test shipped it; stream estimates stay labeled and bounded."""
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import ltr, stream_when  # noqa: E402


def test_ranker_only_when_shipped():
    conf = ROOT / "data" / "ltr_confirm.json"
    shipped = conf.exists() and json.loads(conf.read_text()).get("ship")
    assert ltr.available() == bool(shipped and (ROOT / "data" / "ltr_model.joblib").exists())


def test_stream_estimates():
    today = datetime.date(2026, 10, 30)
    assert "estimates" in stream_when.line("2026-10-10", [], today)
    assert stream_when.estimate("2026-10-10", [], today)[0] == datetime.date(2026, 11, 18)        # +39 days
    assert stream_when.estimate("2026-10-10", ["Pixar"], today)[0] == datetime.date(2026, 12, 11)  # Disney-style +62
    assert stream_when.line("2024-01-01", [], today) == ""          # long out of theaters: nothing to estimate
    assert stream_when.line("not a date", [], today) == ""


def test_profile_link_round_trip_and_privacy():
    from src.profile_link import decode, encode
    snap = {"likes": ["Up"], "saved": ["Heat"], "genres": ["Drama"], "analytics_events": [{"x": 1}], "anon_id": "abc",
            "external_movies": {"Heat": {"title": "Heat", "year": 1995, "tmdb_id": 949}, "Unused": {"title": "Unused"}}}
    back = decode(encode(snap))
    assert back["likes"] == ["Up"] and back["saved"] == ["Heat"] and back["genres"] == ["Drama"]
    assert "analytics_events" not in back and "anon_id" not in back          # nothing personal or behavioral
    assert list(back["external_movies"]) == ["Heat"]
    assert decode("not-a-real-link") is None


def test_tv_show_names_group_seasons():
    sys.path.insert(0, str(ROOT / "training"))
    from confirm_tv import is_tv, show_name
    assert show_name("Breaking Bad: Season 3") == "Breaking Bad"
    assert show_name("The Wire - The Complete Series") == "The Wire"
    assert is_tv({"title": "Lost Season 1", "categories": []}) and not is_tv({"title": "Heat", "categories": ["Movies"]})
    assert not is_tv({"title": "Heat", "categories": ["Movies & TV", "Movies"]})   # the store name isn't a TV category
    assert is_tv({"title": "Lost", "categories": ["Movies & TV", "TV"]})
