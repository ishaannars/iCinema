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


def render_home(ctx):
    """One screen, read top to bottom by someone who has never heard of iCinema:
    what it does for you, how (three steps), the button, why to believe it, then the services it covers."""
    ctx["logo"]()
    st.markdown('<div class="hero-title">Know what to watch<br>tonight.</div>'
                '<div class="hero-subtitle">Like a few movies you love. iCinema picks the one you’re most likely to love tonight, '
                'shows which of your services has it, and tells you how likely you are to love it.</div>'
                '<div class="home-steps">'
                '<div class="home-step"><span class="home-step-n">1</span><span>Like a few movies</span></div>'
                '<div class="home-step"><span class="home-step-n">2</span><span>Get tonight’s pick</span></div>'
                '<div class="home-step"><span class="home-step-n">3</span><span>See where to stream it</span></div>'
                '</div>', unsafe_allow_html=True)
    st.button("Start Personalizing →", type="primary", key="start_personalizing", on_click=ctx["go"], args=("shelf",))
    st.markdown('<div class="home-free">Free · No account · Nothing personal stored</div>', unsafe_allow_html=True)

    off = load_offline_results() or {}
    lift = (off.get("lifts_three_likes_vs_popularity") or {}).get("hit@1")
    tested = off.get("held_out_users")
    cfh = ((off.get("three_likes") or {}).get("cf") or {}).get("hit@1")
    poph = ((off.get("full") or {}).get("popularity") or {}).get("hit@1")
    ece = _ece()
    both = isinstance(cfh, (int, float)) and isinstance(poph, (int, float))

    parts = []
    if isinstance(lift, (int, float)):
        who = f"{tested:,} movie fans" if isinstance(tested, int) else "movie fans"
        # One plain sentence a first-time visitor can read: who was tested, what happened, against what.
        detail = (f" ({cfh * 1000:.0f} in 1,000, vs {poph * 1000:.0f} in 1,000 for the most popular movie)" if both else "")
        parts.append('<div class="home-proof-line"><span class="pf-dot on home-dot"></span><span>'
                     f'<strong>Tested on {html.escape(who)}.</strong> They loved iCinema’s first pick {lift:.0f}% more often '
                     f'than the most popular movie{html.escape(detail)}.</span></div>')
    # Counted from the result files (src/claims.py), so this line can never claim more than the tests showed.
    from src.claims import models_passed
    _np = models_passed()
    _pass = ("Each passed a test against a simpler option before it shipped." if _np == MODELS_TOTAL
             else f"{_np} of {MODELS_TOTAL} have a passing test on file; the README lists every result.")
    rows = [("Models", f"{MODELS_TOTAL} models: {MODELS_TOTAL - 1} pick movies, 1 turns the score into your odds. " + _pass)]
    if isinstance(tested, int):
        rows.append(("Who", f"{tested:,} movie fans the models never saw, each starting from just 3 likes."))
    if both:
        rows.append(("First pick", f"Rated 4+ stars by {cfh:.1%} of test viewers, vs {poph:.1%} for the most popular movie."))
    if isinstance(ece, float):
        rows.append(("Odds", f"Each “chance you’ll love it” is off by {max(ece * 100, 0.1):.1f} points on average "
                             "from what test viewers did."))
    rows.append(("Rule", "A model ships only if it beats the simpler option. What lost is listed in the README."))
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
