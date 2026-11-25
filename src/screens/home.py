"""Home: the promise, the button, one tested number, the models behind it, then the art and the services.

Every number is read from the results files, so it always matches the README. The page leads with the
one result an everyday visitor cares about (first picks loved more often); the rest of the testing sits
behind "How We Tested" for anyone who wants it.
"""
import html
import json
from pathlib import Path

import streamlit as st

from src.model_names import MODELS_TOTAL
from src.tested_settings import load_offline_results

ROOT = Path(__file__).resolve().parents[2]


def _ece():
    try:
        lv = json.loads((ROOT / "data" / "love_chance.json").read_text())
        return float(lv["test_ece"]) if lv.get("ships") else None
    except Exception:
        return None


# Current names (2026): Max went back to HBO Max in July 2025, and Apple TV+ became Apple TV in October 2025.
SERVICE_NAMES = {"Max": "HBO Max", "Apple TV+": "Apple TV"}


def _services_row():
    """“Works with” and each service as one pill: its own logo and its current name."""
    from src.ui.watch import STREAMING_SERVICES
    try:
        from src.watch_providers import service_logos
        logos = service_logos() or {}
    except Exception:
        logos = {}
    pills = []
    for n in (x for x in STREAMING_SERVICES if not x.startswith("Free")):
        # Names only: logo images from data providers can lag a rebrand; a name is always current.
        pills.append(f'<span class="home-svc">{html.escape(SERVICE_NAMES.get(n, n))}</span>')
    pills.append('<span class="home-svc">Free with ads</span>')
    return f'<div class="home-svcs"><span class="home-svcs-k">Works with</span>{"".join(pills)}</div>'


def _learning_curve_passed():
    """True only if training/confirm_learning_curve.py found picks improve with more choices (CI above zero)."""
    try:
        return bool(json.loads((ROOT / "data" / "learning_curve_confirm.json").read_text()).get("claim_allowed"))
    except Exception:
        return False


def render_home(ctx):
    """One screen, read top to bottom by someone who has never heard of iCinema:
    what it does for you, how (three steps), the button, why to believe it, then the services it covers."""
    ctx["logo"]()
    off = load_offline_results() or {}
    lifts = off.get("lifts_three_likes_vs_popularity") or {}
    lift, rows_lift = lifts.get("hit@1"), lifts.get("recall@10")
    tested = off.get("held_out_users")
    cfh = ((off.get("three_likes") or {}).get("cf") or {}).get("hit@1")
    poph = ((off.get("full") or {}).get("popularity") or {}).get("hit@1")
    ece = _ece()
    both = isinstance(cfh, (int, float)) and isinstance(poph, (int, float))
    sharper = _learning_curve_passed()

    # The value proposition: one headline, one sentence, then three pillars, one per founder question
    # (painful: ranked for you; shared: all your services; recurring: sharper every time). Each pillar
    # carries its own proof, read from the result files, and says nothing the tests didn't show.
    st.markdown('<div class="hero-title">Every service.<br>Ranked for you.</div>'
                '<div class="hero-subtitle">iCinema brings together what’s on the services you pay for, ranks it around '
                'what you like, and gets sharper with every save and skip.</div>', unsafe_allow_html=True)
    st.button("Start Personalizing →", type="primary", key="start_personalizing", on_click=ctx["go"], args=("shelf",))
    st.markdown('<div class="home-free">Free · No account · Nothing personal stored</div>', unsafe_allow_html=True)

    rank_proof = (f"First pick loved {lift:.0f}% more often, and {rows_lift:.0f}% more loved movies in each row."
                  if isinstance(lift, (int, float)) and isinstance(rows_lift, (int, float)) else
                  f"First pick loved {lift:.0f}% more often than the most popular movie." if isinstance(lift, (int, float)) else "")
    pillars = [
        ("Ranked for You", "Your best match first, then a Showroom of strong backups, each with your odds and why.", rank_proof),
        ("All Your Services", "See where every pick is streaming, or switch to only what\u2019s on the services you pay for.",
         "Netflix, HBO Max, Hulu, Prime Video, Disney+, Apple TV, Peacock, Paramount+, and free apps."),
        ("Sharper Every Time", "Saves, skips, moods, and what you’ve seen teach it what you love.",
         "Tested: picks improved as viewers made more choices." if sharper else "Your own model joins after 50 choices."),
    ]
    st.markdown('<div class="home-pillars">' + "".join(
        f'<div class="home-pillar"><div class="home-pillar-t">{html.escape(t)}</div>'
        f'<div class="home-pillar-d">{html.escape(d)}</div>'
        + (f'<div class="home-pillar-p"><span class="pf-dot on home-dot"></span>{html.escape(pr)}</div>' if pr else "")
        + '</div>' for t, d, pr in pillars) + '</div>'
        '<div class="home-why">US viewers spend 12 minutes deciding what to watch (Gracenote, 2025).</div>',
        unsafe_allow_html=True)

    parts = []
    # Counted from the result files (src/claims.py), so this line can never claim more than the tests showed.
    from src.claims import models_passed
    _np = models_passed()
    _pass = ("Each passed a test against a simpler option before it shipped." if _np == MODELS_TOTAL
             else f"{_np} of {MODELS_TOTAL} have a passing test on file; the README lists every result.")
    rows = [("Models", f"{MODELS_TOTAL} models: {MODELS_TOTAL - 1} pick movies, 1 turns the score into your odds. " + _pass)]
    if isinstance(tested, int):
        rows.append(("Who", f"{tested:,} movie fans the models never saw, each starting from just 3 likes."))
    if both:
        rows.append(("First pick", f"{cfh * 1000:.0f} in 1,000 test fans loved iCinema’s first pick, vs {poph * 1000:.0f} "
                                   "in 1,000 for the most popular movie."))
    if isinstance(ece, float):
        rows.append(("Odds", f"Each “chance you’ll love it” is off by {max(ece * 100, 0.1):.1f} points on average "
                             "from what test viewers did."))
    rows.append(("Rule", "Every model is tested against a simpler option, and every result is in the README, including the content model, which stays at 20% so your answers count."))
    parts.append('<details class="home-tested"><summary><span class="pf-dot on home-dot"></span>How We Tested</summary>'
                 + "".join(f'<div class="home-tested-row"><span>{html.escape(k)}</span>{html.escape(v)}</div>' for k, v in rows)
                 + '</details>')
    st.markdown("".join(parts), unsafe_allow_html=True)

    # What's popular right now, refreshed as new movies trend: shows the product without a word.
    hits = ctx["current_hits"](6, set())
    imgs = [m for m in hits if str(m.get("poster_url", "")).startswith("https://")]
    if len(imgs) >= 4:
        st.markdown('<div class="home-strip-k">Popular right now</div><div class="home-strip">' + "".join(
            f'<img src="{html.escape(str(m["poster_url"]), quote=True)}" alt="{html.escape(str(m.get("title", "")))}">'
            for m in imgs) + '</div>', unsafe_allow_html=True)
    st.markdown(_services_row(), unsafe_allow_html=True)
