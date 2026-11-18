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
    ctx["logo"]()
    # One screen, three beats: the problem (a sourced number), the promise, the proof (tested numbers).
    st.markdown('<div class="hero-kicker">Viewers spend 10.5 minutes per session deciding what to watch · Nielsen, 2023</div>'
                '<div class="hero-title">Less scrolling.<br>More movies you love.</div>'
                '<div class="hero-subtitle">Tell iCinema a few movies you like. It picks the one you’re most likely to love tonight, '
                'on the services you already pay for, and gets sharper with every save and skip.</div>', unsafe_allow_html=True)
    st.button("Start Personalizing →", type="primary", key="start_personalizing", on_click=ctx["go"], args=("shelf",))

    # Proof, read from the results files so it always matches the README.
    _off = load_offline_results() or {}
    _lift = (_off.get("lifts_three_likes_vs_popularity") or {}).get("hit@1")
    _tested = _off.get("held_out_users")
    _cfh = ((_off.get("three_likes") or {}).get("cf") or {}).get("hit@1")
    _poph = ((_off.get("full") or {}).get("popularity") or {}).get("hit@1")
    try:
        _lv = json.loads((ROOT / "data" / "love_chance.json").read_text())
        _ece = float(_lv["test_ece"]) if _lv.get("ships") else None
    except Exception:
        _ece = None
    _stats = []
    if isinstance(_lift, (int, float)):
        _stats.append((f"+{_lift:.0f}%", "more first picks you’d love", "than going with the most popular movie"))
    if isinstance(_ece, float):
        _stats.append((f"±{max(_ece * 100, 0.1):.1f} pts", "honest odds", "each “chance you’ll love it” vs what test viewers did"))
    if isinstance(_tested, int):
        _stats.append((f"{_tested:,}", "test viewers", "movie fans the models never saw, from 3 likes each"))
    if _stats:
        st.markdown('<div class="home-stats">' + "".join(
            f'<div class="home-stat"><div class="home-stat-num">{html.escape(n)}</div>'
            f'<div class="home-stat-k">{html.escape(k)}</div><div class="home-stat-v">{html.escape(v)}</div></div>'
            for n, k, v in _stats) + '</div>', unsafe_allow_html=True)

    # Show the product: what's big right now, the kind of movie iCinema finds for you.
    _hits = ctx["current_hits"](6, set())
    if len(_hits) >= 4:
        st.markdown(
            '<div class="home-strip">' + "".join(
                f'<img src="{html.escape(str(m["poster_url"]), quote=True)}" alt="{html.escape(str(m.get("title", "")))}">'
                for m in _hits if str(m.get("poster_url", "")).startswith("https://")) + '</div>',
            unsafe_allow_html=True)
    if isinstance(_cfh, (int, float)) and isinstance(_poph, (int, float)):
        # The baseline as plain counts next to the relative number (Bodemer, Meder & Gigerenzer, 2014).
        st.markdown(f'<div class="home-foot">In testing, its first pick was loved by {_cfh * 1000:.0f} in 1,000 viewers, '
                    f'vs {_poph * 1000:.0f} in 1,000 for the most popular movie. Every number links to a test in the README.</div>',
                    unsafe_allow_html=True)
