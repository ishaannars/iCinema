
import streamlit as st
from src.recommender import (
    STARTER_MOVIES, GENRES, MORE_OF_OPTIONS,
    build_profile, recommend_for_row, get_movie
)
from src.live_metadata import display_metadata

st.set_page_config(page_title="iCinema", page_icon="🎬", layout="wide", initial_sidebar_state="collapsed")

st.markdown('''
<style>
:root{
--sumi:#151719;--surface:#1D2024;--surface2:#22262B;--border:#32373E;
--ivory:#F5F1E8;--muted:#AEB3BB;--muted2:#858C96;--ai:#6D7FAC;
--aiso:#8996B9;--aideep:#596A95;
}
html,body,[class*="css"]{font-family:Inter,-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",sans-serif}
.stApp{background:var(--sumi);color:var(--ivory)}
.block-container{max-width:1180px;padding-top:1.4rem;padding-bottom:3rem}
h1,h2,h3,h4{color:var(--ivory);letter-spacing:-.025em}
.icinema-logo{display:inline-flex;align-items:center;gap:.55rem;font-size:1.75rem;font-weight:850;letter-spacing:-.045em;color:var(--ivory);margin-bottom:.55rem}
.icinema-mark{width:10px;height:10px;border-radius:999px;background:var(--aiso);box-shadow:0 0 0 5px rgba(137,150,185,.12)}
.hero-title{font-size:clamp(3rem,6vw,5rem);line-height:1;font-weight:850;max-width:920px;margin-top:1.65rem;color:var(--ivory)}
.hero-subtitle{color:var(--muted);font-size:1.08rem;max-width:760px;margin-top:1rem;margin-bottom:1.3rem;line-height:1.55}
.step-bubbles{display:flex;flex-wrap:wrap;gap:.65rem;margin:.55rem 0 1.15rem}
.step-bubble{display:inline-flex;align-items:center;gap:.5rem;border:1px solid var(--border);background:var(--surface);border-radius:999px;padding:.58rem .88rem;color:var(--ivory);font-size:.9rem}
.step-index{color:var(--aiso);font-size:.74rem;letter-spacing:.08em;font-weight:800}
.adapt-banner{margin:.7rem 0 1.5rem;border-left:3px solid var(--ai);background:linear-gradient(90deg,rgba(109,127,172,.12),rgba(109,127,172,.03));padding:.95rem 1rem;border-radius:0 14px 14px 0}
.adapt-title{color:var(--ivory);font-weight:800;margin-bottom:.15rem}
.adapt-copy{color:var(--muted);font-size:.93rem}
.poster{height:242px;border-radius:18px;background:linear-gradient(180deg,rgba(255,255,255,.025),rgba(0,0,0,.34)),radial-gradient(circle at 32% 18%,#303741 0%,#22272D 43%,#191C20 100%);border:1px solid var(--border);display:flex;align-items:flex-end;padding:1rem;margin-bottom:.55rem}
.poster-meta{color:var(--muted);font-size:.69rem;text-transform:uppercase;letter-spacing:.08em}
.poster-title{color:var(--ivory);font-size:1.12rem;font-weight:800;margin-top:.2rem;line-height:1.2}
.match{color:var(--ivory);font-size:1rem;font-weight:800}
.rating-line{color:var(--muted);font-size:.85rem;margin-top:.14rem}
.profile-shell{max-width:820px}
.profile-section{margin-top:.9rem;margin-bottom:.95rem}
.profile-title{color:var(--muted2);text-transform:uppercase;letter-spacing:.12em;font-size:.73rem;font-weight:800;margin-bottom:.3rem}
.profile-value{color:var(--ivory);font-size:1.38rem;font-weight:760;line-height:1.2}
.insight-list{border-top:1px solid var(--border);border-bottom:1px solid var(--border);margin-top:.3rem}
.insight-item{display:flex;align-items:center;gap:.6rem;padding:.56rem 0;color:var(--ivory);border-bottom:1px solid rgba(50,55,62,.7)}
.insight-item:last-child{border-bottom:none}
.insight-dot{width:7px;height:7px;background:var(--aiso);border-radius:999px;flex:0 0 auto}
.drawn-grid{display:flex;flex-wrap:wrap;gap:.42rem;margin-top:.4rem}
.drawn-chip{display:inline-block;padding:.46rem .68rem;border-radius:10px;background:rgba(109,127,172,.13);border:1px solid rgba(137,150,185,.24);color:var(--ivory);font-size:.88rem}
.summary-line{border-top:1px solid var(--border);padding-top:.85rem;margin-top:1rem;color:var(--muted);font-style:italic;font-size:.96rem}
.step3-panel{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:.9rem .95rem .45rem;margin-bottom:.7rem}
.step3-title{color:var(--ivory);font-weight:780;margin-bottom:.15rem}
.step3-copy{color:var(--muted);font-size:.88rem}
div.stButton>button{border-radius:999px;min-height:36px;font-weight:700;border-color:var(--border)}
div.stButton>button[kind="primary"]{background:var(--ai);color:white;border-color:var(--ai)}
div.stButton>button[kind="primary"]:hover{background:var(--aideep);border-color:var(--aideep)}
div[data-testid="stSlider"] [data-testid="stThumbValue"],div[data-testid="stSlider"] div[role="tooltip"],div[data-baseweb="slider"] div[role="tooltip"]{display:none!important;visibility:hidden!important}
.row-title{color:var(--ivory);font-size:1.45rem;font-weight:800;margin:1.1rem 0 .6rem}
</style>
''', unsafe_allow_html=True)

