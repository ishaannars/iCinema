"""Small screen pieces shared across pages: poster art, the profile likes grid, popovers.

Moved out of app.py unchanged (behavior-preserving restructure)."""
import html
import streamlit as st
from src.recommender import MORE_OF_OPTIONS, get_movie
from src.tmdb_catalog import get_poster_batch
from src.cf_model import preferred_title
from src.ui.cards import fit_head, genre_pair
from src.actions import _MORE_DESCRIPTIONS, _remove_like_from_profile, go, learning_model_for, save_movie, toggle_priority_choice, whats_next_another


def movie_thumb(movie, poster_url=None, compact=False, library_mode=None, landscape=False, toggle_id=None, return_html=False):
    title = html.escape(str(movie.get("title", "")))
    year = html.escape(str(movie.get("year", "")))
    poster_url = poster_url or movie.get("poster_url")
    if poster_url and not str(poster_url).lower().startswith(("https://", "http://")):
        poster_url = None   # only web image links reach the page
    logo_url = None
    if poster_url and "#logo=" in str(poster_url):
        poster_url, logo_url = str(poster_url).split("#logo=", 1)
    if poster_url:
        safe_url = html.escape(str(poster_url), quote=True)
        portrait = landscape and "/w780" not in str(poster_url)       # no 16:9 art: fit the poster inside the frame
        logo_html = (f'<img class="art-logo" src="{html.escape(logo_url, quote=True)}" alt="">' if logo_url else
                     (f'<div class="art-title-text">{title}</div>' if landscape and not str(poster_url).endswith("#titled") else ""))
        titled = landscape and str(poster_url).endswith("#titled")     # the title is painted into the art
        poster_html = (f'<div class="poster has-image{" landscape" if landscape else ""}{" fallback" if portrait else ""}{" titled" if titled else ""}">'
                       f'<img src="{safe_url}" alt="Poster for {title}">{logo_html}</div>')
    elif landscape:
        poster_html = f'<div class="poster landscape"><div class="art-title-text">{title}</div></div>'
    else:
        poster_html = '<div class="poster"><div class="poster-placeholder-mark">iCINEMA</div></div>'

    year_html = f'<div class="poster-caption-year">{year}</div>' if year else ''
    # Key art that already shows the title gets no text title (like streaming apps); others keep it.
    art_has_title = bool(logo_url) or landscape or (bool(poster_url) and str(poster_url).endswith("#titled"))
    title_html = "" if art_has_title else f'<div class="poster-caption-title" title="{title}">{title}</div>'
    
    if library_mode == "saved":
        caption_class = "poster-caption library-poster-caption saved-poster-caption"
    elif library_mode == "seen":
        caption_class = "poster-caption library-poster-caption seen-poster-caption"
    else:
        caption_class = 'poster-caption library-poster-caption' if compact else 'poster-caption'
    if return_html:      # the caller puts the art in the same block as the card's text (one block, even spacing)
        return poster_html
    if toggle_id:
        poster_html = f'<label class="art-toggle" for="{toggle_id}" aria-label="Show the story">{poster_html}</label>'
    st.markdown(
        poster_html
        + f'<div class="{caption_class}{" art-titled" if art_has_title else ""}">{title_html}{year_html}</div>',
        unsafe_allow_html=True
    )


def _render_profile_likes():
    """Your likes, editable from the Showroom: small posters with ×, and a way to add more."""
    ss = st.session_state
    liked = [t for t in (ss.get("selection_order") or []) if t in ss.likes] + sorted(set(ss.likes) - set(ss.get("selection_order") or []))
    st.markdown(f'<div class="profile-likes-head">Your Likes</div>'
                f'<div class="profile-likes-copy">{len(liked)} movie{"s" if len(liked) != 1 else ""}. Every pick starts from these.</div>',
                unsafe_allow_html=True)
    if liked:
        ms = [get_movie(t, ss.external_movies) or {"title": t} for t in liked]
        need = tuple((m["title"], int(m.get("year") or 0)) for m in ms if not m.get("poster_url"))
        pm = get_poster_batch(need) if need else {}
        with st.container(key="profile_likes"):
            cols = st.columns(12, gap="small")
            for i, t in enumerate(liked):
                u = str(ms[i].get("poster_url") or pm.get(t) or "")
                with cols[i % 12]:
                    with st.container(key=f"selection_card_p{i}"):
                        st.markdown('<div class="sel-poster">'
                                    + (f'<img src="{html.escape(u, quote=True)}" alt="">' if u.startswith("https://")
                                       else f'<div class="live-hit-blank">{html.escape(t[:24])}</div>')
                                    + f'</div><div class="sel-cap"><span class="sel-title">{html.escape(t)}</span></div>',
                                    unsafe_allow_html=True)
                        if len(liked) > 1:   # × is always visible; the last like stays so picks have a start
                            st.button("×", key=f"remove_selection_p{i}",
                                      on_click=_remove_like_from_profile, args=(t,))
            with cols[len(liked) % 12]:
                # The last tile adds more: the same search as Step 1, with your likes filled in.
                with st.container(key="profile_add_like"):
                    st.button("+ Add", key="add_like_tile", use_container_width=True, on_click=go, args=("shelf",))


