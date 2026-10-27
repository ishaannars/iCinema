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
    assert out.startswith("On your services:") and out.index("Hulu") < out.index("Netflix")


def test_links_are_encoded():
    assert " " not in provider_watch_url("Unknown Service", "A Film & More")
