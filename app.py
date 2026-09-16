
import html
import json
import re
import streamlit as st
from src.recommender import (
    STARTER_MOVIES, GENRES, MORE_OF_OPTIONS, searchable_titles, get_movie,
    build_profile, score_movie, recommend, rank_movies, score_movie_components, CATALOG,
    recommendation_explanation, profile_confidence_label, mmr_rerank, availability_utility
)
from src.analytics import ensure_session, start_new_session, record_event, record_impressions, analytics_insights
from src.ml_engine import train_learning_model, predict_success, ranking_metrics, calibration_metrics
from src.watch_providers import get_watch_availability_batch, tmdb_configured
from src.tmdb_catalog import search_movies, get_poster_batch, get_movie_identity_batch, tmdb_catalog_configured, discover_movies
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

/* V5.84 global spacing polish */
/* One consistent logo-to-first-heading rhythm across every page. */
.icinema-logo{margin-bottom:1.05rem !important}
.hero-title{margin-top:0 !important}
.page-top-heading,
.step2-title,
.profile-heading,
.showroom-heading{margin-top:0 !important}
.page-top-heading{
    color:var(--ivory);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:2rem;
    line-height:1.08;
    font-weight:760;
    letter-spacing:-.03em;
    margin-bottom:.48rem;
}
.page-top-subtitle{
    color:var(--muted);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:.93rem;
    line-height:1.5;
    font-weight:450;
    margin:0 0 1.35rem;
    max-width:760px;
}
.step2-header{margin-top:0 !important}
.profile-wrap{margin-top:0 !important}
.showroom-header{margin-top:0 !important}

/* Consistent Showroom row spacing and calmer card information hierarchy. */
.showroom-row{
    margin-top:1.18rem !important;
    margin-bottom:.32rem !important;
}
.showroom-row.first{margin-top:.28rem !important}
.showroom-row h3{
    margin:0 0 .5rem !important;
    line-height:1.15 !important;
}
.poster-caption{
    min-height:3.75rem !important;
    margin-top:.62rem !important;
    margin-bottom:.24rem !important;
}
.match{
    min-height:1.45rem !important;
    margin-top:.22rem !important;
    margin-bottom:.08rem !important;
}
.ratings{
    min-height:1.25rem !important;
    margin-top:.04rem !important;
    margin-bottom:.28rem !important;
}
.watch-availability{
    min-height:2.5rem !important;
    max-height:2.5rem !important;
    margin:.3rem 0 .42rem !important;
    line-height:1.35 !important;
}
.movie-description{
    min-height:4.85rem !important;
    max-height:4.85rem !important;
    line-height:1.48 !important;
    margin-top:0 !important;
    margin-bottom:.58rem !important;
}
.movie-card-actions{
    margin-top:.42rem !important;
    margin-bottom:.24rem !important;
}

/* V5.90 showroom text-fit polish: preserve alignment without clipping streaming or descriptions. */
.watch-availability{
    min-height:3.45rem !important;
    max-height:3.45rem !important;
    margin:.28rem 0 .42rem !important;
    line-height:1.35 !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    overflow-wrap:anywhere !important;
}
.movie-description{
    min-height:6.2rem !important;
    max-height:6.2rem !important;
    line-height:1.48 !important;
    margin-top:0 !important;
    margin-bottom:.58rem !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:4 !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    overflow-wrap:anywhere !important;
}

/* Saved / Seen library cards: same poster size, tighter caption-to-action rhythm. */
.library-poster-caption{
    min-height:0 !important;
    margin:.56rem 0 .32rem !important;
    padding:0 .05rem !important;
}
.library-poster-caption .poster-caption-title{
    margin:0 !important;
    line-height:1.16 !important;
}
.library-poster-caption .poster-caption-year{
    margin-top:.10rem !important;
    min-height:0 !important;
}
[class*="st-key-savedseen_"], [class*="st-key-unsave_"]{margin-top:.08rem !important}
[class*="st-key-savedseen_"] button, [class*="st-key-unsave_"] button{min-height:2.6rem !important}
.tab-section-heading{margin-bottom:1rem !important}

/* V5.92 title/year rhythm: keep year directly under title without losing card alignment. */
.poster-caption-title{
    min-height:0 !important;
}
.poster-caption-year{
    margin-top:.10rem !important;
}
.library-poster-caption .poster-caption-title{
    min-height:0 !important;
    max-height:none !important;
}
.library-poster-caption .poster-caption-year{
    margin-top:.08rem !important;
}

/* V5.93 library + text polish: Saved and Seen get independent spacing rules. */
.saved-poster-caption{
    margin:.64rem 0 .48rem !important;
    min-height:0 !important;
    padding:0 .05rem !important;
}
.saved-poster-caption .poster-caption-title{
    margin:0 !important;
    line-height:1.16 !important;
    min-height:0 !important;
    max-height:none !important;
}
.saved-poster-caption .poster-caption-year{
    margin-top:.18rem !important;
    min-height:0 !important;
}
.seen-poster-caption{
    margin:.62rem 0 .40rem !important;
    min-height:0 !important;
    padding:0 .05rem !important;
}
.seen-poster-caption .poster-caption-title{
    margin:0 !important;
    line-height:1.16 !important;
    min-height:0 !important;
    max-height:none !important;
}
.seen-poster-caption .poster-caption-year{
    margin-top:.26rem !important;
    min-height:0 !important;
}
[class*="st-key-savedseen_"], [class*="st-key-unsave_"]{
    margin-top:.38rem !important;
}
/* Render complete, concise text. No CSS-generated ellipsis/clipping. */
.watch-availability{
    min-height:3.15rem !important;
    max-height:none !important;
    margin:.28rem 0 .38rem !important;
    line-height:1.35 !important;
    display:block !important;
    overflow:visible !important;
    text-overflow:clip !important;
    overflow-wrap:anywhere !important;
}
.movie-description{
    min-height:5.55rem !important;
    max-height:none !important;
    line-height:1.46 !important;
    margin-top:0 !important;
    margin-bottom:.52rem !important;
    display:block !important;
    overflow:visible !important;
    text-overflow:clip !important;
    overflow-wrap:anywhere !important;
}


/* V5.86 onboarding compactness + profile spacing + hidden persistence bridge */
/* The localStorage component is functional-only; keep its iframe/container invisible so
   ordinary selections never flash a small black rectangle near the bottom of the page. */
div[data-testid="stCustomComponentV1"]{
    height:0 !important;
    min-height:0 !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
    position:relative !important;
}
div[data-testid="stCustomComponentV1"] iframe{
    position:absolute !important;
    width:1px !important;
    height:1px !important;
    min-height:0 !important;
    border:0 !important;
    opacity:0 !important;
    pointer-events:none !important;
}

/* Step 1: slightly denser without changing the poster treatment. */
.shelf-action-gap{height:.30rem !important}
[class*="st-key-like_"] button,
[class*="st-key-fav_"] button{
    min-height:1.92rem !important;
    padding:.28rem .2rem !important;
}
.search-shell{
    margin-top:1.10rem !important;
    margin-bottom:.50rem !important;
    padding:1.05rem 1rem 1rem !important;
}
.selection-area{margin-top:.78rem !important;margin-bottom:.88rem !important}
div[data-testid="stTextInput"]{margin-top:.2rem !important;margin-bottom:.22rem !important}
.st-key-continue_rate{margin-top:.32rem !important}

/* Step 2: preserve readability while pulling the full step closer to one viewport. */
.step2-header{margin-bottom:.82rem !important}
.step2-title{margin-bottom:.34rem !important}
.step2-question{margin:.04rem 0 .48rem !important}
.pref-scale-wrap{margin:.26rem 0 .54rem !important}
.pref-scale-ends{margin-bottom:.34rem !important}
.pref-scale-helper{margin-top:.52rem !important}
.pref-scale-clicks{margin-top:.46rem !important;margin-bottom:1.02rem !important}
.pref-scale-clicks div.stButton>button{
    min-height:3.35rem !important;
    height:3.35rem !important;
}
.genre-helper{margin:.08rem 0 .52rem !important}
[class*="st-key-genre_"] button{
    margin:.04rem 0 .26rem !important;
}
.st-key-continue_taste{margin-top:.26rem !important}

/* Cinema Profile: slightly more breathing room than V5.77, while staying page-friendly. */
.profile-intro{margin-bottom:.82rem !important}
.profile-grid{padding-top:.96rem !important}
.profile-block + .profile-block{margin-top:1.16rem !important}
.profile-label{margin-bottom:.42rem !important}
.profile-summary{
    margin-top:1.12rem !important;
    padding-top:1.02rem !important;
    margin-bottom:.66rem !important;
}


/* V5.88 profile header alignment + durable Step 1 selections */
.profile-wrap{
    margin-left:0 !important;
    padding-left:0 !important;
}
.profile-heading,
.profile-intro,
.profile-grid,
.profile-summary{
    margin-left:0 !important;
    padding-left:0 !important;
}
.profile-heading{
    margin-bottom:.72rem !important;
}
.profile-intro{
    margin-top:0 !important;
}

/* V5.101 Cinema Profile spacing: shared by standalone profile and Showroom Profile tab. */
.profile-wrap{
    padding-bottom:.42rem !important;
}
.profile-heading{
    margin-bottom:.78rem !important;
}
.profile-intro{
    margin-bottom:1.18rem !important;
    line-height:1.48 !important;
}
.profile-grid{
    padding-top:.18rem !important;
}
.profile-block + .profile-block{
    margin-top:1.42rem !important;
}
.profile-label{
    margin-bottom:.5rem !important;
}
.profile-chip-wrap{
    row-gap:.46rem !important;
    column-gap:.52rem !important;
}
.profile-analysis{
    gap:.44rem !important;
}
.profile-summary{
    margin-top:1.48rem !important;
    padding-top:1.18rem !important;
    margin-bottom:.88rem !important;
    line-height:1.5 !important;
}
@media (max-width:800px){
    .profile-intro{margin-bottom:1.02rem !important;}
    .profile-block + .profile-block{margin-top:1.22rem !important;}
    .profile-summary{margin-top:1.28rem !important;padding-top:1.02rem !important;}
}

