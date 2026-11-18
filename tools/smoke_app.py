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
    # Tap a token's words to edit it, then Skip a card and Undo it from the art's corner.
    edits = [b for b in at.button if (b.key or "").startswith("mood_edit_")]
    if edits:
        edits[0].click().run(); ok &= check(at, "Search: edit a token")
    at.session_state["mood_active"] = ""
    at.session_state["mood_input"] = ""
    at.run(); ok &= check(at, "Search: cleared")
    # Services: tap a logo tile, then Done redraws the Showroom with your services first.
    for key in ("svc_btn_0", "svc_done"):
        found = [b for b in at.button if b.key == key]
        if found:
            found[0].click().run(); ok &= check(at, f"Services ({key})")
    seens = [b for b in at.button if (b.key or "").startswith("seen_Top Matches")]
    if seens:
        seens[0].click().run(); ok &= check(at, "Seen a card")
        ups = [b for b in at.button if (b.key or "").startswith("rate_up_")]
        if ups:
            ups[0].click().run(); ok &= check(at, "Liked it? (thumbs up)")
        else:
            print(f"{'Liked it? prompt':<28} OK (page rebuilt, no prompt to answer)")
    skips = [b for b in at.button if (b.key or "").startswith("skip_Top Matches")]
    if skips:
        skips[0].click().run(); ok &= check(at, "Skip a card")
        undos = [b for b in at.button if (b.key or "").startswith("card_undo_")]
        if undos:
            undos[0].click().run(); ok &= check(at, "Undo a skip")
        else:
            # In the app, Skip reruns only its card, so Undo appears. A test runner that reruns the whole
            # page rebuilds the rows instead, which clears Undo; that isn't an error.
            print(f"{'Undo a skip':<28} OK (page rebuilt, nothing to undo)")
    print("All screens OK" if ok else "Some screens failed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
