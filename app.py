
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
.hero-title{
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
        font-size:3.95rem;
        line-height:.99;
        font-weight:790;
        max-width:760px;
        margin-top:2.9rem;
        color:var(--ivory);
        letter-spacing:-.055em;
        text-wrap:balance
    }
.hero-subtitle{
        color:var(--muted);
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
        font-size:1.03rem;
        font-weight:450;
        max-width:730px;
        margin-top:1.18rem;
        margin-bottom:2.25rem;
        line-height:1.58;
        letter-spacing:-.008em
    }
.step-card{border:1px solid var(--border);background:var(--surface);border-radius:20px;padding:1.16rem 1.18rem;height:100%}
.step-num,.section-kicker{
        color:var(--muted2);
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
        font-size:.76rem;
        text-transform:uppercase;
        letter-spacing:.10em;
        font-weight:760
    }
.step-card h3{font-size:1.08rem;margin:.35rem 0 .25rem}
.step-card .muted{
        color:var(--muted);
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
        font-size:.92rem;
        font-weight:450;
        line-height:1.5;
        letter-spacing:-.005em
    }
.adapt-note{
        border:1px solid var(--border);
        border-radius:18px;
        background:rgba(255,255,255,.018);
        padding:1.28rem 1.3rem 1.24rem;
        margin:2rem 0 1.7rem;
        color:var(--muted);
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
        font-size:.92rem;
        font-weight:450;
        line-height:1.55;
        letter-spacing:-.005em
    }
.adapt-note strong{
        display:inline-block;
        color:var(--ivory);
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
        font-size:1.42rem;
        line-height:1.2;
        font-weight:760;
        letter-spacing:-.018em;
        text-transform:none;
        margin-bottom:.55rem
    }
.adapt-note span{
        display:block;
        max-width:760px;
        color:var(--muted);
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
        font-size:.92rem;
        font-weight:450;
        line-height:1.5;
        letter-spacing:-.005em
    }
