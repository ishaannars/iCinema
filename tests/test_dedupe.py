"""One movie per series in the Showroom, and no making-of specials."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dedupe import MAKING_OF, franchise  # noqa: E402


def test_sequels_share_a_series():
    assert franchise("The Lord of the Rings: The Two Towers") == franchise("The Lord of the Rings: The Return of the King")
    assert franchise("Star Wars") == franchise("Star Wars: Episode IV - A New Hope")
    assert franchise("Toy Story 2") == franchise("Toy Story")
    assert franchise("Kill Bill: Vol. 1") == franchise("Kill Bill: Vol. 2")


def test_different_movies_stay_apart():
    assert franchise("Up") != franchise("Se7en")
    assert franchise("Before Sunrise") != franchise("Before Midnight")


def test_making_of_specials_are_dropped():
    assert MAKING_OF.search("Squid Game: Making Season 2")
    assert MAKING_OF.search("The Making of Jaws")
    assert not MAKING_OF.search("The Matrix")


def test_cards_use_the_tagline_before_a_generic_line():
    from src.descriptions import quick_card_description as q
    m = {"title": "The Matrix", "genre": "Action", "year": 1999, "tagline": "Welcome to the Real World.",
         "overview": "Set in the 22nd century, The Matrix tells the story of a computer hacker who joins a group of "
                     "underground insurgents fighting the vast and powerful computers who now rule the earth."}
    assert q(m, limit=92) == "Welcome to the Real World."
