"""Unit tests for the "viewers like you" layer (src/cf_model.py) on the shipped model file."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import cf_model as cf  # noqa: E402

SPIRITED = {"title": "Spirited Away", "year": 2001}
MONONOKE = {"title": "Princess Mononoke", "year": 1997}
MATRIX = {"title": "The Matrix", "year": 1999}
MAMMA = {"title": "Mamma Mia!", "year": 2008}


def test_model_loads():
    assert cf.cf_available()


def test_no_likes_means_no_taste():
    assert cf.user_vector([]) is None
    assert cf.cf_affinity(MONONOKE, None) is None


def test_scores_stay_between_0_and_1():
    taste = cf.user_vector([(SPIRITED, "like"), (MATRIX, "like")])
    for m in (MONONOKE, MATRIX, MAMMA, {"title": "Toy Story", "year": 1995}):
        a = cf.cf_affinity(m, taste)
        assert a is None or 0.0 <= a <= 1.0


def test_similar_movie_beats_unrelated_movie():
    taste = cf.user_vector([(SPIRITED, "like")])
    assert cf.cf_affinity(MONONOKE, taste) > cf.cf_affinity(MAMMA, taste)


def test_no_evidence_is_neutral():
    taste = cf.user_vector([(SPIRITED, "like")])
    assert cf.cf_affinity(MAMMA, taste) == 0.5


def test_dislike_pushes_down():
    liked = cf.user_vector([(MATRIX, "like")])
    both = cf.user_vector([(MATRIX, "like"), (SPIRITED, "dislike")])
    assert cf.cf_affinity(MONONOKE, both) < cf.cf_affinity(MONONOKE, liked) or cf.cf_affinity(MONONOKE, both) < 0.5


def test_fans_of_names_the_right_liked_movie():
    assert cf.closest_liked(MONONOKE, [(SPIRITED, "like"), (MATRIX, "like")]) == "Spirited Away"


def test_seen_is_never_quoted_as_a_fan():
    assert cf.closest_liked(MONONOKE, [(SPIRITED, "seen")]) is None


def test_item_similarity_bounds_and_order():
    close, far = cf.item_similarity(SPIRITED, MONONOKE), cf.item_similarity(SPIRITED, MAMMA)
    assert 0.5 < close <= 1.0 and far == 0.5
    assert cf.item_similarity(SPIRITED, {"title": "Not A Real Movie Title", "year": 1900}) is None


def test_falls_back_to_svd_when_knn_file_missing():
    old = cf.KNN_PATH
    try:
        cf.KNN_PATH = ROOT / "data" / "missing.npz"
        cf._load.cache_clear()
        taste = cf.user_vector([(SPIRITED, "like")])
        assert cf._load().kind == "svd" and 0.0 <= cf.cf_affinity(MONONOKE, taste) <= 1.0
    finally:
        cf.KNN_PATH = old
        cf._load.cache_clear()
