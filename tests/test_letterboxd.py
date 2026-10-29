"""Ratings import keeps only tested signals and never invents matches."""
import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import letterboxd as lb  # noqa: E402

CSV = (b"Date,Name,Year,Letterboxd URI,Rating\n"
       b"2024-01-02,Alpha,2001,x,5\n2024-01-03,Beta,2010,x,4\n2024-01-04,Gamma,2011,x,3.5\n"
       b"2024-01-05,Delta,2012,x,\n2024-01-06,Unknown,1999,x,4.5\n")
LIB = {("Alpha", 2001): {"title": "Alpha"}, ("Beta", 2010): {"title": "Beta"}, ("Gamma", 2011): {"title": "Gamma"}}


def fake_lookup(name, year):
    m = LIB.get((name, year))
    return dict(m) if m else None


def test_reads_csv_and_zip():
    rows = lb.read_ratings(CSV)
    assert [r[0] for r in rows] == ["Alpha", "Beta", "Gamma", "Unknown"]   # unrated row dropped
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("letterboxd-export/ratings.csv", CSV)
        z.writestr("letterboxd-export/watched.csv", b"Date,Name,Year\n")
    assert lb.read_ratings(buf.getvalue()) == rows


def test_thresholds_match_the_models_4_star_rule():
    choices, summary = lb.to_choices(lb.read_ratings(CSV), fake_lookup)
    kinds = {m["title"]: k for m, k in choices}
    assert kinds == {"Alpha": "favorite", "Beta": "like"}              # 3.5 stars is left out
    assert summary == {"rated": 4, "kept": 3, "matched": 2, "not_found": 1}


def test_cap_and_newest_first():
    rows = [(f"M{i}", 2000, 5.0, f"2024-01-{i % 28 + 1:02d}") for i in range(400)]
    choices, s = lb.to_choices(rows, lambda n, y: {"title": n})
    assert len(choices) == lb.MAX_IMPORT and s["matched"] == lb.MAX_IMPORT


def test_real_lookup_matches_known_titles():
    from src import cf_model as cf
    if not cf.cf_available():
        return
    m = cf.lookup("Spirited Away", 2001)
    assert m and m["title"] == "Spirited Away" and m["tmdb_id"] == 129
    assert cf.lookup("Spirited Away", 2002)                              # year off by one is allowed
    assert cf.lookup("Zzzz Not A Movie", 1999) is None


def test_imdb_export_is_halved_to_five_stars():
    imdb = (b"Const,Your Rating,Date Rated,Title,URL,Title Type,IMDb Rating,Runtime (mins),Year\n"
            b"tt1,10,2024-02-01,Alpha,x,Movie,8,100,2001\ntt2,8,2024-02-02,Beta,x,Movie,7,100,2010\n"
            b"tt3,9,2024-02-03,Some Show,x,TV Series,8,50,2015\n")
    rows = lb.read_ratings(imdb)
    assert [(r[0], r[2]) for r in rows] == [("Alpha", 5.0), ("Beta", 4.0)]      # series left out


def test_low_and_middling_only_when_their_test_passed():
    rows = [("Alpha", 2001, 1.5, "2024-01-01"), ("Beta", 2010, 3.0, "2024-01-02"), ("Gamma", 2011, 4.0, "2024-01-03")]
    off, _ = lb.to_choices(rows, fake_lookup)
    assert [k for _, k in off] == ["like"]
    on, _ = lb.to_choices(rows, fake_lookup, use_low=True, use_mid=True)
    assert {m["title"]: k for m, k in on} == {"Alpha": "dislike", "Beta": "seen", "Gamma": "like"}


def test_search_puts_exact_and_well_known_titles_first():
    from src.search_rank import rerank
    res = [{"title": "Jodorowsky's Dune", "tmdb_vote_count": 600}, {"title": "Dune", "tmdb_vote_count": 200, "year": 1984},
           {"title": "Dune: Part Two", "tmdb_vote_count": 7000}, {"title": "Dune", "tmdb_vote_count": 12000, "year": 2021}]
    out = rerank("dune", res)
    assert [(m["title"], m.get("year")) for m in out[:2]] == [("Dune", 2021), ("Dune", 1984)]
    assert out[2]["title"] == "Dune: Part Two"


def test_typos_still_find_the_movie():
    from src import cf_model as cf
    if not cf.cf_available():
        return
    assert cf.fuzzy_titles("interstallar")[0]["title"] == "Interstellar"
    assert cf.fuzzy_titles("parasit")[0]["year"] == 2019      # the famous one, not the 1982 film
    assert cf.fuzzy_titles("zz") == []
