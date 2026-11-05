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
    assert "scikit-learn==1.6.1" in (ROOT / "requirements.txt").read_text()


def test_no_raw_errors_and_no_purple():
    assert 'showErrorDetails = "none"' in (ROOT / ".streamlit" / "config.toml").read_text()
    css = (ROOT / "src" / "ui" / "styles.css").read_text()
    assert "92,111,168" not in css and "5C6FA8" not in css.upper()
