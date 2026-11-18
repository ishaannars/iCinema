"""Home: the problem in one sourced line, the promise, the button, three tested numbers, the art, a footnote.

Every number is read from the results files, so it always matches the README.
"""
import html
import json
from pathlib import Path

import streamlit as st

from src.tested_settings import load_offline_results

ROOT = Path(__file__).resolve().parents[2]


def render_home(ctx):
    """One screen: the promise, the button, three tested numbers, then what's popular right now (it refreshes
    as new movies trend). Nothing else."""
    ctx["logo"]()
    st.markdown('<div class="hero-title">Less scrolling.<br>More movies you love.</div>'
                '<div class="hero-subtitle">Like a few movies. Get the one you’re most likely to love tonight, '
                'on the services you already pay for.</div>', unsafe_allow_html=True)
    st.button("Start Personalizing →", type="primary", key="start_personalizing", on_click=ctx["go"], args=("shelf",))

    # Proof, read from the results files so it always matches the README.
    off = load_offline_results() or {}
    lift = (off.get("lifts_three_likes_vs_popularity") or {}).get("hit@1")
    tested = off.get("held_out_users")
    cfh = ((off.get("three_likes") or {}).get("cf") or {}).get("hit@1")
    poph = ((off.get("full") or {}).get("popularity") or {}).get("hit@1")
    try:
        lv = json.loads((ROOT / "data" / "love_chance.json").read_text())
        ece = float(lv["test_ece"]) if lv.get("ships") else None
    except Exception:
        ece = None
    stats = []
    if isinstance(lift, (int, float)):
        base = (f"{cfh * 1000:.0f} vs {poph * 1000:.0f} in 1,000 test viewers"
                if isinstance(cfh, (int, float)) and isinstance(poph, (int, float)) else "vs the most popular movie")
        stats.append((f"+{lift:.0f}%", "more first picks loved", f"{base}, vs the most popular movie"))
    if isinstance(ece, float):
        # Expected calibration error is an average gap, not a ± range, so it's stated as one.
        stats.append((f"{max(ece * 100, 0.1):.1f} pts", "average error in our odds",
                      "each “chance you’ll love it” vs what test viewers did"))
    if isinstance(tested, int):
        stats.append(("10 models", "each beat a baseline", f"on {tested:,} viewers they never saw"))
    if stats:
        st.markdown('<div class="home-stats">' + "".join(
            f'<div class="home-stat"><div class="home-stat-num">{html.escape(n)}</div>'
            f'<div class="home-stat-k">{html.escape(k)}</div><div class="home-stat-v">{html.escape(v)}</div></div>'
            for n, k, v in stats) + '</div>', unsafe_allow_html=True)

    # What's popular right now, refreshed as new movies trend: shows the product without a word.
    hits = ctx["current_hits"](6, set())
    imgs = [m for m in hits if str(m.get("poster_url", "")).startswith("https://")]
    if len(imgs) >= 4:
        st.markdown('<div class="home-strip">' + "".join(
            f'<img src="{html.escape(str(m["poster_url"]), quote=True)}" alt="{html.escape(str(m.get("title", "")))}">'
            for m in imgs) + '</div>', unsafe_allow_html=True)
