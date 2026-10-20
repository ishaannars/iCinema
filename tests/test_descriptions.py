"""Card line rules (src/descriptions.py). Summaries below are short test texts written for these
tests, shaped like the TMDB summaries that produced odd card lines in the app."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.descriptions import quick_card_description as card  # noqa: E402

LIMIT = 92


def test_vague_tagline_loses_to_a_real_summary_line():
    m = {"title": "Prisoners", "tagline": "Someone is missing.",
         "overview": "A desperate father takes the law into his own hands after his young daughter disappears. "
                     "The police detective on the case races to find her first."}
    out = card(m, LIMIT)
    assert out != "Someone is missing." and "daughter" in out


def test_tagline_ellipsis_is_tidied():
    m = {"title": "Castle in the Sky", "tagline": "One day, a girl came down from the sky....", "overview": ""}
    assert card(m, LIMIT) == "One day, a girl came down from the sky."


def test_no_usable_text_gives_a_plain_details_line():
    m = {"title": "Arise", "genre": "Anime", "year": 2013, "tags": ["Tense"], "original_language": "ja",
         "overview": "Following the events of the previous chapter, Major Kusanagi and her newly formed unit investigate "
                     "a string of cyber attacks tied to a mysterious hacker who seems to know every move they plan to make next."}
    out = card(m, LIMIT)
    assert out.endswith(".") and "Tap for the premise" not in out and len(out) <= LIMIT


def test_sentence_that_needs_earlier_context_is_skipped():
    m = {"title": "Fury Road", "tagline": "",
         "overview": "An apocalyptic story set in the furthest reaches of our planet. "
                     "Within this world exist two rebels on the run who might be able to restore order."}
    assert not card(m, LIMIT).startswith("Within this world")


def test_praise_loses_to_a_premise():
    m = {"title": "The Shining", "tagline": "A masterpiece of modern horror.",
         "overview": "A struggling writer takes a job caring for an isolated hotel over the winter with his wife and son."}
    assert "masterpiece" not in card(m, LIMIT)


def test_hand_written_hook_wins():
    assert card({"why": "A heist told backwards.", "overview": "Long text."}, LIMIT) == "A heist told backwards."


def test_every_line_is_complete_and_fits():
    movies = [
        {"overview": "A programmer is invited to evaluate a highly advanced artificial intelligence."},
        {"overview": "Two rival magicians become consumed by outdoing one another, with deadly results for both of them."},
        {"genre": "Comedy", "year": 2015, "original_language": "es", "overview": ""},
        {"tagline": "The world will never be the same once you've seen it through the eyes of a stranger.",
         "overview": "A kind man with a low IQ drifts through decades of American history."},
    ]
    for m in movies:
        out = card(m, LIMIT)
        assert out[-1] in ".!?" and len(out) <= LIMIT + 30, out
