"""Release checks for the details that make the app feel finished."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_emoji_anywhere_in_the_app():
    pattern = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u21B6]")
    for f in [ROOT / "app.py", *ROOT.glob("src/**/*.py")]:
        assert not pattern.search(f.read_text()), f.name


def test_ml_engine_does_not_load_sklearn_at_startup():
    code = "import sys; import src.ml_engine; print('sklearn' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert out.stdout.strip() == "False", out.stderr


def test_ranker_runs_on_the_version_it_was_trained_with():
    assert "scikit-learn>=1.6.1" in (ROOT / "requirements.txt").read_text()


def test_no_raw_errors_and_no_purple():
    assert 'showErrorDetails = "none"' in (ROOT / ".streamlit" / "config.toml").read_text()
    css = (ROOT / "src" / "ui" / "styles.css").read_text()
    assert "92,111,168" not in css and "5C6FA8" not in css.upper()


def test_runtimes_read_in_minutes():
    from src.ui.mood_time import fmt
    assert fmt(136) == "136 min" and fmt(None) == ""


def test_fit_pill_says_what_the_rank_means():
    from src.ui.cards import fit_head, match_pill
    assert fit_head({"fit_top_pct": 4}, 80) == "Top 4% for you"
    assert "for you for you" not in match_pill(80, [], head=fit_head({"fit_top_pct": 4}, 80))[0]


def test_saves_from_every_discovery_row_count():
    from src.analytics import analytics_insights
    ev = [{"event": "save", "title": "A", "row": "Classics for You", "timestamp": 1, "session_id": "s"},
          {"event": "save", "title": "B", "row": "Top Matches for You", "timestamp": 2, "session_id": "s"}]
    assert analytics_insights(ev)["discovery_rate"] == 0.5


def test_score_mix_matches_the_scoring_blend():
    from src.ui.cards import score_mix
    mix = score_mix({"content": 0.6, "cf": 0.9, "personal": 0.7, "cf_source": "ranker"}, 0.2)
    assert [n for n, _, _ in mix] == ["Fans like you", "What it’s like", "Your choices"]
    assert abs(sum(s for _, _, s in mix) - 1) < 1e-9
    fans, content, mine = (s for _, _, s in mix)
    total = 0.78 * 0.8 * 0.9 + 0.78 * 0.2 * 0.6 + 0.22 * 0.7
    assert abs(fans - 0.78 * 0.8 * 0.9 / total) < 1e-9 and abs(mine - 0.22 * 0.7 / total) < 1e-9
    assert score_mix({"cf": 0.9}, 0.2) == []


def test_ratings_reason_follows_the_step2_answer():
    from src.ui.cards import ratings_reason
    assert "critics count more" in ratings_reason("RT 97%", 20)
    assert "audiences count more" in ratings_reason("RT 97%", 80)
    assert "equally" in ratings_reason("RT 97%", 50) and ratings_reason("", 50) == ""
