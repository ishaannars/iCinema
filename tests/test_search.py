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
    src = _app_src()
    for part in ("tokens", "tonight", "top_result", "top_picks", "shows", "explore"):
        assert f'"{part}"' in src
    for state in ("none", "mood", "movie", "like"):
        assert f'"{state}"' in src


def test_undo_is_not_in_the_pill_row():
    src = _app_src()
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
    assert "in 1,000" in src and "for the most popular movie" in src and "current_hits" in src   # the baseline sits next to the lift


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
    src = _app_src()
    assert "from src.screens.home import render_home" in src and "from src.screens.ready import render_ready_summary" in src


def test_stylesheet_ships_in_whole_rules_under_the_size_limit():
    """One ~200k-character <style> block was cut off in the browser; it now ships in balanced pieces."""
    from src.ui import app_css, css_chunks
    css = app_css()
    parts = css_chunks(css)
    assert "".join(parts) == css and all(len(p) <= 60000 for p in parts)
    assert all(p.count("{") == p.count("}") for p in parts)


def test_a_movie_search_is_one_focused_answer():
    src = _app_src()
    assert '"movie": {"tokens": "X, editable", "tonight": None' in src
    assert "like Inception”\"" not in src


def test_only_new_releases_are_credited_to_the_new_release_model():
    """The order-model blend used to label every blended movie "new", so a 2014 film said "New, from filmmakers…"."""
    src = _app_src()
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
           r'why-|mix-|svc-|services-|data-|poster|watch-|ratings|profile-|shero-|pc-|plike-|showroom-|hit-|pf-|imp-)')
    allowed = {"body:has(.q-block) .block-container"}
    for group in re.findall(r"([^{}]+)\{", block):
        for sel in (x.strip() for x in group.split(",")):
            if sel and not sel.startswith("@") and sel not in allowed:
                assert re.search(own, sel), f"unscoped CSS selector: {sel}"


def test_title_search_puts_the_known_movie_first():
    from src.tmdb_catalog import rank_search_results
    items = [{"title": "Bikini Inception", "vote_count": 12}, {"title": "Inception: The Cobol Job", "vote_count": 140},
             {"title": "Inception", "vote_count": 38000}, {"title": "The Crack: Inception", "vote_count": 300},
             {"title": "Inception of Seeing", "vote_count": 150}]
    out = [i["title"] for i in rank_search_results(items, "inception")]
    assert out[0] == "Inception" and "Bikini Inception" not in out
    assert out[1] == "The Crack: Inception"


def test_a_reload_opens_the_normal_showroom():
    """A search is for this visit only: it isn't saved, and a restored profile starts with no search."""
    app = _app_src()
    snap = app[app.index("def profile_snapshot"):app.index("def _snapshot_signature")]
    assert "mood_active" not in snap
    assert 'st.session_state.mood_active = ""' in (ROOT / "src" / "app_state.py").read_text()


def test_one_why_popup_for_cards_and_tonight():
    src = _app_src()
    assert src.count("why_popup_html(") >= 3          # the definition, every card, and Tonight's Show
    assert "What decided this pick" in src


def test_movie_search_asks_the_one_question_that_tells_two_people_apart():
    src = _app_src()
    assert "Save to Watch" in src and "I’ve Seen It" in src and "How was it?" in src
    assert "def _fork_answer(title, movie, value):" in src


def test_like_blend_test_orders_by_both_ranks():
    """The blend in training/confirm_like_blend.py: w=0 keeps closest first, w=1 is pure fit."""
    import ast
    import numpy as np
    src = (ROOT / "training" / "confirm_like_blend.py").read_text()
    ns = {"np": np}
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in ("ranks01", "blend_order"):
            exec(compile(ast.Module([node], []), "blend", "exec"), ns)
    near = np.array([10, 11, 12])
    close, fit = np.array([0.9, 0.5, 0.1]), np.array([0.1, 0.2, 0.9])
    assert list(ns["blend_order"](near, close, fit, 0.0)) == [10, 11, 12]
    assert list(ns["blend_order"](near, close, fit, 1.0)) == [12, 11, 10]
    src_app = _app_src()
    assert "_like_blend_weight()" in src_app and "like_blend_confirm.json" in src_app


def test_seen_thumbs_train_the_personal_model_only_after_their_test():
    import json
    import src.ml_engine as ml
    path = ROOT / "data" / "seen_thumbs_confirm.json"
    existed = path.exists()
    old = path.read_text() if existed else None
    try:
        if existed:
            path.unlink()
        assert ml.seen_thumbs_ship() is False                       # no result yet: thumbs don't train it
        path.write_text(json.dumps({"ship": True, "auc": {"saves_and_skips": 0.49}}))
        assert ml.seen_thumbs_ship() is False                       # a chance-level baseline can't count
        path.write_text(json.dumps({"ship": True, "auc": {"saves_and_skips": 0.68}}))
        assert ml.seen_thumbs_ship() is True
    finally:
        if existed:
            path.write_text(old)
        elif path.exists():
            path.unlink()


