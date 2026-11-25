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
    # The front page says what iCinema does first, and service pills are names (never outdated logo images).
    page = " ".join(str(m.value) for m in at.markdown)
    svcs = page[page.find('class="home-svcs"'):] if 'class="home-svcs"' in page else ""
    good = "Every service." in page and "Sharper Every Time" in page and svcs != "" and "<img" not in svcs[:1500]
    print(f"{'Home: value prop + pills':<28} {'OK' if good else 'ERROR: headline or service pills wrong'}")
    ok &= good
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
    for sec in ("How It Works", "Activity", "Privacy", "Your Likes"):
        at.session_state["pf_section_v"] = sec
        at.run(); ok &= check(at, f"Profile: {sec}")
        if sec == "How It Works":
            # Checked by what's on screen: the answer ("Does It Work?") comes before the model list.
            page = " ".join(str(m.value) for m in at.markdown)
            good = "Does It Work?" in page and page.find("Does It Work?") < page.find("See all 11 models")
            print(f"{'How It Works: answer first':<28} {'OK' if good else 'ERROR: model list shows before the answer'}")
            ok &= good
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
    # "Nothing too violent" must hold for every visible card and every backup a Skip could bring in.
    at.session_state["_audit_avoid"] = True
    at.session_state["mood_active"] = "not violent"
    at.session_state["mood_input"] = "not violent"
    at.run()
    bad = at.session_state["_avoid_audit"] if "_avoid_audit" in at.session_state else None
    if bad is None:
        print(f"{'Avoid: nothing violent':<28} ERROR: the audit did not run"); ok = False
    else:
        print(f"{'Avoid: nothing violent':<28} {'OK' if not bad else 'ERROR: still showing ' + ', '.join(bad[:5])}")
        ok &= not bad
    at.session_state["_audit_avoid"] = False
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
    # "Nothing too violent" must hold for what's shown AND for what slides in after a Skip (GoodFellas did).
    rough = {"Crime", "War", "Horror"}

    def _rough(m):
        g = set()
        for v in (m.get("genres"), m.get("genre")):
            if isinstance(v, str):
                g |= {x.strip() for x in v.replace("|", ",").split(",")}
            elif v:
                g |= {str(x) for x in v}
        g |= {{80: "Crime", 10752: "War", 27: "Horror"}.get(int(i), "") for i in (m.get("genre_ids") or [])}
        return g & rough

    def _shown_rough():
        slots = at.session_state["showroom_slots"] if "showroom_slots" in at.session_state else {}
        pays = at.session_state["showroom_payloads"] if "showroom_payloads" in at.session_state else {}
        return [t for k, t in slots.items() if t and "Shows" not in k and _rough((pays.get(t) or {}).get("movie") or {})]

    at.session_state["mood_active"] = "not violent"
    at.session_state["mood_input"] = "not violent"
    at.run()
    bad = _shown_rough()
    for _ in range(3):
        sk = [b for b in at.button if (b.key or "").startswith("skip_Top Matches")]
        if not sk:
            break
        sk[0].click().run()
        bad += _shown_rough()
    print(f"{'Avoid violence holds':<28} {'OK' if not bad and not at.exception else 'ERROR: shown ' + ', '.join(sorted(set(bad)))}")
    ok &= not bad and not at.exception
    at.session_state["mood_active"] = ""
    at.session_state["mood_input"] = ""
    at.run()
    # "Only show movies on my services": every movie shown must stream on the chosen service.
    from src.ui.watch import movie_on_services
    at.session_state["streaming_services"] = ["Netflix"]
    at.session_state["only_mine"] = True
    at.run()
    slots = at.session_state["showroom_slots"] if "showroom_slots" in at.session_state else {}
    cache = at.session_state["showroom_watch_cache"] if "showroom_watch_cache" in at.session_state else {}
    shown = [t for k, t in slots.items() if t and "Shows" not in k]
    off = [t for t in shown if not movie_on_services(cache.get(t), ["Netflix"])]
    if not shown:
        print(f"{'Only my services':<28} SKIP (no availability data here, so no movies to check)")
    else:
        print(f"{'Only my services':<28} {'OK' if not off and not at.exception else 'ERROR: off-service ' + ', '.join(off[:3])}")
        ok &= not off and not at.exception
    at.session_state["only_mine"] = False
    at.session_state["streaming_services"] = []
    at.run()
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