/* V5.94 Showroom vertical rhythm: balanced spacing without stretching cards */
.poster-caption{
    margin-top:.68rem !important;
    margin-bottom:.12rem !important;
}
.poster-caption-year{
    margin-top:.28rem !important;
}
.match{
    margin-top:.48rem !important;
    margin-bottom:.02rem !important;
}
.ratings{
    margin-top:.04rem !important;
    margin-bottom:.28rem !important;
}
.watch-availability{
    margin-top:.26rem !important;
    margin-bottom:.28rem !important;
    min-height:2.35rem !important;
}
.movie-description{
    margin-top:.24rem !important;
    margin-bottom:.36rem !important;
    min-height:5.35rem !important;
    line-height:1.42 !important;
}
.movie-card-actions{
    margin-top:.28rem !important;
}

/* V5.96 Showroom action alignment: exact vertical slots keep every action row level. */
/* Keep title/year visually close while reserving a consistent total caption slot. */
.showroom-row ~ div .poster-caption,
.poster-caption:not(.library-poster-caption){
    height:4.35rem !important;
    min-height:4.35rem !important;
    box-sizing:border-box !important;
    overflow:hidden !important;
}
/* Ratings and match are one-line slots. */
.match{
    height:1.55rem !important;
    min-height:1.55rem !important;
    box-sizing:border-box !important;
}
.ratings{
    height:1.48rem !important;
    min-height:1.48rem !important;
    box-sizing:border-box !important;
}
/* Streaming and description get exact slots rather than variable minimum heights. */
.watch-availability{
    height:2.75rem !important;
    min-height:2.75rem !important;
    max-height:2.75rem !important;
    box-sizing:border-box !important;
    overflow:hidden !important;
}
.movie-description{
    height:5.05rem !important;
    min-height:5.05rem !important;
    max-height:5.05rem !important;
    box-sizing:border-box !important;
    overflow:hidden !important;
}
.movie-card-actions{
    margin-top:.12rem !important;
    margin-bottom:.08rem !important;
}

/* V5.97 tighter showroom vertical rhythm while preserving fixed alignment */
.showroom-row{
    margin-top:.82rem !important;
    margin-bottom:.14rem !important;
}
.showroom-row.first{margin-top:.22rem !important}
.showroom-row h3{margin-bottom:.34rem !important}


/* V5.98 onboarding transition + spacing polish */
/* Step 2: give the intro and first question a clearer visual break. */
.step2-header{
    margin-bottom:1.22rem !important;
}
.step2-question{
    margin-top:.10rem !important;
}
/* Keep Continue clearly separated from the final Step 2 preference block. */
.st-key-continue_taste{
    margin-top:.88rem !important;
}
/* Step 3: add breathing room between the prompt and the six selection cards. */
.step3-subtitle{
    margin-bottom:2.02rem !important;
}

/* V5.99: keep all Showroom tabs starting at the same vertical position. */
.showroom-tab-start{
    height:1.9rem !important;
}
.showroom-row.first{
    margin-top:0 !important;
}
.tab-section-heading{
    margin-top:0 !important;
}

/* V5.100 final onboarding + tab alignment polish */
/* Step 1: pull Like/Favorite closer to the year without changing card sizing. */
.shelf-action-gap{height:0 !important;}
[class*="st-key-like_"],
[class*="st-key-fav_"]{
    margin-top:-.24rem !important;
}

/* Step 3: ordinary card clicks stay fragment-local; persistence occurs on the
   page transition, preventing the browser-storage bridge from flashing. */

/* The larger Top Matches heading rendered visually lower than the Saved/Seen
   headings even with the same spacer. Lift only that first heading so its top
   edge matches the other tabs. */
.showroom-row.first{
    transform:translateY(-1.65rem) !important;
    margin-bottom:-1.2rem !important;
}


/* V5.102 compact showroom controls + tighter card rhythm */
.showroom-top-controls{
    margin-bottom:.12rem !important;
}
.match-pill{
    width:100%;
    min-height:1.5rem;
    height:1.5rem;
    border:1px solid #4A4F57;
    border-radius:999px;
    display:flex;
    align-items:center;
    justify-content:center;
    box-sizing:border-box;
    padding:.14rem .34rem;
    color:var(--ivory);
    font-family:var(--ui-font);
    font-size:.63rem;
    font-weight:700;
    line-height:1;
    white-space:nowrap;
}
/* With match moved above the poster, keep title/year compact and pull ratings up. */
.showroom-row ~ div .poster-caption,
.poster-caption:not(.library-poster-caption){
    height:4.02rem !important;
    min-height:4.02rem !important;
}
.ratings{
    margin-top:.12rem !important;
    margin-bottom:.24rem !important;
}
/* Bring actions closer to the description while keeping exact alignment. */
.movie-description{
    height:4.55rem !important;
    min-height:4.55rem !important;
    max-height:4.55rem !important;
}
.movie-card-actions{
    margin-top:.04rem !important;
}
[class*="st-key-skip_"]{
    margin-top:-.04rem !important;
    margin-bottom:-.16rem !important;
}
.showroom-skip-row{
    height:1.52rem !important;
    margin-bottom:0 !important;
}


/* V5.104 final control alignment + clean Showroom transition */
/* Step 1: keep Like/Favorite close to the title/year block. */
[class*="st-key-like_"],
[class*="st-key-fav_"]{
    margin-top:-.78rem !important;
}

/* iCinema Match and Skip share one clean horizontal control row.
   Match is intentionally more prominent, while Skip stays centered. */
[data-testid="stMarkdownContainer"]:has(.match-pill){
    margin:0 !important;
    padding:0 !important;
    min-height:1.95rem !important;
    height:1.95rem !important;
    display:flex !important;
    align-items:center !important;
}
.match-pill{
    width:100% !important;
    min-height:1.95rem !important;
    height:1.95rem !important;
    padding:.22rem .58rem !important;
    border-radius:999px !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    box-sizing:border-box !important;
    font-family:var(--ui-font, -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif) !important;
    color:var(--ivory) !important;
    font-size:.72rem !important;
    font-weight:700 !important;
    letter-spacing:0 !important;
    line-height:1 !important;
    text-align:center !important;
    margin:0 !important;
    white-space:nowrap !important;
}
[class*="st-key-skip_"]{
    margin:0 !important;
    padding:0 !important;
    width:100% !important;
    min-height:1.95rem !important;
    height:1.95rem !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
}
[class*="st-key-skip_"] button{
    width:100% !important;
    min-height:1.95rem !important;
    height:1.95rem !important;
    padding:.18rem .58rem !important;
    margin:0 !important;
    border-radius:999px !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    text-align:center !important;
}
[class*="st-key-skip_"] button p{
    width:100% !important;
    margin:0 !important;
    text-align:center !important;
    line-height:1 !important;
    font-size:.72rem !important;
}
/* Keep the control row close to the poster. */
.showroom-top-controls{
    margin:0 0 .2rem !important;
}

/* V5.108 explainable ML + iCinema Insights */
.model-status-line{
    display:flex;
    align-items:center;
    gap:.42rem;
    flex-wrap:wrap;
    margin:.18rem 0 1.05rem;
    font-family:var(--ui-font);
    font-size:.72rem;
    line-height:1.3;
    letter-spacing:.004em;
    color:var(--muted2);
}
.model-status-dot{
    width:.38rem;
    height:.38rem;
    border-radius:999px;
    background:var(--ai);
    display:inline-block;
    flex:0 0 auto;
}
.model-status-primary{
    color:var(--ivory);
    font-size:.74rem;
    font-weight:680;
    letter-spacing:-.006em;
}
.model-status-secondary{
    color:var(--muted);
    font-size:.72rem;
    font-weight:500;
}
.model-status-separator{
    color:rgba(169,173,183,.46);
    padding:0 .04rem;
}
.profile-insights{width:100%;max-width:760px;margin-top:1.3rem;padding-top:1.18rem;border-top:1px solid var(--border)}
.profile-insights-title{font-family:var(--ui-font);font-size:1rem;font-weight:760;color:var(--ivory);margin-bottom:.24rem;letter-spacing:-.015em}
.profile-insights-copy{font-family:var(--ui-font);font-size:.78rem;line-height:1.4;color:var(--muted);margin-bottom:.82rem}
.insight-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.62rem}
.insight-card{border:1px solid var(--border);border-radius:14px;background:rgba(255,255,255,.018);padding:.72rem .76rem;min-height:4.4rem}
.insight-value{font-family:var(--ui-font);font-size:1.05rem;font-weight:780;color:var(--ivory);letter-spacing:-.02em}
.insight-label{font-family:var(--ui-font);font-size:.66rem;line-height:1.28;color:var(--muted);margin-top:.25rem}
.row-model-note{font-family:var(--ui-font);font-size:.72rem;line-height:1.3;color:var(--muted2);margin:-.04rem 0 .4rem}
div[data-testid="stPopover"] button{min-height:1.7rem !important;padding:.18rem .58rem !important;font-size:.68rem !important;border-radius:999px !important;color:var(--muted) !important}
div[data-testid="stPopover"] button p{font-size:.68rem !important;font-weight:650 !important;margin:0 !important}
.why-reason{font-family:var(--ui-font);font-size:.77rem;line-height:1.42;color:var(--muted);margin:.22rem 0}
@media(max-width:800px){.insight-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}