def test_movie_plus_mood_stays_inside_the_movie_matches():
    """'Inception' + 'Funny' must order Inception's closest matches by mood, never pull in unrelated funny films."""
    src = _app_src()
    assert "if _mood is not None and top_all and not _like_source():" in src
    assert "Movie + mood (\"Inception\" + \"Funny\")" in src
    assert '"like":  {"tokens": "X + mood, editable", "tonight": None, "top_result": True' in src


def test_meaning_search_only_runs_after_its_test():
    import src.mood as mood
    mood._embed.cache_clear()
    if not (ROOT / "data" / "mood_embed_confirm.json").exists():
        assert mood._embed() is None
    assert "def _meaning(query):" in (ROOT / "src" / "mood.py").read_text()


APP_FILES = ("app.py", "src/actions.py", "src/ui/parts.py")   # app.py, split into modules (restructure)


def _app_src():
    return "\n".join((ROOT / f).read_text() for f in APP_FILES)


def _fn_src(path, name):
    import ast
    for f in (APP_FILES if path == "app.py" else (path,)):
        src = (ROOT / f).read_text()
        node = next((n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == name), None)
        if node is not None:
            return ast.get_source_segment(src, node)
    raise AssertionError(f"{name} not found")


def test_search_tiles_tap_across_the_whole_tile():
    """A tooltip (help=) wraps a button in a box sized to its hidden label, which shrank the tap area to a
    thin strip. Tile buttons stretch instead, and the stylesheet stretches every box around them."""
    body = _fn_src("app.py", "_render_search_tiles")
    assert "help=" not in body and "use_container_width=True" in body
    grid = _fn_src("app.py", "_render_services_grid")
    assert "help=" not in grid
    css = (ROOT / "src" / "ui" / "styles.css").read_text()
    assert '[class*="st-key-hit_tile_"] [class*="st-key-search_result_"] div' in css


def test_step1_is_one_tap_to_like():
    """Step 1 has one action, Like: no Favorite button, and tapping a search poster likes it."""
    shelf = _fn_src("app.py", "render_shelf_fragment")
    assert '"Favorite"' not in shelf and "Add as Favorite" not in shelf
    assert "like_search_result" in shelf


def test_every_page_counts_the_same_eleven_models():
    from src.model_names import MODELS_TOTAL, PICKING
    assert MODELS_TOTAL == 11 and len(PICKING) == 10
    for path in ("app.py", "src/screens/home.py", "src/screens/ready.py"):
        src = (ROOT / path).read_text()
        assert "10 + 1" not in src and "models picking" not in src
        assert " of 11 models" not in src.replace("MODELS_TOTAL", "")


def test_title_search_drops_near_unknown_matches():
    from src.tmdb_catalog import rank_search_results
    items = [{"title": "Oldboy", "vote_count": 9000}, {"title": "Oldboy", "vote_count": 3000},
             {"title": "Super Oldboy", "vote_count": 6}, {"title": "Oldboys", "vote_count": 40}]
    out = [(i["title"], i["vote_count"]) for i in rank_search_results(items, "oldboy")]
    assert out == [("Oldboy", 9000), ("Oldboy", 3000)]


def test_show_cards_print_a_percent_only_when_calibrated():
    """Show odds must pass training/confirm_tv_calibration.py; until then a card shows its rank."""
    src = (ROOT / "src" / "ui" / "shows.py").read_text()
    assert "tv.love_chance(rank, total)" in src and 'for you"' in src
    assert '% match"' not in src


def test_profile_shows_one_section_at_a_time():
    src = _app_src()
    assert '["Your Likes", "How It Works", "Activity", "Privacy"]' in src and "Reset Everything" in src
    assert '"Edit My Likes"' not in src


def test_one_skip_then_never_show():
    """Unwatched cards have one negative action, Skip. "Never Show" appears only after a Skip and replaces
    the skip with Not for Me. Thumbs are kept for movies you've seen (the "Liked it?" prompt and Seen tab)."""
    src = _app_src()
    assert 'key=f"dislike_{row_name}' not in src and 'key=f"tonight_dislike_' not in src
    assert "card_never_" in src and "tonight_never_" in src
    body = _fn_src("app.py", "never_show_skipped")
    assert '_drop_last_event(title, "skip")' in body and "dislike_movie(" in body


def test_search_art_is_keyed_by_year_so_remakes_differ():
    src = (ROOT / "src" / "tmdb_catalog.py").read_text()
    assert 'result[f"{title} ({year})"] = url' in src and 'result[f"tmdb:{tmdb_id}"] = url' in src
    assert 'art.get(f"tmdb:' in _fn_src("app.py", "_render_search_tiles")


