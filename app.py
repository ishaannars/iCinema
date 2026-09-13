
import streamlit as st
from src.recommender import (
    STARTER_MOVIES, GENRES, MORE_OF_OPTIONS, searchable_titles, get_movie,
    build_profile, score_movie, recommend
)

st.set_page_config(page_title="iCinema", page_icon="🎬", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
:root{
--sumi:#111315;--surface:#171A1F;--border:#2A2E35;--ivory:#F3F0EA;
--muted:#A9ADB7;--muted2:#858B96;--ai:#5C6FA8;--ai-hover:#4B5D8B;
}
.stApp{background:var(--sumi);color:var(--ivory)}
html,body,[class*="css"]{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.block-container{max-width:1240px;padding-top:2.1rem;padding-bottom:3rem}
h1,h2,h3,h4{letter-spacing:-.025em;color:var(--ivory);font-weight:760}
.icinema-logo{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:1.7rem;font-weight:800;letter-spacing:-.055em;color:var(--ivory);margin-bottom:.8rem}
.hero-title{font-size:3.8rem;line-height:1.03;font-weight:820;max-width:900px;margin-top:1.9rem;color:var(--ivory);letter-spacing:-.045em}
.hero-subtitle{color:var(--muted);font-size:1.08rem;max-width:790px;margin-top:.95rem;margin-bottom:1.7rem;line-height:1.55}
.step-card{border:1px solid var(--border);background:var(--surface);border-radius:20px;padding:1.05rem 1.1rem;height:100%}
.step-num,.section-kicker{color:var(--muted2);font-size:.76rem;text-transform:uppercase;letter-spacing:.10em;font-weight:760}
.step-card h3{font-size:1.08rem;margin:.35rem 0 .25rem}
.step-card .muted{font-size:.9rem;line-height:1.45}
.adapt-note{border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:.8rem 0;margin:.9rem 0 1.25rem;color:var(--muted);font-size:.92rem}
.adapt-note strong{color:var(--ivory)}
.movie-card{margin-bottom:.55rem}
.poster{height:255px;border-radius:18px;background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(0,0,0,.32)),radial-gradient(circle at 30% 20%,#303640 0%,#1E232A 42%,#15181D 100%);border:1px solid var(--border);display:flex;align-items:flex-end;padding:1rem}
.poster-meta{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em}
.poster-title{font-size:1.18rem;font-weight:800;margin-top:.25rem;color:var(--ivory)}
.match{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-weight:650;
    font-size:.98rem;
    color:var(--ivory);
    margin-top:.6rem;
    letter-spacing:-.01em
}
.ratings{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    color:var(--muted);
    font-size:.87rem;
    margin-top:.1rem
}
.movie-description{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    color:var(--muted);
    font-size:.92rem;
    line-height:1.5;
    font-weight:400
}
div.stButton>button{border-radius:999px;min-height:40px;font-weight:700}
div.stButton>button[kind="primary"]{background:var(--ai);border-color:var(--ai);color:white}
div.stButton>button[kind="primary"]:hover{background:var(--ai-hover);border-color:var(--ai-hover)}
div[data-testid="stSlider"] [data-testid="stThumbValue"],div[data-testid="stSlider"] div[role="tooltip"],div[data-baseweb="slider"] div[role="tooltip"]{display:none!important;visibility:hidden!important}
.profile-wrap{max-width:970px}
.profile-intro{color:var(--muted);margin-top:-.4rem;margin-bottom:1.2rem}
.profile-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem 1.25rem}
.profile-block{border-top:1px solid var(--border);padding-top:.75rem}
.profile-label{color:var(--muted2);font-size:.74rem;text-transform:uppercase;letter-spacing:.1em;font-weight:760;margin-bottom:.32rem}
.profile-value{
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:1rem;
    line-height:1.62;
    font-weight:500;
    letter-spacing:-.01em
}
.profile-list{
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:1rem;
    line-height:1.7;
    font-weight:500
}
.profile-summary{
    margin-top:1.1rem;
    border-top:1px solid var(--border);
    padding-top:1rem;
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:1.02rem;
    line-height:1.55;
    font-weight:500
}
.profile-summary strong{font-weight:650}
@media (max-width:800px){.profile-grid{grid-template-columns:1fr}.hero-title{font-size:2.8rem}}
</style>
""", unsafe_allow_html=True)

defaults={
    "screen":"welcome","likes":set(),"favorites":set(),"review_priority":50,
    "genres":[],"adventure":45,"more_of":[],"saved":set(),"seen":set(),"dismissed":set(),
    "custom_like":None
}
for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k]=v.copy() if isinstance(v,set) else (list(v) if isinstance(v,list) else v)

def go(screen):
    st.session_state.screen=screen
    st.rerun()

def logo():
    st.markdown('<div class="icinema-logo">iCinema</div>',unsafe_allow_html=True)

def movie_thumb(movie):
    st.markdown(
        f'<div class="poster"><div><div class="poster-meta">{movie["year"]} · {movie["genre"]}</div>'
        f'<div class="poster-title">{movie["title"]}</div></div></div>',
        unsafe_allow_html=True
    )

def current_profile():
    return build_profile(
        st.session_state.likes, st.session_state.favorites, st.session_state.genres,
        st.session_state.review_priority, st.session_state.more_of,
        st.session_state.saved, st.session_state.dismissed, st.session_state.adventure
    )

screen=st.session_state.screen

if screen=="welcome":
    logo()
    st.markdown('<div class="hero-title">Always find your next great watch.</div>',unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">iCinema learns what you like and narrows the search to movies, series, and documentaries that fit your preferences</div>',unsafe_allow_html=True)

    c1,c2,c3=st.columns(3)
    steps=[
        ("01","Rate the Shelf","Choose titles you already enjoy, or search for one you like"),
        ("02","Tailor Your Preferences","Tell iCinema what matters most when choosing what to watch"),
        ("03","Shape Your Showroom","Choose what iCinema should surface more often"),
    ]
    for col,(n,title,body) in zip((c1,c2,c3),steps):
        with col:
            st.markdown(f'<div class="step-card"><div class="step-num">Step {n}</div><h3>{title}</h3><div class="muted">{body}</div></div>',unsafe_allow_html=True)

    st.markdown('<div class="adapt-note"><strong>iCinema responds to your choices</strong><br><span>Every save, skip, and seen title continuously influences what appears next</span></div>',unsafe_allow_html=True)
    if st.button("Start Personalizing →",type="primary"):go("shelf")

elif screen=="shelf":
    logo()
    st.markdown("### Step 1 of 3 — Rate the Shelf")
    st.caption("Choose a few titles you already like. If none fit, search for one you know you enjoy.")

    cols=st.columns(4)
    for i,movie in enumerate(STARTER_MOVIES):
        title=movie["title"]
        with cols[i%4]:
            movie_thumb(movie)
            b1,b2=st.columns(2)
            liked=title in st.session_state.likes and title not in st.session_state.favorites
            fav=title in st.session_state.favorites
            with b1:
                if st.button("Like",key=f"like_{i}",type="primary" if liked else "secondary",use_container_width=True):
                    if liked:st.session_state.likes.discard(title)
                    else:st.session_state.likes.add(title);st.session_state.favorites.discard(title)
                    st.rerun()
            with b2:
                if st.button("Favorite",key=f"fav_{i}",type="primary" if fav else "secondary",use_container_width=True):
                    if fav:st.session_state.favorites.discard(title);st.session_state.likes.discard(title)
                    else:st.session_state.favorites.add(title);st.session_state.likes.add(title)
                    st.rerun()

    st.markdown("#### Don’t see one you like?")
    st.caption("Search for a movie you already enjoy")

    search_query = st.text_input(
        "Search movies",
        placeholder="Search by title",
        label_visibility="collapsed",
        key="movie_search_query"
    )

    titles = searchable_titles()
    matches = []
    if search_query.strip():
        q = search_query.strip().lower()
        matches = [title for title in titles if q in title.lower()][:8]

    choice = None
    if search_query.strip():
        if matches:
            choice = st.radio(
                "Search results",
                matches,
                label_visibility="collapsed",
                key="movie_search_result"
            )
        else:
            st.caption("No matches found in the current iCinema catalog")

    a,b=st.columns([1,1])
    with a:
        if st.button("Add as Like",use_container_width=True,disabled=not choice):
            st.session_state.likes.add(choice)
            st.session_state.favorites.discard(choice)
            st.rerun()
    with b:
        if st.button("Add as Favorite",use_container_width=True,disabled=not choice):
            st.session_state.likes.add(choice)
            st.session_state.favorites.add(choice)
            st.rerun()

    chosen_count=len(st.session_state.likes|st.session_state.favorites)
    st.caption(f"{chosen_count} title{'s' if chosen_count!=1 else ''} selected.")
    if st.button("Continue →",type="primary",disabled=chosen_count==0):go("taste")

elif screen=="taste":
    logo()
    st.markdown("### Step 2 of 3 — Tailor Your Preferences")
    st.caption("Tell iCinema what matters most when deciding what to watch.")

    st.markdown("#### Which matters more?")
    st.markdown('<div style="display:flex;justify-content:space-between;color:#F3F0EA;font-weight:650"><span>Great reviews</span><span>Pure entertainment</span></div>',unsafe_allow_html=True)
    st.session_state.review_priority=st.slider("Review priority",0,100,st.session_state.review_priority,label_visibility="collapsed")
    st.caption("Choose how much critical reception should influence your recommendations.")

    st.markdown("#### What do you like to watch?")
    st.caption("Select up to five genres.")
    selected=set(st.session_state.genres)
    genre_cols=st.columns(5)
    for i,genre in enumerate(GENRES):
        with genre_cols[i%5]:
            active=genre in selected
            if st.button(genre,key=f"genre_{i}",type="primary" if active else "secondary",use_container_width=True):
                if active:selected.discard(genre)
                elif len(selected)<5:selected.add(genre)
                st.session_state.genres=list(selected);st.rerun()

    st.markdown("#### How open are you to something different?")
    st.markdown('<div style="display:flex;justify-content:space-between;color:#F3F0EA;font-weight:650"><span>Keep it familiar</span><span>Surprise me</span></div>',unsafe_allow_html=True)
    st.session_state.adventure=st.slider("Adventure level",0,100,st.session_state.adventure,label_visibility="collapsed")

    if st.button("Continue →",type="primary"):go("more")

elif screen=="more":
    logo()
    st.markdown("### Step 3 of 3 — Shape Your Showroom")
    st.caption("Choose what you want iCinema to prioritize. You can select more than one.")

    st.session_state.more_of=st.multiselect(
        "Recommendation priorities",
        MORE_OF_OPTIONS,
        default=st.session_state.more_of,
        placeholder="Choose what you want more of",
        label_visibility="collapsed"
    )

    if st.button("Build My Cinema Profile →",type="primary"):go("profile")

elif screen=="profile":
    logo()
    p=current_profile()
    st.markdown('<div class="profile-wrap">',unsafe_allow_html=True)
    st.markdown('<h2 style="font-family:-apple-system,BlinkMacSystemFont,&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif;font-weight:760;letter-spacing:-.03em;margin-bottom:.4rem">Your Cinema Profile</h2>',unsafe_allow_html=True)
    st.markdown('<div class="profile-intro">Built from your tailored preferences.</div>',unsafe_allow_html=True)

    st.markdown('<div class="profile-grid">',unsafe_allow_html=True)

    blocks=[
        ("You tend to enjoy"," • ".join(p["traits"])),
        ("Top genres"," • ".join(p["genres"])),
        ("What matters most","<br>".join(p["matters"])),
        ("What iCinema should prioritize"," • ".join(p["priorities"])),
        ("Viewing patterns","<br>".join(p["patterns"])),
        ("Recommendation balance","<br>".join(p["balance"])),
    ]

    for label,value in blocks:
        st.markdown(f'<div class="profile-block"><div class="profile-label">{label}</div><div class="profile-value">{value}</div></div>',unsafe_allow_html=True)

    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="profile-summary"><strong>{p["summary"]}</strong></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

    if st.button("Enter My Showroom →",type="primary"):go("showroom")

elif screen=="showroom":
    logo()
    p=current_profile()
    st.markdown("## Your Showroom")
    st.caption("Recommendations tailored to your preferences and updated as you save, skip, and mark titles as seen.")

    tabs=st.tabs(["Showroom",f"Saved ({len(st.session_state.saved)})",f"Seen ({len(st.session_state.seen)})","Profile"])

    excluded=st.session_state.saved|st.session_state.seen|st.session_state.dismissed
    ranked=recommend(p,st.session_state.adventure,st.session_state.review_priority,excluded,32)

    row_specs=[
        ("Top Matches for You",lambda m,s: True),
        ("Critically Acclaimed",lambda m,s: "Critically Acclaimed" in m.get("tags",[]) or m.get("rt",0)>=90),
        ("Hidden Gems",lambda m,s: "Hidden Gem" in m.get("tags",[])),
        ("Something Different",lambda m,s: m["genre"] not in p["genres"]),
    ]

    with tabs[0]:
        used=set()
        for row_name,predicate in row_specs:
            choices=[]
            for score,movie in ranked:
                if movie["title"] in used:continue
                if predicate(movie,score):
                    choices.append((score,movie))
                if len(choices)==4:break
            used.update(m["title"] for _,m in choices)
            st.markdown(f"### {row_name}")
            if not choices:
                st.caption("No additional matches in this demo catalog.")
                continue
            cols=st.columns(len(choices))
            for i,(match,movie) in enumerate(choices):
                with cols[i]:
                    movie_thumb(movie)
                    st.markdown(f'<div class="match">{match}% iCinema Match</div>',unsafe_allow_html=True)
                    st.markdown(f'<div class="ratings">IMDb {movie["imdb"]} · RT {movie["rt"]}%</div>',unsafe_allow_html=True)
                    st.markdown(f'<div class="movie-description">{movie["why"]}</div>',unsafe_allow_html=True)
                    a,b,c=st.columns(3)
                    with a:
                        if st.button("Save",key=f"save_{row_name}_{movie['title']}",use_container_width=True):
                            st.session_state.saved.add(movie["title"]);st.session_state.seen.discard(movie["title"]);st.session_state.dismissed.discard(movie["title"]);st.rerun()
                    with b:
                        if st.button("Seen",key=f"seen_{row_name}_{movie['title']}",use_container_width=True):
                            st.session_state.seen.add(movie["title"]);st.session_state.saved.discard(movie["title"]);st.session_state.dismissed.discard(movie["title"]);st.rerun()
                    with c:
                        if st.button("Skip",key=f"skip_{row_name}_{movie['title']}",use_container_width=True):
                            st.session_state.dismissed.add(movie["title"]);st.session_state.saved.discard(movie["title"]);st.rerun()

    with tabs[1]:
        st.markdown("### Saved")
        movies=[get_movie(t) for t in st.session_state.saved if get_movie(t)]
        if not movies:st.caption("Nothing saved yet.")
        else:
            cols=st.columns(min(4,len(movies)))
            for i,m in enumerate(movies):
                with cols[i%len(cols)]:
                    movie_thumb(m)
                    if st.button("Mark Seen",key=f"savedseen_{m['title']}",use_container_width=True):
                        st.session_state.seen.add(m["title"]);st.session_state.saved.discard(m["title"]);st.rerun()

    with tabs[2]:
        st.markdown("### Seen")
        movies=[get_movie(t) for t in st.session_state.seen if get_movie(t)]
        if not movies:st.caption("Nothing marked as seen yet.")
        else:
            cols=st.columns(min(4,len(movies)))
            for i,m in enumerate(movies):
                with cols[i%len(cols)]:movie_thumb(m)

    with tabs[3]:
        st.markdown("### Cinema Profile")
        st.markdown(f"**You tend to enjoy**  \n{' • '.join(p['traits'])}")
        st.markdown(f"**Top genres**  \n{' • '.join(p['genres'])}")
        st.markdown(f"**What matters most**  \n{' • '.join(p['matters'])}")
        st.markdown(f"**What iCinema should prioritize**  \n{' • '.join(p['priorities'])}")
        st.markdown(f"**Viewing patterns**  \n{' • '.join(p['patterns'])}")
        st.markdown(f"**Recommendation balance**  \n{' • '.join(p['balance'])}")
        st.markdown(f"*{p['summary']}*")

    if st.button("Reset Profile"):
        for k,v in defaults.items():
            st.session_state[k]=v.copy() if isinstance(v,set) else (list(v) if isinstance(v,list) else v)
        st.rerun()