/* V5.111 — Match explanation, complete descriptions, and interaction stability */
/* The iCinema Match pill is now the explanation control itself. */
div[data-testid="stPopover"]{
    width:100% !important;
    margin:0 !important;
    padding:0 !important;
}
div[data-testid="stPopover"] > button,
div[data-testid="stPopover"] button{
    width:100% !important;
    min-height:1.95rem !important;
    height:1.95rem !important;
    padding:.18rem .58rem !important;
    margin:0 !important;
    border:1px solid #4A4F57 !important;
    border-radius:999px !important;
    background:transparent !important;
    color:var(--ivory) !important;
    font-family:var(--ui-font) !important;
    font-size:.72rem !important;
    font-weight:700 !important;
    letter-spacing:0 !important;
    line-height:1 !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    text-align:center !important;
    box-shadow:none !important;
}
div[data-testid="stPopover"] button p{
    margin:0 !important;
    width:100% !important;
    color:var(--ivory) !important;
    font-family:var(--ui-font) !important;
    font-size:.72rem !important;
    font-weight:700 !important;
    line-height:1 !important;
    text-align:center !important;
    white-space:nowrap !important;
}
div[data-testid="stPopover"] button:hover{
    border-color:rgba(169,173,183,.58) !important;
    background:rgba(255,255,255,.028) !important;
}
.match-explain-title{
    font-family:var(--ui-font);
    color:var(--ivory);
    font-size:.82rem;
    font-weight:760;
    letter-spacing:-.01em;
    margin:0 0 .45rem;
}
/* Descriptions are generated as complete phrases and receive the same roomy slot
   on every card so no card looks clipped or shifts its action row. */
.movie-description{
    height:5.85rem !important;
    min-height:5.85rem !important;
    max-height:5.85rem !important;
    line-height:1.42 !important;
    margin-top:.18rem !important;
    margin-bottom:.16rem !important;
    overflow:hidden !important;
    display:block !important;
}
/* The persistence bridge must never occupy a visible pixel during any rerun. */
div[data-testid="stCustomComponentV1"],
div[data-testid="stCustomComponentV1"] iframe,
iframe[title*="icinema_browser_storage"],
iframe[src*="icinema_browser_storage"]{
    height:0 !important;
    min-height:0 !important;
    max-height:0 !important;
    width:0 !important;
    min-width:0 !important;
    margin:0 !important;
    padding:0 !important;
    border:0 !important;
    overflow:hidden !important;
    opacity:0 !important;
    visibility:hidden !important;
    background:transparent !important;
}


/* V5.112 — cinematic running state + relaxed Match pill */
/* Give the Match label enough room to breathe while preserving the compact card top row. */
.showroom-top-controls [data-testid="stHorizontalBlock"]{
    align-items:center !important;
    column-gap:.55rem !important;
}
.showroom-top-controls div[data-testid="stPopover"] > button,
.showroom-top-controls div[data-testid="stPopover"] button{
    min-height:2.02rem !important;
    height:2.02rem !important;
    padding:.18rem .78rem !important;
    border-radius:999px !important;
    justify-content:center !important;
}
.showroom-top-controls div[data-testid="stPopover"] button p,
.showroom-top-controls div[data-testid="stPopover"] button span{
    font-family:var(--ui-font) !important;
    color:var(--ivory) !important;
    font-size:.68rem !important;
    font-weight:690 !important;
    letter-spacing:-.006em !important;
    line-height:1 !important;
    white-space:nowrap !important;
    text-align:center !important;
}
.showroom-top-controls [class*="st-key-skip_"] button{
    min-height:2.02rem !important;
    height:2.02rem !important;
}

/* Replace Streamlit's generic running indicator with a small iCinema screening cue.
   It appears only while Streamlit is actively executing a rerun. */
div[data-testid="stStatusWidget"]{
    position:fixed !important;
    top:1rem !important;
    left:50% !important;
    right:auto !important;
    transform:translateX(-50%) !important;
    z-index:999999 !important;
    width:auto !important;
    min-width:13.2rem !important;
    height:2.35rem !important;
    min-height:2.35rem !important;
    padding:0 .9rem !important;
    border:1px solid rgba(169,173,183,.26) !important;
    border-radius:999px !important;
    background:rgba(17,19,21,.96) !important;
    box-shadow:0 10px 28px rgba(0,0,0,.28) !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    overflow:hidden !important;
    backdrop-filter:blur(12px) !important;
}
div[data-testid="stStatusWidget"] > *{
    display:none !important;
}
div[data-testid="stStatusWidget"]::before{
    content:"▣  iCinema · Cueing your next scene…";
    display:block !important;
    color:var(--ivory) !important;
    font-family:var(--ui-font) !important;
    font-size:.7rem !important;
    font-weight:650 !important;
    letter-spacing:-.006em !important;
    line-height:1 !important;
    white-space:nowrap !important;
}
div[data-testid="stStatusWidget"]::after{
    content:"";
    position:absolute;
    left:.55rem;
    right:.55rem;
    bottom:.22rem;
    height:1px;
    border-radius:999px;
    background:linear-gradient(90deg, transparent 0%, rgba(92,111,168,.35) 20%, rgba(92,111,168,.95) 50%, rgba(92,111,168,.35) 80%, transparent 100%);
    animation:icinema-projector-pulse 1.2s ease-in-out infinite;
}
@keyframes icinema-projector-pulse{
    0%,100%{opacity:.28;transform:scaleX(.55)}
    50%{opacity:1;transform:scaleX(1)}
}
@media(max-width:700px){
    div[data-testid="stStatusWidget"]{
        top:.72rem !important;
        min-width:11.5rem !important;
        max-width:calc(100vw - 2rem) !important;
        height:2.2rem !important;
        min-height:2.2rem !important;
        padding:0 .72rem !important;
    }
    div[data-testid="stStatusWidget"]::before{font-size:.64rem !important}
}


/* V5.114 — full Match label + complete aligned descriptions */
/* Give the Match popover enough room and disable Streamlit text ellipsis. */
.showroom-top-controls [data-testid="stHorizontalBlock"]{
    align-items:center !important;
    column-gap:.46rem !important;
}
.showroom-top-controls div[data-testid="stPopover"],
.showroom-top-controls div[data-testid="stPopover"] > button,
.showroom-top-controls div[data-testid="stPopover"] button{
    width:100% !important;
    max-width:none !important;
    min-width:0 !important;
    overflow:visible !important;
}
.showroom-top-controls div[data-testid="stPopover"] > button,
.showroom-top-controls div[data-testid="stPopover"] button{
    min-height:2.08rem !important;
    height:2.08rem !important;
    padding:.18rem .5rem !important;
}
.showroom-top-controls div[data-testid="stPopover"] button p,
.showroom-top-controls div[data-testid="stPopover"] button span{
    display:block !important;
    width:auto !important;
    max-width:none !important;
    min-width:max-content !important;
    overflow:visible !important;
    text-overflow:clip !important;
    white-space:nowrap !important;
    flex-shrink:0 !important;
    font-size:.66rem !important;
    font-weight:700 !important;
    letter-spacing:-.008em !important;
}
.showroom-top-controls [class*="st-key-skip_"],
.showroom-top-controls [class*="st-key-skip_"] button{
    min-width:0 !important;
    width:100% !important;
}
.showroom-top-controls [class*="st-key-skip_"] button{
    min-height:2.08rem !important;
    height:2.08rem !important;
    padding:.16rem .34rem !important;
}

/* The concise description is capped in Python. Reserve enough room for that
   complete text at four-column card widths so no last line is hidden. */
.movie-description{
    height:7.65rem !important;
    min-height:7.65rem !important;
    max-height:7.65rem !important;
    overflow:visible !important;
    display:block !important;
    line-height:1.42 !important;
    margin-top:.18rem !important;
    margin-bottom:.22rem !important;
}


/* V5.115 — final product spacing pass */
/* All four Showroom tabs begin their first content heading at the same vertical position. */
.showroom-tab-start{
    height:1.12rem !important;
    margin:0 !important;
    padding:0 !important;
}
.showroom-row.first{
    transform:none !important;
    margin-top:0 !important;
    margin-bottom:.08rem !important;
}
.tab-section-heading,
.profile-heading{
    margin-top:0 !important;
}
.tab-section-heading{
    margin-bottom:.56rem !important;
}
/* Keep the Profile tab from inheriting any extra top offset compared with Showroom/Saved/Seen. */
.profile-wrap{
    margin-top:0 !important;
    padding-top:0 !important;
}
.profile-heading{
    margin-bottom:.48rem !important;
}
.profile-intro{
    margin-top:0 !important;
    margin-bottom:.88rem !important;
}

/* Showroom section title + explanation read as one compact header block. */
.showroom-row{
    margin-top:.88rem !important;
    margin-bottom:0 !important;
}
.showroom-row.first{
    margin-top:0 !important;
}
.showroom-row h3{
    margin:0 0 .16rem !important;
    line-height:1.08 !important;
}
.row-model-note{
    margin:0 0 .54rem !important;
    line-height:1.32 !important;
}

/* Keep controls close to the section explanation and poster. */
.showroom-top-controls{
    margin-top:0 !important;
    margin-bottom:.18rem !important;
}

/* Refine card rhythm without changing the established alignment system. */
.poster-caption{
    margin-top:.58rem !important;
    margin-bottom:.18rem !important;
}
.ratings{
    margin-top:.02rem !important;
    margin-bottom:.16rem !important;
}
.watch-availability{
    margin-top:.16rem !important;
    margin-bottom:.16rem !important;
}
.movie-description{
    margin-top:.12rem !important;
    margin-bottom:.18rem !important;
}
.movie-card-actions{
    margin-top:.1rem !important;
    margin-bottom:.08rem !important;
}

/* Consistent top-page rhythm across onboarding and standalone profile screens. */
.page-top-heading{
    margin-bottom:.36rem !important;
}
.page-top-subtitle{
    margin-top:0 !important;
    margin-bottom:1.08rem !important;
}
.step2-header{
    margin-bottom:1.02rem !important;
}
.step3-subtitle{
    margin-bottom:1.48rem !important;
}
.search-shell{
    margin-top:1.35rem !important;
}


/* V5.117 — final landing-page rhythm */
body:has(.hero-title) .icinema-logo{
    margin-bottom:.62rem !important;
}
.hero-title{
    margin-top:0 !important;
    margin-bottom:0 !important;
}
.hero-subtitle{
    margin-top:.78rem !important;
    margin-bottom:1.55rem !important;
    line-height:1.52 !important;
}
.step-card{
    padding:1.1rem 1.16rem !important;
}
.adapt-note{
    margin:1.35rem 0 .9rem !important;
    padding:1.12rem 1.22rem 1.08rem !important;
}
.adapt-note strong{
    margin-bottom:.38rem !important;
}
.st-key-start_personalizing{
    margin-top:.5rem !important;
    margin-bottom:0 !important;
}


