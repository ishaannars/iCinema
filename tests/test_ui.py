"""Page building blocks: the stylesheet loads, and outside text can't inject HTML or scripts."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ui import app_css  # noqa: E402
from src.ui.watch import watch_line_html, provider_watch_url, _safe_url  # noqa: E402


def test_stylesheet_lives_in_its_own_file():
    css = app_css()
    assert ":root" in css and "<style>" not in css
    assert "--sumi:" not in (ROOT / "app.py").read_text()   # no inline stylesheet left in app.py


def test_provider_and_title_text_is_escaped():
    bad = '<img src=x onerror=alert(1)>'
    out = watch_line_html({"providers": [bad]}, bad)
    assert "<img" not in out and "&lt;img" in out


def test_only_web_links_render():
    assert _safe_url("javascript:alert(1)") == "" and _safe_url("https://www.netflix.com") == "https://www.netflix.com"
    out = watch_line_html({"providers": ["Unknown Service"], "url": "javascript:alert(1)"}, "Film")
    assert "javascript:" not in out


def test_your_services_come_first():
    out = watch_line_html({"providers": ["Netflix", "Hulu"]}, "Film", ["Hulu"])
    assert out.startswith("On your services:") and "Hulu" in out and "Netflix" not in out and "+ 1 more" in out


def test_links_are_encoded():
    assert " " not in provider_watch_url("Unknown Service", "A Film & More")


def test_more_options_are_a_link_to_every_option():
    out = watch_line_html({"providers": ["Netflix", "Hulu", "Max", "Peacock"], "url": "https://www.themoviedb.org/movie/1/watch"}, "Film")
    assert "+ 3 more</a>" in out and 'href="https://www.justwatch.com/us/search?q=Film"' in out
    out = watch_line_html({"providers": ["Netflix", "Hulu", "Max"], "url": "javascript:alert(1)"}, "Film")
    assert "javascript:" not in out and "+ 2 more" in out


def test_one_clean_name_per_service_and_big_services_first():
    from src.ui.watch import clean_provider
    assert clean_provider("AMC+ Roku Premium Channel") == "AMC+" and clean_provider("Netflix Standard with Ads") == "Netflix"
    out = watch_line_html({"providers": ["Fandor", "Night Flight Plus", "Hulu"]}, "Film")
    assert out.startswith("Streaming:") and "Hulu" in out and "Fandor" not in out and "+ 2 more" in out
    out = watch_line_html({"providers": ["Netflix", "Netflix basic with Ads"]}, "Film")
    assert "more" not in out
