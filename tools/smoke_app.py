"""Click through every screen of the app headlessly and report any error.

    python tools/smoke_app.py

Uses Streamlit's AppTest. Runs the home page, Profile, and Showroom (all four tabs), then
presses Refresh on Saved and Seen and the first Save button, then repeats with less mainstream
likes so the live interleaving test in Top Matches runs. Prints OK or the errors it hit.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))     # so app.py can import src/ like it does under `streamlit run`
os.chdir(ROOT)

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(ROOT / "app.py")


def check(at, step):
    errs = [str(e.value)[:300] for e in at.exception]
    print(f"{step:<28} {'OK' if not errs else 'ERROR: ' + ' | '.join(errs)}")
    return not errs


def main():
    at = AppTest.from_file(APP, default_timeout=300)
    at.session_state["_storage_hydrated"] = True
    ok = True
    at.run(); ok &= check(at, "Home")
    at.session_state["likes"] = {"Spirited Away"}
    at.session_state["genres"] = ["Anime", "Action"]
    at.session_state["more_of"] = ["Hidden Gems"]
    # Onboarding is two steps now: Step 2 holds the four questions, including "show me more of".
    for scr in ("shelf", "taste", "more"):
        at.session_state["screen"] = scr
        at.run(); ok &= check(at, f"Onboarding ({scr})")
    # Step 1 search: tap a poster and it must become a like (a real click, checked by its result).
    at.session_state["screen"] = "shelf"
    at.session_state["_smoke_typed"] = "Past Lives"
    at.run(); ok &= check(at, "Step 1: search")
    tiles = [b for b in at.button if (b.key or "").startswith("search_result_")]
    if not tiles:
        print(f"{'Step 1: tap a poster':<28} ERROR: no search tiles to tap"); ok = False
    else:
        before = len(at.session_state["likes"])
        tiles[0].click().run()
        liked = len(at.session_state["likes"]) == before + 1
        print(f"{'Step 1: tap a poster':<28} {'OK' if liked and not at.exception else 'ERROR: the tap did not add a like'}")
        ok &= liked and not at.exception
    at.session_state["_smoke_typed"] = None
    at.session_state["likes"] = {"Spirited Away"}
    at.session_state["screen"] = "taste"
    at.run()
    svc = [b for b in at.button if (b.key or "") == "svc_btn_0"]
    if svc:
        svc[0].click().run(); ok &= check(at, "Step 2: a service tile")
    cards = [b for b in at.button if (b.key or "").startswith("priority_card_")]
    if cards:
        cards[0].click().run(); ok &= check(at, "Step 2: show me more card")
    at.session_state["screen"] = "profile"
    at.run(); ok &= check(at, "Profile (1 like)")
    at.session_state["screen"] = "showroom"
    at.session_state["onboarding_complete"] = True
    at.run(); ok &= check(at, "Showroom")
    for key in ("refresh_saved", "refresh_seen"):
        found = [b for b in at.button if b.key == key]
        if found:
            found[0].click().run(); ok &= check(at, f"Tab refresh ({key})")
    # Profile shows one section at a time: draw each one.
    for sec in ("Models", "Stats", "Privacy", "Taste"):
        at.session_state["pf_section_v"] = sec
        at.run(); ok &= check(at, f"Profile: {sec}")
    saves = [b for b in at.button if (b.key or "").startswith("save_")]
    if saves:
        saves[0].click().run(); ok &= check(at, "Save a movie")
    # Less mainstream likes route to RP3beta, which turns on the live interleaving test in Top Matches.
    at.session_state["likes"] = {"Past Lives", "The Rescue", "The Worst Person in the World"}
    at.session_state["saved"] = set()
    at.run(); ok &= check(at, "Showroom (live test on)")
    teams = at.session_state["interleave_teams"] if "interleave_teams" in at.session_state else {}
    print(f"{'Interleaving':<28} {'OK' if teams else 'ERROR: no interleaved Top Matches'}")
    ok &= bool(teams)
    saves = [b for b in at.button if (b.key or "").startswith("save_Top Matches")]
    if saves:
        saves[0].click().run(); ok &= check(at, "Save in live test")
    # The search's four states (SEARCH_RULE in app.py), plus a movie with a mood, each render every section.
    at.session_state["likes"] = {"Spirited Away"}
    for label, query in (("Search: mood + time", "funny, under 2 hours"), ("Search: mood", "mind-bending"),
                         ("Search: movie", "Inception"), ("Search: like a movie", "like Inception"),
                         ("Search: movie + mood", "funny, like Inception")):
        try:
            at.session_state["mood_active"] = query
            at.session_state["mood_input"] = query
            at.run(); ok &= check(at, label)
        except Exception as e:
            print(f"{label:<28} ERROR: {e}"); ok = False
    # Movie search fork: I've Seen It -> How was it? -> Loved it.
    try:
        at.session_state["mood_active"] = "Inception"
        at.session_state["mood_input"] = "Inception"
        at.run(); ok &= check(at, "Search: movie hero")
        fs = [b for b in at.button if (b.key or "") == "fork_seen"]
        if fs:
            fs[0].click().run(); ok &= check(at, "Search: I've Seen It")
            fl = [b for b in at.button if (b.key or "") == "fork_loved"]
            if fl:
                fl[0].click().run(); ok &= check(at, "Search: Loved it")
    except Exception as e:
        print(f"{'Search fork':<28} ERROR: {e}"); ok = False
    # Tap a token's words to edit it, then Skip a card and Undo it from the art's corner.
    edits = [b for b in at.button if (b.key or "").startswith("mood_edit_")]
    if edits:
        edits[0].click().run(); ok &= check(at, "Search: edit a token")
    at.session_state["mood_active"] = ""
    at.session_state["mood_input"] = ""
    at.run(); ok &= check(at, "Search: cleared")
    # Showroom search: type, tap a poster, and the search must become that exact movie.
    at.session_state["_smoke_typed"] = "Inception"
    at.run()
    tiles = [b for b in at.button if (b.key or "").startswith("live_hit_")]
    if not tiles:
        # Poster suggestions come from TMDB; without a key there is nothing to tap. Reported, not counted as OK.
        print(f"{'Search: tap a poster':<28} SKIP (no TMDB key, so no poster suggestions)")
    else:
        tiles[0].click().run()
        picked = bool(at.session_state["_exact_pick"]) if "_exact_pick" in at.session_state else False
        print(f"{'Search: tap a poster':<28} {'OK' if picked and not at.exception else 'ERROR: the tap did not open the movie'}")
        ok &= picked and not at.exception
    at.session_state["_smoke_typed"] = None
    at.session_state["mood_active"] = ""
    at.session_state["mood_input"] = ""
    at.run()
    # Services: tap a logo tile, then Done redraws the Showroom with your services first.
    for key in ("svc_btn_0", "svc_done"):
        found = [b for b in at.button if b.key == key]
        if found:
            found[0].click().run(); ok &= check(at, f"Services ({key})")
    # Each action is checked by what it changed, not only by "no error".
    seens = [b for b in at.button if (b.key or "").startswith("seen_Top Matches")]
    if seens:
        n = len(at.session_state["seen"])
        seens[0].click().run()
        good = len(at.session_state["seen"]) == n + 1 and not at.exception
        print(f"{'Seen a card':<28} {'OK' if good else 'ERROR: Seen did not record the movie'}")
        ok &= good
        ups = [b for b in at.button if (b.key or "").startswith("rate_up_")]
        if ups:
            ups[0].click().run(); ok &= check(at, "Liked it? (thumbs up)")
        else:
            # The prompt lives in the card's own rerun; this runner reruns the whole page. Not counted as OK.
            print(f"{'Liked it? prompt':<28} SKIP (only appears in a card-only rerun)")
    skips = [b for b in at.button if (b.key or "").startswith("skip_Top Matches")]
    if skips:
        n = len(at.session_state["dismissed"])
        skips[0].click().run()
        good = len(at.session_state["dismissed"]) == n + 1 and not at.exception
        print(f"{'Skip a card':<28} {'OK' if good else 'ERROR: Skip did not record the movie'}")
        ok &= good
        undos = [b for b in at.button if (b.key or "").startswith("card_undo_")]
        if undos:
            undos[0].click().run(); ok &= check(at, "Undo a skip")
        else:
            print(f"{'Undo a skip':<28} SKIP (only appears in a card-only rerun)")
    print("All screens OK" if ok else "Some screens failed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