defaults={
    "screen":"welcome","likes":set(),"favorites":set(),"review_priority":50,
    "genres":[],"adventure":45,"more_of":[],"saved":set(),"seen":set(),"skipped":set()
}
for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k]=set() if isinstance(v,set) else ([] if isinstance(v,list) else v)

def logo():
    st.markdown('<div class="icinema-logo"><span class="icinema-mark"></span><span>iCinema</span></div>',unsafe_allow_html=True)

def go(screen):
    st.session_state.screen=screen
    st.rerun()

def poster(movie):
    meta = display_metadata(movie)
    genre_text = " / ".join(meta["genres"][:3]) if meta["genres"] else movie.get("genre", "")
    st.markdown(
        f'<div class="poster"><div><div class="poster-meta">{meta["year"]} &middot; {genre_text}</div>'
        f'<div class="poster-title">{meta["title"]}</div></div></div>',
        unsafe_allow_html=True
    )
    return meta

def current_profile():
    return build_profile(
        st.session_state.likes,st.session_state.favorites,st.session_state.genres,
        st.session_state.review_priority,st.session_state.more_of,
        st.session_state.saved,st.session_state.skipped
    )

def apply_action(title,action):
    if action=="save":
        st.session_state.saved.add(title);st.session_state.seen.discard(title);st.session_state.skipped.discard(title)
    elif action=="seen":
        st.session_state.seen.add(title);st.session_state.saved.discard(title);st.session_state.skipped.discard(title)
    elif action=="skip":
        st.session_state.skipped.add(title);st.session_state.saved.discard(title)
    st.rerun()

screen=st.session_state.screen

