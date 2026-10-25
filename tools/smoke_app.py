"""Click through every screen of the app headlessly and report any error.

    python tools/smoke_app.py

Uses Streamlit's AppTest. Runs the home page, Profile, and Showroom (all four tabs), then
presses Refresh on Saved and Seen and the first Save button. Prints OK or the errors it hit.
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
    print("All screens OK" if ok else "Some screens failed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
