
import html
import json
import streamlit as st
from src.recommender import (
    STARTER_MOVIES, GENRES, MORE_OF_OPTIONS, searchable_titles, get_movie,
    build_profile, score_movie, recommend, rank_movies, score_movie_components, CATALOG
)
from src.watch_providers import get_watch_availability_batch, tmdb_configured
from src.tmdb_catalog import search_movies, get_poster_batch, tmdb_catalog_configured, discover_movies
from src.live_ratings import get_live_ratings_batch, omdb_configured
from src.browser_storage import browser_storage

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
.poster{
    width:100%;
    aspect-ratio:2 / 3;
    border-radius:18px;
    border:1px solid var(--border);
    background:#0F1114;
    position:relative;
    overflow:hidden;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:0;
    box-sizing:border-box;
}
.poster.has-image{
    padding:0;
    background:#0F1114;
}
.poster.has-image img{
    width:100%;
    height:100%;
    object-fit:contain;
    object-position:center center;
    display:block;
    margin:0;
    padding:0;
    border-radius:17px;
}
.poster-placeholder-mark{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:.86rem;font-weight:700;letter-spacing:.08em;color:rgba(243,240,234,.34)}
.poster-caption{margin:.62rem 0 .28rem;padding:0 .08rem;min-height:3rem;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.poster-caption-title{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:1.18rem;line-height:1.18;font-weight:800;letter-spacing:-.025em;color:var(--ivory)}
.poster-caption-year{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:.75rem;line-height:1.35;font-weight:700;letter-spacing:.055em;text-transform:uppercase;color:var(--muted);margin-top:.18rem}
@media (max-width:900px){.poster{aspect-ratio:2 / 3}}
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
    font-size:.94rem;
    line-height:1.35;
    font-weight:650;
}
.pref-scale-ends span:last-child{
    text-align:right;
}
.pref-scale-helper{
    margin-top:.82rem;
    color:var(--muted2);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.86rem;
    line-height:1.35;
    font-weight:650;
}
.genre-helper{
    margin:.15rem 0 .72rem;
    color:var(--muted);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.92rem;
    line-height:1.4;
    font-weight:550;
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
    font-size:.74rem !important;
    line-height:1.16 !important;
    border:1px solid rgba(169,173,183,.28) !important;
    background:rgba(255,255,255,.02) !important;
}
.pref-scale-clicks div.stButton>button:hover{
    border-color:rgba(186,191,202,.48) !important;
    background:rgba(255,255,255,.05) !important;
}
.pref-scale-clicks div.stButton>button p{
    font-size:.74rem !important;
    line-height:1.16 !important;
    margin:0 !important;
    white-space:normal !important;
    text-align:center !important;
    font-weight:700 !important;
}

