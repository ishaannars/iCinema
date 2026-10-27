"""Content model: built from MovieLens genres and fan tags, with no TMDB content."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import content_model as cm  # noqa: E402

SPIRITED = {"title": "Spirited Away", "year": 2001}
MONONOKE = {"title": "Princess Mononoke", "year": 1997}
SAW = {"title": "Saw", "year": 2004}


def test_shipped_and_built_without_tmdb():
    assert cm.available(), "run: python training/build_content.py --data-dir ml-32m"
    info = json.loads((ROOT / "data" / "content_ml.json").read_text())
    assert info["tmdb_content_used"] is False and info["movies_with_vectors"] > 10000


def test_similar_movies_score_higher():
    s = cm.similarity_scores([MONONOKE, SAW], [(SPIRITED, 1.0)])
    assert s[id(MONONOKE)] > s[id(SAW)]


def test_unknown_movie_is_neutral():
    unknown = {"title": "A Movie That Does Not Exist", "year": 1900}
    assert cm.similarity_scores([unknown], [(SPIRITED, 1.0)])[id(unknown)] == 0.5
    assert cm.similarity_scores([MONONOKE], [])[id(MONONOKE)] == 0.5


def test_no_model_learns_from_tmdb_text():
    for path in ("src/recommender.py", "app.py"):
        code = (ROOT / path).read_text()
        assert "TfidfVectorizer" not in code and "TruncatedSVD" not in code, path