/* V5.118 — exact tab-heading alignment + Match/Skip breathing room */
/* Every tab now uses the same spacer + same heading class as its first content. */
.showroom-tab-start{
    height:1.12rem !important;
    margin:0 !important;
    padding:0 !important;
}
.tab-primary-heading{
    color:var(--ivory) !important;
    font-family:var(--ui-font) !important;
    font-size:2rem !important;
    line-height:1.08 !important;
    font-weight:760 !important;
    letter-spacing:-.03em !important;
    margin:0 0 .16rem !important;
    padding:0 !important;
}
/* Profile's internal content begins immediately after the shared tab heading. */
.profile-wrap{
    margin-top:0 !important;
    padding-top:0 !important;
}
.profile-wrap .profile-intro{
    margin-top:0 !important;
}
/* Add a little more breathing room between the Match control and Skip. */
.showroom-top-controls [data-testid="stHorizontalBlock"]{
    column-gap:.72rem !important;
}


/* V5.119 — aligned Profile header, live learning signal, cinematic camera loader */

/* Profile title + subtitle are now in the same wrapper; lock them to one left edge. */
.profile-wrap{
    margin-left:0 !important;
    padding-left:0 !important;
    align-items:flex-start !important;
}
.profile-wrap .profile-heading,
.profile-wrap .profile-heading-aligned,
.profile-wrap .profile-intro{
    width:100% !important;
    max-width:760px !important;
    margin-left:0 !important;
    padding-left:0 !important;
    text-indent:0 !important;
    box-sizing:border-box !important;
}
.profile-wrap .profile-heading-aligned{
    margin-top:0 !important;
    margin-bottom:.48rem !important;
}

/* Keep the learning system visibly active with a calm, continuous lens-like glow. */
.model-status-dot{
    width:.42rem !important;
    height:.42rem !important;
    background:var(--ai) !important;
    box-shadow:
        0 0 0 2px rgba(92,111,168,.10),
        0 0 7px rgba(92,111,168,.68),
        0 0 14px rgba(92,111,168,.28) !important;
    animation:icinema-learning-live 1.8s ease-in-out infinite !important;
}
@keyframes icinema-learning-live{
    0%,100%{
        opacity:.78;
        transform:scale(.94);
        box-shadow:
            0 0 0 2px rgba(92,111,168,.08),
            0 0 6px rgba(92,111,168,.50),
            0 0 11px rgba(92,111,168,.20);
    }
    50%{
        opacity:1;
        transform:scale(1.08);
        box-shadow:
            0 0 0 3px rgba(92,111,168,.12),
            0 0 9px rgba(92,111,168,.88),
            0 0 18px rgba(92,111,168,.36);
    }
}

/* Loading indicator: compact camera body with a glowing circular lens, no text. */
div[data-testid="stStatusWidget"]{
    position:fixed !important;
    top:1rem !important;
    left:50% !important;
    right:auto !important;
    transform:translateX(-50%) !important;
    z-index:999999 !important;
    width:2.72rem !important;
    min-width:2.72rem !important;
    max-width:2.72rem !important;
    height:2.72rem !important;
    min-height:2.72rem !important;
    max-height:2.72rem !important;
    padding:0 !important;
    border:1px solid rgba(169,173,183,.26) !important;
    border-radius:14px !important;
    background:rgba(17,19,21,.96) !important;
    box-shadow:0 8px 24px rgba(0,0,0,.28) !important;
    overflow:visible !important;
    backdrop-filter:blur(12px) !important;
}
div[data-testid="stStatusWidget"] > *{
    display:none !important;
}
/* Camera body */
div[data-testid="stStatusWidget"]::before{
    content:"" !important;
    position:absolute !important;
    left:50% !important;
    top:50% !important;
    width:1.34rem !important;
    height:.92rem !important;
    transform:translate(-50%,-46%) !important;
    border:1.5px solid rgba(243,240,234,.90) !important;
    border-radius:4px !important;
    background:transparent !important;
    box-sizing:border-box !important;
}
/* Lens */
div[data-testid="stStatusWidget"]::after{
    content:"" !important;
    position:absolute !important;
    left:50% !important;
    top:50% !important;
    width:.48rem !important;
    height:.48rem !important;
    transform:translate(-50%,-42%) !important;
    border:1.5px solid rgba(243,240,234,.95) !important;
    border-radius:50% !important;
    background:rgba(92,111,168,.20) !important;
    box-shadow:
        0 0 0 2px rgba(92,111,168,.10),
        0 0 8px rgba(92,111,168,.78) !important;
    animation:icinema-camera-lens 1.05s ease-in-out infinite !important;
    box-sizing:border-box !important;
}
@keyframes icinema-camera-lens{
    0%,100%{
        opacity:.62;
        transform:translate(-50%,-42%) scale(.9);
        box-shadow:
            0 0 0 2px rgba(92,111,168,.08),
            0 0 6px rgba(92,111,168,.50);
    }
    50%{
        opacity:1;
        transform:translate(-50%,-42%) scale(1.08);
        box-shadow:
            0 0 0 3px rgba(92,111,168,.12),
            0 0 11px rgba(92,111,168,.95);
    }
}
/* Small camera top housing. */
div[data-testid="stStatusWidget"]{
    background-image:
        linear-gradient(rgba(243,240,234,.88),rgba(243,240,234,.88)) !important;
    background-size:.46rem .16rem !important;
    background-repeat:no-repeat !important;
    background-position:50% .63rem !important;
}
@media(max-width:700px){
    div[data-testid="stStatusWidget"]{
        top:.72rem !important;
        width:2.5rem !important;
        min-width:2.5rem !important;
        max-width:2.5rem !important;
        height:2.5rem !important;
        min-height:2.5rem !important;
        max-height:2.5rem !important;
    }
}


/* V5.120 — showroom header alignment, cleaner control row, logo-adjacent loader */

/* Use the exact same heading + note wrapper for all four showroom sections. */
.showroom-row-header{
    margin-top:0 !important;
    margin-bottom:.58rem !important;
}
.showroom-row-header .tab-primary-heading,
.showroom-row-header h3{
    margin:0 0 .18rem !important;
    padding:0 !important;
    line-height:1.08 !important;
}
.showroom-row-header .row-model-note{
    margin:0 !important;
    padding:0 !important;
    line-height:1.34 !important;
}

/* Keep Match and Skip distinct, aligned, and non-overlapping across card widths. */
.showroom-top-controls{
    margin-top:0 !important;
    margin-bottom:.2rem !important;
}
.showroom-top-controls [data-testid="stHorizontalBlock"]{
    align-items:center !important;
    column-gap:.42rem !important;
}
.showroom-top-controls [data-testid="column"]{
    min-width:0 !important;
}
.showroom-top-controls div[data-testid="stPopover"],
.showroom-top-controls div[data-testid="stPopover"] > button,
.showroom-top-controls div[data-testid="stPopover"] button{
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
    overflow:hidden !important;
}
.showroom-top-controls div[data-testid="stPopover"] > button,
.showroom-top-controls div[data-testid="stPopover"] button{
    min-height:2rem !important;
    height:2rem !important;
    padding:.14rem .42rem !important;
    justify-content:center !important;
}
.showroom-top-controls div[data-testid="stPopover"] button p,
.showroom-top-controls div[data-testid="stPopover"] button span{
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
    overflow:visible !important;
    text-overflow:clip !important;
    white-space:nowrap !important;
    flex-shrink:1 !important;
    font-size:.64rem !important;
    font-weight:700 !important;
    text-align:center !important;
}
.showroom-top-controls [class*="st-key-skip_"]{
    margin:0 !important;
    min-width:0 !important;
}
.showroom-top-controls [class*="st-key-skip_"] button{
    min-height:2rem !important;
    height:2rem !important;
    padding:.14rem .26rem !important;
    margin:0 !important;
}
.showroom-top-controls [class*="st-key-skip_"] button p{
    font-size:.66rem !important;
    font-weight:700 !important;
    text-align:center !important;
}

/* V5.121 — refined film-camera loader beside the iCinema logo. */
div[data-testid="stStatusWidget"]{
    position:fixed !important;
    top:1.02rem !important;
    left:8.72rem !important;
    right:auto !important;
    transform:none !important;
    z-index:999999 !important;
    width:2.9rem !important;
    min-width:2.9rem !important;
    max-width:2.9rem !important;
    height:1.85rem !important;
    min-height:1.85rem !important;
    max-height:1.85rem !important;
    padding:0 !important;
    border:0 !important;
    border-radius:0 !important;
    background:transparent !important;
    box-shadow:none !important;
    overflow:visible !important;
    backdrop-filter:none !important;
    background-image:none !important;
}
div[data-testid="stStatusWidget"] > *{
    display:none !important;
}
/* Camera silhouette with body, viewfinder, support, and twin reels. */
div[data-testid="stStatusWidget"]::before{
    content:"" !important;
    position:absolute !important;
    inset:0 !important;
    background:
        radial-gradient(circle at .56rem .38rem, rgba(244,241,235,.98) 0 .17rem, transparent .18rem),
        radial-gradient(circle at 1.03rem .38rem, rgba(244,241,235,.98) 0 .17rem, transparent .18rem),
        radial-gradient(circle at .56rem .38rem, rgba(15,20,32,1) 0 .06rem, transparent .065rem),
        radial-gradient(circle at 1.03rem .38rem, rgba(15,20,32,1) 0 .06rem, transparent .065rem),
        linear-gradient(rgba(244,241,235,.96), rgba(244,241,235,.96)) .56rem .6rem / 1.02rem .54rem no-repeat,
        linear-gradient(rgba(244,241,235,.96), rgba(244,241,235,.96)) 1.52rem .68rem / .36rem .11rem no-repeat,
        linear-gradient(rgba(244,241,235,.96), rgba(244,241,235,.96)) .73rem .43rem / .42rem .11rem no-repeat,
        linear-gradient(rgba(244,241,235,.96), rgba(244,241,235,.96)) .71rem 1.13rem / .1rem .22rem no-repeat,
        linear-gradient(rgba(244,241,235,.96), rgba(244,241,235,.96)) 1.2rem 1.13rem / .1rem .22rem no-repeat,
        linear-gradient(rgba(244,241,235,.96), rgba(244,241,235,.96)) .81rem 1.24rem / .38rem .08rem no-repeat;
    filter:drop-shadow(0 0 8px rgba(255,255,255,.05));
    opacity:.98 !important;
}
/* Lens acts as the active loading indicator. */
div[data-testid="stStatusWidget"]::after{
    content:"" !important;
    position:absolute !important;
    left:1.74rem !important;
    top:.57rem !important;
    width:.54rem !important;
    height:.54rem !important;
    border-radius:50% !important;
    border:1.6px solid rgba(244,241,235,.98) !important;
    background:
        radial-gradient(circle at 38% 34%, rgba(135,160,255,.82) 0 .08rem, rgba(135,160,255,.28) .09rem .18rem, rgba(12,18,29,.86) .19rem 100%) !important;
    box-shadow:
        0 0 0 2px rgba(92,111,168,.08),
        0 0 10px rgba(92,111,168,.42),
        inset 0 0 7px rgba(135,160,255,.26) !important;
    animation:icinema-camera-lens 1.05s ease-in-out infinite !important;
}
@media(max-width:700px){
    div[data-testid="stStatusWidget"]{
        top:.82rem !important;
        left:6rem !important;
        width:2.45rem !important;
        min-width:2.45rem !important;
        max-width:2.45rem !important;
        height:1.55rem !important;
        min-height:1.55rem !important;
        max-height:1.55rem !important;
    }
    div[data-testid="stStatusWidget"]::before{
        transform:scale(.88) !important;
        transform-origin:left top !important;
    }
    div[data-testid="stStatusWidget"]::after{
        left:1.48rem !important;
        top:.48rem !important;
        width:.46rem !important;
        height:.46rem !important;
    }
}