.step3-grid-gap{height:.15rem}
[class*="st-key-priority_card_"]{
    margin-bottom:1.15rem !important;
}
[class*="st-key-priority_card_"] button{
    width:100% !important;
    min-height:8.55rem !important;
    height:auto !important;
    padding:1.15rem 1.15rem 1.2rem !important;
    border:1px solid var(--border) !important;
    border-radius:20px !important;
    background:linear-gradient(180deg, rgba(255,255,255,.025), rgba(255,255,255,.018)) !important;
    box-shadow:none !important;
    justify-content:flex-start !important;
    text-align:left !important;
}
[class*="st-key-priority_card_"] button:hover{
    border-color:rgba(169,173,183,.46) !important;
    background:rgba(255,255,255,.035) !important;
    box-shadow:none !important;
}
[class*="st-key-priority_card_"] button p{
    width:100% !important;
    margin:0 !important;
    white-space:normal !important;
    text-align:left !important;
    color:var(--muted) !important;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif !important;
    font-size:.89rem !important;
    font-weight:450 !important;
    line-height:1.46 !important;
}
[class*="st-key-priority_card_"] button p strong{
    display:block !important;
    color:var(--ivory) !important;
    font-size:1.02rem !important;
    font-weight:700 !important;
    letter-spacing:-.012em !important;
    line-height:1.2 !important;
    margin-bottom:.42rem !important;
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
    line-height:1.3;
    font-weight:800
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
    font-weight:800;
    letter-spacing:-.018em;
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
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    text-align:center !important;
}
[class*="st-key-save_"] button p,
[class*="st-key-seen_"] button p{
    font-size:.7rem !important;
    line-height:1 !important;
    white-space:nowrap !important;
    overflow:visible !important;
    text-overflow:clip !important;
    margin:0 !important;
    width:100% !important;
    text-align:center !important;
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
    min-width:3.6rem !important;
    width:100% !important;
    min-height:1.5rem !important;
    height:1.5rem !important;
    padding:.14rem .38rem !important;
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
    overflow:visible !important;
    text-overflow:clip !important;
    margin:0 !important;
    width:100% !important;
    min-width:max-content !important;
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


/* V5.58 targeted typography polish — only user-requested elements */
/* Showroom metadata/details use the same strong system-font treatment. */
.match{font-weight:800 !important;letter-spacing:-.018em !important}
.ratings{font-weight:700 !important;letter-spacing:-.006em !important}
.watch-availability{font-family:var(--ui-font) !important;font-weight:700 !important;letter-spacing:-.006em !important}
.movie-description{font-family:var(--ui-font) !important;font-weight:600 !important;letter-spacing:-.006em !important}

/* Step 2 genre buttons only. */
[class*="st-key-genre_"] button,
[class*="st-key-genre_"] button p{
    font-family:var(--ui-font) !important;
    font-weight:800 !important;
    letter-spacing:-.018em !important;
}

/* All six Cinema Profile value groups: same stronger bubble text treatment. */
.profile-chip,
.profile-analysis-row{
    font-family:var(--ui-font) !important;
    font-weight:600 !important;
    letter-spacing:-.008em !important;
}

/* V5.48 tighter showroom row/card rhythm */
[class*="st-key-skip_"] + div{
    margin-top:0 !important;
}
@media (max-width:900px){
    [class*="st-key-skip_"]{
        min-width:3.6rem !important;
    }
    [class*="st-key-skip_"] button{
        min-width:3.6rem !important;
        padding:.14rem .32rem !important;
        font-size:.62rem !important;
    }
    [class*="st-key-skip_"] button p{
        font-size:.62rem !important;
    }
}

.watch-availability{
    color:#C8CBD2;
    font-family:var(--ui-font);
    font-size:.73rem;
    line-height:1.35;
    margin:.34rem 0 .22rem;
    min-height:1.02rem;
}
.watch-availability.muted{color:var(--muted2)}
.watch-attribution{
    color:var(--muted2);
    font-family:var(--ui-font);
    font-size:.66rem;
    line-height:1.45;
    margin-top:.65rem;
    margin-bottom:.15rem;
}


/* V5.68 full polish: distinct Step 2 tiles, cleaner Step 3 selection, balanced rhythm */
/* Step 2 genres are intentionally sharp mini-squares to distinguish this step. */
[class*="st-key-genre_"] button{
    border-radius:0 !important;
    width:100% !important;
    max-width:6.6rem !important;
    aspect-ratio:1 / 1 !important;
    min-height:0 !important;
    height:auto !important;
    padding:.42rem !important;
    margin:.08rem 0 .42rem !important;
}
[class*="st-key-genre_"] button p{
    font-size:.77rem !important;
    line-height:1.15 !important;
    text-align:center !important;
    white-space:normal !important;
}
.genre-helper{margin-bottom:.9rem !important}

/* Step 3: card itself is the control; selected state is a small top-right check. */
[class*="st-key-priority_card_"] button{
    position:relative !important;
    min-height:7.55rem !important;
    padding:1.12rem 2.9rem 1.12rem 1.15rem !important;
}
[class*="st-key-priority_card_active_"] button{
    border-color:rgba(92,111,168,.82) !important;
    background:rgba(92,111,168,.075) !important;
}
[class*="st-key-priority_card_active_"] button::after{
    content:"✓";
    position:absolute;
    top:.8rem;
    right:.9rem;
    width:1.55rem;
    height:1.55rem;
    display:flex;
    align-items:center;
    justify-content:center;
    border-radius:50%;
    color:var(--ivory);
    background:rgba(92,111,168,.9);
    font-size:.78rem;
    font-weight:800;
    line-height:1;
}

/* Global rhythm pass: calm, consistent spacing across onboarding and showroom. */
h1,h2,h3,h4{letter-spacing:-.025em}
div[data-testid="stHeadingWithActionElements"]{margin-bottom:.12rem}
div[data-testid="stCaptionContainer"]{margin-top:.08rem;margin-bottom:.68rem}
.pref-scale-wrap{margin:.42rem 0 .95rem !important}
.pref-scale-helper{margin-top:1rem !important}
.pref-scale-clicks{margin-top:.82rem !important;margin-bottom:1.7rem !important}
.showroom-header{margin-bottom:1.1rem !important}
.showroom-tab-start{height:.24rem !important}
.showroom-row{margin-top:.82rem !important;margin-bottom:.06rem !important}
.showroom-row h3{margin-bottom:.22rem !important}
.poster-caption{margin-top:.46rem !important}
.movie-card-actions{margin-top:.34rem !important}

/* V5.73 Step 2 + analytical profile polish */
.step2-header{margin:0 0 1.35rem}
.step2-title{
    color:var(--ivory);
    font-family:var(--ui-font);
    font-size:2rem;
    line-height:1.1;
    font-weight:760;
    letter-spacing:-.035em;
    margin:0 0 .48rem;
}
.step2-subtitle{
    color:var(--muted);
    font-family:var(--ui-font);
    font-size:.95rem;
    line-height:1.45;
    margin:0;
}
.step2-question{
    color:var(--ivory);
    font-family:var(--ui-font);
    font-size:1.48rem;
    line-height:1.15;
    font-weight:740;
    letter-spacing:-.025em;
    margin:.1rem 0 .72rem;
}

/* Keep the pre-Showroom analysis dense enough to fit comfortably on one screen. */
.profile-wrap{max-width:760px !important;padding-bottom:.3rem !important}
.profile-heading{font-size:1.88rem !important;margin-bottom:.34rem !important}
.profile-intro{font-size:.86rem !important;line-height:1.4 !important;margin-bottom:.88rem !important}
.profile-block + .profile-block{margin-top:1.22rem !important}
.profile-label{font-size:.68rem !important;margin-bottom:.42rem !important}
.profile-chip-wrap{column-gap:.5rem !important;row-gap:.44rem !important}
.profile-chip{min-height:1.88rem !important;padding:.32rem .66rem !important;font-size:.83rem !important;border-radius:12px !important}
.profile-analysis{gap:.4rem !important}
.profile-analysis-row{min-height:1.88rem !important;padding:.32rem .66rem !important;font-size:.82rem !important;line-height:1.22 !important;border-radius:12px !important}
.profile-summary{margin-top:1.2rem !important;margin-bottom:.72rem !important;padding-top:1.05rem !important;font-size:.96rem !important;line-height:1.48 !important}
.st-key-enter_showroom{margin-top:.3rem !important}
.st-key-enter_showroom button{min-height:3rem !important;padding:.68rem 1.35rem !important}
@media (max-width:800px){
    .step2-title{font-size:1.72rem}
    .step2-question{font-size:1.3rem}
    .profile-block + .profile-block{margin-top:1.05rem !important}
}

/* V5.59 showroom balance: tighter, more even vertical rhythm without changing card height */
.poster-caption{margin:.52rem 0 .18rem !important;min-height:2.9rem !important}
.match{margin-top:.28rem !important;margin-bottom:.04rem !important}
.ratings{margin-top:.02rem !important;margin-bottom:.24rem !important}
.watch-availability{margin:.24rem 0 .18rem !important;min-height:.96rem !important}
.movie-description{margin-top:.12rem !important;margin-bottom:.34rem !important;line-height:1.45 !important}
.movie-card-actions{margin-top:.28rem !important;margin-bottom:.18rem !important}
.showroom-row{margin-top:.68rem !important;margin-bottom:.04rem !important}
.showroom-row h3{margin-bottom:.14rem !important}

/* V5.74 showroom card alignment + CTA sizing */
/* Give the poster-to-details transition a little more breathing room. */
.poster-caption{
    margin-top:.72rem !important;
    margin-bottom:.2rem !important;
}
/* Reserve a consistent description area so Save / Seen align across a row. */
.movie-description{
    min-height:3.95rem !important;
    margin-top:.14rem !important;
    margin-bottom:.38rem !important;
    display:-webkit-box;
    -webkit-box-orient:vertical;
    -webkit-line-clamp:3;
    overflow:hidden;
}
.movie-card-actions{
    margin-top:.3rem !important;
    margin-bottom:.2rem !important;
}
/* V5.81 showroom card grid: normalize vertical content blocks across every movie card. */
.poster-caption{
    min-height:4.45rem !important;
    margin-top:.72rem !important;
    margin-bottom:.22rem !important;
}
.poster-caption-title{
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    overflow:hidden !important;
}
.poster-caption-year{
    min-height:1rem !important;
}
.match{
    min-height:1.65rem !important;
    display:flex !important;
    align-items:flex-end !important;
    margin-top:.18rem !important;
    margin-bottom:.04rem !important;
}
.ratings{
    min-height:1.45rem !important;
    display:flex !important;
    align-items:flex-start !important;
    margin-top:.02rem !important;
    margin-bottom:.2rem !important;
}
.watch-availability{
    min-height:2.7rem !important;
    max-height:2.7rem !important;
    line-height:1.32 !important;
    overflow:hidden !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    margin:.18rem 0 .18rem !important;
}
.movie-description{
    min-height:4.5rem !important;
    max-height:4.5rem !important;
    line-height:1.45 !important;
    margin-top:.08rem !important;
    margin-bottom:.36rem !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:3 !important;
    overflow:hidden !important;
}
.movie-card-actions{
    margin-top:.22rem !important;
    margin-bottom:.2rem !important;
}

/* V5.83: tighter, more even Showroom metadata rhythm. */
.poster-caption{
    min-height:3.85rem !important;
    margin-top:.58rem !important;
    margin-bottom:.16rem !important;
}
.poster-caption-title{
    font-size:1.12rem !important;
    line-height:1.16 !important;
    min-height:2.58rem !important;
    max-height:2.58rem !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    overflow:hidden !important;
}
.poster-caption-year{
    min-height:.95rem !important;
    margin-top:.08rem !important;
}
.match{
    min-height:1.45rem !important;
    margin-top:.08rem !important;
    margin-bottom:.02rem !important;
}
.ratings{
    min-height:1.3rem !important;
    margin-bottom:.14rem !important;
}
.watch-availability{
    min-height:2.35rem !important;
    max-height:2.35rem !important;
    margin:.12rem 0 .14rem !important;
}
.movie-description{
    min-height:4.35rem !important;
    max-height:4.35rem !important;
    margin-top:.04rem !important;
    margin-bottom:.26rem !important;
}
.movie-card-actions{
    margin-top:.12rem !important;
    margin-bottom:.18rem !important;
}

/* Continue CTAs: larger physical target with restrained label size. */
.st-key-continue_rate,
.st-key-continue_taste{
    margin-top:.5rem !important;
}
.st-key-continue_rate button,
.st-key-continue_taste button,
.st-key-enter_showroom button{
    min-height:3.55rem !important;
    padding:.9rem 1.7rem !important;
    border-radius:18px !important;
}
.st-key-continue_rate button p,
.st-key-continue_taste button p,
.st-key-enter_showroom button p{
    font-size:.76rem !important;
    line-height:1.1 !important;
    font-weight:650 !important;
    margin:0 !important;
}

/* V5.75 interaction + Preference Analysis spacing polish */
/* Keep the analysis compact enough for one view while using a more even rhythm. */
.profile-wrap{padding-bottom:.18rem !important}
.profile-heading{margin-bottom:.28rem !important}
.profile-intro{margin-bottom:.7rem !important}
.profile-block + .profile-block{margin-top:.92rem !important}
.profile-label{margin-bottom:.34rem !important}
.profile-chip-wrap{row-gap:.38rem !important}
.profile-analysis{gap:.34rem !important}
.profile-summary{
    margin-top:.92rem !important;
    margin-bottom:.58rem !important;
    padding-top:.9rem !important;
}
/* Build Profile gets the same large-target / restrained-label treatment. */
.st-key-build_profile{margin-top:.5rem !important}
.st-key-build_profile button{
    min-height:3.55rem !important;
    padding:.9rem 1.7rem !important;
    border-radius:18px !important;
}
.st-key-build_profile button p{
    font-size:.76rem !important;
    line-height:1.1 !important;
    font-weight:650 !important;
    margin:0 !important;
}

/* V5.77 Cinema Profile wording + balanced one-page rhythm */
.profile-heading{margin-bottom:.32rem !important}
.profile-intro{
    margin-bottom:.72rem !important;
    max-width:720px !important;
    line-height:1.42 !important;
}
.profile-grid{padding-top:.82rem !important}
.profile-block + .profile-block{margin-top:1.02rem !important}
.profile-label{margin-bottom:.38rem !important}
.profile-chip-wrap{row-gap:.4rem !important}
.profile-analysis{gap:.36rem !important}
.profile-summary{
    margin-top:1.02rem !important;
    margin-bottom:.66rem !important;
    padding-top:.96rem !important;
    max-width:760px !important;
    font-size:.96rem !important;
    line-height:1.5 !important;
}
</style>
""", unsafe_allow_html=True)

defaults={
    "screen":"welcome","onboarding_complete":False,"likes":set(),"favorites":set(),"review_priority":50,
    "genres":[],"adventure":50,"more_of":[],"saved":set(),"seen":set(),"dismissed":set(),
    "custom_like":None,"search_selected_title":None,"search_selected_movie":None,"external_movies":{}
}
for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k]=v.copy() if isinstance(v,(set,dict)) else (list(v) if isinstance(v,list) else v)

PROFILE_STORAGE_KEY = "icinema_profile_v1"

def profile_snapshot():
    return {
        "version": 1,
        "onboarding_complete": bool(st.session_state.onboarding_complete),
        "likes": sorted(st.session_state.likes),
        "favorites": sorted(st.session_state.favorites),
        "review_priority": st.session_state.review_priority,
        "genres": list(st.session_state.genres),
        "adventure": st.session_state.adventure,
        "more_of": list(st.session_state.more_of),
        "saved": sorted(st.session_state.saved),
        "seen": sorted(st.session_state.seen),
        "dismissed": sorted(st.session_state.dismissed),
        "external_movies": st.session_state.external_movies,
    }

def restore_profile(data):
    if not isinstance(data, dict):
        return False
    try:
        st.session_state.likes = set(data.get("likes") or [])
        st.session_state.favorites = set(data.get("favorites") or [])
        st.session_state.review_priority = int(data.get("review_priority", 50))
        st.session_state.genres = list(data.get("genres") or [])
        st.session_state.adventure = int(data.get("adventure", 50))
        st.session_state.more_of = list(data.get("more_of") or [])
        st.session_state.saved = set(data.get("saved") or [])
        st.session_state.seen = set(data.get("seen") or [])
        st.session_state.dismissed = set(data.get("dismissed") or [])
        st.session_state.external_movies = dict(data.get("external_movies") or {})
        st.session_state.onboarding_complete = bool(data.get("onboarding_complete", False))
        if st.session_state.onboarding_complete:
            st.session_state.screen = "showroom"
        return True
    except (TypeError, ValueError):
        return False

# Hydrate once per browser session before rendering the product. The component stores
# only recommendation/profile state in this browser's localStorage.
if not st.session_state.get("_storage_hydrated", False):
    _stored = browser_storage("get", PROFILE_STORAGE_KEY, key="icinema_profile_loader")
    if not (isinstance(_stored, dict) and _stored.get("loaded") is True):
        logo_placeholder = '<div class="icinema-logo">iCinema</div><div style="color:#858B96;font-size:.86rem">Loading your cinema profile…</div>'
        st.markdown(logo_placeholder, unsafe_allow_html=True)
        st.stop()
    restored = restore_profile(_stored.get("value")) if _stored.get("value") else False
    st.session_state._storage_hydrated = True
    st.session_state._last_persisted_profile = json.dumps(profile_snapshot(), sort_keys=True, default=str) if restored else None

# A profile-changing button may request an immediate rerun. Complete its
# localStorage write first, then continue rendering. This makes refreshes, tab
# closes/reopens, and Streamlit restarts reliably restore the latest profile.
_pending_profile = st.session_state.get("_pending_profile_save")
if _pending_profile is not None:
    _pending_sig = json.dumps(_pending_profile, sort_keys=True, default=str)
    # localStorage writes are synchronous in the browser. Use the silent action
    # so the persistence component does not emit a second value-change rerun
    # after an ordinary Streamlit button interaction.
    browser_storage(
        "set_silent", PROFILE_STORAGE_KEY, value=_pending_profile, key="icinema_profile_pending_saver"
    )
    st.session_state._last_persisted_profile = _pending_sig
    st.session_state._pending_profile_save = None

def _snapshot_signature(snapshot):
    return json.dumps(snapshot, sort_keys=True, default=str)

def persist_profile_if_needed():
    if not st.session_state.get("_storage_hydrated", False):
        return
    snapshot = profile_snapshot()
    serialized = _snapshot_signature(snapshot)
    if serialized != st.session_state.get("_last_persisted_profile"):
        # Stable component key lets the browser acknowledge the write without
        # creating a new component instance on every ordinary render.
        browser_storage("set_silent", PROFILE_STORAGE_KEY, value=snapshot, key="icinema_profile_saver")
        st.session_state._last_persisted_profile = serialized
        st.session_state._pending_profile_save = None

def queue_profile_save():
    """Queue persistence without forcing an extra rerun.

    Every Streamlit widget interaction already causes one normal app rerun.
    Profile changes are written to localStorage during that same rerun, so we
    never trigger a second rerun just to persist state. This keeps selections
    visually stable and prevents the brief black/blank transition that can
    happen when explicit reruns are stacked on top of widget reruns.
    """
    st.session_state._pending_profile_save = profile_snapshot()

def toggle_shelf_like(title):
    liked = title in st.session_state.likes and title not in st.session_state.favorites
    if liked:
        st.session_state.likes.discard(title)
    else:
        st.session_state.likes.add(title)
        st.session_state.favorites.discard(title)
    queue_profile_save()

def toggle_shelf_favorite(title):
    fav = title in st.session_state.favorites
    if fav:
        st.session_state.favorites.discard(title)
        st.session_state.likes.discard(title)
    else:
        st.session_state.favorites.add(title)
        st.session_state.likes.add(title)
    queue_profile_save()

def add_search_choice(kind):
    movie = st.session_state.get("search_selected_movie")
    if not movie:
        return
    title = movie["title"]
    if movie.get("external"):
        st.session_state.external_movies[title] = movie
    st.session_state.likes.add(title)
    if kind == "favorite":
        st.session_state.favorites.add(title)
    else:
        st.session_state.favorites.discard(title)
    st.session_state.search_selected_movie = None
    st.session_state.search_selected_title = None
    queue_profile_save()

def go(screen):
    """Navigate using the widget's normal single rerun."""
    st.session_state.screen = screen
    if screen == "showroom":
        st.session_state.onboarding_complete = True
    queue_profile_save()

def go_from_fragment(screen):
    """Leave a fragment with one intentional page-level transition.

    Do not synchronously write browser storage before navigating. The next page
    render persists the queued snapshot, which avoids making Step 1 → 2 → 3 →
    Profile → Showroom transitions wait on the browser component first.
    """
    go(screen)
    st.rerun(scope="app")

def select_search_result(movie):
    st.session_state.search_selected_movie = movie
    st.session_state.search_selected_title = movie.get("title")

def set_review_priority(value):
    st.session_state.review_priority = value
    queue_profile_save()

def toggle_genre_choice(genre):
    selected = set(st.session_state.genres)
    if genre in selected:
        selected.discard(genre)
    elif len(selected) < 5:
        selected.add(genre)
    st.session_state.genres = list(selected)
    queue_profile_save()

def set_adventure_level(value):
    st.session_state.adventure = value
    queue_profile_save()

def toggle_priority_choice(option):
    selected = set(st.session_state.more_of)
    if option in selected:
        selected.discard(option)
    else:
        selected.add(option)
    st.session_state.more_of = list(selected)
    queue_profile_save()

def _remember_movie(movie):
    if not movie or not isinstance(movie, dict):
        return
    title = movie.get("title")
    if not title:
        return
    if movie.get("external") or not get_movie(title, {}):
        st.session_state.external_movies[title] = dict(movie)

def skip_movie(title, movie=None):
    _remember_movie(movie)
    st.session_state.dismissed.add(title)
    st.session_state.saved.discard(title)
    queue_profile_save()

def save_movie(title, movie=None):
    _remember_movie(movie)
    st.session_state.saved.add(title)
    st.session_state.seen.discard(title)
    st.session_state.dismissed.discard(title)
    queue_profile_save()

def mark_movie_seen(title, movie=None):
    _remember_movie(movie)
    st.session_state.seen.add(title)
    st.session_state.saved.discard(title)
    st.session_state.dismissed.discard(title)
    queue_profile_save()

def resolve_history_movie(title):
    movie = get_movie(title, st.session_state.external_movies)
    if movie:
        return movie
    if tmdb_catalog_configured():
        try:
            movie = find_movie(title)
        except Exception:
            movie = None
        if movie:
            st.session_state.external_movies[title] = movie
            queue_profile_save()
            return movie
    return None

def reset_profile_state():
    for k, v in defaults.items():
        st.session_state[k] = v.copy() if isinstance(v, (set, dict)) else (list(v) if isinstance(v, list) else v)
    st.session_state._last_persisted_profile = None
    queue_profile_save()

def reset_profile_from_fragment():
    reset_profile_state()
    persist_profile_if_needed()
    st.rerun(scope="app")

def logo():
    st.markdown('<div class="icinema-logo">iCinema</div>',unsafe_allow_html=True)

def movie_thumb(movie, poster_url=None):
    title = html.escape(str(movie.get("title", "")))
    year = html.escape(str(movie.get("year", "")))
    poster_url = poster_url or movie.get("poster_url")
    if poster_url:
        safe_url = html.escape(str(poster_url), quote=True)
        poster_html = f'<div class="poster has-image"><img src="{safe_url}" alt="Poster for {title}"></div>'
    else:
        poster_html = '<div class="poster"><div class="poster-placeholder-mark">iCINEMA</div></div>'

    year_html = f'<div class="poster-caption-year">{year}</div>' if year else ''
    st.markdown(
        poster_html
        + f'<div class="poster-caption"><div class="poster-caption-title">{title}</div>{year_html}</div>',
        unsafe_allow_html=True
    )

def current_profile():
    return build_profile(
        st.session_state.likes, st.session_state.favorites, st.session_state.genres,
        st.session_state.review_priority, st.session_state.more_of,
        st.session_state.saved, st.session_state.dismissed, st.session_state.adventure,
        st.session_state.external_movies, st.session_state.seen
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
        f'<div class="profile-intro">A detailed showing of the preferences, viewing patterns, and recommendation signals iCinema has learned from your choices.</div>'
        f'<div class="profile-grid">{section_html}</div>'
        f'<div class="profile-summary">{p["summary"]}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


@st.fragment
def render_shelf_fragment():
    logo()
    st.markdown("### Step 1 of 3 — Rate the Shelf")
    st.caption("Choose a few titles you already like. If none fit, search for one you know you enjoy.")

    starter_poster_map = get_poster_batch(tuple((m["title"], int(m["year"])) for m in STARTER_MOVIES))
    cols=st.columns(4)
    for i,movie in enumerate(STARTER_MOVIES):
        title=movie["title"]
        with cols[i%4]:
            movie_thumb(movie, starter_poster_map.get(title))
            st.markdown('<div class="shelf-action-gap"></div>', unsafe_allow_html=True)
            b1,b2=st.columns(2)
            liked=title in st.session_state.likes and title not in st.session_state.favorites
            fav=title in st.session_state.favorites
            with b1:
                st.button(
                    "Like",
                    key=f"like_{i}",
                    type="primary" if liked else "secondary",
                    use_container_width=True,
                    on_click=toggle_shelf_like,
                    args=(title,),
                )
            with b2:
                st.button(
                    "Favorite",
                    key=f"fav_{i}",
                    type="primary" if fav else "secondary",
                    use_container_width=True,
                    on_click=toggle_shelf_favorite,
                    args=(title,),
                )

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

    matches = []
    already_selected_matches = []
    if search_query.strip():
        if tmdb_catalog_configured():
            matches = search_movies(search_query.strip(), 8)
        else:
            q = search_query.strip().lower()
            local_titles = [title for title in searchable_titles() if q in title.lower()][:8]
            matches = [get_movie(title) for title in local_titles if get_movie(title)]

        selected_titles = st.session_state.likes | st.session_state.favorites
        already_selected_matches = [m for m in matches if m["title"] in selected_titles]
        matches = [m for m in matches if m["title"] not in selected_titles]

    selected_movie = st.session_state.search_selected_movie
    valid_ids = {m.get("tmdb_id") for m in matches if m.get("tmdb_id") is not None}
    valid_titles = {m["title"] for m in matches}
    if selected_movie:
        selected_valid = (selected_movie.get("tmdb_id") in valid_ids) if selected_movie.get("tmdb_id") is not None else (selected_movie.get("title") in valid_titles)
        if not selected_valid:
            st.session_state.search_selected_movie = None
            st.session_state.search_selected_title = None

    if search_query.strip():
        if matches:
            st.markdown('<div class="search-results-label">Matching titles</div>', unsafe_allow_html=True)
            result_cols = st.columns(2)
            for j, movie in enumerate(matches):
                title = movie["title"]
                year_label = f" ({movie['year']})" if movie.get("year") else ""
                selected_movie = st.session_state.search_selected_movie
                selected = bool(selected_movie and selected_movie.get("tmdb_id") == movie.get("tmdb_id") and movie.get("tmdb_id") is not None)
                with result_cols[j % 2]:
                    st.button(
                        f"{title}{year_label}",
                        key=f"search_result_{j}_{movie.get('tmdb_id') or title}",
                        type="primary" if selected else "secondary",
                        use_container_width=True,
                        on_click=select_search_result,
                        args=(movie,),
                    )

        if already_selected_matches:
            selected_name = already_selected_matches[0]["title"]
            state = "Favorite" if selected_name in st.session_state.favorites else "Liked"
            st.markdown(
                f'<div class="search-already-selected">'
                f'<strong>{html.escape(selected_name)}</strong> is already in your selections as {state.lower()}'
                f'</div>',
                unsafe_allow_html=True
            )

        if not matches and not already_selected_matches:
            if tmdb_catalog_configured():
                st.caption("No movie matches found")
            else:
                st.caption("TMDB search is unavailable, showing matches from the current iCinema catalog only")

    choice_movie = st.session_state.search_selected_movie
    if choice_movie:
        choice = choice_movie["title"]
        st.markdown(
            f'<div class="search-selected-card">'
            f'<div class="search-selected-kicker">Selected title</div>'
            f'<div class="search-selected-title">{html.escape(choice)}{f" ({choice_movie.get("year")})" if choice_movie.get("year") else ""}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        preview_cols = st.columns([1, 3])
        with preview_cols[0]:
            movie_thumb(choice_movie)
        with preview_cols[1]:
            a,b=st.columns([1,1])
            with a:
                st.button(
                    "Add as Like",
                    key="search_add_like",
                    use_container_width=True,
                    on_click=add_search_choice,
                    args=("like",),
                )
            with b:
                st.button(
                    "Add as Favorite",
                    key="search_add_favorite",
                    use_container_width=True,
                    on_click=add_search_choice,
                    args=("favorite",),
                )

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
    st.button("Continue →", type="primary", disabled=chosen_count==0, key="continue_rate", on_click=go_from_fragment, args=("taste",))


    persist_profile_if_needed()

@st.fragment
def render_taste_fragment():
    logo()
    st.markdown(
        '<div class="step2-header">'
        '<div class="step2-title">Step 2 of 3 — Tailor Your Preferences</div>'
        '<div class="step2-subtitle">Choose what matters most when deciding what to watch</div>'
        '</div>'
        '<div class="step2-question">Which matters more?</div>',
        unsafe_allow_html=True,
    )

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

    review_button_labels = ["Reviews first", "Lean reviews", "Balanced", "Lean enjoyment", "Enjoyment first"]
    st.markdown('<div class="pref-scale-clicks">', unsafe_allow_html=True)
    review_cols = st.columns(5, gap="small")
    for i, value in enumerate(review_scale_map):
        with review_cols[i]:
            st.button(
                review_button_labels[i],
                key=f"review_scale_{i}",
                type="primary" if i == review_idx else "secondary",
                use_container_width=True,
                on_click=set_review_priority,
                args=(value,),
            )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("#### What do you like to watch?")
    st.markdown('<div class="genre-helper">Select up to five genres</div>', unsafe_allow_html=True)
    selected=set(st.session_state.genres)
    genre_cols=st.columns(7, gap="small")
    for i,genre in enumerate(GENRES):
        with genre_cols[i%7]:
            active=genre in selected
            st.button(
                genre,
                key=f"genre_{i}",
                type="primary" if active else "secondary",
                use_container_width=True,
                on_click=toggle_genre_choice,
                args=(genre,),
            )

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

    adventure_button_labels = ["Very familiar", "Mostly familiar", "Balanced", "More discovery", "Very different"]
    st.markdown('<div class="pref-scale-clicks">', unsafe_allow_html=True)
    adventure_cols = st.columns(5, gap="small")
    for i, value in enumerate(adventure_scale_map):
        with adventure_cols[i]:
            st.button(
                adventure_button_labels[i],
                key=f"adventure_scale_{i}",
                type="primary" if i == adventure_idx else "secondary",
                use_container_width=True,
                on_click=set_adventure_level,
                args=(value,),
            )
    st.markdown('</div>', unsafe_allow_html=True)

    st.button("Continue →", type="primary", key="continue_taste", on_click=go_from_fragment, args=("more",))


    persist_profile_if_needed()

@st.fragment
def render_more_fragment():
    logo()
    st.markdown("### Step 3 of 3 — Shape Your Showroom")
    st.caption("What should iCinema lean toward? Choose any that you want to see more often")

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
            st.button(
                f"**{option}**  \n{descriptions[option]}",
                key=f"priority_card_{'active_' if active else ''}{i}",
                use_container_width=True,
                type="secondary",
                on_click=toggle_priority_choice,
                args=(option,),
            )

    st.session_state.more_of = list(selected)

    st.button("Build My Cinema Profile →", type="primary", key="build_profile", on_click=go_from_fragment, args=("profile",))


    persist_profile_if_needed()


@st.fragment
def render_showroom_fragment(p):
    tabs=st.tabs(["Showroom",f"Saved ({len(st.session_state.saved)})",f"Seen ({len(st.session_state.seen)})","Profile"])

    excluded=st.session_state.saved|st.session_state.seen|st.session_state.dismissed

    # Build a deep candidate pool, then rank every candidate with the same iCinema
    # personalization algorithm. TMDB discovery acts only as replenishment: it does not
    # bypass the user's profile, and excluded Save/Seen/Skip titles stay excluded.
    # Rotate deeper into TMDB as a user skips more titles, so the showroom keeps
    # replenishing instead of exhausting one fixed discovery slice.
    discovery_start_page = 1 + (len(st.session_state.dismissed) // 80) * 8
    external_pool = []
    if tmdb_catalog_configured():
        try:
            external_pool = discover_movies(640, discovery_start_page)
        except TypeError:
            # Backward-compatible fallback if Streamlit is briefly serving an
            # older cached module during a deployment. Never take down Showroom.
            try:
                external_pool = discover_movies(640)
            except Exception:
                external_pool = []
        except Exception:
            external_pool = []
    candidate_pool = list(CATALOG) + list(st.session_state.external_movies.values()) + external_pool
    ranked = rank_movies(
        candidate_pool,
        p,
        st.session_state.adventure,
        st.session_state.review_priority,
        excluded,
        None,
    )

    def _safe_num(value, default=0):
        try:
            return float(value) if value is not None else default
        except (TypeError, ValueError):
            return default

    def _row_signal(row_name, movie):
        """Section-specific signal layered on the same learned iCinema profile."""
        tags=set(movie.get("tags", []))
        popularity=max(0.0, _safe_num(movie.get("popularity"), 0.0))
        rt=_safe_num(movie.get("rt"), -1.0)
        imdb=_safe_num(movie.get("imdb"), -1.0)
        tmdb_vote=_safe_num(movie.get("tmdb_vote"), -1.0)
        year=int(_safe_num(movie.get("year"), 0))

        if row_name=="Critically Acclaimed":
            critic=(rt/100.0) if rt>=0 else 0.5
            audience_vals=[]
            if imdb>=0: audience_vals.append(imdb/10.0)
            if tmdb_vote>=0: audience_vals.append(tmdb_vote/10.0)
            audience=sum(audience_vals)/len(audience_vals) if audience_vals else 0.5
            tagged=1.0 if "Critically Acclaimed" in tags else 0.0
            return max(0.0,min(1.0,0.50*critic+0.35*audience+0.15*tagged))

        if row_name=="Hidden Gems":
            # Prefer lower-popularity titles with discovery-oriented metadata, while
            # keeping enough quality evidence to avoid rewarding obscurity by itself.
            obscurity=1.0/(1.0+popularity/28.0) if popularity else 0.58
            hidden=1.0 if "Hidden Gem" in tags else 0.0
            discovery_tags={"International","Offbeat","Slow-burn","Psychological","Documentary","Grounded","Cerebral"}
            discovery=min(1.0,len(discovery_tags.intersection(tags))/2.0)
            quality=max(0.0,min(1.0,((rt/100.0) if rt>=0 else ((imdb/10.0) if imdb>=0 else 0.55))))
            return max(0.0,min(1.0,0.42*obscurity+0.24*hidden+0.18*discovery+0.16*quality))

        if row_name=="Something Different":
            preferred=set(p.get("genres", []))
            genre_novelty=0.0 if movie.get("genre") in preferred else 1.0
            language_novelty=1.0 if str(movie.get("original_language") or "en").lower() not in {"", "en"} else 0.0
            era_novelty=1.0 if year and (year<=2005 or year>=2023) else 0.35
            obscurity=1.0/(1.0+popularity/40.0) if popularity else 0.45
            return max(0.0,min(1.0,0.52*genre_novelty+0.20*language_novelty+0.14*era_novelty+0.14*obscurity))

        return 1.0

    def _row_candidates(row_name, already_used):
        available=[item for item in ranked if item[1]["title"] not in already_used]
        scored=[]
        for display_match,movie in available:
            components=score_movie_components(movie,p,st.session_state.adventure,st.session_state.review_priority)
            base=components["raw_score"]
            section=_row_signal(row_name,movie)
            # The learned profile remains dominant in every row. The section signal
            # changes the objective, not the underlying personalization system.
            if row_name=="Top Matches for You":
                objective=base
            elif row_name=="Critically Acclaimed":
                objective=0.70*base+0.30*section
            elif row_name=="Hidden Gems":
                objective=0.72*base+0.28*section
            else:  # Something Different
                objective=0.68*base+0.32*section
            scored.append((objective,base,display_match,movie))

        # Section objective chooses membership. Within that objective, stronger core
        # personalized fit breaks ties, so every row remains grounded in the same model.
        scored.sort(key=lambda x:(x[0],x[1]),reverse=True)
        return [(display_match,movie) for _,_,display_match,movie in scored]

    # Reserve distinct movies for each row before rendering. This prevents a title from
    # migrating into another section during the same refresh and keeps every row populated.
    row_order=["Top Matches for You","Critically Acclaimed","Hidden Gems","Something Different"]
    row_choices={name: [] for name in row_order}
    reserved=set()

    # Pass 1: category-specific ordering with strict cross-row de-duplication.
    for row_name in row_order:
        picks=_row_candidates(row_name,reserved)[:4]
        row_choices[row_name].extend(picks)
        reserved.update(movie["title"] for _,movie in picks)

    # Pass 2: if any category pool is thin, fill it with the next-best personalized
    # candidates that have not appeared elsewhere. This keeps every section alive.
    for row_name in row_order:
        need=4-len(row_choices[row_name])
        if need<=0:
            continue
        fallback=[item for item in ranked if item[1]["title"] not in reserved]
        extra=fallback[:need]
        row_choices[row_name].extend(extra)
        reserved.update(movie["title"] for _,movie in extra)

    visible_movies=[movie for row_name in ["Top Matches for You","Critically Acclaimed","Hidden Gems","Something Different"] for _,movie in row_choices.get(row_name,[])]
    visible_movie_keys=tuple((movie["title"], int(movie.get("year") or 0)) for movie in visible_movies)
    watch_by_title=get_watch_availability_batch(visible_movie_keys,"US")
    showroom_poster_map=get_poster_batch(visible_movie_keys)
    live_ratings_by_title=get_live_ratings_batch(visible_movie_keys)

    row_specs=["Top Matches for You","Critically Acclaimed","Hidden Gems","Something Different"]

    with tabs[0]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        for row_index,row_name in enumerate(row_specs):
            choices=row_choices.get(row_name,[])
            row_class = "showroom-row first" if row_index == 0 else "showroom-row"
            st.markdown(f'<div class="{row_class}"><h3>{row_name}</h3></div>', unsafe_allow_html=True)
            if not choices:
                st.caption("Refreshing personalized matches…")
                continue
            cols=st.columns(len(choices))
            for i,(match,movie) in enumerate(choices):
                with cols[i]:
                    skip_spacer, skip_col = st.columns([3.45,1.55], gap="small")
                    with skip_col:
                        st.markdown('<div class="showroom-skip-row">', unsafe_allow_html=True)
                        st.button(
                            "Skip",
                            key=f"skip_{row_name}_{movie['title']}",
                            use_container_width=True,
                            on_click=skip_movie,
                            args=(movie["title"], movie),
                        )
                        st.markdown('</div>', unsafe_allow_html=True)
                    movie_thumb(movie, showroom_poster_map.get(movie["title"]))
                    st.markdown(f'<div class="match">{match}% iCinema Match</div>',unsafe_allow_html=True)
                    live_rating = live_ratings_by_title.get(movie["title"], {})
                    imdb_value = live_rating.get("imdb")
                    rt_value = live_rating.get("rt")
                    imdb_text = f"{imdb_value:.1f}" if isinstance(imdb_value, (int, float)) else "—"
                    rt_text = f"{int(rt_value)}%" if isinstance(rt_value, (int, float)) else "—"
                    rating_class = "ratings" if live_rating else "ratings muted"
                    st.markdown(f'<div class="{rating_class}">IMDb {imdb_text} · RT {rt_text}</div>',unsafe_allow_html=True)
                    availability = watch_by_title.get(movie["title"], {"status":"unknown","text":"Where to watch: availability unavailable","url":None})
                    availability_class = "watch-availability muted" if availability.get("status") in {"unknown", "not_configured", "unavailable"} else "watch-availability"
                    st.markdown(f'<div class="{availability_class}">{availability["text"]}</div>', unsafe_allow_html=True)
                    short_desc = concise_description(movie["why"])
                    st.markdown(f'<div class="movie-description">{short_desc}</div>',unsafe_allow_html=True)
                    st.markdown('<div class="movie-card-actions">', unsafe_allow_html=True)
                    a,b=st.columns(2, gap="small")
                    with a:
                        st.button(
                            "Save",
                            key=f"save_{row_name}_{movie['title']}",
                            use_container_width=True,
                            on_click=save_movie,
                            args=(movie["title"], movie),
                        )
                    with b:
                        st.button(
                            "Seen",
                            key=f"seen_{row_name}_{movie['title']}",
                            use_container_width=True,
                            on_click=mark_movie_seen,
                            args=(movie["title"], movie),
                        )
                    st.markdown('</div>', unsafe_allow_html=True)
        rating_note = "" if omdb_configured() else " IMDb and Rotten Tomatoes ratings require OMDB_API_KEY in Streamlit Secrets."
        st.markdown(
            '<div class="watch-attribution">Streaming availability for the United States. Data by JustWatch via TMDB. '
            'IMDb and Rotten Tomatoes ratings are retrieved through OMDb and cached for 14 days. '
            'This product uses the TMDB API but is not endorsed or certified by TMDB.' + rating_note + '</div>',
            unsafe_allow_html=True
        )

    with tabs[1]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        st.markdown('<div class="tab-section-heading">Saved</div>', unsafe_allow_html=True)
        movies=[m for t in st.session_state.saved if (m := resolve_history_movie(t))]
        saved_poster_map = get_poster_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies))
        if not movies:st.caption("Nothing saved yet.")
        else:
            cols=st.columns(4, gap="medium")
            for i,m in enumerate(movies):
                with cols[i % 4]:
                    movie_thumb(m, m.get("poster_url") or saved_poster_map.get(m["title"]))
                    st.button(
                        "Mark Seen",
                        key=f"savedseen_{m['title']}",
                        use_container_width=True,
                        on_click=mark_movie_seen,
                        args=(m["title"], m),
                    )

    with tabs[2]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        st.markdown('<div class="tab-section-heading">Seen</div>', unsafe_allow_html=True)
        movies=[m for t in st.session_state.seen if (m := resolve_history_movie(t))]
        seen_poster_map = get_poster_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies))
        if not movies:st.caption("Nothing marked as seen yet.")
        else:
            cols=st.columns(4, gap="medium")
            for i,m in enumerate(movies):
                with cols[i % 4]:
                    movie_thumb(m, m.get("poster_url") or seen_poster_map.get(m["title"]))

    with tabs[3]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        render_cinema_profile(p)
        st.markdown('<div class="profile-tab-reset"></div>', unsafe_allow_html=True)
        st.button("Reset Profile", key="reset_profile_tab", on_click=reset_profile_from_fragment)


    persist_profile_if_needed()

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
    st.button("Start Personalizing →", type="primary", key="start_personalizing", on_click=go, args=("shelf",))

elif screen=="shelf":
    render_shelf_fragment()

elif screen=="taste":
    render_taste_fragment()

elif screen=="more":
    render_more_fragment()

elif screen=="profile":
    logo()
    p=current_profile()
    render_cinema_profile(p)

    st.button("Enter My Showroom →", type="primary", key="enter_showroom", on_click=go, args=("showroom",))

elif screen=="showroom":
    logo()
    p=current_profile()
    st.markdown(
        '<div class="showroom-header">'
        '<div class="showroom-heading">Your Showroom of Movies</div>'
        '<div class="showroom-intro">Personalized to your taste and refined with every save, skip, and title you mark as seen</div>'
        '</div>',
        unsafe_allow_html=True
    )

    render_showroom_fragment(p)

# Persist the latest profile/history after the page has processed this run.
persist_profile_if_needed()