def test_avoiding_violence_is_never_quietly_undone():
    body = _fn_src("app.py", "_avoid_filter")
    assert "kept if len(kept) >= 4 else items" not in body
    assert '"Crime"' in body and "quantile(sc[sc > 0], 0.25)" in body


def test_home_says_what_it_does_first():
    src = (ROOT / "src" / "screens" / "home.py").read_text()
    assert "Every service." in src and "home-pillars" in src and "Free · No account" in src
    assert "Ranked for You" in src and "All Your Services" in src and "Sharper Every Time" in src
    assert "taste" not in src.lower().replace("taste_", "")          # the word stays out of iCinema copy
    assert '"Max": "HBO Max"' in src and '"Apple TV+": "Apple TV"' in src


def test_a_replacement_after_skip_respects_what_you_avoid():
    """Goodfellas slid in after a Skip under "Nothing too violent": replacements now pass the same filter,
    and TMDB's own genre ids (80 Crime, 10752 War, 27 Horror) count as genres."""
    assert "_avoid_ok(" in _fn_src("app.py", "_advance_showroom_slot")
    assert "genre_ids" in _fn_src("app.py", "_avoid_filter")
    assert '"genre_ids"' in (ROOT / "src" / "tmdb_catalog.py").read_text()


def test_search_tiles_use_each_results_own_backdrop():
    assert 'm.get("backdrop_url")' in _fn_src("app.py", "_render_search_tiles")
    assert '"backdrop_url"' in (ROOT / "src" / "tmdb_catalog.py").read_text()


def test_a_looked_up_movie_keeps_its_own_picture_everywhere():
    src = _app_src()
    assert src.count("_art_for(m, ") >= 2                      # Saved and Seen
    assert 'poster = str(src.get("poster_url") or ident.get("poster_url")' in src   # the search's large card
    assert '_art_for' in _fn_src("app.py", "_art_for") and "tmdb:" in _fn_src("app.py", "_art_for")


def test_front_page_service_pills_are_names_only():
    body = _fn_src("src/screens/home.py", "_services_row")
    assert "<img" not in body


def test_front_page_model_claim_is_counted_from_result_files():
    """FTC-style substantiation: the "each passed a test" line is only shown if every model's file says PASS."""
    from src.claims import EVIDENCE, audit
    from src.model_names import MODELS_TOTAL
    assert len(EVIDENCE) == MODELS_TOTAL and len(audit()) == MODELS_TOTAL
    body = _fn_src("src/screens/home.py", "render_home")
    assert "models_passed()" in body and "_np == MODELS_TOTAL" in body


def test_horror_and_war_always_leave_under_nothing_too_violent():
    """Caught by the smoke test: Train to Busan and The Wailing showed under "Nothing too violent" because fans
    never tagged them "violence". Horror and War now leave on genre alone."""
    body = _fn_src("app.py", "_avoid_filter")
    assert "always_out" in body and '"violent": {"Horror", "War"}' in body and "_genres(m) & out_genres" in body


def test_value_proposition_is_on_every_surface():
    """Every service. Ranked for you.: front page pillars, README opening and founder table, and the Showroom
    showing it learns (one line per founder question: painful, shared, recurring)."""
    home = (ROOT / "src" / "screens" / "home.py").read_text()
    assert "Every service." in home and all(p in home for p in ("Ranked for You", "All Your Services", "Sharper Every Time"))
    readme = (ROOT / "README.md").read_text()
    assert "**Every service. Ranked for you.**" in readme and "**Recurring?**" in readme and "Sharper every time" in readme
    assert "showroom-learning" in _app_src()


def test_only_my_services_filters_every_row():
    """All your services, fully: with the switch on, rows fill only from movies streaming on your apps."""
    src = _app_src()
    assert 'st.toggle("Only show movies on my services", key="only_mine")' in src
    assert 'ordered=[it for it in ordered if it[1]["title"] in _mine_ok]' in src
    assert '(not _only or item[1]["title"] in _mine_ok)' in src


def test_only_my_services_switch_rebuilds_the_showroom():
    """Caught by the smoke test: the switch was missing from the build key, so rows were reused unchanged."""
    assert 'bool(ss.get("only_mine"))' in _fn_src("app.py", "_build_key")


def test_quick_reuse_never_keeps_off_service_rows():
    """Caught by the smoke test: a Save marks the next run as a quick reuse, which kept the old rows even after
    "Only show movies on my services" was turned on. Reuse now requires the same services, switch, and search."""
    src = _app_src()
    assert 'st.session_state.get("_slots_hard_key") == _hard' in src and '"_slots_hard_key": _hard' in src