/* V5.122 — final compact Showroom spacing + collision-proof controls */

/* Give each section subtitle a little breathing room below the heading. */
.showroom-row-header .tab-primary-heading,
.showroom-row-header h3{
    margin-bottom:.34rem !important;
}
.showroom-row-header .row-model-note{
    margin:0 !important;
    padding:0 !important;
    line-height:1.34 !important;
}
.showroom-row-header{
    margin-bottom:.52rem !important;
}

/* Keep Match and Skip fully contained inside each individual movie card. */
.showroom-top-controls{
    width:100% !important;
    max-width:100% !important;
    overflow:hidden !important;
    margin:0 0 .18rem !important;
}
.showroom-top-controls [data-testid="stHorizontalBlock"]{
    width:100% !important;
    max-width:100% !important;
    display:grid !important;
    grid-template-columns:minmax(0,2.75fr) minmax(3.25rem,1.05fr) !important;
    gap:.46rem !important;
    align-items:center !important;
}
.showroom-top-controls [data-testid="column"]{
    width:auto !important;
    min-width:0 !important;
    max-width:100% !important;
    flex:none !important;
    overflow:hidden !important;
}
.showroom-top-controls div[data-testid="stPopover"]{
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    overflow:hidden !important;
}
.showroom-top-controls div[data-testid="stPopover"] > button,
.showroom-top-controls div[data-testid="stPopover"] button{
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    height:1.96rem !important;
    min-height:1.96rem !important;
    padding:.12rem .28rem !important;
    overflow:hidden !important;
}
.showroom-top-controls div[data-testid="stPopover"] button p,
.showroom-top-controls div[data-testid="stPopover"] button span{
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    overflow:visible !important;
    text-overflow:clip !important;
    white-space:nowrap !important;
    font-size:.59rem !important;
    line-height:1 !important;
    letter-spacing:-.012em !important;
    text-align:center !important;
}
.showroom-top-controls [class*="st-key-skip_"]{
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    margin:0 !important;
    overflow:hidden !important;
}
.showroom-top-controls [class*="st-key-skip_"] button{
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    height:1.96rem !important;
    min-height:1.96rem !important;
    padding:.12rem .2rem !important;
    margin:0 !important;
}
.showroom-top-controls [class*="st-key-skip_"] button p{
    font-size:.62rem !important;
    line-height:1 !important;
    margin:0 !important;
    text-align:center !important;
}

/* Reduce unused description whitespace so actions sit closer while preserving row alignment. */
.movie-description{
    height:5.45rem !important;
    min-height:5.45rem !important;
    max-height:5.45rem !important;
    overflow:hidden !important;
    line-height:1.42 !important;
    margin-top:.12rem !important;
    margin-bottom:.08rem !important;
}
.movie-card-actions{
    margin-top:0 !important;
    margin-bottom:.06rem !important;
}


/* V5.123 — full Match label + compact expandable movie description */
/* Guarantee enough visual width for the complete Match label. */
.showroom-top-controls [data-testid="stHorizontalBlock"]{
    column-gap:.46rem !important;
}
.showroom-top-controls [data-testid="column"]{
    min-width:0 !important;
}
.showroom-top-controls div[data-testid="stPopover"]{
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    overflow:visible !important;
}
.showroom-top-controls div[data-testid="stPopover"] > button,
.showroom-top-controls div[data-testid="stPopover"] button{
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    height:1.96rem !important;
    min-height:1.96rem !important;
    padding:.12rem .34rem !important;
    overflow:visible !important;
}
.showroom-top-controls div[data-testid="stPopover"] button p,
.showroom-top-controls div[data-testid="stPopover"] button span{
    display:block !important;
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    overflow:visible !important;
    text-overflow:clip !important;
    white-space:nowrap !important;
    flex-shrink:1 !important;
    font-size:.575rem !important;
    font-weight:700 !important;
    letter-spacing:-.012em !important;
    text-align:center !important;
}
.showroom-top-controls [class*="st-key-skip_"] button,
.showroom-top-controls [class*="st-key-skip_"] button p{
    font-size:.59rem !important;
}

/* One complete quick line stays visible; full plot lives in the expander below. */
.movie-quick-description{
    min-height:2.55rem !important;
    max-height:2.55rem !important;
    overflow:hidden !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.76rem !important;
    line-height:1.38 !important;
    font-weight:600 !important;
    letter-spacing:-.006em !important;
    margin:.12rem 0 .18rem !important;
}
/* Retire the old fixed plot slot now that descriptions are expandable. */
.movie-description{
    display:none !important;
}
/* Make the description expander read like a small text control, not a large panel. */
div[data-testid="stExpander"]{
    border:0 !important;
    background:transparent !important;
    margin:0 0 .14rem !important;
    padding:0 !important;
}
div[data-testid="stExpander"] details{
    border:0 !important;
    background:transparent !important;
}
div[data-testid="stExpander"] summary{
    min-height:1.35rem !important;
    padding:0 !important;
    margin:0 !important;
    color:var(--muted2) !important;
    font-family:var(--ui-font) !important;
    font-size:.62rem !important;
    line-height:1.2 !important;
    font-weight:650 !important;
}
div[data-testid="stExpander"] summary p{
    margin:0 !important;
    font-size:.62rem !important;
    font-weight:650 !important;
    color:var(--muted2) !important;
}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"]{
    padding:.38rem 0 .12rem !important;
}
.movie-full-description{
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.72rem !important;
    line-height:1.48 !important;
    font-weight:500 !important;
}
.movie-card-actions{
    margin-top:.02rem !important;
    margin-bottom:.05rem !important;
}


/* V5.124 — compact controls + one-line expandable plot summary */

/* Use the keyed Streamlit container to reliably pull controls toward the poster. */
[class*="st-key-showroom_controls_"]{
    margin-top:0 !important;
    margin-bottom:-.42rem !important;
    padding:0 !important;
}
[class*="st-key-showroom_controls_"] [data-testid="stHorizontalBlock"]{
    align-items:center !important;
    column-gap:.44rem !important;
}
[class*="st-key-showroom_controls_"] [data-testid="column"]{
    min-width:0 !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"],
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] > button,
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button{
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] > button,
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button,
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button{
    height:1.92rem !important;
    min-height:1.92rem !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button p,
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button span{
    font-size:.60rem !important;
    white-space:nowrap !important;
    overflow:visible !important;
    text-overflow:clip !important;
}
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button p{
    font-size:.62rem !important;
}

/* The summary sentence itself is the expander. Keep it to one line. */
div[data-testid="stExpander"]{
    margin:.08rem 0 .08rem !important;
    border:0 !important;
    background:transparent !important;
}
div[data-testid="stExpander"] details{
    border:0 !important;
    background:transparent !important;
}
div[data-testid="stExpander"] summary{
    min-height:1.72rem !important;
    padding:0 !important;
    margin:0 !important;
    display:flex !important;
    align-items:center !important;
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
}
div[data-testid="stExpander"] summary p{
    margin:0 !important;
    padding:0 !important;
    max-width:calc(100% - 1rem) !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    white-space:nowrap !important;
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.68rem !important;
    line-height:1.25 !important;
    font-weight:620 !important;
    letter-spacing:-.004em !important;
}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"]{
    padding:.3rem 0 .1rem !important;
}
.movie-full-description{
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.70rem !important;
    line-height:1.42 !important;
    font-weight:500 !important;
    letter-spacing:-.003em !important;
    margin:0 !important;
}

/* Retire the separate quick-description block from earlier builds. */
.movie-quick-description{
    display:none !important;
}

/* Keep Save / Seen immediately below the collapsed summary. */
.movie-card-actions{
    margin-top:.04rem !important;
    margin-bottom:.04rem !important;
}

