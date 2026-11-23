""""Nothing too violent": shows use the official TV descriptor V first, TV-MA only when no descriptors exist."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_show_violence_rule(monkeypatch):
    import src.tv as tv
    show = {"tmdb_id": 1, "keywords": ["dragons"], "overview": "Families fight for a throne."}
    monkeypatch.setattr(tv, "content_rating", lambda *_: ("TV-MA", ("L", "S", "V")))
    assert tv.avoids(show, ["violence"], ["violent"])
    monkeypatch.setattr(tv, "content_rating", lambda *_: ("TV-MA", ("L",)))
    assert not tv.avoids(show, ["violence"], ["violent"])          # mature for language only: kept
    monkeypatch.setattr(tv, "content_rating", lambda *_: ("TV-MA", ()))
    assert tv.avoids(show, ["violence"], ["violent"])              # no descriptors listed: TV-MA fallback
    assert tv.avoids({"keywords": ["gore"], "overview": ""}, ["gore"], ["violent"])
    assert not tv.avoids(show, [], [])


def test_movie_filter_reads_rating_board_descriptors():
    src = (ROOT / "src" / "tmdb_catalog.py").read_text()
    assert "def flagged_by_rating_boards" in src and "geweld" in src
    assert "flagged_by_rating_boards" in (ROOT / "app.py").read_text()