.movie-card{margin-bottom:.55rem}
.poster{height:255px;border-radius:18px;background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(0,0,0,.32)),radial-gradient(circle at 30% 20%,#303640 0%,#1E232A 42%,#15181D 100%);border:1px solid var(--border);display:flex;align-items:flex-end;padding:1rem}
.poster-meta{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em}
.poster-title{font-size:1.18rem;font-weight:800;margin-top:.25rem;color:var(--ivory)}
.match{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-weight:600;
    font-size:.91rem;
    color:var(--ivory);
    margin-top:.4rem;
    letter-spacing:-.008em
}
.ratings{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    color:var(--muted);
    font-size:.82rem;
    margin-top:.08rem;
    margin-bottom:.32rem
}
.movie-description{
    font-family:Georgia,"Times New Roman",serif;
    color:var(--muted);
    font-size:.88rem;
    line-height:1.48;
    font-weight:400;
    margin-bottom:.45rem
}
.showroom-row{
    margin-top:1.65rem;
    margin-bottom:.45rem
}
.showroom-row h3{
    margin-bottom:.55rem
}
div.stButton>button{
    border-radius:999px;
    min-height:40px;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-weight:600;
    letter-spacing:-.008em
}
div.stButton>button p{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-weight:600
}
div[data-testid="stCaptionContainer"],
div[data-testid="stTextInput"] input,
div[data-testid="stRadio"] label,
div[data-testid="stMarkdownContainer"] p{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif
}

/* Step 2 preference block scales */
.pref-scale-wrap{
    margin:.35rem 0 .8rem;
}
.pref-scale-ends{
    display:flex;
    justify-content:space-between;
    align-items:flex-end;
    gap:1rem;
    margin-bottom:.55rem;
    color:var(--muted);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.82rem;
    line-height:1.35;
    font-weight:600;
}
.pref-scale-ends span:last-child{
    text-align:right;
}
.pref-scale-helper{
    margin-top:.42rem;
    color:var(--muted2);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.74rem;
    line-height:1.35;
    font-weight:650;
}
.pref-scale-clicks{
    margin-top:.95rem;
    margin-bottom:1.9rem;
}
.pref-scale-clicks div[data-testid="stHorizontalBlock"]{
    gap:.72rem !important;
}
.pref-scale-clicks div.stButton>button{
    min-height:4.05rem !important;
    height:4.05rem !important;
    padding:0 !important;
    border-radius:999px !important;
    font-size:0 !important;
    line-height:0 !important;
    border:1px solid rgba(169,173,183,.28) !important;
    background:rgba(255,255,255,.02) !important;
}
.pref-scale-clicks div.stButton>button:hover{
    border-color:rgba(186,191,202,.48) !important;
    background:rgba(255,255,255,.05) !important;
}
.pref-scale-clicks div.stButton>button p{
    font-size:0 !important;
    line-height:0 !important;
    margin:0 !important;
}

.step3-grid-gap{height:.15rem}
.step3-card{
    border:1px solid var(--border);
    background:linear-gradient(180deg, rgba(255,255,255,.025), rgba(255,255,255,.018));
    border-radius:20px;
    padding:1.05rem 1.05rem .95rem;
    min-height:8.3rem;
    margin-bottom:.62rem;
}
.step3-card-title{
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:1.02rem;
    font-weight:670;
    letter-spacing:-.012em;
    line-height:1.2;
    margin-bottom:.35rem;
}
.step3-card-copy{
    color:var(--muted);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.89rem;
    font-weight:450;
    line-height:1.46;
}
.step3-toggle-wrap{
    margin-top:-1.08rem;
    margin-bottom:1.15rem;
    padding:0 1rem .95rem 1rem;
    border-left:1px solid var(--border);
    border-right:1px solid var(--border);
    border-bottom:1px solid var(--border);
    border-radius:0 0 20px 20px;
    background:linear-gradient(180deg, rgba(255,255,255,.018), rgba(255,255,255,.012));
}
.step3-toggle-line{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:1rem;
    padding-top:.75rem;
    border-top:1px solid rgba(169,173,183,.14);
}
.step3-toggle-label{
    color:var(--muted);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.84rem;
    line-height:1.35;
    font-weight:560;
    letter-spacing:-.006em;
}
.step3-active-card{
    border-color:rgba(92,111,168,.48);
    box-shadow:0 0 0 1px rgba(92,111,168,.20) inset;
    background:linear-gradient(180deg, rgba(92,111,168,.11), rgba(255,255,255,.02));
}
[class*="st-key-priority_toggle_"]{
    margin-top:-3.08rem !important;
    margin-bottom:1.72rem !important;
    padding-right:1.05rem !important;
    display:flex !important;
    justify-content:flex-end !important;
    position:relative !important;
    z-index:2 !important;
}
[class*="st-key-priority_toggle_"] [data-testid="stToggle"]{
    margin:0 !important;
}
[class*="st-key-priority_toggle_"] label{
    gap:.45rem !important;
}
[class*="st-key-priority_toggle_"] p{
    font-size:0 !important;
    line-height:0 !important;
}

/* Step 1 — rating + search polish */
.shelf-action-gap{height:.52rem}

[class*="st-key-like_"] button,
[class*="st-key-fav_"] button{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif !important;
    font-size:.68rem !important;
    font-weight:700 !important;
    letter-spacing:.01em !important;
    text-transform:none !important;
    min-height:2.05rem !important;
    padding:.34rem .22rem !important;
    white-space:nowrap !important;
}
.st-key-search_add_like button,
.st-key-search_add_favorite button{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif !important;
    font-size:.74rem !important;
    font-weight:700 !important;
    letter-spacing:.01em !important;
    text-transform:none !important;
    min-height:2.2rem !important;
    padding:.4rem .55rem !important;
}

.search-shell{
    margin-top:1.7rem;
    margin-bottom:.75rem;
    padding:1.35rem 1.15rem 1.28rem;
    border:1px solid var(--border);
    border-radius:18px;
    background:rgba(255,255,255,.018);
}
.search-shell-title{
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:1.02rem;
    font-weight:400;
    letter-spacing:-.012em;
    margin-bottom:.38rem
}
.search-shell-copy{
    color:var(--muted);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.88rem;
    line-height:1.5;
    font-weight:450;
    margin-bottom:.05rem
}
.search-results-label{
    color:var(--muted2);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.69rem;
    font-weight:760;
    text-transform:uppercase;
    letter-spacing:.095em;
    margin:.58rem 0 .34rem
}
.search-selected-card{
    border:1px solid rgba(92,111,168,.52);
    background:rgba(92,111,168,.11);
    border-radius:14px;
    padding:.74rem .84rem;
    margin:.65rem 0 .68rem
}
.search-selected-kicker{
    color:var(--muted2);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.68rem;
    font-weight:760;
    text-transform:uppercase;
    letter-spacing:.095em;
    margin-bottom:.18rem
}
.search-selected-title{
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.96rem;
    line-height:1.35;
    font-weight:400
}
.selection-area{
    margin-top:1.1rem;
    margin-bottom:1.25rem;
}
.selection-heading{
    color:var(--muted2);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.69rem;
    font-weight:760;
    text-transform:uppercase;
    letter-spacing:.095em;
    margin-bottom:.5rem
}
.selection-grid{
    display:flex;
    flex-wrap:wrap;
    gap:.5rem;
}
.selection-chip{
    display:inline-flex;
    flex-direction:column;
    gap:.08rem;
    padding:.52rem .7rem;
    border:1px solid rgba(169,173,183,.22);
    background:rgba(243,240,234,.04);
    border-radius:13px;
    min-width:130px;
}
.selection-title{
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.91rem;
    line-height:1.3;
}
.selection-state{
    color:var(--muted2);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.64rem;
    font-weight:740;
    text-transform:uppercase;
    letter-spacing:.08em;
}
.search-already-selected{
    margin-top:.55rem;
    padding:.65rem .78rem;
    border:1px solid rgba(92,111,168,.34);
    border-radius:12px;
    background:rgba(92,111,168,.075);
    color:var(--muted);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.84rem;
    line-height:1.4;
}

div[data-testid="stTextInput"]{
    margin-top:.35rem;
    margin-bottom:.35rem;
}
div[data-testid="stTextInput"] input{
    border-radius:12px !important;
    min-height:46px !important;
    padding:.72rem .9rem !important;
}
[class*="st-key-search_result_"] button{
    justify-content:flex-start !important;
    text-align:left !important;
    border-radius:12px !important;
    min-height:42px !important;
    padding:.55rem .72rem !important;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif !important;
    font-size:.88rem !important;
    font-weight:560 !important;
    letter-spacing:-.005em !important;
}


/* Front-page primary CTA refinement */
.st-key-start_personalizing{
    margin-top:2.05rem;
}
.st-key-start_personalizing button{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif !important;
    font-size:.78rem !important;
    font-weight:650 !important;
    line-height:1.15 !important;
    letter-spacing:-.004em !important;
    min-height:3.05rem !important;
    padding:.78rem 1.35rem !important;
    border-radius:16px !important;
}
.st-key-start_personalizing button p{
    font-size:.78rem !important;
    line-height:1.15 !important;
    margin:0 !important;
}

div.stButton>button[kind="primary"]{background:var(--ai);border-color:var(--ai);color:white}
div.stButton>button[kind="primary"]:hover{background:var(--ai-hover);border-color:var(--ai-hover)}

div[data-testid="stSlider"] [data-testid="stThumbValue"],
div[data-testid="stSlider"] [data-testid="stSliderThumbValue"],
div[data-testid="stSlider"] div[role="tooltip"],
div[data-baseweb="slider"] div[role="tooltip"],
div[data-baseweb="slider"] [class*="ThumbValue"],
div[data-baseweb="slider"] [class*="thumbValue"]{
    display:none!important;
    visibility:hidden!important;
    opacity:0!important;
}

/* V5.41 Showroom polish */
.showroom-header{
    width:100%;
    max-width:100%;
    margin:0 0 1.25rem;
    padding:0;
    box-sizing:border-box;
}
.showroom-header,
.showroom-row{
    margin-left:0 !important;
    padding-left:0 !important;
}
.showroom-row{
    margin-top:.78rem;
    margin-bottom:.08rem;
}
.showroom-row.first{
    margin-top:0;
}
.showroom-row h3{
    margin-bottom:.18rem !important;
}
.showroom-tab-start{
    height:1.05rem;
}
.tab-section-heading{
    color:var(--ivory);
    font-family:var(--ui-font, -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif);
    font-size:1.65rem;
    line-height:1.1;
    font-weight:740;
    letter-spacing:-.025em;
    margin:0 0 .9rem;
}
.showroom-heading{
    color:var(--ivory);
    font-family:var(--ui-font, -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif);
    font-size:2rem;
    line-height:1.08;
    font-weight:760;
    letter-spacing:-.03em;
    margin:0 0 .48rem;
}
.showroom-intro{
    color:var(--muted);
    font-family:var(--ui-font, -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif);
    font-size:.93rem;
    line-height:1.5;
    font-weight:450;
    margin:0;
    max-width:760px;
}
[class*="st-key-save_"] button,
[class*="st-key-seen_"] button{
    min-width:0 !important;
    min-height:2.15rem !important;
    padding:.34rem .22rem !important;
    font-size:.7rem !important;
    line-height:1 !important;
    letter-spacing:0 !important;
    white-space:nowrap !important;
    overflow:visible !important;
    text-overflow:clip !important;
    font-family:var(--ui-font, -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif) !important;
}
[class*="st-key-save_"] button p,
[class*="st-key-seen_"] button p{
    font-size:.7rem !important;
    line-height:1 !important;
    white-space:nowrap !important;
    overflow:visible !important;
    text-overflow:clip !important;
}
.showroom-skip-row{
    height:.95rem;
    margin-bottom:-.18rem;
}
[class*="st-key-skip_"]{
    margin-top:-.12rem !important;
    margin-bottom:-.38rem !important;
}
[class*="st-key-skip_"] button{
    min-height:1.5rem !important;
    height:1.5rem !important;
    padding:.14rem .42rem !important;
    border-radius:999px !important;
    font-size:.64rem !important;
    font-weight:650 !important;
    line-height:1 !important;
    letter-spacing:0 !important;
    white-space:nowrap !important;
    font-family:var(--ui-font, -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif) !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    text-align:center !important;
}
[class*="st-key-skip_"] button p{
    font-size:.64rem !important;
    line-height:1 !important;
    white-space:nowrap !important;
    margin:0 !important;
    width:100% !important;
    text-align:center !important;
}
.movie-card-actions{
    margin-top:.35rem;
    margin-bottom:.22rem;
}
.profile-tab-reset{margin-top:1.2rem}
.profile-wrap{
    width:100%;
    max-width:780px;
    display:flex;
    flex-direction:column;
    align-items:flex-start;
    box-sizing:border-box;
    padding-bottom:.7rem;
}
.profile-heading,
.profile-intro,
.profile-grid,
.profile-summary{
    width:100%;
    max-width:760px;
    box-sizing:border-box;
}
.profile-heading{
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:2.12rem;
    line-height:1.08;
    font-weight:760;
    letter-spacing:-.032em;
    margin:0 0 .58rem;
}
.profile-intro{
    color:var(--muted);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    margin:0 0 1.55rem;
    font-size:.94rem;
    line-height:1.5;
    font-weight:450;
}
.profile-grid{
    display:grid;
    grid-template-columns:1fr;
    row-gap:0;
}
.profile-block{
    padding:0;
    margin:0;
}
.profile-block.full{
    grid-column:1;
    padding:0;
}
.profile-block + .profile-block{
    margin-top:2.15rem;
}
.profile-label{
    color:var(--muted2);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.72rem;
    text-transform:uppercase;
    letter-spacing:.105em;
    font-weight:760;
    margin:0 0 .62rem;
}
.profile-chip-wrap{
    display:flex;
    flex-wrap:wrap;
    column-gap:.66rem;
    row-gap:.62rem;
    align-items:center;
}
.profile-chip{
    display:inline-flex;
    align-items:center;
    width:fit-content;
    max-width:100%;
    min-height:2.12rem;
    padding:.42rem .78rem;
    border-radius:14px;
    border:1px solid rgba(169,173,183,.22);
    background:rgba(243,240,234,.032);
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.89rem;
    line-height:1.24;
    font-weight:600;
    letter-spacing:-.008em;
}
.profile-analysis{
    display:flex;
    flex-direction:column;
    align-items:flex-start;
    gap:.56rem;
}
.profile-analysis-row{
    display:inline-flex;
    align-items:center;
    width:fit-content;
    max-width:min(100%, 760px);
    min-height:2.12rem;
    padding:.42rem .78rem;
    border-radius:14px;
    border:1px solid rgba(169,173,183,.22);
    background:rgba(243,240,234,.032);
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.87rem;
    line-height:1.28;
    font-weight:500;
    letter-spacing:-.006em;
}
.profile-summary{
    margin-top:2rem;
    margin-bottom:1.25rem;
    border-top:1px solid var(--border);
    padding-top:1.7rem;
    color:var(--ivory);
    font-family:Georgia,"Times New Roman",serif;
    font-size:1.06rem;
    line-height:1.6;
    font-style:italic;
    font-weight:400;
}
.profile-summary strong{
    font-weight:400;
    font-style:italic
}
.st-key-enter_showroom{
    margin-top:.55rem;
}
.st-key-enter_showroom button{
    min-height:3.35rem !important;
    padding:.82rem 1.55rem !important;
    border-radius:18px !important;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif !important;
    font-size:.78rem !important;
    font-weight:650 !important;
    letter-spacing:-.004em !important;
}
.st-key-enter_showroom button p{
    font-size:.78rem !important;
    line-height:1.15 !important;
    margin:0 !important;
}
@media (max-width:800px){
    .profile-grid{row-gap:0}
    .profile-block + .profile-block{margin-top:1.8rem}
    .profile-heading{font-size:1.8rem}
    .hero-title{font-size:2.8rem}
}

/* V5.27 unified iCinema typography */
:root {
    --ui-font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}

/* Primary display headings */
h1, h2, h3, h4,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4 {
    font-family:var(--ui-font) !important;
    letter-spacing:-.03em;
}

/* UI controls / selections */
div.stButton>button,
div.stButton>button p,
div[data-testid="stRadio"] label,
div[data-testid="stCheckbox"] label,
div[data-testid="stToggle"] label {
    font-family:var(--ui-font) !important;
}

/* Supporting copy */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
[data-testid="stMarkdownContainer"] p,
div[data-testid="stTextInput"] input {
    font-family:var(--ui-font) !important;
}

/* Showroom section titles */
.showroom-row h3 {
    font-family:var(--ui-font) !important;
    font-weight:700 !important;
    letter-spacing:-.025em !important;
}

/* Movie descriptions now use the shared body font */
.movie-description {
    font-family:var(--ui-font) !important;
    font-size:.88rem !important;
    line-height:1.5 !important;
    font-weight:400 !important;
}

/* Match + ratings stay within same UI system */
.match,
.ratings {
    font-family:var(--ui-font) !important;
}

/* Profile value chips use the same UI font system as Steps 1 and 2 */
.profile-chip {
    font-family:var(--ui-font) !important;
    font-size:.9rem !important;
    font-weight:600 !important;
    letter-spacing:-.008em !important;
}

/* Analytical profile text uses shared body font */
.profile-analysis-row {
    font-family:var(--ui-font) !important;
}

/* Keep the final profile interpretation as the single editorial accent */
.profile-summary {
    font-family:Georgia,"Times New Roman",serif !important;
    font-style:italic !important;
    font-weight:400 !important;
}

/* Step 2 scale text follows the shared system */
.pref-scale-ends,
.pref-scale-helper {
    font-family:var(--ui-font) !important;
}

/* Step 3 rows */
.step3-row-title,
.step3-row-copy {
    font-family:var(--ui-font) !important;
}

/* Front page: only this adaptive heading gets the emphasized special treatment */
.adapt-note strong {
    font-family:var(--ui-font) !important;
    color:var(--ivory) !important;
    font-size:.92rem !important;
    font-weight:760 !important;
    letter-spacing:-.018em !important;
    text-transform:none !important;
}


/* V5.48 tighter showroom row/card rhythm */
[class*="st-key-skip_"] + div{
    margin-top:0 !important;
}
@media (max-width:900px){
    [class*="st-key-skip_"] button{
        min-width:3.2rem !important;
        padding:.14rem .36rem !important;
    }
}

</style>
""", unsafe_allow_html=True)

defaults={
    "screen":"welcome","likes":set(),"favorites":set(),"review_priority":50,
    "genres":[],"adventure":50,"more_of":[],"saved":set(),"seen":set(),"dismissed":set(),
    "custom_like":None,"search_selected_title":None
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

def concise_description(text, limit=118):
    text = " ".join(str(text).split()).strip()
    if not text:
        return ""
    # Prefer the first clause/sentence for a cleaner card.
    for separator in ["; ", ". "]:
        if separator in text:
            first = text.split(separator, 1)[0].strip()
            if len(first) >= 55:
                text = first
                break
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.…")
    return text.rstrip(" ,;:.…") + "."

def profile_chip_html(items):
    return "".join(f'<span class="profile-chip">{item}</span>' for item in items)

def profile_analysis_html(items):
    return "".join(f'<div class="profile-analysis-row">{item}</div>' for item in items)

def render_cinema_profile(p):
    sections = [
        ("You tend to enjoy", profile_chip_html(p["traits"]), "profile-chip-wrap"),
        ("Top genres", profile_chip_html(p["genres"]), "profile-chip-wrap"),
        ("What matters most", profile_chip_html(p["matters"]), "profile-chip-wrap"),
        ("What iCinema should prioritize", profile_chip_html(p["priorities"]), "profile-chip-wrap"),
        ("Viewing patterns", profile_analysis_html(p["patterns"]), "profile-analysis"),
        ("Recommendation balance", profile_analysis_html(p["balance"]), "profile-analysis"),
    ]

    section_html = "".join(
        f'<div class="profile-block full">'
        f'<div class="profile-label">{label}</div>'
        f'<div class="{wrapper_class}">{content}</div>'
        f'</div>'
        for label, content, wrapper_class in sections
    )

    st.markdown(
        f'<div class="profile-wrap">'
        f'<div class="profile-heading">Your Cinema Profile</div>'
        f'<div class="profile-intro">Built from your tailored preferences</div>'
        f'<div class="profile-grid">{section_html}</div>'
        f'<div class="profile-summary">{p["summary"]}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

screen=st.session_state.screen

if screen=="welcome":
    logo()
    st.markdown('<div class="hero-title">Always find your next great watch.</div>',unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">iCinema learns what you like and narrows the search to movies, series, and documentaries that fit your preferences</div>',unsafe_allow_html=True)

    c1,c2,c3=st.columns(3)
    steps=[
        ("01","Rate the Shelf","Choose titles you already enjoy, or search for one you like"),
        ("02","Tailor Your Preferences","Choose what matters most when deciding what to watch"),
        ("03","Shape Your Showroom","Choose what iCinema should surface more often"),
    ]
    for col,(n,title,body) in zip((c1,c2,c3),steps):
        with col:
            st.markdown(f'<div class="step-card"><div class="step-num">Step {n}</div><h3>{title}</h3><div class="muted">{body}</div></div>',unsafe_allow_html=True)

    st.markdown('<div class="adapt-note"><strong>iCinema responds to your choices</strong><br><span>Every save, skip, and seen title continuously influences what appears next</span></div>',unsafe_allow_html=True)
    if st.button("Start Personalizing →",type="primary",key="start_personalizing"):go("shelf")

elif screen=="shelf":
    logo()
    st.markdown("### Step 1 of 3 — Rate the Shelf")
    st.caption("Choose a few titles you already like. If none fit, search for one you know you enjoy.")

    cols=st.columns(4)
    for i,movie in enumerate(STARTER_MOVIES):
        title=movie["title"]
        with cols[i%4]:
            movie_thumb(movie)
            st.markdown('<div class="shelf-action-gap"></div>', unsafe_allow_html=True)
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

    st.markdown(
        '<div class="search-shell">'
        '<div class="search-shell-title">Don’t see one you like?</div>'
        '<div class="search-shell-copy">Search for a movie you already enjoy</div>'
        '</div>',
        unsafe_allow_html=True
    )

    search_query = st.text_input(
        "Search movies",
        placeholder="Search by title",
        label_visibility="collapsed",
        key="movie_search_query"
    )

    titles = searchable_titles()
    matches = []
    already_selected_matches = []
    if search_query.strip():
        q = search_query.strip().lower()
        all_matches = [title for title in titles if q in title.lower()][:6]
        selected_titles = st.session_state.likes | st.session_state.favorites
        matches = [title for title in all_matches if title not in selected_titles]
        already_selected_matches = [title for title in all_matches if title in selected_titles]

    # Keep a pending search selection only while it is still a valid unselected result.
    if st.session_state.search_selected_title not in matches:
        st.session_state.search_selected_title = None

    if search_query.strip():
        if matches:
            st.markdown('<div class="search-results-label">Matching titles</div>', unsafe_allow_html=True)
            result_cols = st.columns(2)
            for j, title in enumerate(matches):
                selected = st.session_state.search_selected_title == title
                with result_cols[j % 2]:
                    if st.button(
                        title,
                        key=f"search_result_{j}",
                        type="primary" if selected else "secondary",
                        use_container_width=True
                    ):
                        st.session_state.search_selected_title = title
                        st.rerun()

        if already_selected_matches:
            selected_name = already_selected_matches[0]
            state = "Favorite" if selected_name in st.session_state.favorites else "Liked"
            st.markdown(
                f'<div class="search-already-selected">'
                f'<strong>{selected_name}</strong> is already in your selections as {state.lower()}'
                f'</div>',
                unsafe_allow_html=True
            )

        if not matches and not already_selected_matches:
            st.caption("No matches found in the current iCinema catalog")

    choice = st.session_state.search_selected_title
    if choice:
        st.markdown(
            f'<div class="search-selected-card">'
            f'<div class="search-selected-kicker">Selected title</div>'
            f'<div class="search-selected-title">{choice}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        a,b=st.columns([1,1])
        with a:
            if st.button(
                "Add as Like",
                key="search_add_like",
                use_container_width=True
            ):
                st.session_state.likes.add(choice)
                st.session_state.favorites.discard(choice)
                st.session_state.search_selected_title = None
                st.rerun()
        with b:
            if st.button(
                "Add as Favorite",
                key="search_add_favorite",
                use_container_width=True
            ):
                st.session_state.likes.add(choice)
                st.session_state.favorites.add(choice)
                st.session_state.search_selected_title = None
                st.rerun()

    chosen_titles = sorted(st.session_state.likes | st.session_state.favorites)
    chosen_count = len(chosen_titles)

    if chosen_titles:
        chips = []
        for title in chosen_titles:
            state = "Favorite" if title in st.session_state.favorites else "Liked"
            chips.append(
                f'<div class="selection-chip">'
                f'<div class="selection-title">{title}</div>'
                f'<div class="selection-state">{state}</div>'
                f'</div>'
            )
        st.markdown(
            '<div class="selection-area">'
            '<div class="selection-heading">Your selections</div>'
            '<div class="selection-grid">' + "".join(chips) + '</div>'
            '</div>',
            unsafe_allow_html=True
        )

    st.caption(f"{chosen_count} title{'s' if chosen_count!=1 else ''} selected")
    if st.button("Continue →",type="primary",disabled=chosen_count==0):go("taste")

elif screen=="taste":
    logo()
    st.markdown("### Step 2 of 3 — Tailor Your Preferences")
    st.caption("Choose what matters most when deciding what to watch")

    st.markdown("### Which matters more?")

    review_scale_map = [15, 32, 50, 68, 85]
    review_idx = min(range(5), key=lambda i: abs(review_scale_map[i] - st.session_state.review_priority))

    review_label = [
        "Leaning strongly toward reviews",
        "Leaning toward reviews",
        "Balanced",
        "Leaning toward entertainment",
        "Leaning strongly toward entertainment",
    ][review_idx]

    st.markdown(
        '<div class="pref-scale-wrap">'
        '<div class="pref-scale-ends"><span>Great reviews</span><span>Easy to enjoy</span></div>'
        f'<div class="pref-scale-helper">{review_label}</div>'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown('<div class="pref-scale-clicks">', unsafe_allow_html=True)
    review_cols = st.columns(5, gap="small")
    for i, value in enumerate(review_scale_map):
        with review_cols[i]:
            if st.button(
                " ",
                key=f"review_scale_{i}",
                type="primary" if i == review_idx else "secondary",
                use_container_width=True
            ):
                st.session_state.review_priority = value
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("#### What do you like to watch?")
    st.caption("Select up to five genres")
    selected=set(st.session_state.genres)
    genre_cols=st.columns(5)
    for i,genre in enumerate(GENRES):
        with genre_cols[i%5]:
            active=genre in selected
            if st.button(
                genre,
                key=f"genre_{i}",
                type="primary" if active else "secondary",
                use_container_width=True
            ):
                if active:
                    selected.discard(genre)
                elif len(selected)<5:
                    selected.add(genre)
                st.session_state.genres=list(selected)
                st.rerun()

    st.markdown("### How open are you to something different?")

    adventure_scale_map = [15, 32, 50, 68, 85]
    adventure_idx = min(range(5), key=lambda i: abs(adventure_scale_map[i] - st.session_state.adventure))

    adventure_label = [
        "Stay very close to my taste",
        "Stay mostly familiar",
        "Balanced",
        "Explore a little more",
        "Show me something different",
    ][adventure_idx]

    st.markdown(
        '<div class="pref-scale-wrap">'
        '<div class="pref-scale-ends"><span>Stay close to my taste</span><span>Show me something different</span></div>'
        f'<div class="pref-scale-helper">{adventure_label}</div>'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown('<div class="pref-scale-clicks">', unsafe_allow_html=True)
    adventure_cols = st.columns(5, gap="small")
    for i, value in enumerate(adventure_scale_map):
        with adventure_cols[i]:
            if st.button(
                " ",
                key=f"adventure_scale_{i}",
                type="primary" if i == adventure_idx else "secondary",
                use_container_width=True
            ):
                st.session_state.adventure = value
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Continue →",type="primary"):
        go("more")

elif screen=="more":
    logo()
    st.markdown("### Step 3 of 3 — Shape Your Showroom")
    st.caption("Choose what iCinema should surface more often")

    descriptions = {
        "Hidden Gems": "Less obvious titles that still fit your taste",
        "Critically Acclaimed": "Titles with especially strong critical reception",
        "Recent Releases": "Newer films and recent additions",
        "International Films": "Stories and filmmakers from around the world",
        "Classics": "Established favorites across earlier eras",
        "Documentaries": "Nonfiction stories matched to your interests",
    }

    selected = set(st.session_state.more_of)
    left, right = st.columns(2, gap="large")

    for i, option in enumerate(MORE_OF_OPTIONS):
        with (left if i % 2 == 0 else right):
            active = option in selected
            active_class = ' step3-active-card' if active else ''
            st.markdown(
                f'<div class="step3-card{active_class}">'
                f'<div class="step3-card-title">{option}</div>'
                f'<div class="step3-card-copy">{descriptions[option]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            st.markdown(
                '<div class="step3-toggle-wrap">'
                '<div class="step3-toggle-line">'
                '<div class="step3-toggle-label">Surface more often</div>'
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )
            new_state = st.toggle(
                f'Prioritize {option}',
                value=active,
                key=f'priority_toggle_{option}',
                label_visibility='collapsed'
            )
            if new_state and option not in selected:
                selected.add(option)
            elif not new_state and option in selected:
                selected.discard(option)

    st.session_state.more_of = list(selected)

    if st.button("Build My Cinema Profile →", type="primary"):
        go("profile")

elif screen=="profile":
    logo()
    p=current_profile()
    render_cinema_profile(p)

    if st.button("Enter My Showroom →",type="primary",key="enter_showroom"):
        go("showroom")

elif screen=="showroom":
    logo()
    p=current_profile()
    st.markdown(
        '<div class="showroom-header">'
        '<div class="showroom-heading">Your Showroom</div>'
        '<div class="showroom-intro">Personalized to your taste and refined with every save, skip, and title you mark as seen</div>'
        '</div>',
        unsafe_allow_html=True
    )

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
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        used=set()
        for row_index,(row_name,predicate) in enumerate(row_specs):
            choices=[]
            for score,movie in ranked:
                if movie["title"] in used:continue
                if predicate(movie,score):
                    choices.append((score,movie))
                if len(choices)==4:break
            used.update(m["title"] for _,m in choices)
            row_class = "showroom-row first" if row_index == 0 else "showroom-row"
            st.markdown(f'<div class="{row_class}"><h3>{row_name}</h3></div>', unsafe_allow_html=True)
            if not choices:
                st.caption("No additional matches in this demo catalog.")
                continue
            cols=st.columns(len(choices))
            for i,(match,movie) in enumerate(choices):
                with cols[i]:
                    skip_spacer, skip_col = st.columns([4.0,1.1], gap="small")
                    with skip_col:
                        st.markdown('<div class="showroom-skip-row">', unsafe_allow_html=True)
                        if st.button("Skip",key=f"skip_{row_name}_{movie['title']}",use_container_width=True):
                            st.session_state.dismissed.add(movie["title"])
                            st.session_state.saved.discard(movie["title"])
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                    movie_thumb(movie)
                    st.markdown(f'<div class="match">{match}% iCinema Match</div>',unsafe_allow_html=True)
                    st.markdown(f'<div class="ratings">IMDb {movie["imdb"]} · RT {movie["rt"]}%</div>',unsafe_allow_html=True)
                    short_desc = concise_description(movie["why"])
                    st.markdown(f'<div class="movie-description">{short_desc}</div>',unsafe_allow_html=True)
                    st.markdown('<div class="movie-card-actions">', unsafe_allow_html=True)
                    a,b=st.columns(2, gap="small")
                    with a:
                        if st.button("Save",key=f"save_{row_name}_{movie['title']}",use_container_width=True):
                            st.session_state.saved.add(movie["title"]);st.session_state.seen.discard(movie["title"]);st.session_state.dismissed.discard(movie["title"]);st.rerun()
                    with b:
                        if st.button("Seen",key=f"seen_{row_name}_{movie['title']}",use_container_width=True):
                            st.session_state.seen.add(movie["title"]);st.session_state.saved.discard(movie["title"]);st.session_state.dismissed.discard(movie["title"]);st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

    with tabs[1]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        st.markdown('<div class="tab-section-heading">Saved</div>', unsafe_allow_html=True)
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
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        st.markdown('<div class="tab-section-heading">Seen</div>', unsafe_allow_html=True)
        movies=[get_movie(t) for t in st.session_state.seen if get_movie(t)]
        if not movies:st.caption("Nothing marked as seen yet.")
        else:
            cols=st.columns(min(4,len(movies)))
            for i,m in enumerate(movies):
                with cols[i%len(cols)]:movie_thumb(m)

    with tabs[3]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        render_cinema_profile(p)
        st.markdown('<div class="profile-tab-reset"></div>', unsafe_allow_html=True)
        if st.button("Reset Profile", key="reset_profile_tab"):
            for k,v in defaults.items():
                st.session_state[k]=v.copy() if isinstance(v,set) else (list(v) if isinstance(v,list) else v)
            st.rerun()

