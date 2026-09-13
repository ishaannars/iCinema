
import streamlit as st
from src.recommender import (
    STARTER_MOVIES,
    SHOWROOM_ROWS,
    build_profile,
    score_movie,
)

st.set_page_config(
    page_title="iCinema",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Styling ----------
st.markdown("""
<style>
    .stApp {
        background: #0b0b0d;
        color: #f6f6f6;
    }
    .block-container {
        max-width: 1240px;
        padding-top: 1.6rem;
        padding-bottom: 3rem;
    }
    h1, h2, h3, h4 {
        letter-spacing: -0.02em;
    }
    .icinema-logo {
        font-size: 1.45rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        margin-bottom: 0.5rem;
    }
    .hero-title {
        font-size: 3.7rem;
        line-height: 1.02;
        font-weight: 850;
        max-width: 860px;
        margin-top: 2.2rem;
    }
    .hero-subtitle {
        color: #b8b8bd;
        font-size: 1.12rem;
        max-width: 760px;
        margin-top: 1rem;
        margin-bottom: 2rem;
    }
    .step-card, .profile-card, .movie-card, .info-card {
        border: 1px solid #25252b;
        background: #121216;
        border-radius: 20px;
        padding: 1.2rem;
    }
    .step-num {
        color: #8c8c93;
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: .08em;
        margin-bottom: .35rem;
    }
    .muted {
        color: #9a9aa1;
    }
    .section-kicker {
        color: #8f8f96;
        text-transform: uppercase;
        letter-spacing: .12em;
        font-size: .76rem;
        font-weight: 700;
        margin-top: .35rem;
    }
    .pill {
        display: inline-block;
        padding: .38rem .72rem;
        margin: .16rem .18rem .16rem 0;
        border: 1px solid #34343a;
        border-radius: 999px;
        color: #ececf0;
        background: #17171b;
        font-size: .88rem;
    }
    .match {
        font-weight: 800;
        font-size: 1.05rem;
    }
    .ratings {
        color: #b5b5bb;
        font-size: .89rem;
    }
    div.stButton > button {
        border-radius: 999px;
        min-height: 42px;
        font-weight: 700;
    }
    .movie-title {
        font-weight: 800;
        font-size: 1.05rem;
        margin-top: .65rem;
    }
    .caption {
        color: #a2a2aa;
        font-size: .9rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Session state ----------
defaults = {
    "screen": "welcome",
    "likes": set(),
    "favorites": set(),
    "review_priority": 50,
    "moods": [],
    "adventure": 45,
    "more_of": [],
    "saved": set(),
    "seen": set(),
    "dismissed": set(),
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v.copy() if isinstance(v, set) else list(v) if isinstance(v, list) else v

def go(screen):
    st.session_state.screen = screen
    st.rerun()

def logo():
    st.markdown('<div class="icinema-logo">iCinema</div>', unsafe_allow_html=True)

def movie_thumb(movie, key_prefix="m"):
    # Placeholder visual block keeps repo self-contained; TMDB poster API can replace this.
    st.markdown(
        f"""
        <div style="
            height:260px;
            border-radius:18px;
            background:
                linear-gradient(180deg, rgba(255,255,255,.05), rgba(0,0,0,.38)),
                radial-gradient(circle at 30% 20%, #34343e 0%, #19191f 40%, #0f0f12 100%);
            border:1px solid #292930;
            display:flex;
            align-items:flex-end;
            padding:1rem;
        ">
            <div>
                <div style="font-size:.72rem;color:#aaaab2;text-transform:uppercase;letter-spacing:.1em;">
                    {movie["year"]} · {movie["genre"]}
                </div>
                <div style="font-size:1.2rem;font-weight:800;margin-top:.25rem;">
                    {movie["title"]}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------- Screens ----------
screen = st.session_state.screen

if screen == "welcome":
    logo()
    st.markdown('<div class="hero-title">Find something worth watching.</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">iCinema learns your taste through a fast three-step calibration, then builds a personalized showroom of movies, series, and documentaries.</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)
    steps = [
        ("01", "Rate the Shelf", "Tap films you already like. Tap again for favorites."),
        ("02", "Tune Your Taste", "Set what matters to you, your mood, and how adventurous you want recommendations to be."),
        ("03", "Choose More Of", "Tell iCinema which kinds of titles you want surfaced more often."),
    ]
    for col, (n, title, body) in zip((c1, c2, c3), steps):
        with col:
            st.markdown(
                f'<div class="step-card"><div class="step-num">Step {n}</div><h3>{title}</h3><div class="muted">{body}</div></div>',
                unsafe_allow_html=True
            )
    st.write("")
    if st.button("Start Taste Setup  →", type="primary", use_container_width=False):
        go("shelf")

elif screen == "shelf":
    logo()
    st.markdown("### Step 1 of 3 — Rate the Shelf")
    st.caption("Tap the films you like. Tap again for the ones you consider favorites. Leave everything else untouched.")

    cols = st.columns(4)
    for i, movie in enumerate(STARTER_MOVIES):
        with cols[i % 4]:
            movie_thumb(movie)
            state = "Favorite" if movie["title"] in st.session_state.favorites else "Liked" if movie["title"] in st.session_state.likes else "Neutral"
            label = "★ Favorite" if state == "Favorite" else "✓ Liked" if state == "Liked" else "Like"
            if st.button(label, key=f"shelf_{i}", use_container_width=True):
                title = movie["title"]
                if title in st.session_state.favorites:
                    st.session_state.favorites.remove(title)
                    st.session_state.likes.discard(title)
                elif title in st.session_state.likes:
                    st.session_state.favorites.add(title)
                else:
                    st.session_state.likes.add(title)
                st.rerun()
    st.write("")
    if st.button("Continue  →", type="primary"):
        go("taste")

elif screen == "taste":
    logo()
    st.markdown("### Step 2 of 3 — Tune Your Taste")

    st.markdown("#### Which matters more?")
    st.session_state.review_priority = st.slider(
        "Great reviews  ←→  Just entertaining",
        min_value=0, max_value=100, value=st.session_state.review_priority,
        label_visibility="visible"
    )
    st.caption("Move left for stronger critical reception; move right for pure entertainment value.")

    st.markdown("#### Pick your mood")
    mood_options = ["Dark", "Funny", "Emotional", "Intense", "Relaxing"]
    st.session_state.moods = st.multiselect(
        "Select any that fit",
        mood_options,
        default=st.session_state.moods,
        label_visibility="collapsed",
        max_selections=3
    )

    st.markdown("#### How adventurous are you?")
    st.session_state.adventure = st.slider(
        "Familiar picks  ←→  Surprise me",
        min_value=0, max_value=100, value=st.session_state.adventure,
        label_visibility="visible"
    )
    st.write("")
    if st.button("Continue  →", type="primary"):
        go("more")

elif screen == "more":
    logo()
    st.markdown("### Step 3 of 3 — Choose What You Want More Of")
    st.caption("Choose the categories you want iCinema to prioritize in your showroom.")

    options = [
        "Hidden Gems",
        "Critically Acclaimed",
        "Recent Releases",
        "International Films",
        "Classics",
        "Documentaries",
    ]

    cols = st.columns(3)
    selected = set(st.session_state.more_of)
    for i, option in enumerate(options):
        with cols[i % 3]:
            chosen = option in selected
            if st.toggle(option, value=chosen, key=f"more_{i}"):
                selected.add(option)
            else:
                selected.discard(option)
    st.session_state.more_of = list(selected)

    st.write("")
    if st.button("Build My Cinema Profile  →", type="primary"):
        go("profile")

elif screen == "profile":
    logo()
    profile = build_profile(
        st.session_state.likes,
        st.session_state.favorites,
        st.session_state.moods,
        st.session_state.review_priority,
        st.session_state.more_of,
    )

    st.markdown("## Your Cinema Profile")
    st.caption("Built from your initial taste calibration.")

    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown('<div class="profile-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-kicker">You lean toward</div>', unsafe_allow_html=True)
        st.markdown("### " + " • ".join(profile["lean"]))
        st.markdown('<div class="section-kicker">Top Genres</div>', unsafe_allow_html=True)
        st.markdown("### " + " • ".join(profile["genres"]))
        st.markdown('<div class="section-kicker">What stands out to you</div>', unsafe_allow_html=True)
        for x in profile["stands_out"]:
            st.markdown(f'<span class="pill">{x}</span>', unsafe_allow_html=True)
        st.markdown('<div class="section-kicker">You’re drawn to</div>', unsafe_allow_html=True)
        for x in profile["drawn_to"]:
            st.markdown(f'<span class="pill">{x}</span>', unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(f"*{profile['summary']}*")
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown(
            """
            <div class="info-card">
                <div class="section-kicker">How iCinema uses this</div>
                <h3>Your profile becomes the starting point.</h3>
                <div class="muted">
                    Every save, seen title, dismissal, and “more like this” action refines the ranking of future recommendations.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.write("")
    if st.button("Enter My Showroom  →", type="primary"):
        go("showroom")

elif screen == "showroom":
    logo()
    profile = build_profile(
        st.session_state.likes,
        st.session_state.favorites,
        st.session_state.moods,
        st.session_state.review_priority,
        st.session_state.more_of,
    )
    st.markdown("## Your Showroom")
    st.caption("Curated around your taste. Mark titles as seen or not for you and your recommendations adapt.")

    tabs = st.tabs(["Showroom", "Saved", "Profile"])

    with tabs[0]:
        for row_name, movies in SHOWROOM_ROWS.items():
            st.markdown(f"### {row_name}")
            available = [
                m for m in movies
                if m["title"] not in st.session_state.seen
                and m["title"] not in st.session_state.dismissed
            ]
            if not available:
                st.caption("You cleared this shelf.")
                continue

            cols = st.columns(min(4, len(available)))
            for i, movie in enumerate(available[:4]):
                with cols[i]:
                    movie_thumb(movie, key_prefix=f"{row_name}_{i}")
                    match = score_movie(movie, profile, st.session_state.adventure, st.session_state.review_priority)
                    st.markdown(f'<div class="match">{match}% iCinema Match</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="ratings">IMDb {movie["imdb"]} · RT {movie["rt"]}%</div>',
                        unsafe_allow_html=True
                    )
                    st.caption(movie["why"])
                    a, b, c = st.columns(3)
                    with a:
                        if st.button("Save", key=f"save_{row_name}_{i}", use_container_width=True):
                            st.session_state.saved.add(movie["title"])
                            st.rerun()
                    with b:
                        if st.button("Seen", key=f"seen_{row_name}_{i}", use_container_width=True):
                            st.session_state.seen.add(movie["title"])
                            st.session_state.saved.discard(movie["title"])
                            st.rerun()
                    with c:
                        if st.button("Skip", key=f"skip_{row_name}_{i}", use_container_width=True):
                            st.session_state.dismissed.add(movie["title"])
                            st.session_state.saved.discard(movie["title"])
                            st.rerun()
            st.write("")

    with tabs[1]:
        st.markdown("### Saved")
        saved_movies = []
        for movies in SHOWROOM_ROWS.values():
            for m in movies:
                if m["title"] in st.session_state.saved and m["title"] not in {x["title"] for x in saved_movies}:
                    saved_movies.append(m)
        if not saved_movies:
            st.caption("Nothing saved yet.")
        else:
            cols = st.columns(4)
            for i, movie in enumerate(saved_movies):
                with cols[i % 4]:
                    movie_thumb(movie)
                    st.markdown(f"**IMDb {movie['imdb']} · RT {movie['rt']}%**")

    with tabs[2]:
        st.markdown("### Cinema Profile")
        st.markdown("**You lean toward**")
        st.write(" • ".join(profile["lean"]))
        st.markdown("**Top Genres**")
        st.write(" • ".join(profile["genres"]))
        st.markdown("**What stands out to you**")
        st.write(" • ".join(profile["stands_out"]))
        st.markdown("**You’re drawn to**")
        st.write(" • ".join(profile["drawn_to"]))
        st.write("")
        st.markdown(f"*{profile['summary']}*")

    st.write("")
    if st.button("Reset Taste Profile"):
        for k, v in defaults.items():
            st.session_state[k] = v.copy() if isinstance(v, set) else list(v) if isinstance(v, list) else v
        st.rerun()
