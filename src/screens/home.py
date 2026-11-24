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


def _services_row():
    """“Works with” and the services' own logos, quiet and grey: the cross-service promise, shown."""
    from src.ui.watch import STREAMING_SERVICES
    try:
        from src.watch_providers import service_logos
        logos = service_logos() or {}
    except Exception:
        logos = {}
    names = [n for n in STREAMING_SERVICES if not n.startswith("Free")]
    imgs = [(n, (logos.get(n) or [None])[0]) for n in names]
    imgs = [(n, u) for n, u in imgs if str(u or "").startswith("https://")]
    if len(imgs) >= 4:
        art = "".join(f'<img src="{html.escape(u, quote=True)}" alt="{html.escape(n)}" title="{html.escape(n)}">' for n, u in imgs)
    else:
        art = f'<span class="home-svcs-words">{html.escape(" · ".join(names[:6]))}</span>'
    return f'<div class="home-svcs"><span class="home-svcs-k">Works with</span>{art}</div>'


def render_home(ctx):
    """One screen: the promise, the button, the lift, the models, then what's popular right now."""
    ctx["logo"]()
    st.markdown('<div class="hero-title">Less scrolling.<br>More movies you love.</div>'
                '<div class="hero-subtitle">Like a few movies. Get tonight’s best pick on the services you already pay for.</div>',
                unsafe_allow_html=True)
    st.button("Start Personalizing →", type="primary", key="start_personalizing", on_click=ctx["go"], args=("shelf",))

    off = load_offline_results() or {}
    lift = (off.get("lifts_three_likes_vs_popularity") or {}).get("hit@1")
    tested = off.get("held_out_users")
    cfh = ((off.get("three_likes") or {}).get("cf") or {}).get("hit@1")
    poph = ((off.get("full") or {}).get("popularity") or {}).get("hit@1")
    ece = _ece()
    both = isinstance(cfh, (int, float)) and isinstance(poph, (int, float))

    parts = []
    if isinstance(lift, (int, float)):
        base = (f"{cfh * 1000:.0f} vs {poph * 1000:.0f} in 1,000 test viewers, against the most popular movie"
                if both else "against the most popular movie")
        parts.append('<div class="home-lift">'
                     f'<div class="home-lift-num">+{lift:.0f}%</div>'
                     '<div class="home-lift-body"><div class="home-lift-k">more first picks loved</div>'
                     f'<div class="home-lift-v">{html.escape(base)}</div></div></div>')
    parts.append('<div class="home-models"><span class="pf-dot on home-dot"></span>'
                 f'<span><strong>{MODELS_TOTAL} models</strong> · {MODELS_TOTAL - 1} pick, 1 sets the odds · '
                 'each beat a simpler baseline</span></div>')
    rows = []
    if isinstance(tested, int):
        rows.append(("Who", f"{tested:,} movie fans the models never saw, each starting from 3 likes."))
    if both:
        rows.append(("First pick", f"Rated 4+ stars by {cfh:.1%} of test viewers, vs {poph:.1%} for the most popular movie."))
    if isinstance(ece, float):
        rows.append(("Odds", f"Each “chance you’ll love it” is off by {max(ece * 100, 0.1):.1f} points on average "
                             "from what test viewers did."))
    rows.append(("Rule", "A model ships only if it beats the simpler option. What lost is listed in the README."))
    parts.append('<details class="home-tested"><summary>How We Tested</summary>'
                 + "".join(f'<div class="home-tested-row"><span>{html.escape(k)}</span>{html.escape(v)}</div>' for k, v in rows)
                 + '</details>')
    st.markdown("".join(parts), unsafe_allow_html=True)

    # What's popular right now, refreshed as new movies trend: shows the product without a word.
    hits = ctx["current_hits"](6, set())
    imgs = [m for m in hits if str(m.get("poster_url", "")).startswith("https://")]
    if len(imgs) >= 4:
        st.markdown('<div class="home-strip">' + "".join(
            f'<img src="{html.escape(str(m["poster_url"]), quote=True)}" alt="{html.escape(str(m.get("title", "")))}">'
            for m in imgs) + '</div>', unsafe_allow_html=True)
    st.markdown(_services_row(), unsafe_allow_html=True)
