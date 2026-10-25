"""The Profile only claims what the viewer's choices support."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.recommender import build_profile, recommendation_explanation, CATALOG  # noqa: E402

STEP2 = ["Anime", "Action", "Adventure"]


def test_one_like_shows_no_tone_traits():
    p = build_profile({"Spirited Away"}, set(), STEP2, 25, ["Hidden Gems"])
    assert p["traits"] == [] and p["patterns"] == [] and p["movies_used"] == 1
    assert p["summary"].startswith("So far you lean toward")


def test_three_likes_unlock_traits():
    p = build_profile({"Spirited Away", "Princess Mononoke", "The Prestige"}, set(), STEP2, 50, [])
    assert p["traits"] and p["movies_used"] == 3


def test_long_step3_list_stays_short():
    p = build_profile({"Spirited Away"}, set(), STEP2, 50,
                      ["Recent Releases", "Critically Acclaimed", "Classics", "Hidden Gems"])
    assert "2 more you picked" in p["summary"]


def test_reasons_name_the_single_liked_movie():
    p = build_profile({"Spirited Away"}, set(), STEP2, 50, [])
    movie = next(m for m in CATALOG if m["title"] == "Princess Mononoke")
    texts = " ".join(r["text"] for r in recommendation_explanation(movie, p, 50, 50, semantic_similarity=0.9))
    assert "the movies you liked" not in texts