def _render_more_choices():
    """The six "show me more of" cards (formerly Step 3). Each card is drawn in HTML, so the title and line
    always start at the same left edge, with an invisible button over the whole card as the tap target."""
    selected = set(st.session_state.more_of)
    with st.container(key="step3_grid"):
        cols = st.columns(3, gap="small")
        for i, option in enumerate(MORE_OF_OPTIONS):
            with cols[i % 3]:
                active = option in selected
                with st.container(key=f"pcard_{'on_' if active else ''}{i}"):
                    st.markdown(f'<div class="pcard-title">{html.escape(option)}</div>'
                                f'<div class="pcard-desc">{html.escape(_MORE_DESCRIPTIONS[option])}</div>', unsafe_allow_html=True)
                    st.button(option, key=f"priority_card_{'active_' if active else ''}{i}", use_container_width=True,
                              type="secondary", help=("Remove " if active else "Add ") + option,
                              on_click=toggle_priority_choice, args=(option,))


def _sat_out(used, payload):
    """The models that didn't touch this pick, each with the plain reason why."""
    ranker = payload.get("cf_source") == "ranker"
    reasons = [
        ("ranker", "Learned ranker", "This pick used item-kNN alone." if "item-kNN" in used else "No fan data for this movie yet."),
        ("item-kNN", "item-kNN", "No fan data for this movie yet."),
        ("RP3beta", "RP3beta", "Only runs inside the learned ranker." if not ranker else "No fan data for this movie yet."),
        ("EASE", "EASE", "Only runs inside the learned ranker." if not ranker else "No fan data for this movie yet."),
        ("markov", "Markov chain", "Your recent likes didn’t point to this movie."),
        ("content", "TF-IDF + SVD", "No genres or fan tags for this movie."),
        ("ridge", "New-release model", "It has fan data, so it isn’t treated as new."),
        ("mood", "Mood search", "No mood searched."),
        ("tv", "TV model", "This is a movie."),
        ("personal", "Your personal model", "Turns on after 50 saves and skips."),
    ]
    try:
        if learning_model_for(st.session_state.get("analytics_events") or []).ready:
            reasons[-1] = ("personal", "Your personal model", "Running, but it barely moved this pick.")
    except Exception:
        pass
    return [(name, why) for key, name, why in reasons if key not in used]


def _whats_next_popover(i, m, pick, wn_payloads, wn_identity):
    """The What's next pick for one Seen movie, in a popover."""
    nt, used_cf = pick
    npay = wn_payloads.get(nt) or {}
    nmovie = npay.get("movie") or {}
    nid = wn_identity.get(nt) or {}
    nposter = nid.get("poster_url") or nmovie.get("poster_url")
    ntitle = preferred_title(nmovie, nid.get("display_title") or nmovie.get("title") or nt)
    nyear = nid.get("year") or nmovie.get("year") or ""
    why = (f"Viewers who loved “{m['title']}” tend to love this too."
           if used_cf else f"Shares the genre and tone of “{m['title']}”.")
    with st.container(key=f"whatsnext_{i}"):
        with st.popover("What’s Next", use_container_width=True):
            img = (f'<img src="{html.escape(str(nposter), quote=True)}" alt="">'
                   if nposter else '<div class="whatsnext-noimg">iCINEMA</div>')
            st.markdown(
                f'<div class="whatsnext-kicker">Watch next after “{html.escape(m["title"])}”</div>'
                f'<div class="whatsnext-pick"><div class="whatsnext-poster">{img}</div>'
                f'<div class="whatsnext-info">'
                f'<div class="whatsnext-title">{html.escape(str(ntitle))}</div>'
                f'<div class="whatsnext-meta">{html.escape(" · ".join(str(x) for x in [nyear, genre_pair(nmovie) or nmovie.get("genre")] if x))}'
                f' · {fit_head(npay, npay.get("match"))}</div>'
                f'<div class="whatsnext-why">{html.escape(why)}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            # Compact pills, about the poster's width, aligned under the poster.
            a, b, _ = st.columns([1, 1.7, 3.3], gap="small")
            with a:
                st.button("Save", key=f"whatsnext_save_{i}_{nt}", use_container_width=True,
                          on_click=save_movie, args=(nt, nmovie))
            with b:
                st.button("Another Pick", key=f"whatsnext_more_{i}_{nt}", use_container_width=True,
                          on_click=whats_next_another, args=(m["title"],))