</style>
""", unsafe_allow_html=True)

defaults={
    "screen":"welcome","onboarding_complete":False,"likes":set(),"favorites":set(),"review_priority":50,
    "genres":[],"adventure":50,"more_of":[],"saved":set(),"seen":set(),"dismissed":set(),"selection_order":[],
    "custom_like":None,"search_selected_title":None,"search_selected_movie":None,"external_movies":{},
    "shelf_movies":[],"shelf_replacement_pool":[],"shelf_seen_titles":set(),
    "shelf_pool_initialized":False,"shelf_tmdb_loaded":False,
    "analytics_events":[],"showroom_session_id":None,"showroom_session_start":None,
    "showroom_impression_keys":set(),"recommendation_context":{}
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
        "selection_order": list(st.session_state.get("selection_order", [])),
        "external_movies": st.session_state.external_movies,
        "analytics_events": list(st.session_state.get("analytics_events", []))[-500:],
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
        st.session_state.selection_order = list(data.get("selection_order") or [])
        st.session_state.external_movies = dict(data.get("external_movies") or {})
        st.session_state.analytics_events = list(data.get("analytics_events") or [])[-500:]
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

# Profile-changing actions queue a snapshot, but we deliberately do NOT mount
# the browser-storage component before the destination page renders. Mounting
# that component at the top of a page transition can briefly expose its iframe
# background as a black strip. The normal persist_profile_if_needed() call at
# the end of the render writes the exact same snapshot silently.
_pending_profile = st.session_state.get("_pending_profile_save")

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

RECOGNIZABLE_SHELF_TITLES = [
    "Dune: Part Two", "Blade Runner 2049", "The Prestige", "Prisoners",
    "Nightcrawler", "The Truman Show", "The Grand Budapest Hotel",
    "No Country for Old Men", "Before Sunrise", "Train to Busan",
    "Your Name", "Princess Mononoke", "Akira", "Ex Machina",
    "Past Lives", "The Holdovers", "The Wailing", "The Handmaiden",
    "Memories of Murder", "The Worst Person in the World",
]

def _shelf_key(movie):
    return (str(movie.get("title", "")).casefold(), int(movie.get("year") or 0))

def _seed_local_shelf_pool():
    if st.session_state.shelf_pool_initialized:
        return
    selected = st.session_state.likes | st.session_state.favorites
    pool = []
    for title in RECOGNIZABLE_SHELF_TITLES:
        movie = get_movie(title)
        if not movie or movie.get("title") in selected:
            continue
        pool.append(dict(movie))
    st.session_state.shelf_replacement_pool = pool
    st.session_state.shelf_pool_initialized = True

def _load_tmdb_shelf_pool():
    if st.session_state.shelf_tmdb_loaded or not tmdb_catalog_configured():
        return
    try:
        candidates = discover_movies(100)
    except Exception:
        candidates = []
    # Keep the shelf broadly recognizable: prioritize popularity and substantial voting.
    candidates = [
        dict(m) for m in candidates
        if m.get("poster_url")
        and (float(m.get("popularity") or 0) >= 25 or int(m.get("tmdb_vote_count") or 0) >= 750)
    ]
    candidates.sort(
        key=lambda m: (float(m.get("popularity") or 0), int(m.get("tmdb_vote_count") or 0)),
        reverse=True,
    )
    existing = {_shelf_key(m) for m in st.session_state.shelf_replacement_pool}
    existing |= {_shelf_key(m) for m in st.session_state.shelf_movies}
    existing |= {(str(t).casefold(), 0) for t in (st.session_state.likes | st.session_state.favorites)}
    for movie in candidates:
        key = _shelf_key(movie)
        if key in existing or movie.get("title") in st.session_state.likes or movie.get("title") in st.session_state.favorites:
            continue
        st.session_state.shelf_replacement_pool.append(movie)
        existing.add(key)
    st.session_state.shelf_tmdb_loaded = True

def _next_shelf_movie():
    _seed_local_shelf_pool()
    visible_keys = {_shelf_key(m) for m in st.session_state.shelf_movies}
    selected = st.session_state.likes | st.session_state.favorites

    def pop_valid():
        while st.session_state.shelf_replacement_pool:
            movie = st.session_state.shelf_replacement_pool.pop(0)
            if movie.get("title") in selected:
                continue
            key = _shelf_key(movie)
            if key in visible_keys or key in st.session_state.shelf_seen_titles:
                continue
            return movie
        return None

    movie = pop_valid()
    if movie is None:
        _load_tmdb_shelf_pool()
        movie = pop_valid()
    return movie

def ensure_rotating_shelf():
    selected = st.session_state.likes | st.session_state.favorites
    if not st.session_state.shelf_movies:
        st.session_state.shelf_movies = [dict(m) for m in STARTER_MOVIES if m.get("title") not in selected]
        st.session_state.shelf_seen_titles.update(_shelf_key(m) for m in st.session_state.shelf_movies)
    else:
        st.session_state.shelf_movies = [m for m in st.session_state.shelf_movies if m.get("title") not in selected]

    while len(st.session_state.shelf_movies) < 12:
        replacement = _next_shelf_movie()
        if not replacement:
            break
        st.session_state.shelf_movies.append(replacement)
        st.session_state.shelf_seen_titles.add(_shelf_key(replacement))

def rate_shelf_movie(movie, kind, slot_index):
    movie = dict(movie)
    title = movie.get("title")
    if not title:
        return
    # TMDB replacement movies carry rich metadata. Persist that metadata so every
    # available feature (genre, semantic traits, popularity, quality, language, era)
    # enters the same recommendation model immediately after Like/Favorite.
    if movie.get("external") or movie.get("tmdb_id"):
        st.session_state.external_movies[title] = movie

    st.session_state.likes.add(title)
    if title not in st.session_state.selection_order:
        st.session_state.selection_order.append(title)
    if kind == "favorite":
        st.session_state.favorites.add(title)
    else:
        st.session_state.favorites.discard(title)

    replacement = _next_shelf_movie()
    if 0 <= slot_index < len(st.session_state.shelf_movies):
        if replacement:
            st.session_state.shelf_movies[slot_index] = replacement
            st.session_state.shelf_seen_titles.add(_shelf_key(replacement))
        else:
            st.session_state.shelf_movies.pop(slot_index)
    queue_profile_save()

def add_search_choice(kind):
    movie = st.session_state.get("search_selected_movie")
    if not movie:
        return
    title = movie["title"]
    if movie.get("external"):
        st.session_state.external_movies[title] = movie
    st.session_state.likes.add(title)
    if title not in st.session_state.selection_order:
        st.session_state.selection_order.append(title)
    if kind == "favorite":
        st.session_state.favorites.add(title)
    else:
        st.session_state.favorites.discard(title)
    st.session_state.search_selected_movie = None
    st.session_state.search_selected_title = None
    queue_profile_save()

def go(screen):
    """Navigate using the widget's normal single rerun.

    Ordinary onboarding page navigation does not change the learned profile, so
    it should not invoke the localStorage bridge. Only entering the Showroom
    changes the persisted onboarding-complete state. Avoiding that unnecessary
    write also prevents a transient dark component strip during Start
    Personalizing -> Step 1.
    """
    st.session_state.screen = screen
    if screen == "showroom":
        st.session_state.onboarding_complete = True
        start_new_session(st.session_state)
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

def _current_recommendation_context(title):
    return dict((st.session_state.get("recommendation_context") or {}).get(title) or {})

def skip_movie(title, movie=None):
    _remember_movie(movie)
    record_event(st.session_state, "skip", title, _current_recommendation_context(title))
    st.session_state.dismissed.add(title)
    st.session_state.saved.discard(title)
    queue_profile_save()

def save_movie(title, movie=None):
    _remember_movie(movie)
    record_event(st.session_state, "save", title, _current_recommendation_context(title))
    st.session_state.saved.add(title)
    st.session_state.seen.discard(title)
    st.session_state.dismissed.discard(title)
    queue_profile_save()

def remove_saved_movie(title):
    st.session_state.saved.discard(title)
    queue_profile_save()

def mark_movie_seen(title, movie=None):
    _remember_movie(movie)
    record_event(st.session_state, "seen", title, _current_recommendation_context(title))
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
            matches = search_movies(title, 1)
            movie = matches[0] if matches else None
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

def movie_thumb(movie, poster_url=None, compact=False, library_mode=None):
    title = html.escape(str(movie.get("title", "")))
    year = html.escape(str(movie.get("year", "")))
    poster_url = poster_url or movie.get("poster_url")
    if poster_url:
        safe_url = html.escape(str(poster_url), quote=True)
        poster_html = f'<div class="poster has-image"><img src="{safe_url}" alt="Poster for {title}"></div>'
    else:
        poster_html = '<div class="poster"><div class="poster-placeholder-mark">iCINEMA</div></div>'

    year_html = f'<div class="poster-caption-year">{year}</div>' if year else ''
    
    if library_mode == "saved":
        caption_class = "poster-caption library-poster-caption saved-poster-caption"
    elif library_mode == "seen":
        caption_class = "poster-caption library-poster-caption seen-poster-caption"
    else:
        caption_class = 'poster-caption library-poster-caption' if compact else 'poster-caption'
    st.markdown(
        poster_html
        + f'<div class="{caption_class}"><div class="poster-caption-title">{title}</div>{year_html}</div>',
        unsafe_allow_html=True
    )

def current_profile():
    return build_profile(
        st.session_state.likes, st.session_state.favorites, st.session_state.genres,
        st.session_state.review_priority, st.session_state.more_of,
        st.session_state.saved, st.session_state.dismissed, st.session_state.adventure,
        st.session_state.external_movies, st.session_state.seen
    )

def concise_description(text, limit=138):
    """Return a compact *complete-sounding* description for aligned movie cards.

    Prefer a full first sentence. If the source is longer, shorten on a natural
    phrase boundary and never leave dangling filler words such as "a" or "the".
    """
    text = " ".join(str(text or "").split()).strip()
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text)
    first_sentence = sentences[0].strip() if sentences else text
    if len(first_sentence) <= limit:
        return first_sentence if first_sentence.endswith((".", "!", "?")) else first_sentence + "."

    candidate = first_sentence
    # Prefer a natural clause boundary before falling back to a word boundary.
    boundaries = [m.end() for m in re.finditer(r"[,;:]\s+|\s+[–—-]\s+", candidate[:limit + 1])]
    if boundaries:
        candidate = candidate[:boundaries[-1]].rstrip(" ,;:–—-")
    else:
        candidate = candidate[:limit].rsplit(" ", 1)[0].rstrip(" ,;:–—-")

    dangling = {"a", "an", "the", "and", "or", "but", "with", "to", "of", "in", "for", "from", "by"}
    words = candidate.split()
    while words and words[-1].casefold().strip(".,;:") in dangling:
        words.pop()
    candidate = " ".join(words).rstrip(" ,;:.…")
    return candidate + "." if candidate else first_sentence

def quick_card_description(movie, limit=82):
    """Create one informative, slightly witty sentence for the collapsed card.

    The line stays grounded in the movie's real overview, explains the setup,
    and adds only a restrained genre-aware finish.
    """
    full = " ".join(str((movie or {}).get("why") or "").split()).strip()
    if not full:
        return "A strong match with enough going on to deserve a closer look."

    # Start from the actual plot setup rather than a generic tag line.
    first = re.split(r"(?<=[.!?;])\s+", full)[0].strip().rstrip(".;:,")
    first = first.split(";", 1)[0].strip()

    # Keep enough plot information to explain the premise in one visual line.
    target_base = max(50, limit - 22)
    if len(first) > target_base:
        cut = first[:target_base]
        natural = max(cut.rfind(", "), cut.rfind(" and "), cut.rfind(" but "), cut.rfind(" while "))
        if natural >= 34:
            first = cut[:natural]
        else:
            first = cut.rsplit(" ", 1)[0]
    first = first.rstrip(" ,;:–—-")

    genre = str((movie or {}).get("genre") or "").casefold()
    if genre in {"thriller", "mystery", "horror"}:
        finish = "—and calm does not last."
    elif genre == "comedy":
        finish = "—with chaos nearby."
    elif genre in {"sci-fi", "science fiction"}:
        finish = "—then reality bends."
    elif genre == "romance":
        finish = "—timing has opinions."
    elif genre == "documentary":
        finish = "—with very real stakes."
    elif genre in {"action", "adventure"}:
        finish = "—the plan gets complicated."
    elif genre in {"anime", "animation", "fantasy"}:
        finish = "—normal rules need not apply."
    else:
        finish = "—and things get complicated."

    quick = f"{first} {finish}" if first else finish.lstrip("—").capitalize()
    if len(quick) > limit:
        # Keep the plot premise intact; shorten the witty finish first.
        short_finishes = {
            "thriller": "—tension follows.",
            "mystery": "—questions follow.",
            "horror": "—calm does not last.",
            "comedy": "—chaos follows.",
            "sci-fi": "—reality bends.",
            "science fiction": "—reality bends.",
            "romance": "—timing matters.",
            "documentary": "—real stakes.",
            "action": "—the plan shifts.",
            "adventure": "—the plan shifts.",
            "anime": "—rules bend.",
            "animation": "—rules bend.",
            "fantasy": "—rules bend.",
        }
        finish = short_finishes.get(genre, "—pressure builds.")
        quick = f"{first} {finish}"
    if len(quick) > limit:
        first_limit = max(42, limit - len(finish) - 1)
        first = first[:first_limit].rsplit(" ", 1)[0].rstrip(" ,;:–—-")
        quick = f"{first} {finish}"
    return quick.rstrip()


def expanded_card_description(movie, max_chars=330):
    """Return a short spoiler-conscious expanded overview (usually 2 sentences).

    iCinema uses the catalog overview/why text and caps it before it turns into
    a long synopsis. This avoids adding plot details beyond the supplied source.
    """
    full = " ".join(str((movie or {}).get("why") or "").split()).strip()
    if not full:
        return "iCinema does not have a longer spoiler-free overview for this title yet."

    sentences = re.split(r"(?<=[.!?])\s+", full)
    chosen = []
    total = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        projected = total + len(sentence) + (1 if chosen else 0)
        if chosen and projected > max_chars:
            break
        chosen.append(sentence)
        total = projected
        if len(chosen) >= 2:
            break

    expanded = " ".join(chosen).strip() or full[:max_chars].rsplit(" ", 1)[0].strip()
    if len(expanded) > max_chars:
        expanded = expanded[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:")
        if expanded and not expanded.endswith((".", "!", "?")):
            expanded += "."
    return expanded


def concise_availability_text(text, max_providers=2):
    """Keep watch availability complete and compact instead of visually truncating it."""
    text = " ".join(str(text or "").split()).strip()
    if not text or ":" not in text:
        return text
    label, providers = text.split(":", 1)
    parts = [p.strip(" .") for p in providers.split("·") if p.strip(" .")]
    # Preserve order while removing duplicate provider names.
    unique = []
    seen = set()
    for part in parts:
        key = part.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(part)
    if len(unique) <= max_providers:
        return f"{label.strip()}: " + " · ".join(unique)
    shown = " · ".join(unique[:max_providers])
    return f"{label.strip()}: {shown} + more"

def profile_chip_html(items):
    return "".join(f'<span class="profile-chip">{item}</span>' for item in items)

def profile_analysis_html(items):
    return "".join(f'<div class="profile-analysis-row">{item}</div>' for item in items)

def _format_seconds(value):
    if value is None:
        return "Learning"
    value=max(0,int(round(value)))
    if value<60:
        return f"{value}s"
    return f"{value//60}m {value%60:02d}s"


def render_cinema_profile(p, include_insights=False, show_heading=True, tab_heading=False):
    sections = [
        ("You tend to enjoy", profile_chip_html(p["traits"]), "profile-chip-wrap"),
        ("Top genres", profile_chip_html(p["genres"]), "profile-chip-wrap"),
        ("What matters most", profile_chip_html(p["matters"]), "profile-chip-wrap"),
        ("What iCinema should prioritize", profile_chip_html(p["priorities"]), "profile-chip-wrap"),
        ("Viewing patterns", profile_analysis_html(p["patterns"]), "profile-analysis"),
        ("Recommendation balance", profile_analysis_html(p["balance"]), "profile-analysis"),
    ]
    section_html = "".join(
        f'<div class="profile-block full"><div class="profile-label">{label}</div><div class="{wrapper_class}">{content}</div></div>'
        for label, content, wrapper_class in sections
    )
    events=list(st.session_state.get("analytics_events") or [])
    insights=analytics_insights(events)
    learned=train_learning_model(events)
    conf=profile_confidence_label(p)
    signals=sum((p.get("behavior_counts") or {}).values()) + len((p.get("controls") or {}).get("selected_genres",[]) or []) + len((p.get("controls") or {}).get("priorities",[]) or [])
    model_primary = "Learning model active"
    model_secondary = "Adapting from your choices" if learned.ready else "Learning from your choices"
    signal_text = f"{signals} signal{'s' if signals != 1 else ''} shaping recommendations"

    ttm=_format_seconds(insights.get("time_to_match_seconds"))
    skips="Learning" if insights.get("avg_skips_before_save") is None else f'{insights["avg_skips_before_save"]:.1f}'
    conv="Learning" if insights.get("saved_to_seen_rate") is None else f'{insights["saved_to_seen_rate"]*100:.0f}%'
    discovery="Learning" if insights.get("discovery_rate") is None else f'{insights["discovery_rate"]*100:.0f}%'
    cards=[(ttm,"Median Time to Match"),(skips,"Avg. Skips Before Save"),(conv,"Save → Seen Conversion"),(conf,"Profile Confidence")]
    insight_html="".join(f'<div class="insight-card"><div class="insight-value">{v}</div><div class="insight-label">{l}</div></div>' for v,l in cards)

    insights_section = (
        f'<div class="profile-insights"><div class="profile-insights-title">iCinema’s Insights</div>'
        f'<div class="profile-insights-copy">Your recent activity, summarized.</div>'
        f'<div class="insight-grid">{insight_html}</div></div>'
        if include_insights else ""
    )

    heading_class = "tab-primary-heading profile-heading-aligned" if tab_heading else "profile-heading"
    profile_heading_html = f'<div class="{heading_class}">Your Cinema Profile</div>' if show_heading else ""

    st.markdown(
        f'<div class="profile-wrap">'
        f'{profile_heading_html}'
        f'<div class="profile-intro">A detailed showing of the preferences, viewing patterns, and recommendation signals iCinema has learned from your choices.</div>'
        f'<div class="model-status-line">'
        f'<span class="model-status-dot"></span>'
        f'<span class="model-status-primary">{model_primary}</span>'
        f'<span class="model-status-separator">·</span>'
        f'<span class="model-status-secondary">{model_secondary}</span>'
        f'<span class="model-status-separator">·</span>'
        f'<span class="model-status-secondary">{signal_text}</span>'
        f'</div>'
        f'<div class="profile-grid">{section_html}</div>'
        f'<div class="profile-summary">{p["summary"]}</div>'
        f'{insights_section}'
        f'</div>', unsafe_allow_html=True
    )


@st.fragment
def render_shelf_fragment():
    logo()
    st.markdown(
        '<div class="page-top-heading">Step 1 of 3 — Rate the Shelf</div>'
        '<div class="page-top-subtitle">Choose a few titles you already like. If none fit, search for one you know you enjoy.</div>',
        unsafe_allow_html=True,
    )

    ensure_rotating_shelf()
    shelf_movies = list(st.session_state.shelf_movies)
    missing_posters = tuple(
        (m["title"], int(m.get("year") or 0))
        for m in shelf_movies if not m.get("poster_url")
    )
    shelf_poster_map = get_poster_batch(missing_posters) if missing_posters else {}
    cols=st.columns(4)
    for i,movie in enumerate(shelf_movies):
        title=movie["title"]
        with cols[i%4]:
            movie_thumb(movie, movie.get("poster_url") or shelf_poster_map.get(title))
            st.markdown('<div class="shelf-action-gap"></div>', unsafe_allow_html=True)
            b1,b2=st.columns(2)
            with b1:
                st.button(
                    "Like",
                    key=f"like_{i}_{movie.get('tmdb_id') or title}",
                    use_container_width=True,
                    on_click=rate_shelf_movie,
                    args=(movie, "like", i),
                )
            with b2:
                st.button(
                    "Favorite",
                    key=f"fav_{i}_{movie.get('tmdb_id') or title}",
                    use_container_width=True,
                    on_click=rate_shelf_movie,
                    args=(movie, "favorite", i),
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

    _selected_set = st.session_state.likes | st.session_state.favorites
    chosen_titles = [t for t in st.session_state.get("selection_order", []) if t in _selected_set]
    chosen_titles += sorted(_selected_set - set(chosen_titles))
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
    st.markdown(
        '<div class="page-top-heading">Step 3 of 3 — Shape Your Showroom</div>'
        '<div class="page-top-subtitle step3-subtitle">What should iCinema lean toward? Choose any that you want to see more often</div>',
        unsafe_allow_html=True,
    )

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

    # Step 3 selections are queued in session state and persisted on the page-level
    # transition to Profile. Avoid rendering the localStorage bridge inside this
    # fragment, which could briefly surface as a dark strip after a card click.


@st.fragment
def render_showroom_fragment(p):
    ensure_session(st.session_state)
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
    learning_result=train_learning_model(st.session_state.get("analytics_events", []))

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
            ml_context=dict(components)
            ml_context.update({"model_score":base,"decision_utility":components.get("decision_utility",base),"match":display_match,"position":2})
            learned_probability=predict_success(learning_result,ml_context)
            if learned_probability is not None:
                base=0.78*base+0.22*learned_probability
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
        diversified=mmr_rerank(scored,limit=min(12,len(scored)),relevance_lambda=0.80 if row_name=="Top Matches for You" else 0.74)
        chosen={item[3]["title"] for item in diversified}
        ordered=diversified+[item for item in scored if item[3]["title"] not in chosen]
        return [(display_match,movie) for _,_,display_match,movie in ordered]

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
    visible_identity_keys=tuple((movie["title"], int(movie.get("year") or 0), int(movie.get("tmdb_id") or 0)) for movie in visible_movies)
    watch_by_title=get_watch_availability_batch(visible_movie_keys,"US")
    for row_name in row_order:
        row_choices[row_name].sort(key=lambda item:0.91*(item[0]/100.0)+0.09*availability_utility((watch_by_title.get(item[1]["title"]) or {}).get("status")),reverse=True)

    recommendation_context={}
    for row_name in row_order:
        for position,(match,movie) in enumerate(row_choices.get(row_name,[]),start=1):
            comps=score_movie_components(movie,p,st.session_state.adventure,st.session_state.review_priority)
            availability_value=availability_utility((watch_by_title.get(movie["title"]) or {}).get("status"))
            comps=score_movie_components(movie,p,st.session_state.adventure,st.session_state.review_priority,availability_score=availability_value)
            recommendation_context[movie["title"]]={
                "row":row_name,"position":position,"match":match,
                "model_score":round(float(comps.get("raw_score",0)),6),
                "decision_utility":round(float(comps.get("decision_utility",comps.get("raw_score",0))),6),
                **{k:round(float(comps.get(k,.5)),6) for k in ["genre_affinity","trait_affinity","semantic_similarity","quality_alignment","discovery_alignment","priority_alignment","availability_alignment","vote_confidence","profile_confidence"]}
            }
    st.session_state.recommendation_context=recommendation_context
    record_impressions(st.session_state,recommendation_context)
    identity_by_title=get_movie_identity_batch(visible_identity_keys)
    showroom_poster_map={title: data.get("poster_url") for title, data in identity_by_title.items()}
    live_rating_keys=tuple((movie["title"], int(movie.get("year") or 0), (identity_by_title.get(movie["title"], {}) or {}).get("imdb_id") or "") for movie in visible_movies)
    live_ratings_by_title=get_live_ratings_batch(live_rating_keys)

    row_specs=["Top Matches for You","Critically Acclaimed","Hidden Gems","Something Different"]

    with tabs[0]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        for row_index,row_name in enumerate(row_specs):
            choices=row_choices.get(row_name,[])
            row_class = "showroom-row first" if row_index == 0 else "showroom-row"
            row_notes={
                "Top Matches for You":"Best overall fits based on your full preference profile",
                "Critically Acclaimed":"Highly rated films that still match your taste",
                "Hidden Gems":"Strong matches that are less obvious or widely promoted",
                "Something Different":"A little outside your usual taste, but still likely to click",
            }
            if row_index == 0:
                st.markdown(
                    f'<div class="{row_class} showroom-row-header">'
                    f'<div class="tab-primary-heading">{row_name}</div>'
                    f'<div class="row-model-note">{row_notes[row_name]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="{row_class} showroom-row-header"><h3>{row_name}</h3>'
                    f'<div class="row-model-note">{row_notes[row_name]}</div></div>',
                    unsafe_allow_html=True,
                )
            if not choices:
                st.caption("Refreshing personalized matches…")
                continue
            cols=st.columns(len(choices))
            for i,(match,movie) in enumerate(choices):
                with cols[i]:
                    with st.container(key=f"showroom_controls_{row_index}_{i}"):
                        match_col, skip_col = st.columns([3.35,0.9], gap="small")
                        with match_col:
                            with st.popover(f"{match}% iCinema Match", use_container_width=True):
                                reasons=recommendation_explanation(movie,p,st.session_state.adventure,st.session_state.review_priority)
                                st.markdown('<div class="match-explain-title">Why this matches you</div>', unsafe_allow_html=True)
                                for reason in reasons:
                                    st.markdown(f'<div class="why-reason">{html.escape(reason)}</div>',unsafe_allow_html=True)
                                if learning_result.ready:
                                    st.caption(f"Personalized with the {learning_result.model_name} learning layer and the recommendation model.")
                                else:
                                    st.caption("Personalized by the learning model while it gathers enough interaction history to train its supervised layer.")
                        with skip_col:
                            st.button(
                                "Skip",
                                key=f"skip_{row_name}_{movie['title']}",
                                use_container_width=True,
                                on_click=skip_movie,
                                args=(movie["title"], movie),
                            )
                    identity = identity_by_title.get(movie["title"], {}) or {}
                    display_movie = dict(movie)
                    if identity.get("display_title"):
                        display_movie["title"] = identity["display_title"]
                    if identity.get("year"):
                        display_movie["year"] = identity["year"]
                    movie_thumb(display_movie, showroom_poster_map.get(movie["title"]) or movie.get("poster_url"))
                    live_rating = live_ratings_by_title.get(movie["title"], {})
                    imdb_value = live_rating.get("imdb")
                    rt_value = live_rating.get("rt")
                    imdb_text = f"{imdb_value:.1f}" if isinstance(imdb_value, (int, float)) else "Not available"
                    rt_text = f"{int(rt_value)}%" if isinstance(rt_value, (int, float)) else "Not available"
                    rating_class = "ratings" if live_rating and (isinstance(imdb_value, (int, float)) or isinstance(rt_value, (int, float))) else "ratings muted"
                    st.markdown(f'<div class="{rating_class}">IMDb {imdb_text} · RT {rt_text}</div>',unsafe_allow_html=True)
                    availability = watch_by_title.get(movie["title"], {"status":"unknown","text":"Where to watch: availability unavailable","url":None})
                    availability_class = "watch-availability muted" if availability.get("status") in {"unknown", "not_configured", "unavailable"} else "watch-availability"
                    availability_text = concise_availability_text(availability["text"])
                    st.markdown(f'<div class="{availability_class}">{html.escape(availability_text)}</div>', unsafe_allow_html=True)
                    quick_desc = quick_card_description(movie)
                    expanded_desc = expanded_card_description(movie)
                    with st.expander(quick_desc):
                        st.markdown(f'<div class="movie-full-description">{html.escape(expanded_desc)}</div>', unsafe_allow_html=True)
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
        st.markdown('<div class="tab-primary-heading">Saved</div>', unsafe_allow_html=True)
        movies=[m for t in st.session_state.saved if (m := resolve_history_movie(t))]
        saved_identity_keys=tuple((m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in movies)
        saved_identity_map = get_movie_identity_batch(saved_identity_keys)
        saved_poster_map = get_poster_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies))
        if not movies:st.caption("Nothing saved yet.")
        else:
            cols=st.columns(4, gap="medium")
            for i,m in enumerate(movies):
                with cols[i % 4]:
                    identity = saved_identity_map.get(m["title"], {}) or {}
                    display_movie = dict(m)
                    if identity.get("display_title"):
                        display_movie["title"] = identity["display_title"]
                    if identity.get("year"):
                        display_movie["year"] = identity["year"]
                    movie_thumb(display_movie, identity.get("poster_url") or m.get("poster_url") or saved_poster_map.get(m["title"]), compact=True, library_mode="saved")
                    saved_actions = st.columns(2, gap="small")
                    with saved_actions[0]:
                        st.button(
                            "Mark Seen",
                            key=f"savedseen_{m['title']}",
                            use_container_width=True,
                            on_click=mark_movie_seen,
                            args=(m["title"], m),
                        )
                    with saved_actions[1]:
                        st.button(
                            "Remove",
                            key=f"unsave_{m['title']}",
                            use_container_width=True,
                            on_click=remove_saved_movie,
                            args=(m["title"],),
                        )

    with tabs[2]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        st.markdown('<div class="tab-primary-heading">Seen</div>', unsafe_allow_html=True)
        movies=[m for t in st.session_state.seen if (m := resolve_history_movie(t))]
        seen_identity_keys=tuple((m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in movies)
        seen_identity_map = get_movie_identity_batch(seen_identity_keys)
        seen_poster_map = get_poster_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies))
        if not movies:st.caption("Nothing marked as seen yet.")
        else:
            cols=st.columns(4, gap="medium")
            for i,m in enumerate(movies):
                with cols[i % 4]:
                    identity = seen_identity_map.get(m["title"], {}) or {}
                    display_movie = dict(m)
                    if identity.get("display_title"):
                        display_movie["title"] = identity["display_title"]
                    if identity.get("year"):
                        display_movie["year"] = identity["year"]
                    movie_thumb(display_movie, identity.get("poster_url") or m.get("poster_url") or seen_poster_map.get(m["title"]), compact=True, library_mode="seen")

    with tabs[3]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        render_cinema_profile(p, include_insights=True, show_heading=True, tab_heading=True)
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

    st.markdown('<div class="adapt-note"><strong>iCinema RESPONDS TO YOUR CHOICES</strong><br><span>Every save, skip, and seen title feeds iCinema’s learning model, updating your preference profile and shaping what appears next.</span></div>',unsafe_allow_html=True)
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

# V5.90 is implemented through CSS overrides injected above in the main style block.

# V5.99 tab content alignment polish injected via CSS override.

