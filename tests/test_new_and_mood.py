"""New-release placement and mood search behave as their tests describe, and stay off unless shipped."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "training"))
from src import mood, new_releases  # noqa: E402

DATA = ROOT / "data"


def test_off_unless_their_test_passed():
    for name, conf, mod in (("new_releases.npz", "new_release_confirm.json", new_releases), ("mood_index.npz", "mood_confirm.json", mood)):
        shipped = (DATA / conf).exists() and json.loads((DATA / conf).read_text()).get("ship")
        assert (DATA / name).exists() == bool(shipped)
        assert mod.available() == bool(shipped)


def test_mood_words_drop_filler():
    assert mood.words("A slow-burn movie with a twist ending") == ["slow-burn", "twist", "ending"]


def test_mood_search_finds_the_tagged_movie():
    from confirm_mood import build, search
    M, vocab, idf = build([(0, "slow-burn twist ending"), (1, "funny feel-good"), (2, "funny"), (3, "twist"),
                           (0, "twist"), (1, "feel-good"), (2, "slow-burn"), (3, "ending funny")] * 3, 4)
    s = search(M, vocab, idf, "twist ending slow-burn")
    assert int(np.argmax(s)) == 0


def test_facts_tokens_cover_every_kind():
    from confirm_new_releases import tokens
    t = tokens({"director": ["Q1"], "cast": ["Q2"], "company": ["Q3"], "genre": ["Q4"], "country": ["Q5"], "year": 2024})
    assert {x.split(":")[0] for x in t} == {"d", "c", "co", "g", "n", "y"}
    assert tokens({"genre": ["Q4"], "director": ["Q1"]}, genres_only=True) == ["g:Q4"]


def test_new_release_finds_its_closest_known_movies():
    import numpy as np
    from src import new_releases as nr
    if not nr.available():
        return
    tid = int(np.load(ROOT / "data" / "new_releases.npz")["tmdb_id"][0])
    near = nr.nearest({"tmdb_id": tid}, 20)
    assert len(near) == 20 and all(near[k][1] >= near[k + 1][1] for k in range(19))
    assert nr.nearest({"tmdb_id": -1}) == []


def test_mood_typos_are_fixed_against_fan_words():
    from src import mood
    if not mood.available():
        return
    assert mood.correct("dakr") == "dark" and mood.correct("fuuny") == "funny"
    assert mood.correct("dark") == "dark"


def test_mood_words_vs_titles():
    from src import mood
    if not mood.available():
        return
    assert mood.is_mood_word("dark") and mood.is_mood_word("mystery") and mood.is_mood_word("funny")
    assert not mood.is_mood_word("hokum") and not mood.is_mood_word("oldboy")
