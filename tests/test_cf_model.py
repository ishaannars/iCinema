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
        cf._load.cache_clear(); cf._load_rank.cache_clear()
        taste = cf.user_vector([(SPIRITED, "like")])
        assert cf._load().kind == "svd" and 0.0 <= cf.cf_affinity(MONONOKE, taste) <= 1.0
    finally:
        cf.KNN_PATH = old
        cf._load.cache_clear(); cf._load_rank.cache_clear()


def test_famous_movies_are_not_hidden():
    assert cf.fan_percentile(MONONOKE) > 0.8
    assert cf.fan_percentile({"title": "Not A Real Movie Title", "year": 1900}) is None


def test_routing_sends_less_mainstream_likes_to_rp3beta():
    if cf._routing_cut() is None:
        return
    mainstream = [(MATRIX, "like"), ({"title": "Toy Story", "year": 1995}, "like"), ({"title": "Fight Club", "year": 1999}, "like")]
    assert cf._ranker_for(mainstream) is cf._load()
    niche = [({"title": "Tampopo", "year": 1985}, "like"), ({"title": "Coherence", "year": 2013}, "like"),
             ({"title": "The Wailing", "year": 2016}, "like")]
    assert cf._ranker_for(niche) is cf._load_rank()


def test_ranking_uses_rp3beta_when_shipped():
    import json
    shipped = json.loads((ROOT / "data" / "long_tail_confirm.json").read_text())["replaces_item_knn"]
    assert (cf.RANK_PATH.exists()) == shipped
    if shipped:
        assert float(__import__("numpy").load(cf.RANK_PATH)["beta"]) > 0


def test_title_matches_the_poster():
    assert cf.preferred_title({"title": "Warriors of the Wind", "year": 1984, "tmdb_id": 81},
                              "Warriors of the Wind") == "Nausicaä of the Valley of the Wind"
    assert cf.preferred_title({"title": "Se7en", "year": 1995, "tmdb_id": 807}, "Se7en") == "Se7en"
    assert cf.preferred_title({"title": "Spirited Away", "year": 2001}, "Spirited Away") == "Spirited Away"


def test_interleaving_only_for_viewers_routed_to_rp3beta():
    mainstream = [(MATRIX, "like")]
    assert not cf.interleave_eligible(mainstream)
    model = cf._load()
    import numpy as np
    niche = [({"title": model.titles[i], "year": int(0)}, "like") for i in np.argsort(model.fan_pct)[200:3200:1000][:3]]
    if cf._routing_cut() is not None and cf._load_rank() is not model:
        assert cf.interleave_eligible(niche)
        a, b = cf.user_vector(niche), cf.user_vector(niche, force_knn=True)
        assert a is not None and b is not None and not np.allclose(a.scores, b.scores)


def test_history_routing_is_off_unless_its_test_passed():
    import json
    full, cut = cf._history_cut()
    path = cf.HISTORY_PATH
    shipped = path.exists() and json.loads(path.read_text()).get("ship") and cf.FULL_PATH.exists()
    assert (full is not None) == bool(shipped)
    if full is None:
        many = [({"title": t}, "like") for t in ("The Matrix", "Inception", "Up", "Heat")]
        assert cf._ranker_for(many) is cf._niche_ranker(many)
