"""Card and popup text (src/ui/cards.py): the lines people read come straight from the numbers."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ui import cards  # noqa: E402


def test_genres_and_titles():
    assert cards.genre_pair({"genre": "Sci-Fi", "tags": ["Sci-Fi", "Action", "Dark"]}) == "Sci-Fi, Action"
    assert cards.genre_pair({"genre": "Drama", "tags": []}) == "Drama"
    assert cards._short_title("The Lord of the Rings: The Fellowship of the Ring") == "The Lord of the Rings"


def test_plain_premise_is_the_plot():
    m = {"overview": "Astronaut Mark Watney is presumed dead after a fierce storm. He survives.", "tagline": "Bring him home."}
    assert cards.plain_premise(m).startswith("Astronaut Mark Watney")
    assert cards.plain_premise({"overview": ""}) == ""


def test_why_rows_are_numbers():
    rows = dict(cards.why_rows([{"label": "Loved by fans of “Up”", "text": ""}], {"title": "X", "rt": 91, "imdb": 8.2},
                               {}, {"fit_rank": 12, "fit_pool": 900, "cf": 0.94, "semantic_similarity": 0.8}))
    assert rows["Rank"] == "#12 of 900 movies scored for you"
    assert "RT 91%" in rows["Ratings"] and "IMDb 8.2" in rows["Ratings"]


def test_tv_only_when_its_test_passed():
    import json
    from src import tv
    blend = ROOT / "data" / "tv_blend_confirm.json"
    shipped = blend.exists() and json.loads(blend.read_text()).get("ship")
    first = ROOT / "data" / "tv_confirm.json"
    shipped = shipped or (first.exists() and json.loads(first.read_text()).get("ship"))
    assert tv.available() == bool(shipped and (ROOT / "data" / "tv_knn.npz").exists())
