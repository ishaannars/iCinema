
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
    :root {
        --sumi: #111315;
        --surface: #171A1F;
        --border: #2A2E35;
        --ivory: #F3F0EA;
        --muted: #A9ADB7;
        --ai: #5C6FA8;
        --ai-hover: #4B5D8B;
    }

    .stApp {
        background: var(--sumi);
        color: var(--ivory);
    }

    .block-container {
        max-width: 1240px;
        padding-top: 1.6rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3, h4 {
        letter-spacing: -0.02em;
        color: var(--ivory);
    }

    .icinema-logo {
        font-size: 1.5rem;
        font-weight: 850;
        letter-spacing: -0.04em;
        color: var(--ivory);
        margin-bottom: 0.75rem;
    }

    .hero-title {
        font-size: 3.7rem;
        line-height: 1.02;
        font-weight: 850;
        max-width: 900px;
        margin-top: 2.2rem;
        color: var(--ivory);
    }

    .hero-subtitle {
        color: var(--muted);
        font-size: 1.08rem;
        max-width: 780px;
        margin-top: 1rem;
        margin-bottom: 2rem;
        line-height: 1.6;
    }

    .step-card,
    .profile-card,
    .movie-card,
    .info-card {
        border: 1px solid var(--border);
        background: var(--surface);
        border-radius: 20px;
        padding: 1.2rem;
    }

    .step-num,
    .section-kicker {
        color: #8E94A0;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: .11em;
        font-weight: 750;
    }

    .step-num {
        margin-bottom: .35rem;
    }

    .section-kicker {
        margin-top: .55rem;
        margin-bottom: .45rem;
    }

    .muted,
    .caption {
        color: var(--muted);
    }

    .pill {
        display: inline-block;
        padding: .42rem .78rem;
        margin: .2rem .28rem .2rem 0;
        border: 1px solid var(--border);
        border-radius: 999px;
        color: var(--ivory);
        background: var(--surface);
        font-size: .9rem;
    }

    .match {
        font-weight: 800;
        font-size: 1.05rem;
        color: var(--ivory);
    }

    .ratings {
        color: var(--muted);
        font-size: .89rem;
    }

    div.stButton > button {
        border-radius: 999px;
        min-height: 42px;
        font-weight: 700;
    }

    div.stButton > button[kind="primary"] {
        background: var(--ai);
        border-color: var(--ai);
        color: white;
    }

    div.stButton > button[kind="primary"]:hover {
        background: var(--ai-hover);
        border-color: var(--ai-hover);
    }

    div[data-testid="stSlider"] [data-testid="stThumbValue"] {
        display: none;
    }

    div[data-testid="stSlider"] {
        padding-top: .15rem;
        padding-bottom: .25rem;
    }

    .movie-title {
        font-weight: 800;
        font-size: 1.05rem;
        margin-top: .65rem;
    }

    .profile-section {
        margin-top: 1.55rem;
        margin-bottom: 1.55rem;
    }

    .profile-values {
        font-size: 1.55rem;
        font-weight: 750;
        line-height: 1.3;
        margin-top: .3rem;
        margin-bottom: .4rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Session state ----------
defaults = {
    "screen": "welcome",
    "likes": set(),
    "favorites": set(),
    "review_priority": 50,
    "genres": [],
    "adventure": 45,
    "more_of": [],
    "saved": set(),
    "seen": set(),
    "dismissed": set(),
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = (
            v.copy() if isinstance(v, set)
            else list(v) if isinstance(v, list)
            else v
        )

def go(screen):
    st.session_state.screen = screen
    st.rerun()

def logo():
    st.markdown('<div class="icinema-logo">iCinema</div>', unsafe_allow_html=True)

def movie_thumb(movie):
    st.markdown(
        f"""
        <div style="
            height:260px;
            border-radius:18px;
            background:
                linear-gradient(180deg, rgba(255,255,255,.045), rgba(0,0,0,.32)),
                radial-gradient(circle at 30% 20%, #303640 0%, #1E232A 42%, #15181D 100%);
            border:1px solid #2A2E35;
            display:flex;
            align-items:flex-end;
            padding:1rem;
        ">
            <div>
                <div style="font-size:.72rem;color:#A9ADB7;text-transform:uppercase;letter-spacing:.1em;">
                    {movie["year"]} · {movie["genre"]}
                </div>
                <div style="font-size:1.2rem;font-weight:800;margin-top:.25rem;color:#F3F0EA;">
                    {movie["title"]}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

screen = st.session_state.screen

if screen == "welcome":
    logo()
    st.markdown('<div class="hero-title">Find something worth watching.</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">When you don’t know what to watch, iCinema learns your taste and curates films, series, and documentaries for you.</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)
    steps = [
        ("01", "Rate the Shelf", "Select titles you like and mark your favorites."),
        ("02", "Tune Your Taste", "Set your priorities, favorite genres, and openness to something new."),
        ("03", "Choose More Of", "Tell iCinema which kinds of titles you want surfaced more often."),
    ]

    for col, (n, title, body) in zip((c1, c2, c3), steps):
        with col:
            st.markdown(
                f'<div class="step-card"><div class="step-num">Step {n}</div><h3>{title}</h3><div class="muted">{body}</div></div>',
                unsafe_allow_html=True
            )

    st.write("")
    if st.button("Start Taste Setup →", type="primary"):
        go("shelf")

elif screen == "shelf":
    logo()
    st.markdown("### Step 1 of 3 — Rate the Shelf")
    st.caption("Select titles you like and mark your favorites.")

    cols = st.columns(4)
    for i, movie in enumerate(STARTER_MOVIES):
        title = movie["title"]
        with cols[i % 4]:
            movie_thumb(movie)

            b1, b2 = st.columns(2)

            liked = title in st.session_state.likes and title not in st.session_state.favorites
            favorited = title in st.session_state.favorites

            with b1:
                if st.button(
                    "Like",
                    key=f"like_{i}",
                    type="primary" if liked else "secondary",
                    use_container_width=True
                ):
                    if liked:
                        st.session_state.likes.discard(title)
                    else:
                        st.session_state.likes.add(title)
                        st.session_state.favorites.discard(title)
                    st.rerun()

            with b2:
                if st.button(
                    "Favorite",
                    key=f"fav_{i}",
                    type="primary" if favorited else "secondary",
                    use_container_width=True
                ):
                    if favorited:
                        st.session_state.favorites.discard(title)
                        st.session_state.likes.discard(title)
                    else:
                        st.session_state.favorites.add(title)
                        st.session_state.likes.add(title)
                    st.rerun()

    st.write("")
    if st.button("Continue →", type="primary"):
        go("taste")

elif screen == "taste":
    logo()
    st.markdown("### Step 2 of 3 — Tune Your Taste")

    st.markdown("#### Which matters more?")
    st.markdown(
        '<div style="display:flex;justify-content:space-between;color:#F3F0EA;font-weight:650;margin-bottom:.15rem;"><span>Great reviews</span><span>Pure entertainment</span></div>',
        unsafe_allow_html=True
    )
    st.session_state.review_priority = st.slider(
        "Review priority",
        min_value=0,
        max_value=100,
        value=st.session_state.review_priority,
        label_visibility="collapsed"
    )
    st.caption("Balance critical acclaim with entertainment value.")

    st.markdown("#### What do you like to watch?")
    st.caption("Select up to five genres.")

    genre_options = [
        "Action", "Adventure", "Animation", "Comedy", "Crime",
        "Documentary", "Drama", "Fantasy", "Horror", "Mystery",
        "Romance", "Sci-Fi", "Thriller"
    ]

    selected = set(st.session_state.genres)
    genre_cols = st.columns(4)

    for i, genre in enumerate(genre_options):
        with genre_cols[i % 4]:
            active = genre in selected
            if st.button(
                genre,
                key=f"genre_{i}",
                type="primary" if active else "secondary",
                use_container_width=True
            ):
                if active:
                    selected.discard(genre)
                elif len(selected) < 5:
                    selected.add(genre)
                st.session_state.genres = list(selected)
                st.rerun()

    st.markdown("#### How adventurous are you?")
    st.markdown(
        '<div style="display:flex;justify-content:space-between;color:#F3F0EA;font-weight:650;margin-bottom:.15rem;"><span>Familiar picks</span><span>Something new</span></div>',
        unsafe_allow_html=True
    )
    st.session_state.adventure = st.slider(
        "Adventure level",
        min_value=0,
        max_value=100,
        value=st.session_state.adventure,
        label_visibility="collapsed"
    )

    st.write("")
    if st.button("Continue →", type="primary"):
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
            active = option in selected
            if st.button(
                option,
                key=f"more_{i}",
                type="primary" if active else "secondary",
                use_container_width=True
            ):
                if active:
                    selected.discard(option)
                else:
                    selected.add(option)
                st.session_state.more_of = list(selected)
                st.rerun()

    st.write("")
    if st.button("Build My Cinema Profile →", type="primary"):
        go("profile")

elif screen == "profile":
    logo()

    profile = build_profile(
        st.session_state.likes,
        st.session_state.favorites,
        st.session_state.genres,
        st.session_state.review_priority,
        st.session_state.more_of,
    )

    st.markdown("## Your Cinema Profile")
    st.caption("Built from your initial taste calibration.")

    c1, c2 = st.columns([1.35, 0.85], gap="large")

    with c1:
        st.markdown('<div class="profile-section">', unsafe_allow_html=True)
        st.markdown('<div class="section-kicker">You lean toward</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="profile-values">{" • ".join(profile["lean"])}</div>',
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="profile-section">', unsafe_allow_html=True)
        st.markdown('<div class="section-kicker">Top Genres</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="profile-values">{" • ".join(profile["genres"])}</div>',
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="profile-section">', unsafe_allow_html=True)
        st.markdown('<div class="section-kicker">What stands out to you</div>', unsafe_allow_html=True)
        st.markdown(
            "".join(f'<span class="pill">{x}</span>' for x in profile["stands_out"]),
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="profile-section">', unsafe_allow_html=True)
        st.markdown('<div class="section-kicker">You’re drawn to</div>', unsafe_allow_html=True)
        st.markdown(
            "".join(f'<span class="pill">{x}</span>' for x in profile["drawn_to"]),
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"*{profile['summary']}*")

    with c2:
        st.markdown(
            """
            <div class="info-card">
                <div class="section-kicker">How iCinema adapts</div>
                <h3>Your profile is the starting point.</h3>
                <div class="muted">
                    Your showroom updates as you save, skip, and mark titles as seen.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    if st.button("Enter My Showroom →", type="primary"):
        go("showroom")

elif screen == "showroom":
    logo()

    profile = build_profile(
        st.session_state.likes,
        st.session_state.favorites,
        st.session_state.genres,
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
                    movie_thumb(movie)

                    match = score_movie(
                        movie,
                        profile,
                        st.session_state.adventure,
                        st.session_state.review_priority
                    )

                    st.markdown(
                        f'<div class="match">{match}% iCinema Match</div>',
                        unsafe_allow_html=True
                    )
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
        seen_titles = set()

        for movies in SHOWROOM_ROWS.values():
            for movie in movies:
                if movie["title"] in st.session_state.saved and movie["title"] not in seen_titles:
                    saved_movies.append(movie)
                    seen_titles.add(movie["title"])

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
            st.session_state[k] = (
                v.copy() if isinstance(v, set)
                else list(v) if isinstance(v, list)
                else v
            )
        st.rerun()
