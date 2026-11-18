"""The search is one system: what's typed adds to what's on, and the parts read back the same way."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ui.mood_time import merge, parse  # noqa: E402


def test_typing_adds_to_the_search():
    assert parse(merge("funny", "under 2 hours")) == parse("funny, under 2 hours")
    assert parse(merge("dark, not violent", "slow-burn"))["avoid"] == ["violent"]
    assert parse(merge("dark", "slow-burn"))["mood"] == "dark slow-burn"


def test_a_new_length_or_movie_replaces_the_old_one():
    assert parse(merge("funny, under 90 min", "under 2 hours"))["max"] == 120
    assert parse(merge("funny, like Inception", "like Heat"))["like"] == "Heat"


def test_a_searched_movie_plus_a_mood_becomes_like_the_movie():
    p = parse(merge("inception", "funny", current_title="Inception"))
    assert p["like"] == "Inception" and p["mood"] == "funny"
    p = parse(merge("mind-bending", "Inception", typed_title="Inception"))
    assert p["like"] == "Inception" and p["mood"] == "mind-bending"


def test_a_movie_typed_alone_keeps_the_filters():
    p = parse(merge("under 90 min, not violent", "Inception", typed_title="Inception"))
    assert p["mood"] == "inception" and p["max"] == 90 and p["avoid"] == ["violent"] and p["like"] is None


def test_every_part_of_the_search_has_one_rule():
    """The written rule in app.py names every part for every state, so nothing is decided ad hoc."""
    src = (ROOT / "app.py").read_text()
    for part in ("tokens", "tonight", "top_result", "top_picks", "shows", "explore"):
        assert f'"{part}"' in src
    for state in ("none", "mood", "movie", "like"):
        assert f'"{state}"' in src


def test_undo_is_not_in_the_pill_row():
    src = (ROOT / "app.py").read_text()
    assert "st.columns([2.75,0.62,0.90]" not in src      # the old three-column pill row with Undo inside it
    assert "card_undo_" in src


def test_a_movie_typed_with_a_length_keeps_both():
    p = parse(merge("funny", "Inception under 2 hours", typed_title="Inception"))
    assert p["like"] == "Inception" and p["mood"] == "funny" and p["max"] == 120


def test_love_chance_reads_the_rank_it_was_tested_on():
    """The calibration table was fit on rank among the 600 most-loved unseen movies, so the pill reads that rank."""
    from src.ui.cards import fit_head
    assert fit_head({"love_top_pct": 2, "fit_top_pct": 40}, 0) == fit_head({"fit_top_pct": 2}, 0)
    assert fit_head({"fit_top_pct": 40}, 0) == fit_head({"love_top_pct": 40}, 0)


def test_home_shows_the_baseline_next_to_the_lift():
    src = (ROOT / "src" / "screens" / "home.py").read_text()
    assert "in 1,000 test viewers" in src and "current_hits" in src      # tested numbers, then what is trending


def test_ready_page_lists_only_running_models_with_five_word_jobs():
    import ast
    src = (ROOT / "src" / "screens" / "ready.py").read_text()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "_ready_models")
    jobs = [c.elts[2].value for c in ast.walk(fn) if isinstance(c, ast.Tuple) and len(c.elts) == 3
            and isinstance(c.elts[2], ast.Constant) and isinstance(c.elts[2].value, str)]
    assert jobs and all(len(j.replace(",", "").split()) == 5 for j in jobs), jobs


def test_screens_live_in_their_own_files():
    """app.py routes; Home and the ready page are their own modules, importable on their own."""
    import importlib
    for name in ("src.screens.home", "src.screens.ready"):
        assert (ROOT / (name.replace(".", "/") + ".py")).exists()
    src = (ROOT / "app.py").read_text()
    assert "from src.screens.home import render_home" in src and "from src.screens.ready import render_ready_summary" in src


def test_stylesheet_ships_in_whole_rules_under_the_size_limit():
    """One ~200k-character <style> block was cut off in the browser; it now ships in balanced pieces."""
    from src.ui import app_css, css_chunks
    css = app_css()
    parts = css_chunks(css)
    assert "".join(parts) == css and all(len(p) <= 60000 for p in parts)
    assert all(p.count("{") == p.count("}") for p in parts)


def test_a_movie_search_is_one_focused_answer():
    src = (ROOT / "app.py").read_text()
    assert '"movie": {"tokens": "Movie: X, editable", "tonight": None' in src
    assert "like Inception”\"" not in src


def test_only_new_releases_are_credited_to_the_new_release_model():
    """The order-model blend used to label every blended movie "new", so a 2014 film said "New, from filmmakers…"."""
    src = (ROOT / "app.py").read_text()
    i = src.index("cf=_nr_affinity(movie,nr_view)")
    block = src[i:i + 300]
    assert 'cf_source_by_title[movie["title"]]="new"' in block.split("if cf is not None and _seq_vec")[0]


def test_new_styles_only_touch_what_they_name():
    """Every rule from Batch 60 on is scoped to a keyed box or one of iCinema's own classes, so a fix on
    one screen can't reach into another. (A broad rule in Batch 62 stacked the whole Step 1 shelf.)"""
    import re
    css = (ROOT / "src" / "ui" / "styles.css").read_text()
    block = re.sub(r"/\*.*?\*/", "", css[css.index("/* ==== Batch 60"):], flags=re.S)
    own = (r'\.st-key-|\[class\*="st-key-|\.(q-|step2|ready|search-|selection|sel-|pcard|genre|hero|home|live-hit|'
           r'why-|mix-|svc-|services-|data-|poster|watch-|ratings)')
    allowed = {"body:has(.q-block) .block-container"}
    for group in re.findall(r"([^{}]+)\{", block):
        for sel in (x.strip() for x in group.split(",")):
            if sel and not sel.startswith("@") and sel not in allowed:
                assert re.search(own, sel), f"unscoped CSS selector: {sel}"
