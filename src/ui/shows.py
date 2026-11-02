"""The "Shows for You" row: same card, popup, and buttons as movies, for TV shows.

Shown only when data/tv_knn.npz exists, i.e. the TV model beat "most popular shows" on held-out
people (training/confirm_tv_blend.py). The app passes in its shared helpers (ctx), so this file holds
only the show-specific parts.
"""
import html

import streamlit as st

from src import tv


def _act(ctx, kind, title, show):
    ss = st.session_state
    ss.external_movies[title] = dict(show)
    if kind == "save":
        ss.saved.add(title)
    elif kind == "seen":
        ss.seen.add(title)
        ss.saved.discard(title)
    else:
        ss.dismissed.add(title)
    ctx["record_event"](ss, kind, title, {"row": "Shows for You", "media": "tv"})
    ctx["queue_profile_save"]()


def _card(ctx, slot, entry):
    name, score, rank, total, anchor = entry
    show = tv.show_details(name)
    if not show:
        return False
    title = show["title"]
    top = max(1, -(-100 * rank // max(total, 1)))
    # Real IMDb and RT scores (OMDb, via the show's IMDb id); TMDB's score only if IMDb has none.
    from src.live_ratings import get_live_ratings_batch
    from src.ui.cards import card_ratings, ratings_text
    from src.ui.mood_time import fmt
    live = (get_live_ratings_batch(((title, int(show.get("year") or 0), show.get("imdb_id") or ""),)) or {}).get(title) or {}
    parts = ratings_text(card_ratings(dict(show, tmdb_vote=show.get("tmdb_vote")), live))
    ratings = " · ".join(parts) or "Ratings unavailable"
    with st.container(key=f"showroom_controls_tv_{slot}"):
        pill, skip = st.columns([3.2, 1], gap="small")
        with pill:
            with st.popover(f"Top {top}%", use_container_width=True):
                rows = [("Rank", f"#{rank:,} of {total:,} shows scored for you")]
                if anchor:
                    rows.append(("Fans like you", f"People who loved {anchor} loved this show"))
                rows.append(("Mix", "Fans like you 80% · popularity 20%, both tested on held-out viewers"))
                if parts:
                    rows.append(("Ratings", ratings))
                st.markdown(
                    f'<div class="why-pop-head">Top {top}% for you</div><div class="why-pop-rows">'
                    + "".join(f'<div class="why-pop-row"><span class="why-pop-k">{html.escape(k)}</span>'
                              f'<span class="why-pop-v">{html.escape(v)}</span></div>' for k, v in rows)
                    + '</div>', unsafe_allow_html=True)
        with skip:
            st.button("Skip", key=f"skip_tv_{slot}_{title}", use_container_width=True,
                      on_click=_act, args=(ctx, "skip", title, show))
    art = ctx["movie_thumb"](dict(show, year=""), show.get("backdrop_url") or show.get("poster_url"),
                             landscape=True, return_html=True)
    meta = [str(x) for x in (show.get("year") or "", ", ".join(show.get("tags", [])[:2])) if x]
    if show.get("episode_runtime"):
        meta.append(f"{fmt(show['episode_runtime'])} episodes")
    watch = tv.show_watch(show["tmdb_id"])
    st.markdown(ctx["card_html"](f"tv-premise-{slot}", art, title, show, {},
                                 f'<div class="poster-caption-year card-year">{" · ".join(html.escape(m) for m in meta)}</div>'
                                 f'<div class="ratings">{ratings}</div>'
                                 f'<div class="watch-availability">{ctx["watch_line_html"](watch, title, st.session_state.get("streaming_services"))}</div>'),
                unsafe_allow_html=True)
    a, b = st.columns(2, gap="small")
    with a:
        st.button("Save", key=f"save_tv_{slot}_{title}", use_container_width=True, on_click=_act, args=(ctx, "save", title, show))
    with b:
        st.button("Seen", key=f"seen_tv_{slot}_{title}", use_container_width=True, on_click=_act, args=(ctx, "seen", title, show))
    return True


@st.fragment
def render_shows(ctx, count):
    """`count` cards (4 per line) of the viewer's best shows. A tap here reruns only this row."""
    ss = st.session_state
    acted = set(ss.saved) | set(ss.seen) | set(ss.dismissed) | set(ss.get("disliked") or ())
    picks = tv.viewer_shows(ctx["signals"](), exclude=acted)
    spec = ctx.get("spec") or {}
    spec = ctx.get("spec") or {}
    note = "Shows loved by fans of the movies you love"
    if spec.get("mood") or spec.get("label"):
        note = "Matching " + " · ".join(x for x in (f"“{spec['mood']}”" if spec.get("mood") else "", spec.get("label", "")) if x)
    st.markdown('<div class="showroom-row showroom-row-header"><div class="showroom-row-title">Shows for You</div>'
                f'<div class="row-model-note">{html.escape(note)}</div></div>', unsafe_allow_html=True)
    if not picks:
        st.caption("Like or save a few movies and your shows appear here.")
        return
    shown, i = 0, 0
    while shown < count and i < len(picks):
        cols = st.columns(4)
        for c in range(4):
            while shown < count and i < len(picks):
                entry = picks[i]
                i += 1
                info = tv.show_details(entry[0])
                if not info or not tv.matches_mood(info, spec.get("mood", "")):
                    continue
                from src.ui.mood_time import fits
                if not fits(info.get("episode_runtime"), spec, show=True):
                    continue
                with cols[c]:
                    if _card(ctx, shown, entry):
                        shown += 1
                        break
            if shown >= count:
                break