if screen=="welcome":
    logo()
    st.markdown('<div class="hero-title">Find something worth watching.</div>',unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">When you don’t know what to watch, iCinema learns your taste and curates films, series, and documentaries for you.</div>',unsafe_allow_html=True)
    st.markdown('''<div class="step-bubbles">
    <div class="step-bubble"><span class="step-index">01</span> Rate the Shelf</div>
    <div class="step-bubble"><span class="step-index">02</span> Tune Your Taste</div>
    <div class="step-bubble"><span class="step-index">03</span> Choose More Of</div>
    </div>''',unsafe_allow_html=True)
    st.markdown('''<div class="adapt-banner"><div class="adapt-title">iCinema keeps learning.</div><div class="adapt-copy">Every save, seen title, and skip reshapes what appears next in your showroom.</div></div>''',unsafe_allow_html=True)
    if st.button("Start Taste Setup →",type="primary"): go("shelf")

elif screen=="shelf":
    logo();st.markdown("### Step 1 of 3 — Rate the Shelf");st.caption("Select titles you like and mark your favorites.")
    cols=st.columns(4)
    for i,m in enumerate(STARTER_MOVIES):
        t=m["title"]
        with cols[i%4]:
            poster(m);a,b=st.columns(2)
            liked=t in st.session_state.likes and t not in st.session_state.favorites
            fav=t in st.session_state.favorites
            with a:
                if st.button("Like",key=f"like_{i}",type="primary" if liked else "secondary",use_container_width=True):
                    if liked: st.session_state.likes.discard(t)
                    else: st.session_state.likes.add(t);st.session_state.favorites.discard(t)
                    st.rerun()
            with b:
                if st.button("Favorite",key=f"fav_{i}",type="primary" if fav else "secondary",use_container_width=True):
                    if fav: st.session_state.favorites.discard(t);st.session_state.likes.discard(t)
                    else: st.session_state.favorites.add(t);st.session_state.likes.add(t)
                    st.rerun()
    if st.button("Continue →",type="primary"): go("taste")

elif screen=="taste":
    logo();st.markdown("### Step 2 of 3 — Tune Your Taste")
    st.markdown("#### Which matters more?")
    st.markdown('<div style="display:flex;justify-content:space-between;color:#F5F1E8;font-weight:650"><span>Great reviews</span><span>Pure entertainment</span></div>',unsafe_allow_html=True)
    st.session_state.review_priority=st.slider("Review priority",0,100,st.session_state.review_priority,label_visibility="collapsed")
    st.caption("Balance critical acclaim with entertainment value.")
    st.markdown("#### What do you like to watch?");st.caption("Select up to five genres.")
    selected=set(st.session_state.genres);cols=st.columns(5)
    for i,g in enumerate(GENRES):
        with cols[i%5]:
            active=g in selected
            if st.button(g,key=f"genre_{g}",type="primary" if active else "secondary",use_container_width=True):
                if active:selected.discard(g)
                elif len(selected)<5:selected.add(g)
                st.session_state.genres=list(selected);st.rerun()
    st.markdown("#### How adventurous are you?")
    st.markdown('<div style="display:flex;justify-content:space-between;color:#F5F1E8;font-weight:650"><span>Familiar picks</span><span>Something new</span></div>',unsafe_allow_html=True)
    st.session_state.adventure=st.slider("Adventure level",0,100,st.session_state.adventure,label_visibility="collapsed")
    if st.button("Continue →",type="primary"): go("more")

elif screen=="more":
    logo();st.markdown("### Step 3 of 3 — Shape Your Showroom");st.caption("Choose what you want iCinema to surface more often.")
    desc={
        "Hidden Gems":"Less obvious titles with strong fit.",
        "Critically Acclaimed":"Films and series with standout reviews.",
        "Recent Releases":"Newer titles worth considering.",
        "International Films":"Stories beyond the mainstream U.S. catalog.",
        "Classics":"Established favorites across eras.",
        "Documentaries":"Nonfiction picks matched to your interests."
    }
    selected=set(st.session_state.more_of);left,right=st.columns(2,gap="large")
    for i,opt in enumerate(MORE_OF_OPTIONS):
        with (left if i%2==0 else right):
            st.markdown(f'<div class="step3-panel"><div class="step3-title">{opt}</div><div class="step3-copy">{desc[opt]}</div></div>',unsafe_allow_html=True)
            if st.checkbox(f"Prioritize {opt}",value=opt in selected,key=f"more_{opt}"): selected.add(opt)
            else:selected.discard(opt)
    st.session_state.more_of=list(selected)
    if st.button("Build My Cinema Profile →",type="primary"): go("profile")

elif screen=="profile":
    logo();p=current_profile()
    st.markdown('<div class="profile-shell">',unsafe_allow_html=True)
    st.markdown("## Your Cinema Profile");st.caption("Built from your initial taste calibration.")
    st.markdown('<div class="profile-section"><div class="profile-title">You lean toward</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="profile-value">{" • ".join(p["lean"])}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="profile-section"><div class="profile-title">Top Genres</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="profile-value">{" • ".join(p["genres"])}</div></div>',unsafe_allow_html=True)
    stands="".join(f'<div class="insight-item"><span class="insight-dot"></span><span>{x}</span></div>' for x in p["stands_out"])
    st.markdown(f'<div class="profile-section"><div class="profile-title">What stands out to you</div><div class="insight-list">{stands}</div></div>',unsafe_allow_html=True)
    drawn="".join(f'<span class="drawn-chip">{x}</span>' for x in p["drawn_to"])
    st.markdown(f'<div class="profile-section"><div class="profile-title">You’re drawn to</div><div class="drawn-grid">{drawn}</div></div>',unsafe_allow_html=True)
    st.markdown(f'<div class="summary-line">{p["summary"]}</div>',unsafe_allow_html=True)
    if st.button("Enter My Showroom →",type="primary"): go("showroom")
    st.markdown('</div>',unsafe_allow_html=True)

elif screen=="showroom":
    logo();p=current_profile()
    st.markdown("## Your Showroom");st.caption("Recommendations adapt as you save, skip, and mark titles as seen.")
    tabs=st.tabs(["Showroom",f"Saved ({len(st.session_state.saved)})",f"Seen ({len(st.session_state.seen)})","Profile"])
    excluded=set(st.session_state.saved)|set(st.session_state.seen)|set(st.session_state.skipped)
    rows=[("Top Matches for You","top"),("Critically Acclaimed","acclaimed"),("Hidden Gems","hidden"),("Something Different","different")]
    with tabs[0]:
        used=set()
        for title,kind in rows:
            st.markdown(f'<div class="row-title">{title}</div>',unsafe_allow_html=True)
            recs=recommend_for_row(p,kind,st.session_state.adventure,st.session_state.review_priority,excluded|used,4)
            used.update(m["title"] for m in recs)
            if not recs:
                st.caption("No additional recommendations are available in this demo catalog.");continue
            cols=st.columns(len(recs))
            for i,m in enumerate(recs):
                with cols[i]:
                    meta=poster(m);st.markdown(f'<div class="match">{m["match"]}% iCinema Match</div>',unsafe_allow_html=True)
                    imdb_text = meta["imdb"] if meta["imdb"] else "—"
                    rt_text = meta["rt"] if meta["rt"] else "—"
                    st.markdown(f'<div class="rating-line">IMDb {imdb_text} · Rotten Tomatoes {rt_text}</div>',unsafe_allow_html=True)
                    st.caption(meta["blurb"])
                    a,b,c=st.columns(3)
                    with a:
                        if st.button("Save",key=f"s_{kind}_{m['title']}",use_container_width=True):apply_action(m["title"],"save")
                    with b:
                        if st.button("Seen",key=f"v_{kind}_{m['title']}",use_container_width=True):apply_action(m["title"],"seen")
                    with c:
                        if st.button("Skip",key=f"k_{kind}_{m['title']}",use_container_width=True):apply_action(m["title"],"skip")
    with tabs[1]:
        st.markdown("### Saved")
        if not st.session_state.saved:st.caption("Nothing saved yet.")
        else:
            movies=[get_movie(t) for t in st.session_state.saved if get_movie(t)]
            cols=st.columns(min(4,len(movies)))
            for i,m in enumerate(movies):
                with cols[i%len(cols)]:
                    poster(m)
                    if st.button("Mark Seen",key=f"ms_{m['title']}",use_container_width=True):apply_action(m["title"],"seen")
    with tabs[2]:
        st.markdown("### Seen")
        if not st.session_state.seen:st.caption("Nothing marked as seen yet.")
        else:
            movies=[get_movie(t) for t in st.session_state.seen if get_movie(t)]
            cols=st.columns(min(4,len(movies)))
            for i,m in enumerate(movies):
                with cols[i%len(cols)]:poster(m)
    with tabs[3]:
        st.markdown("### Cinema Profile")
        st.markdown(f"**You lean toward**  \n{' • '.join(p['lean'])}")
        st.markdown(f"**Top Genres**  \n{' • '.join(p['genres'])}")
        st.markdown(f"**What stands out to you**  \n{' • '.join(p['stands_out'])}")
        st.markdown(f"**You’re drawn to**  \n{' • '.join(p['drawn_to'])}")
        st.markdown(f"*{p['summary']}*")
    if st.button("Reset Taste Profile"):
        for k,v in defaults.items(): st.session_state[k]=set() if isinstance(v,set) else ([] if isinstance(v,list) else v)
        st.rerun()
