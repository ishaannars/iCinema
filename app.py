
import html
from pathlib import Path
from urllib.parse import quote_plus
import json
import re
import streamlit as st
from src.recommender import (
    STARTER_MOVIES, GENRES, MORE_OF_OPTIONS, searchable_titles, get_movie,
    build_profile, score_movie, recommend, rank_movies, score_movie_components, CATALOG,
    recommendation_explanation, profile_confidence_label, mmr_rerank, availability_utility,
    semantic_similarity_scores
)
from src.analytics import ensure_session, start_new_session, record_event, record_impressions, analytics_insights
from src.ml_engine import train_learning_model, predict_success, ranking_metrics, calibration_metrics
from src.watch_providers import get_watch_availability_batch, tmdb_configured
from src.tmdb_catalog import search_movies, get_poster_batch, get_landscape_batch, get_movie_identity_batch, tmdb_catalog_configured, discover_movies
from src.live_ratings import get_live_ratings_batch, omdb_configured
from src.browser_storage import browser_storage
from src.scroll_keeper import scroll_keeper
from src.cf_model import user_vector, cf_affinity, closest_liked, item_similarity
from src.recommender import _calibrated_match_percent

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

/* V5.125 — final Showroom control spacing + clickable full-sentence summary */

/* Give the section explanation its own breathing room before movie controls. */
.showroom-row-header{
    margin-bottom:.86rem !important;
}
.showroom-row-header .row-model-note{
    margin-top:.22rem !important;
    margin-bottom:0 !important;
}

/* Match and Skip stay visually separate inside each card. */
[class*="st-key-showroom_controls_"]{
    margin-top:0 !important;
    margin-bottom:-.34rem !important;
}
[class*="st-key-showroom_controls_"] [data-testid="stHorizontalBlock"]{
    align-items:center !important;
    column-gap:.62rem !important;
}
[class*="st-key-showroom_controls_"] [data-testid="column"]{
    min-width:0 !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] > button,
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button,
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button{
    min-height:1.94rem !important;
    height:1.94rem !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button p,
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button span{
    font-size:.59rem !important;
    white-space:nowrap !important;
    overflow:visible !important;
    text-overflow:clip !important;
}
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button{
    padding-left:.24rem !important;
    padding-right:.24rem !important;
}

/* The sentence itself is the expander. No arrow/chevron or separate label. */
div[data-testid="stExpander"]{
    margin:.1rem 0 .08rem !important;
    border:0 !important;
    background:transparent !important;
}
div[data-testid="stExpander"] details,
div[data-testid="stExpander"] summary{
    border:0 !important;
    background:transparent !important;
}
div[data-testid="stExpander"] summary{
    min-height:2.72rem !important;
    padding:0 !important;
    margin:0 !important;
    display:flex !important;
    align-items:flex-start !important;
    cursor:pointer !important;
    list-style:none !important;
}
div[data-testid="stExpander"] summary::-webkit-details-marker,
div[data-testid="stExpander"] summary::marker{
    display:none !important;
    content:"" !important;
}
div[data-testid="stExpander"] summary svg,
div[data-testid="stExpander"] summary [data-testid="stExpanderToggleIcon"]{
    display:none !important;
    width:0 !important;
    min-width:0 !important;
    margin:0 !important;
}
div[data-testid="stExpander"] summary p{
    margin:0 !important;
    padding:0 !important;
    width:100% !important;
    max-width:100% !important;
    overflow:visible !important;
    text-overflow:clip !important;
    white-space:normal !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.67rem !important;
    line-height:1.34 !important;
    font-weight:620 !important;
    letter-spacing:-.004em !important;
}
div[data-testid="stExpander"] summary:hover p{
    color:var(--ivory) !important;
}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"]{
    padding:.34rem 0 .08rem !important;
}
.movie-full-description{
    margin:0 !important;
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.70rem !important;
    line-height:1.45 !important;
    font-weight:500 !important;
}
.movie-card-actions{
    margin-top:.03rem !important;
    margin-bottom:.04rem !important;
}

/* V5.126 — final Showroom control separation, equal row spacing, native summary toggle */

/* Every row gets the exact same subtitle-to-controls breathing room. */
.showroom-row-header{
    margin-top:0 !important;
    margin-bottom:1.02rem !important;
    padding:0 !important;
}
.showroom-row-header .tab-primary-heading,
.showroom-row-header h3{
    margin:0 0 .28rem !important;
    padding:0 !important;
}
.showroom-row-header .row-model-note{
    margin:0 !important;
    padding:0 !important;
}

/* Pull controls close to poster, but shrink the row inside each card to leave inter-card air. */
[class*="st-key-showroom_controls_"]{
    width:94% !important;
    max-width:94% !important;
    margin:0 6% -.28rem 0 !important;
    padding:0 !important;
}
[class*="st-key-showroom_controls_"] [data-testid="stHorizontalBlock"]{
    align-items:center !important;
    column-gap:.5rem !important;
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
    overflow:hidden !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] > button,
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button,
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button{
    height:1.92rem !important;
    min-height:1.92rem !important;
    padding:.12rem .28rem !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button p,
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button span{
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
    overflow:visible !important;
    text-overflow:clip !important;
    white-space:nowrap !important;
    font-size:.57rem !important;
    letter-spacing:-.008em !important;
}
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"]{
    min-width:0 !important;
    margin:0 !important;
}
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button p{
    font-size:.60rem !important;
}

/* Native clickable sentence: no Streamlit arrow, no marker, no extra label. */
.movie-summary-details{
    margin:.12rem 0 .08rem !important;
    padding:0 !important;
    border:0 !important;
    background:transparent !important;
}
.movie-summary-details > summary{
    list-style:none !important;
    cursor:pointer !important;
    margin:0 !important;
    padding:0 !important;
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.64rem !important;
    line-height:1.25 !important;
    font-weight:630 !important;
    letter-spacing:-.004em !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    min-height:1.48rem !important;
}
.movie-summary-details > summary::-webkit-details-marker{display:none !important;}
.movie-summary-details > summary::marker{content:"" !important;display:none !important;}
.movie-summary-details > summary:hover{color:var(--ivory) !important;}
.movie-summary-details[open] > summary{
    color:var(--ivory) !important;
    margin-bottom:.34rem !important;
}
.movie-summary-details .movie-full-description{
    margin:0 !important;
    padding:.02rem 0 .08rem !important;
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.68rem !important;
    line-height:1.42 !important;
    font-weight:500 !important;
}

/* Loader: only a camera inside a circular loading ring, next to the logo. */
div[data-testid="stStatusWidget"]{
    position:fixed !important;
    top:.96rem !important;
    left:8.68rem !important;
    right:auto !important;
    transform:none !important;
    z-index:999999 !important;
    width:2rem !important;
    min-width:2rem !important;
    max-width:2rem !important;
    height:2rem !important;
    min-height:2rem !important;
    max-height:2rem !important;
    padding:0 !important;
    border:1px solid rgba(169,173,183,.28) !important;
    border-radius:50% !important;
    background:rgba(17,19,21,.96) !important;
    box-shadow:0 0 0 1px rgba(92,111,168,.06) !important;
    overflow:visible !important;
    backdrop-filter:blur(10px) !important;
    animation:icinema-loader-ring 1.1s linear infinite !important;
    background-image:none !important;
}
div[data-testid="stStatusWidget"] > *{display:none !important;}
/* Simple camera body */
div[data-testid="stStatusWidget"]::before{
    content:"" !important;
    position:absolute !important;
    left:50% !important;
    top:50% !important;
    width:.86rem !important;
    height:.58rem !important;
    transform:translate(-50%,-45%) !important;
    border:1.35px solid rgba(243,240,234,.94) !important;
    border-radius:3px !important;
    background:transparent !important;
    box-sizing:border-box !important;
}
/* Camera lens */
div[data-testid="stStatusWidget"]::after{
    content:"" !important;
    position:absolute !important;
    left:50% !important;
    top:50% !important;
    width:.32rem !important;
    height:.32rem !important;
    transform:translate(-50%,-42%) !important;
    border:1.25px solid rgba(243,240,234,.98) !important;
    border-radius:50% !important;
    background:rgba(92,111,168,.2) !important;
    box-shadow:0 0 6px rgba(92,111,168,.65) !important;
    animation:none !important;
}
@keyframes icinema-loader-ring{
    0%{border-top-color:rgba(92,111,168,.95);border-right-color:rgba(169,173,183,.22);}
    25%{border-right-color:rgba(92,111,168,.95);border-bottom-color:rgba(169,173,183,.22);}
    50%{border-bottom-color:rgba(92,111,168,.95);border-left-color:rgba(169,173,183,.22);}
    75%{border-left-color:rgba(92,111,168,.95);border-top-color:rgba(169,173,183,.22);}
    100%{border-top-color:rgba(92,111,168,.95);border-right-color:rgba(169,173,183,.22);}
}


/* V5.127 — exact row-header spacing + truly centered control labels */

/* Use padding rather than margin so the subtitle-to-controls gap cannot collapse
   differently on the first Showroom row. */
.showroom-row-header{
    margin-top:0 !important;
    margin-bottom:0 !important;
    padding:0 0 1.04rem 0 !important;
    box-sizing:border-box !important;
}
.showroom-row-header .tab-primary-heading,
.showroom-row-header h3{
    margin:0 0 .28rem !important;
    padding:0 !important;
}
.showroom-row-header .row-model-note{
    margin:0 !important;
    padding:0 !important;
}

/* Center Match text independently from the chevron. */
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button{
    position:relative !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    text-align:center !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button p,
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button span{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    text-align:center !important;
    width:100% !important;
    margin:0 !important;
    padding:0 .9rem 0 .25rem !important;
    box-sizing:border-box !important;
    line-height:1 !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button svg{
    position:absolute !important;
    right:.42rem !important;
    top:50% !important;
    transform:translateY(-50%) !important;
    margin:0 !important;
    flex:0 0 auto !important;
}

/* Center Skip label exactly in its capsule. */
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    text-align:center !important;
}
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button p,
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button span{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    width:100% !important;
    margin:0 !important;
    padding:0 !important;
    text-align:center !important;
    line-height:1 !important;
}


/* V5.128 — full Match label + deterministic movie-card vertical slots */

/* MATCH PILL
   Keep the popover functionality, but remove the dropdown-chevron appearance. */
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button svg,
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button [data-testid="stIconMaterial"],
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button [data-testid="stExpanderToggleIcon"]{
    display:none !important;
    width:0 !important;
    min-width:0 !important;
    height:0 !important;
    margin:0 !important;
    padding:0 !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    text-align:center !important;
    overflow:hidden !important;
}
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button p,
[class*="st-key-showroom_controls_"] div[data-testid="stPopover"] button span{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
    margin:0 !important;
    padding:0 .18rem !important;
    overflow:visible !important;
    text-overflow:clip !important;
    white-space:nowrap !important;
    text-align:center !important;
    font-size:.57rem !important;
    font-weight:700 !important;
    line-height:1 !important;
    letter-spacing:-.009em !important;
}
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button,
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button p,
[class*="st-key-showroom_controls_"] [class*="st-key-skip_"] button span{
    text-align:center !important;
    justify-content:center !important;
}

/* TITLE + YEAR SLOT
   Two-line titles and one-line titles consume the exact same card height. */
.poster-caption:not(.library-poster-caption){
    height:4.35rem !important;
    min-height:4.35rem !important;
    max-height:4.35rem !important;
    margin-top:.56rem !important;
    margin-bottom:.12rem !important;
    padding:0 .08rem !important;
    overflow:hidden !important;
    display:flex !important;
    flex-direction:column !important;
    justify-content:flex-start !important;
    box-sizing:border-box !important;
}
.poster-caption:not(.library-poster-caption) .poster-caption-title{
    min-height:2.78rem !important;
    max-height:2.78rem !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    overflow:hidden !important;
    line-height:1.18 !important;
}
.poster-caption:not(.library-poster-caption) .poster-caption-year{
    height:1rem !important;
    min-height:1rem !important;
    max-height:1rem !important;
    margin-top:.14rem !important;
    line-height:1 !important;
}

/* RATINGS SLOT
   Ratings always start and end at the same level. */
.ratings{
    height:1.52rem !important;
    min-height:1.52rem !important;
    max-height:1.52rem !important;
    margin:0 0 .10rem !important;
    display:flex !important;
    align-items:center !important;
    overflow:hidden !important;
}

/* STREAMING SLOT
   Reserve room for up to three provider lines so the summary below never shifts. */
.watch-availability{
    height:3.7rem !important;
    min-height:3.7rem !important;
    max-height:3.7rem !important;
    margin:.04rem 0 .12rem !important;
    line-height:1.34 !important;
    overflow:hidden !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:3 !important;
}

/* SUMMARY SLOT
   Give the clickable witty sentence an identical row on every card. */
.movie-summary-details{
    min-height:1.72rem !important;
    margin:0 0 .08rem !important;
}
.movie-summary-details > summary{
    min-height:1.72rem !important;
    max-height:1.72rem !important;
    display:flex !important;
    align-items:center !important;
    overflow:hidden !important;
}

/* Buttons stay close to the collapsed summary but line up across all cards. */
.movie-card-actions{
    margin-top:.02rem !important;
    margin-bottom:.04rem !important;
}


/* V5.129 — content-aware title/year and streaming/summary spacing */

/* Let title height grow naturally up to two lines, with the year always
   directly underneath the actual title. */
.poster-caption:not(.library-poster-caption){
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin-top:.56rem !important;
    margin-bottom:.12rem !important;
    padding:0 .08rem !important;
    overflow:visible !important;
    display:block !important;
}
.poster-caption:not(.library-poster-caption) .poster-caption-title{
    min-height:0 !important;
    max-height:none !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    overflow:hidden !important;
    line-height:1.18 !important;
    margin:0 !important;
}
.poster-caption:not(.library-poster-caption) .poster-caption-year{
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin-top:.18rem !important;
    line-height:1.1 !important;
}

/* IMDb / RT sits a consistent distance below the year, regardless of title length. */
.ratings{
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:.34rem 0 .12rem !important;
    display:block !important;
    overflow:visible !important;
}

/* Streaming can wrap naturally. The summary always sits the same distance
   below the *end* of the streaming block. */
.watch-availability{
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:.06rem 0 .34rem !important;
    line-height:1.34 !important;
    overflow:visible !important;
    display:block !important;
    -webkit-line-clamp:unset !important;
}

/* Keep the clickable one-line summary close to streaming with a consistent gap. */
.movie-summary-details{
    min-height:0 !important;
    margin:0 0 .08rem !important;
}
.movie-summary-details > summary{
    min-height:1.72rem !important;
    max-height:none !important;
    margin:0 !important;
}

/* Actions remain close to the summary. */
.movie-card-actions{
    margin-top:.02rem !important;
    margin-bottom:.04rem !important;
}


/* V5.130 — compact Save / Seen action row */
.movie-card-actions{
    margin-top:.02rem !important;
    margin-bottom:.02rem !important;
}

/* Keep Save / Seen visually balanced but slightly shorter to save vertical space. */
[class*="st-key-save_"],
[class*="st-key-seen_"]{
    margin-top:0 !important;
    margin-bottom:0 !important;
}
[class*="st-key-save_"] button,
[class*="st-key-seen_"] button{
    min-height:1.82rem !important;
    height:1.82rem !important;
    padding:.12rem .28rem !important;
    border-radius:999px !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
}
[class*="st-key-save_"] button p,
[class*="st-key-seen_"] button p{
    margin:0 !important;
    font-size:.64rem !important;
    line-height:1 !important;
    font-weight:690 !important;
    text-align:center !important;
}

/* Pull the action row slightly closer to the collapsed summary without crowding it. */
.movie-summary-details{
    margin-bottom:.04rem !important;
}


/* V5.131 — data-driven Match explanation + two-line clickable movie summary */

.match-reason{
    padding:.44rem 0 .48rem !important;
    border-bottom:1px solid rgba(169,173,183,.12) !important;
}
.match-reason:last-of-type{
    border-bottom:0 !important;
}
.match-reason-label{
    color:var(--ivory) !important;
    font-family:var(--ui-font) !important;
    font-size:.69rem !important;
    line-height:1.18 !important;
    font-weight:760 !important;
    letter-spacing:-.005em !important;
    margin-bottom:.16rem !important;
}
.match-reason-copy{
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.66rem !important;
    line-height:1.38 !important;
    font-weight:500 !important;
}

/* Checkbox-driven disclosure: the sentence itself is clickable and there is no arrow. */
.movie-summary-toggle{
    width:100% !important;
    margin:.1rem 0 .06rem !important;
    padding:0 !important;
}
.movie-summary-checkbox{
    position:absolute !important;
    opacity:0 !important;
    pointer-events:none !important;
    width:0 !important;
    height:0 !important;
}
.movie-summary-label{
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    width:100% !important;
    max-width:100% !important;
    min-height:2.42rem !important;
    max-height:2.42rem !important;
    overflow:hidden !important;
    cursor:pointer !important;
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.66rem !important;
    line-height:1.34 !important;
    font-weight:620 !important;
    letter-spacing:-.004em !important;
    margin:0 !important;
    padding:0 !important;
    box-sizing:border-box !important;
}
.movie-summary-label:hover{
    color:var(--ivory) !important;
}
.movie-summary-toggle .movie-full-description{
    display:none !important;
    margin:.34rem 0 .06rem !important;
    padding:.42rem .02rem .12rem !important;
    border-top:1px solid rgba(169,173,183,.12) !important;
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.68rem !important;
    line-height:1.44 !important;
    font-weight:500 !important;
}
.movie-summary-checkbox:checked ~ .movie-full-description{
    display:block !important;
}

/* Retire native-details styles from older versions. */
.movie-summary-details{
    display:none !important;
}

/* Preserve a clean gap before actions and prevent overlap. */
.movie-card-actions{
    margin-top:.06rem !important;
    clear:both !important;
}


/* V5.139 — clean Showroom rebuild from stable V5.131 */

/* Uniform section heading rhythm. */
.showroom-row-header{
    margin:0 !important;
    padding:0 0 .86rem 0 !important;
}
.showroom-row-title{
    color:var(--ivory) !important;
    font-family:var(--ui-font) !important;
    font-size:2rem !important;
    line-height:1.08 !important;
    font-weight:760 !important;
    letter-spacing:-.03em !important;
    margin:0 0 .26rem 0 !important;
    padding:0 !important;
}
.showroom-row-header .row-model-note{
    margin:0 !important;
    padding:0 !important;
}
.showroom-row,
.showroom-row.first{
    margin:0 !important;
    transform:none !important;
}

/* Match explanation note uses the product font system. */
.match-model-note{
    color:var(--muted2) !important;
    font-family:var(--ui-font) !important;
    font-size:.62rem !important;
    line-height:1.36 !important;
    font-weight:500 !important;
    margin:.42rem 0 0 !important;
}

/* Critical reset: normal document flow for the full Showroom card. */
[class*="st-key-showroom_body_"]{
    display:block !important;
    position:static !important;
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:0 !important;
    padding:0 !important;
    overflow:visible !important;
    container-type:normal !important;
}

/* Title + year use content-aware height. */
[class*="st-key-showroom_body_"] .poster-caption:not(.library-poster-caption){
    display:block !important;
    position:static !important;
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:.52rem 0 .34rem !important;
    padding:0 !important;
    overflow:visible !important;
}
[class*="st-key-showroom_body_"] .poster-caption-title{
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
    line-height:1.17 !important;
}
[class*="st-key-showroom_body_"] .poster-caption-year{
    display:block !important;
    position:static !important;
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:.17rem 0 0 !important;
    padding:0 !important;
    line-height:1.05 !important;
}

/* Each metadata block is ordinary flow with explicit bottom gap. */
[class*="st-key-showroom_body_"] .ratings{
    display:block !important;
    position:static !important;
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:0 0 .30rem !important;
    padding:0 !important;
    line-height:1.22 !important;
    overflow:visible !important;
}
[class*="st-key-showroom_body_"] .watch-availability{
    display:block !important;
    position:static !important;
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:0 0 .32rem !important;
    padding:0 !important;
    line-height:1.32 !important;
    overflow:visible !important;
    -webkit-line-clamp:unset !important;
}

/* Clickable summary: one line collapsed, normal-flow expanded copy. */
[class*="st-key-showroom_body_"] .movie-summary-toggle{
    display:block !important;
    position:static !important;
    width:100% !important;
    height:auto !important;
    min-height:0 !important;
    margin:0 0 .24rem !important;
    padding:0 !important;
}
[class*="st-key-showroom_body_"] .movie-summary-label{
    display:block !important;
    width:100% !important;
    height:auto !important;
    min-height:0 !important;
    max-height:none !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
    white-space:nowrap !important;
    text-overflow:clip !important;
    font-size:.56rem !important;
    line-height:1.35 !important;
}
[class*="st-key-showroom_body_"] .movie-summary-toggle .movie-full-description{
    position:static !important;
    margin:.34rem 0 .06rem !important;
    padding:.36rem 0 .04rem !important;
    line-height:1.42 !important;
}

/* Save/Seen are normal flow. No auto-bottom alignment or artificial card height. */
[class*="st-key-movie_actions_"]{
    display:block !important;
    position:static !important;
    height:auto !important;
    min-height:0 !important;
    margin:.02rem 0 0 !important;
    padding:0 !important;
}
[class*="st-key-movie_actions_"] button{
    height:1.82rem !important;
    min-height:1.82rem !important;
    margin:0 !important;
}

/* Required attribution stays quiet. */
.watch-attribution{
    color:rgba(169,173,183,.45) !important;
    font-family:var(--ui-font) !important;
    font-size:.49rem !important;
    line-height:1.34 !important;
    font-weight:450 !important;
    margin:.55rem 0 .10rem !important;
    max-width:92% !important;
}


/* V5.140 — Saved library action label fix */
[class*="st-key-savedseen_"],
[class*="st-key-unsave_"]{
    min-width:0 !important;
    width:100% !important;
}
[class*="st-key-savedseen_"] button,
[class*="st-key-unsave_"] button{
    width:100% !important;
    min-width:0 !important;
    min-height:2.34rem !important;
    height:2.34rem !important;
    padding:.14rem .34rem !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    text-align:center !important;
    overflow:visible !important;
}
[class*="st-key-savedseen_"] button p,
[class*="st-key-savedseen_"] button span,
[class*="st-key-unsave_"] button p,
[class*="st-key-unsave_"] button span{
    width:100% !important;
    max-width:none !important;
    min-width:0 !important;
    margin:0 !important;
    padding:0 !important;
    overflow:visible !important;
    text-overflow:clip !important;
    white-space:nowrap !important;
    font-size:.62rem !important;
    line-height:1 !important;
    font-weight:690 !important;
    text-align:center !important;
    justify-content:center !important;
}


/* V5.141 — Saved heading breathing room */
.st-key-saved_tab_header,
.tab-primary-heading{
    scroll-margin-top:0;
}

/* Add a little more space only below the Saved tab heading before the grid. */
[data-testid="stVerticalBlock"]:has(.tab-primary-heading) .tab-primary-heading{
    margin-bottom:.34rem !important;
}

.saved-tab-heading{
    margin-bottom:.78rem !important;
}


/* V5.142 — Saved action centering + unique natural summaries */
[class*="st-key-savedseen_"] button,
[class*="st-key-unsave_"] button{
    display:grid !important;
    place-items:center !important;
    text-align:center !important;
}
[class*="st-key-savedseen_"] button p,
[class*="st-key-savedseen_"] button span,
[class*="st-key-unsave_"] button p,
[class*="st-key-unsave_"] button span{
    display:block !important;
    width:100% !important;
    margin:0 !important;
    padding:0 !important;
    text-align:center !important;
    line-height:1 !important;
}


/* V5.143 — even spacing in Match explanation popover */
.match-explain-title{
    margin:0 0 .72rem !important;
    padding:0 !important;
}
.match-reason{
    margin:0 !important;
    padding:.52rem 0 .56rem !important;
    border-bottom:1px solid rgba(169,173,183,.12) !important;
}
.match-reason:first-of-type{
    padding-top:0 !important;
}
.match-reason:last-of-type{
    border-bottom:0 !important;
    padding-bottom:.52rem !important;
}
.match-reason-label{
    margin:0 0 .22rem !important;
    padding:0 !important;
    line-height:1.2 !important;
}
.match-reason-copy{
    margin:0 !important;
    padding:0 !important;
    line-height:1.4 !important;
}
.match-model-note{
    margin:.58rem 0 0 !important;
    padding:.56rem 0 0 !important;
    border-top:1px solid rgba(169,173,183,.10) !important;
    line-height:1.38 !important;
}


/* V5.144 — balanced Match panel + two-line movie summary */

/* Give the Match explanation equal visual breathing room at the top and bottom. */
.match-explain-title{
    margin:.58rem 0 .72rem !important;
    padding:0 !important;
}
.match-reason{
    margin:0 !important;
    padding:.52rem 0 .56rem !important;
}
.match-reason:first-of-type{
    padding-top:0 !important;
}
.match-reason:last-of-type{
    padding-bottom:.52rem !important;
}
.match-model-note{
    margin:.58rem 0 .58rem !important;
    padding:.56rem 0 0 !important;
    border-top:1px solid rgba(169,173,183,.10) !important;
}

/* Let longer movie summaries use two clean lines instead of clipping. */
[class*="st-key-showroom_body_"] .movie-summary-toggle{
    margin:0 0 .24rem !important;
}
[class*="st-key-showroom_body_"] .movie-summary-label{
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    width:100% !important;
    height:auto !important;
    min-height:1.35rem !important;
    max-height:2.72rem !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
    white-space:normal !important;
    text-overflow:clip !important;
    font-size:.56rem !important;
    line-height:1.36rem !important;
}


/* V5.145 — complete two-line witty summary */
[class*="st-key-showroom_body_"] .movie-summary-label{
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    width:100% !important;
    min-height:1.35rem !important;
    max-height:2.76rem !important;
    height:auto !important;
    overflow:hidden !important;
    white-space:normal !important;
    text-overflow:clip !important;
    font-size:.56rem !important;
    line-height:1.38rem !important;
}


/* V5.146 — loading icon aligned directly to the right of iCinema logo */

/* Keep the transient loader visually attached to the brand mark. */
div[data-testid="stStatusWidget"]{
    position:fixed !important;
    top:1.03rem !important;
    left:7.25rem !important;
    right:auto !important;
    transform:none !important;
    z-index:999999 !important;
    margin:0 !important;
}

/* Mobile alignment keeps the same brand-adjacent relationship. */
@media(max-width:700px){
    div[data-testid="stStatusWidget"]{
        top:.82rem !important;
        left:5.15rem !important;
    }
}


/* V5.147 — Step 1 action breathing room */
.shelf-action-gap{
    height:.34rem !important;
}
[class*="st-key-like_"],
[class*="st-key-fav_"]{
    margin-top:0 !important;
}


/* V5.148 — compact Step 1 shelf */

/* Slightly scale the Step 1 movie cards down while preserving proportions. */
.step1-shelf .poster,
[class*="st-key-like_"] ~ * .poster{
    transform:scale(.92);
    transform-origin:top center;
    margin-bottom:-.9rem !important;
}

/* Keep Step 1 title/year proportionally smaller and compact. */
.step1-shelf .poster-caption-title,
.step1-shelf .movie-title,
.step1-shelf .shelf-title{
    font-size:1.02rem !important;
    line-height:1.15 !important;
}
.step1-shelf .poster-caption-year,
.step1-shelf .movie-year,
.step1-shelf .shelf-year{
    font-size:.69rem !important;
    line-height:1 !important;
}

/* Like / Favorite become slightly shorter while staying easy to tap. */
[class*="st-key-like_"] button,
[class*="st-key-fav_"] button{
    min-height:2.05rem !important;
    height:2.05rem !important;
    padding:.12rem .34rem !important;
    border-radius:999px !important;
}
[class*="st-key-like_"] button p,
[class*="st-key-fav_"] button p{
    font-size:.72rem !important;
    line-height:1 !important;
    font-weight:690 !important;
}

/* Preserve the new breathing room from V5.147, but keep it compact. */
.shelf-action-gap{
    height:.28rem !important;
}

/* Tighten horizontal spacing slightly across the Step 1 shelf. */
.step1-shelf [data-testid="stHorizontalBlock"]{
    column-gap:.72rem !important;
}


/* V5.149 — refined Step 1 scale + centered actions */

/* Scale Step 1 posters down slightly more than V5.148. */
.step1-shelf .poster,
[class*="st-key-like_"] ~ * .poster{
    transform:scale(.89) !important;
    transform-origin:top center !important;
    margin-bottom:-1.18rem !important;
}

/* Scale title/year proportionally. */
.step1-shelf .poster-caption-title,
.step1-shelf .movie-title,
.step1-shelf .shelf-title{
    font-size:.98rem !important;
    line-height:1.14 !important;
}
.step1-shelf .poster-caption-year,
.step1-shelf .movie-year,
.step1-shelf .shelf-year{
    font-size:.66rem !important;
    line-height:1 !important;
}

/* Slightly smaller Like/Favorite buttons, with exact centered labels. */
[class*="st-key-like_"] button,
[class*="st-key-fav_"] button{
    min-height:1.96rem !important;
    height:1.96rem !important;
    padding:.1rem .3rem !important;
    border-radius:999px !important;
    display:grid !important;
    place-items:center !important;
    text-align:center !important;
}
[class*="st-key-like_"] button p,
[class*="st-key-like_"] button span,
[class*="st-key-fav_"] button p,
[class*="st-key-fav_"] button span{
    display:block !important;
    width:100% !important;
    margin:0 !important;
    padding:0 !important;
    font-size:.69rem !important;
    line-height:1 !important;
    font-weight:690 !important;
    text-align:center !important;
}

/* Keep spacing compact but not cramped. */
.shelf-action-gap{
    height:.24rem !important;
}
.step1-shelf [data-testid="stHorizontalBlock"]{
    column-gap:.66rem !important;
}


/* V5.150 — removable Step 1 selections */
.selection-area-heading{
    margin-top:.78rem !important;
}
.selection-heading{
    margin-bottom:.5rem !important;
}

[class*="st-key-selection_card_"]{
    position:relative !important;
    min-height:4.1rem !important;
    margin:0 0 .5rem !important;
    padding:.56rem .72rem !important;
    border:1px solid rgba(169,173,183,.22) !important;
    background:rgba(243,240,234,.04) !important;
    border-radius:13px !important;
    box-sizing:border-box !important;
    transition:border-color .16s ease, background .16s ease !important;
}
[class*="st-key-selection_card_"]:hover{
    border-color:rgba(169,173,183,.38) !important;
    background:rgba(243,240,234,.055) !important;
}
[class*="st-key-selection_card_"] .selection-card-copy{
    padding-right:1.45rem !important;
}
[class*="st-key-selection_card_"] .selection-title{
    color:var(--ivory) !important;
    font-family:var(--ui-font) !important;
    font-size:.91rem !important;
    line-height:1.26 !important;
    font-weight:800 !important;
    letter-spacing:-.018em !important;
    margin:0 0 .12rem !important;
}
[class*="st-key-selection_card_"] .selection-state{
    color:var(--muted2) !important;
    font-family:var(--ui-font) !important;
    font-size:.64rem !important;
    line-height:1 !important;
    font-weight:740 !important;
    text-transform:uppercase !important;
    letter-spacing:.08em !important;
}

/* The remove control lives in the top-right and becomes prominent on hover. */
[class*="st-key-selection_card_"] [class*="st-key-remove_selection_"]{
    position:absolute !important;
    top:.28rem !important;
    right:.3rem !important;
    width:1.36rem !important;
    height:1.36rem !important;
    margin:0 !important;
    z-index:3 !important;
    opacity:.28 !important;
    transition:opacity .16s ease, transform .16s ease !important;
}
[class*="st-key-selection_card_"]:hover [class*="st-key-remove_selection_"]{
    opacity:1 !important;
}
[class*="st-key-selection_card_"] [class*="st-key-remove_selection_"] button{
    width:1.36rem !important;
    min-width:1.36rem !important;
    max-width:1.36rem !important;
    height:1.36rem !important;
    min-height:1.36rem !important;
    max-height:1.36rem !important;
    margin:0 !important;
    padding:0 !important;
    border:0 !important;
    border-radius:999px !important;
    background:transparent !important;
    color:var(--muted) !important;
    box-shadow:none !important;
    display:grid !important;
    place-items:center !important;
}
[class*="st-key-selection_card_"] [class*="st-key-remove_selection_"] button:hover{
    color:var(--ivory) !important;
    background:rgba(255,255,255,.06) !important;
}
[class*="st-key-selection_card_"] [class*="st-key-remove_selection_"] button p,
[class*="st-key-selection_card_"] [class*="st-key-remove_selection_"] button span{
    margin:0 !important;
    padding:0 !important;
    font-size:.9rem !important;
    line-height:1 !important;
    font-weight:500 !important;
    text-align:center !important;
}

@media(max-width:800px){
    [class*="st-key-selection_card_"] [class*="st-key-remove_selection_"]{
        opacity:.72 !important;
    }
}


/* V5.151 — single camera loader directly beside the iCinema logo */

/* The app content is max-width 1240px and centered. Position the transient
   status widget from that same content edge, immediately after the logo. */
div[data-testid="stStatusWidget"]{
    position:fixed !important;
    top:2.22rem !important;
    left:max(1.25rem, calc((100vw - 1240px) / 2 + 6.55rem)) !important;
    right:auto !important;
    transform:none !important;
    z-index:999999 !important;

    /* Same visual height as the logo text, not a separate floating badge. */
    width:1.68rem !important;
    min-width:1.68rem !important;
    max-width:1.68rem !important;
    height:1.68rem !important;
    min-height:1.68rem !important;
    max-height:1.68rem !important;
    margin:0 !important;
    padding:0 !important;

    /* Keep only the existing camera-in-circle loader. */
    border:1px solid rgba(169,173,183,.28) !important;
    border-radius:50% !important;
    background:rgba(17,19,21,.96) !important;
    box-shadow:0 0 0 1px rgba(92,111,168,.06) !important;
    overflow:visible !important;
    backdrop-filter:blur(10px) !important;
    animation:icinema-loader-ring 1.1s linear infinite !important;
    background-image:none !important;
}
div[data-testid="stStatusWidget"] > *{
    display:none !important;
}

/* Same camera mark, scaled to the logo-height loader. */
div[data-testid="stStatusWidget"]::before{
    content:"" !important;
    position:absolute !important;
    left:50% !important;
    top:50% !important;
    width:.76rem !important;
    height:.51rem !important;
    transform:translate(-50%,-45%) !important;
    border:1.25px solid rgba(243,240,234,.94) !important;
    border-radius:3px !important;
    background:transparent !important;
    box-sizing:border-box !important;
}
div[data-testid="stStatusWidget"]::after{
    content:"" !important;
    position:absolute !important;
    left:50% !important;
    top:50% !important;
    width:.28rem !important;
    height:.28rem !important;
    transform:translate(-50%,-42%) !important;
    border:1.15px solid rgba(243,240,234,.98) !important;
    border-radius:50% !important;
    background:rgba(92,111,168,.20) !important;
    box-shadow:0 0 6px rgba(92,111,168,.65) !important;
    animation:none !important;
}

/* Suppress any other Streamlit loading/spinner visuals so the camera above
   is the only loader the user sees. */
div[data-testid="stSpinner"],
div[data-testid="stLoadingSpinner"],
.stSpinner,
[data-testid="stStatusWidget"] svg,
[data-testid="stStatusWidget"] [role="progressbar"]{
    display:none !important;
}

/* Align with the mobile logo using the same content edge relationship. */
@media(max-width:700px){
    div[data-testid="stStatusWidget"]{
        top:2.08rem !important;
        left:6.08rem !important;
        width:1.52rem !important;
        min-width:1.52rem !important;
        max-width:1.52rem !important;
        height:1.52rem !important;
        min-height:1.52rem !important;
        max-height:1.52rem !important;
    }
}


/* V5.153 — Profile methodology cards */
.profile-methodology{
    width:100% !important;
    max-width:760px !important;
    margin-top:1.12rem !important;
    padding-top:1.08rem !important;
    border-top:1px solid var(--border) !important;
}
.methodology-grid{
    display:grid !important;
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
    gap:.62rem !important;
}
.methodology-card{
    border:1px solid var(--border) !important;
    border-radius:14px !important;
    background:rgba(255,255,255,.018) !important;
    padding:.76rem .8rem !important;
    min-height:6.15rem !important;
}
.methodology-value{
    font-family:var(--ui-font) !important;
    color:var(--ivory) !important;
    font-size:.78rem !important;
    line-height:1.28 !important;
    font-weight:760 !important;
    letter-spacing:-.012em !important;
    margin-bottom:.34rem !important;
}
.methodology-label{
    font-family:var(--ui-font) !important;
    color:var(--muted) !important;
    font-size:.64rem !important;
    line-height:1.42 !important;
    font-weight:500 !important;
}
@media(max-width:800px){
    .methodology-grid{grid-template-columns:1fr !important;}
}


/* V5.154 — clearly separate witty hook from expanded synopsis */
.movie-full-description{
    margin-top:.42rem !important;
    padding-top:.48rem !important;
    border-top:1px solid rgba(169,173,183,.13) !important;
}
.movie-synopsis-label{
    color:var(--ivory) !important;
    font-family:var(--ui-font) !important;
    font-size:.60rem !important;
    line-height:1.2 !important;
    font-weight:740 !important;
    letter-spacing:.012em !important;
    margin:0 0 .28rem !important;
}
.movie-synopsis-copy{
    color:var(--muted) !important;
    font-family:var(--ui-font) !important;
    font-size:.66rem !important;
    line-height:1.46 !important;
    font-weight:500 !important;
    margin:0 !important;
    padding:0 !important;
}

/* V5.162 — visibly larger gap between the Cinema Profile title and learning-status row.
   Use the more-specific profile-wrap selectors so this overrides the earlier tab-heading rule. */
.profile-wrap .profile-heading,
.profile-wrap .profile-heading-aligned{
    margin-bottom:1.45rem !important;
}
.profile-wrap .model-status-line{
    margin-top:0 !important;
}


/* V5.163 — explicit spacer between Cinema Profile heading and learning-status row.
   This avoids Streamlit/global tab-heading margin rules overriding the intended gap. */
.profile-heading-gap{
    display:block !important;
    height:.78rem !important;
    min-height:.78rem !important;
    width:100% !important;
    flex:0 0 .78rem !important;
}

/* V5.155 — uniform learning-status text color */
.model-status-line,
.model-status-primary,
.model-status-secondary,
.model-status-separator{
    color:var(--muted) !important;
}
.model-status-primary{
    font-weight:680 !important;
}
.model-status-dot{
    color:var(--ai) !important;
    background:var(--ai) !important;
}


/* V5.165 — single, consistent iCinema camera loader.
   Keep transient status away from the logo and anchor it to the top-right of
   the centered product frame, where users expect passive system status. */
div[data-testid="stStatusWidget"],
.icinema-boot-loader{
    position:fixed !important;
    top:2.08rem !important;
    left:auto !important;
    right:max(1.25rem, calc((100vw - 1240px) / 2 + 1.25rem)) !important;
    transform:none !important;
    z-index:999999 !important;
    width:1.62rem !important;
    min-width:1.62rem !important;
    max-width:1.62rem !important;
    height:1.62rem !important;
    min-height:1.62rem !important;
    max-height:1.62rem !important;
    margin:0 !important;
    padding:0 !important;
    border:1px solid rgba(169,173,183,.28) !important;
    border-radius:50% !important;
    background:rgba(17,19,21,.96) !important;
    background-image:none !important;
    box-shadow:0 0 0 1px rgba(92,111,168,.06) !important;
    overflow:visible !important;
    backdrop-filter:blur(10px) !important;
    animation:icinema-loader-ring 1.1s linear infinite !important;
}
div[data-testid="stStatusWidget"] > *{
    display:none !important;
}
div[data-testid="stStatusWidget"]::before,
.icinema-boot-loader::before{
    content:"" !important;
    position:absolute !important;
    left:50% !important;
    top:50% !important;
    width:.74rem !important;
    height:.50rem !important;
    transform:translate(-50%,-45%) !important;
    border:1.25px solid rgba(243,240,234,.94) !important;
    border-radius:3px !important;
    background:transparent !important;
    box-sizing:border-box !important;
}
div[data-testid="stStatusWidget"]::after,
.icinema-boot-loader::after{
    content:"" !important;
    position:absolute !important;
    left:50% !important;
    top:50% !important;
    width:.27rem !important;
    height:.27rem !important;
    transform:translate(-50%,-42%) !important;
    border:1.15px solid rgba(243,240,234,.98) !important;
    border-radius:50% !important;
    background:rgba(92,111,168,.20) !important;
    box-shadow:0 0 6px rgba(92,111,168,.65) !important;
}
/* Suppress competing Streamlit progress/spinner/skeleton visuals. */
div[data-testid="stSpinner"],
div[data-testid="stLoadingSpinner"],
.stSpinner,
[data-testid="stProgress"],
[data-testid="stSkeleton"],
[data-testid="stStatusWidget"] svg,
[data-testid="stStatusWidget"] [role="progressbar"]{
    display:none !important;
}
@media(max-width:700px){
    div[data-testid="stStatusWidget"],
    .icinema-boot-loader{
        top:1.92rem !important;
        right:1rem !important;
        width:1.48rem !important;
        min-width:1.48rem !important;
        max-width:1.48rem !important;
        height:1.48rem !important;
        min-height:1.48rem !important;
        max-height:1.48rem !important;
    }
}

/* Model diagnostics: 3 x 2 grid */
.diag-subhead{font-family:var(--ui-font);font-size:.7rem;font-weight:760;letter-spacing:.08em;text-transform:uppercase;color:var(--muted2);margin:.9rem 0 .3rem;}
.diag-subhead:first-of-type{margin-top:.2rem;}
.diag-grid{grid-template-columns:repeat(3,minmax(0,1fr)) !important;}
@media(max-width:800px){.diag-grid{grid-template-columns:repeat(2,minmax(0,1fr)) !important;}}

/* V5.166 — Tonight's Pick: one confident answer, tastefully spaced */
@keyframes icinema-tonight-in{
    from{opacity:0;transform:translateY(6px)}
    to{opacity:1;transform:translateY(0)}
}
.tonight-header{margin:0 0 .9rem !important;}
.tonight-kicker{
    color:var(--muted2);font-family:var(--ui-font);font-size:.68rem;font-weight:760;
    text-transform:uppercase;letter-spacing:.11em;margin:0 0 .3rem;
}
.tonight-heading{
    color:var(--ivory);font-family:var(--ui-font);font-size:2rem;line-height:1.08;
    font-weight:760;letter-spacing:-.03em;margin:0 0 .28rem;
}
.tonight-note{color:var(--muted);font-family:var(--ui-font);font-size:.8rem;line-height:1.4;margin:0;}
[class*="st-key-tonight_hero"]{
    border:1px solid var(--border) !important;
    border-radius:22px !important;
    background:linear-gradient(180deg,rgba(255,255,255,.028),rgba(255,255,255,.012)) !important;
    padding:1.6rem 1.7rem !important;
    margin:0 0 2.4rem !important;
    animation:icinema-tonight-in .38s ease-out both;
}
[class*="st-key-tonight_hero"] .poster{max-width:280px;margin:0 auto;}
.tonight-title{
    color:var(--ivory);font-family:var(--ui-font);font-size:1.9rem;line-height:1.08;
    font-weight:800;letter-spacing:-.035em;margin:.1rem 0 .3rem;
}
.tonight-meta{
    color:var(--muted);font-family:var(--ui-font);font-size:.74rem;font-weight:700;
    letter-spacing:.06em;text-transform:uppercase;margin:0 0 .95rem;
}
.tonight-match{
    display:inline-flex;align-items:center;height:1.9rem;padding:0 .8rem;border-radius:999px;
    border:1px solid rgba(92,111,168,.6);background:rgba(92,111,168,.12);color:var(--ivory);
    font-family:var(--ui-font);font-size:.72rem;font-weight:720;margin:0 0 1rem;
}
.tonight-line{color:var(--muted);font-family:var(--ui-font);font-size:.8rem;line-height:1.45;font-weight:600;margin:0 0 .35rem;}
.tonight-fit{color:var(--muted2);font-family:var(--ui-font);font-size:.72rem;font-weight:650;margin:0 0 1rem;}
.tonight-fit.good{color:#9FB2E6;}
.tonight-hook{color:var(--ivory);font-family:var(--ui-font);font-size:.95rem;line-height:1.45;font-weight:650;margin:0 0 .6rem;}
.tonight-synopsis{color:var(--muted);font-family:var(--ui-font);font-size:.8rem;line-height:1.55;margin:0 0 1.1rem;max-width:560px;}
.tonight-why-label{color:var(--muted2);font-family:var(--ui-font);font-size:.64rem;font-weight:760;text-transform:uppercase;letter-spacing:.1em;margin:0 0 .4rem;}
.tonight-why{color:var(--muted);font-family:var(--ui-font);font-size:.76rem;line-height:1.45;margin:0 0 .3rem;}
.tonight-why strong{color:var(--ivory);font-weight:700;}
[class*="st-key-tonight_save_"] button,
[class*="st-key-tonight_seen_"] button,
[class*="st-key-tonight_skip_"] button{
    min-height:2.3rem !important;height:2.3rem !important;border-radius:999px !important;
}
[class*="st-key-tonight_save_"] button p,
[class*="st-key-tonight_seen_"] button p,
[class*="st-key-tonight_skip_"] button p{font-size:.74rem !important;font-weight:690 !important;margin:0 !important;}
[class*="st-key-service_"] button{min-height:2.1rem !important;border-radius:999px !important;}
[class*="st-key-service_"] button p{font-size:.72rem !important;font-weight:680 !important;}
@media(max-width:800px){
    [class*="st-key-tonight_hero"]{padding:1.1rem 1rem !important;}
    [class*="st-key-tonight_hero"] .poster{max-width:220px;}
    .tonight-title{font-size:1.5rem;}
}

/* V5.169 — original card spacing restored; compact Tonight's Pick; one loader */
/* Tonight's Pick header uses the row-header style, with a tighter gap to its card. */
.tonight-row-header{margin:0 !important;padding:0 !important;}
[class*="st-key-tonight_hero"]{
    margin:.55rem 0 .35rem !important;padding:.95rem 1.05rem !important;border-radius:18px !important;
    animation:icinema-tonight-in .3s ease-out both;
}
[class*="st-key-tonight_hero"] .poster{max-width:118px !important;margin:0 !important;border-radius:12px !important;}
[class*="st-key-tonight_hero"] .poster.has-image img{border-radius:11px !important;}
.tonight-stack{display:flex;flex-direction:column;gap:.38rem;margin:0 0 .6rem;}
.tonight-stack > div{margin:0 !important;}
.tonight-title{font-size:1.25rem !important;line-height:1.15 !important;margin:0 !important;}
.tonight-meta{font-size:.66rem !important;margin:0 !important;}
.tonight-badges{display:flex;align-items:center;gap:.55rem;flex-wrap:wrap;}
.tonight-match{height:1.55rem !important;font-size:.66rem !important;padding:0 .65rem !important;margin:0 !important;}
.tonight-fit{font-size:.68rem !important;margin:0 !important;}
.tonight-line{font-size:.72rem !important;margin:0 !important;}
.tonight-hook{font-size:.82rem !important;line-height:1.42 !important;margin:0 !important;}
.tonight-whys{display:flex;flex-direction:column;gap:.2rem;}
.tonight-why{font-size:.7rem !important;line-height:1.4 !important;margin:0 !important;}
[class*="st-key-tonight_save_"] button,[class*="st-key-tonight_seen_"] button,
[class*="st-key-tonight_skip_"] button,[class*="st-key-tonight_undo_"] button{
    min-height:1.9rem !important;height:1.9rem !important;padding:0 .5rem !important;border-radius:999px !important;
    display:flex !important;align-items:center !important;justify-content:center !important;
}
[class*="st-key-tonight_save_"] button p,[class*="st-key-tonight_seen_"] button p,
[class*="st-key-tonight_skip_"] button p,[class*="st-key-tonight_undo_"] button p{
    font-size:.68rem !important;margin:0 !important;width:auto !important;text-align:center !important;line-height:1 !important;
}
.services-help{font-family:var(--ui-font);font-size:.72rem;color:var(--muted);line-height:1.4;margin:0 0 .6rem;}
div[data-testid="stPills"] button{font-family:var(--ui-font) !important;}
@media(max-width:800px){
    [class*="st-key-tonight_hero"] .poster{max-width:104px !important;}
    .tonight-title{font-size:1.1rem !important;}
}
/* Per-card Undo sits beside Skip at the same pill height. */
[class*="st-key-undo_"] button{min-height:1.92rem !important;height:1.92rem !important;padding:0 !important;border-radius:999px !important;}
[class*="st-key-undo_"] button p{font-size:.8rem !important;margin:0 !important;}
/* Service names in the streaming line are one-tap links. */
a.watch-link{
    color:inherit !important;text-decoration:none !important;font-weight:inherit;
    border-bottom:1px solid rgba(169,173,183,.45);transition:border-color .15s ease;
}
a.watch-link:hover{border-bottom-color:var(--ivory);color:var(--ivory) !important;}
a.watch-link::after{content:" ↗";font-size:.8em;opacity:.6;}
/* One loader everywhere: match the status widget regardless of element type and
   hide every Streamlit running icon, label, and Stop button inside it. */
[data-testid="stStatusWidget"] *,
[data-testid="stStatusWidget"] img,
[data-testid="stStatusWidget"] svg,
[data-testid="stStatusWidget"] button,
[data-testid*="RunningIcon"],
[data-testid="stAppRunningIcon"]{display:none !important;}
[data-testid="stStatusWidget"]{
    position:fixed !important;top:2.08rem !important;left:auto !important;
    right:max(1.25rem, calc((100vw - 1240px) / 2 + 1.25rem)) !important;
    width:1.62rem !important;min-width:1.62rem !important;max-width:1.62rem !important;
    height:1.62rem !important;min-height:1.62rem !important;max-height:1.62rem !important;
    margin:0 !important;padding:0 !important;overflow:visible !important;z-index:999999 !important;
    border:1px solid rgba(169,173,183,.28) !important;border-radius:50% !important;
    background:rgba(17,19,21,.96) !important;animation:icinema-loader-ring 1.1s linear infinite !important;
}

/* V5.170 — alignment, complete hooks, section breathing room, clear model status, profile rhythm */
/* One left edge: titles, years, and metadata line up with the poster. */
.poster-caption,.poster-caption:not(.library-poster-caption),.library-poster-caption{padding-left:0 !important;padding-right:0 !important;}
.poster-caption-title,.poster-caption-year,.ratings,.watch-availability,.movie-summary-toggle,.movie-summary-label{margin-left:0 !important;padding-left:0 !important;}
/* Hooks are complete sentences up to three lines; never clipped. */
.movie-summary-label,[class*="st-key-showroom_body_"] .movie-summary-label{
    -webkit-line-clamp:3 !important;max-height:none !important;min-height:0 !important;overflow:visible !important;
    white-space:normal !important;text-overflow:clip !important;
}
/* A little more room between the four Showroom sections. */
.showroom-row-header:not(.tonight-row-header){margin-top:1.55rem !important;}
/* Model status: two short, readable rows instead of one long line. */
.model-status-panel{display:flex;flex-direction:column;gap:.38rem;margin:.1rem 0 1.35rem;max-width:760px;}
.model-row{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;font-family:var(--ui-font);font-size:.76rem;line-height:1.35;}
.model-dot{width:.42rem;height:.42rem;border-radius:999px;border:1px solid var(--muted2);flex:0 0 auto;}
.model-dot.on{background:var(--ai);border-color:var(--ai);box-shadow:0 0 8px rgba(92,111,168,.7);animation:icinema-learning-live 1.8s ease-in-out infinite;}
.model-name{color:var(--ivory);font-weight:700;}
.model-note{color:var(--muted);font-weight:500;}
.model-progress{display:inline-block;width:5.5rem;height:.28rem;border-radius:999px;background:rgba(169,173,183,.18);overflow:hidden;}
.model-progress span{display:block;height:100%;background:var(--ai);border-radius:999px;}
/* Profile: heading → status → sections on one even rhythm. */
.profile-heading-gap{height:.55rem !important;min-height:.55rem !important;flex-basis:.55rem !important;}
.profile-wrap .profile-heading,.profile-wrap .profile-heading-aligned{margin-bottom:0 !important;}
.profile-grid{padding-top:0 !important;}
.profile-block + .profile-block{margin-top:1.05rem !important;}
.profile-label{margin:0 0 .45rem !important;}
.profile-chip-wrap{column-gap:.45rem !important;row-gap:.45rem !important;}
.profile-summary{margin-top:1.35rem !important;padding-top:1.05rem !important;}
.profile-methodology,.profile-insights{margin-top:1.35rem !important;padding-top:1.05rem !important;}

/* V5.171 — model status uses the same type as the original status line */
.model-row{font-size:.72rem !important;line-height:1.35 !important;}
.model-name{color:var(--muted) !important;font-size:.74rem !important;font-weight:680 !important;letter-spacing:-.006em !important;}
.model-note{color:var(--muted) !important;font-size:.72rem !important;font-weight:500 !important;}

/* V5.172 — visible camera loader (top bar stays hidden), popover rhythm, centered button labels, spacing */
/* Loader: Streamlit marks the app while a run is in progress; draw the same camera ring top-right. */
.stApp::before,.stApp::after{content:"";position:fixed;z-index:999999;display:none;pointer-events:none;}
.stApp[data-test-script-state="running"]::before,.stApp:has([data-stale="true"])::before{
    display:block;top:2.08rem;right:max(1.25rem, calc((100vw - 1240px) / 2 + 1.25rem));
    width:1.62rem;height:1.62rem;border-radius:50%;box-sizing:border-box;
    border:1px solid rgba(169,173,183,.28);background:rgba(17,19,21,.96);
    animation:icinema-loader-ring 1.1s linear infinite;
}
.stApp[data-test-script-state="running"]::after,.stApp:has([data-stale="true"])::after{
    display:block;top:calc(2.08rem + .56rem);right:calc(max(1.25rem, calc((100vw - 1240px) / 2 + 1.25rem)) + .44rem);
    width:.74rem;height:.5rem;box-sizing:border-box;border:1.25px solid rgba(243,240,234,.94);border-radius:3px;
    background:radial-gradient(circle at 50% 55%, rgba(92,111,168,.55) 0 .07rem, rgba(243,240,234,.95) .075rem .12rem, transparent .125rem);
}
@media(max-width:700px){
    .stApp[data-test-script-state="running"]::before,.stApp:has([data-stale="true"])::before{top:1.92rem;right:1rem;}
    .stApp[data-test-script-state="running"]::after,.stApp:has([data-stale="true"])::after{top:calc(1.92rem + .56rem);right:1.44rem;}
}
/* Match popover: percent, then "why", then well-spaced specific reasons. */
.match-score{display:flex;align-items:baseline;gap:.45rem;margin:.35rem 0 .2rem;}
.match-score-value{font-family:var(--ui-font);font-size:1.5rem;font-weight:800;letter-spacing:-.03em;color:var(--ivory);}
.match-score-label{font-family:var(--ui-font);font-size:.7rem;font-weight:600;color:var(--muted);}
.match-explain-title{margin:.1rem 0 .55rem !important;font-size:.78rem !important;}
.match-reason{padding:.55rem 0 !important;}
.match-reason-label{margin:0 0 .25rem !important;}
/* A little more air between the one-line description and Save / Seen. */
.movie-summary-toggle{margin-bottom:.62rem !important;}
/* Button labels dead-center, vertically and horizontally. */
[class*="st-key-save_"] button,[class*="st-key-seen_"] button,[class*="st-key-skip_"] button,[class*="st-key-undo_"] button,
[class*="st-key-tonight_"] button,[class*="st-key-savedseen_"] button,[class*="st-key-unsave_"] button,
[class*="st-key-like_"] button,[class*="st-key-fav_"] button{
    display:flex !important;align-items:center !important;justify-content:center !important;padding-top:0 !important;padding-bottom:0 !important;
}
[class*="st-key-save_"] button > div,[class*="st-key-seen_"] button > div,[class*="st-key-skip_"] button > div,[class*="st-key-undo_"] button > div,
[class*="st-key-tonight_"] button > div,[class*="st-key-savedseen_"] button > div,[class*="st-key-unsave_"] button > div,
[class*="st-key-like_"] button > div,[class*="st-key-fav_"] button > div{
    display:flex !important;align-items:center !important;justify-content:center !important;margin:0 !important;height:100% !important;
}
[class*="st-key-save_"] button p,[class*="st-key-seen_"] button p,[class*="st-key-skip_"] button p,[class*="st-key-undo_"] button p,
[class*="st-key-tonight_"] button p,[class*="st-key-savedseen_"] button p,[class*="st-key-unsave_"] button p,
[class*="st-key-like_"] button p,[class*="st-key-fav_"] button p{margin:0 !important;padding:0 !important;line-height:1 !important;}
/* Landing: a touch more room, and the note in the profile's editorial serif. */
.hero-subtitle{margin-bottom:1.85rem !important;}
.adapt-note{margin:1.65rem 0 1.25rem !important;padding:1.2rem 1.3rem 1.15rem !important;}
.adapt-note span{font-family:Georgia,"Times New Roman",serif !important;font-style:italic !important;font-size:1rem !important;line-height:1.55 !important;}
/* Profile: more room under the heading; the same gap above and below every section title. */
.profile-heading-gap{height:1rem !important;min-height:1rem !important;flex-basis:1rem !important;}
.profile-block + .profile-block{margin-top:.8rem !important;}
.profile-label{margin:0 0 .8rem !important;line-height:1 !important;}
/* Showroom: Tonight's Pick → Top Matches matches tabs → Tonight's Pick; rows slightly closer. */
[class*="st-key-tonight_hero"]{margin-bottom:.75rem !important;}
.showroom-row-header.first{margin-top:0 !important;}
.showroom-row-header:not(.tonight-row-header):not(.first){margin-top:1.2rem !important;}
/* Services picker type matches the Tonight's Pick heading. */
.st-key-services_picker div[data-testid="stPopover"] button p{
    font-family:var(--ui-font) !important;font-weight:760 !important;letter-spacing:-.02em !important;font-size:.78rem !important;
}
div[data-testid="stPopoverBody"] .services-help{font-family:var(--ui-font) !important;font-weight:450 !important;letter-spacing:-.01em !important;font-size:.8rem !important;}
div[data-testid="stPopoverBody"] [data-testid="stPills"] button p,
div[data-testid="stPopoverBody"] [data-testid="stButtonGroup"] button p{
    font-family:var(--ui-font) !important;font-weight:760 !important;letter-spacing:-.02em !important;
}

/* V5.173 — optical left alignment for large headings + a bit more heading→description room */
/* Big bold glyphs carry left side-bearing; nudge so the letter edge lines up with the text below. */
.hero-title,.showroom-heading,.showroom-row-title,.showroom-row-header .showroom-row-title,
.tab-primary-heading,.page-top-heading,.step2-title,.profile-heading,.profile-wrap .profile-heading-aligned{
    margin-left:-.045em !important;
}
.showroom-row-header .showroom-row-title{margin-bottom:.55rem !important;}
.showroom-heading,.page-top-heading,.step2-title{margin-bottom:.55rem !important;}
.hero-subtitle{margin-top:.95rem !important;}

/* V5.174 — fixed card slots so every Save / Seen row lines up; nothing clipped */
/* Title + year: two-line slot; year hugs the title, spare room sits below it. */
div .poster-caption:not(.library-poster-caption){
    height:3.95rem !important;min-height:3.95rem !important;max-height:3.95rem !important;
    display:flex !important;flex-direction:column !important;justify-content:flex-start !important;
    overflow:hidden !important;box-sizing:border-box !important;margin:.58rem 0 .2rem !important;
}
div .poster-caption:not(.library-poster-caption) .poster-caption-title{
    display:-webkit-box !important;-webkit-box-orient:vertical !important;-webkit-line-clamp:2 !important;
    overflow:hidden !important;min-height:0 !important;max-height:none !important;flex:0 0 auto !important;
}
/* Ratings: one line. Where to watch: two lines. */
div .ratings{height:1.3rem !important;min-height:1.3rem !important;max-height:1.3rem !important;overflow:hidden !important;
    margin:0 0 .2rem !important;display:flex !important;align-items:center !important;white-space:nowrap !important;}
div .watch-availability{height:2.05rem !important;min-height:2.05rem !important;max-height:2.05rem !important;
    overflow:hidden !important;margin:0 0 .35rem !important;line-height:1.02rem !important;
    display:-webkit-box !important;-webkit-box-orient:vertical !important;-webkit-line-clamp:2 !important;}
/* Description: exactly three lines of space; hooks are kept short enough to fit. */
div .movie-summary-toggle{margin:0 0 .6rem !important;}
div .movie-summary-label{
    line-height:1.4em !important;height:4.2em !important;min-height:4.2em !important;max-height:4.2em !important;
    display:-webkit-box !important;-webkit-box-orient:vertical !important;-webkit-line-clamp:3 !important;
    overflow:hidden !important;
}
/* When the synopsis is opened, it expands below the fixed hook slot as before. */
/* Tonight's Pick description uses the exact card-description type. */
.tonight-hook{
    font-family:var(--ui-font) !important;font-size:.66rem !important;font-weight:620 !important;
    line-height:1.4 !important;letter-spacing:-.004em !important;color:var(--muted) !important;
}

/* V5.175 — every action button label dead-center (same rule that already centered card Skip),
   profile titles aligned with the text inside the bubbles. */
[class*="st-key-save_"] button,[class*="st-key-seen_"] button,[class*="st-key-skip_"] button,
[class*="st-key-undo_"] button,[class*="st-key-tonight_"] button,[class*="st-key-savedseen_"] button,
[class*="st-key-unsave_"] button,[class*="st-key-like_"] button,[class*="st-key-fav_"] button{
    display:flex !important;align-items:center !important;justify-content:center !important;
    padding-top:0 !important;padding-bottom:0 !important;line-height:1 !important;
}
[class*="st-key-save_"] button *,[class*="st-key-seen_"] button *,[class*="st-key-skip_"] button *,
[class*="st-key-undo_"] button *,[class*="st-key-tonight_"] button *,[class*="st-key-savedseen_"] button *,
[class*="st-key-unsave_"] button *,[class*="st-key-like_"] button *,[class*="st-key-fav_"] button *{
    display:flex !important;align-items:center !important;justify-content:center !important;
    margin:0 !important;padding:0 !important;line-height:1 !important;text-align:center !important;
}
/* Section titles start where the bubble text starts (bubble border 1px + inner padding). */
.profile-label{padding-left:calc(.66rem + 1px) !important;}

/* V5.176 — the invisible profile-saver component no longer takes a layout row;
   Tonight's Show → Top Matches equals tabs → Tonight's Show. */
div[data-testid="stElementContainer"]:has(iframe[title*="browser_storage"]),
div[data-testid="stElementContainer"]:has(iframe[title*="icinema_"]),
div.element-container:has(iframe[title*="browser_storage"]){
    position:absolute !important;width:0 !important;height:0 !important;overflow:hidden !important;
    margin:0 !important;padding:0 !important;pointer-events:none !important;
}
[class*="st-key-tonight_hero"]{margin-bottom:1.12rem !important;}
.showroom-row-header.first{margin-top:0 !important;padding-top:0 !important;}

/* V5.177 — consumer-friendly methodology; profile titles share the bubbles' left edge */
.how-grid{grid-template-columns:repeat(3,minmax(0,1fr)) !important;}
.proof-grid{grid-template-columns:repeat(2,minmax(0,1fr)) !important;}
.how-grid .methodology-card{min-height:0 !important;}
.model-card-link{margin:.85rem 0 0 !important;}
.live-model-copy{margin:.85rem 0 0 !important;color:var(--ivory) !important;}
@media(max-width:800px){.how-grid,.proof-grid{grid-template-columns:1fr !important;}}
.profile-label{padding-left:0 !important;}

/* V5.177 — profile as a clean two-column list: label left, bubbles right; proof cards in 3 */
.profile-grid{display:flex !important;flex-direction:column !important;gap:.7rem !important;}
.profile-block,.profile-block.full{
    display:grid !important;grid-template-columns:10.5rem minmax(0,1fr) !important;
    align-items:center !important;column-gap:1rem !important;margin:0 !important;padding:0 !important;
}
.profile-block + .profile-block{margin-top:0 !important;}
.profile-label{margin:0 !important;padding:0 !important;line-height:1.3 !important;}
.profile-chip-wrap{margin:0 !important;}
@media(max-width:700px){
    .profile-block,.profile-block.full{grid-template-columns:1fr !important;row-gap:.45rem !important;}
}
.proof-grid{grid-template-columns:repeat(3,minmax(0,1fr)) !important;}
@media(max-width:800px){.proof-grid{grid-template-columns:1fr !important;}}

/* V5.178 — insight cards: number → title → one sentence */
.insight-title{font-family:var(--ui-font);font-size:.78rem;font-weight:700;color:var(--ivory);letter-spacing:-.01em;margin:.28rem 0 .18rem;line-height:1.25;}
.insight-card .insight-label{margin-top:0 !important;}
.stats-grid,.proof-grid{grid-template-columns:repeat(3,minmax(0,1fr)) !important;}
.how-grid{grid-template-columns:repeat(2,minmax(0,1fr)) !important;}
@media(max-width:800px){.stats-grid,.proof-grid,.how-grid{grid-template-columns:1fr !important;}}

/* V5.178 — Undo label matches the other Tonight's Show buttons */
[class*="st-key-tonight_undo_"] button p{font-weight:700 !important;}

/* V5.179 — Step 1 Skip matches Like / Favorite */
[class*="st-key-shelfskip_"] button{min-height:1.96rem !important;height:1.96rem !important;padding:0 .3rem !important;border-radius:999px !important;}
[class*="st-key-shelfskip_"] button p{font-size:.69rem !important;font-weight:690 !important;}

/* V5.180 — ratings source note under "How iCinema works" */
.ratings-note{margin-top:.7rem !important;font-size:.74rem !important;color:var(--muted2) !important;}

/* V5.181 — "Not for me" controls, sized to sit quietly in existing space */
[class*="st-key-dislike_"] button{min-height:1.9rem !important;height:1.9rem !important;border-radius:999px !important;
    padding:0 .8rem !important;margin-top:.35rem !important;}
[class*="st-key-dislike_"] button p{font-size:.7rem !important;font-weight:700 !important;margin:0 !important;}
[class*="st-key-tonight_dislike_"] button{min-height:1.9rem !important;height:1.9rem !important;width:2.6rem !important;
    padding:0 !important;border-radius:999px !important;display:flex !important;align-items:center !important;justify-content:center !important;}
[class*="st-key-tonight_dislike_"] button p{font-size:.85rem !important;margin:0 !important;line-height:1 !important;}

/* V5.182 — professional outline thumbs-down icon instead of an emoji */
[class*="st-key-dislike_"] button p::before,
[class*="st-key-tonight_dislike_"] button p::before{
    content:"";display:inline-block;flex:0 0 auto;width:.95rem;height:.95rem;
    background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23F3F0EA' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 14V2'/><path d='M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z'/></svg>") center / contain no-repeat;opacity:.9;
}
[class*="st-key-dislike_"] button p::before{margin-right:.42rem;}
/* Tonight's Show: icon only, the words stay for screen readers and the tooltip. */
[class*="st-key-tonight_dislike_"] button p{font-size:0 !important;gap:0 !important;}
[class*="st-key-tonight_dislike_"] button p::before{width:1rem;height:1rem;}
[class*="st-key-dislike_"] button:hover p::before,
[class*="st-key-tonight_dislike_"] button:hover p::before{opacity:1;}

/* V5.183 — "Not for me": icon and label share one vertical center */
[class*="st-key-dislike_"] button,
[class*="st-key-tonight_dislike_"] button{display:inline-flex !important;align-items:center !important;justify-content:center !important;
    padding-top:0 !important;padding-bottom:0 !important;}
[class*="st-key-dislike_"] button > div,
[class*="st-key-dislike_"] button [data-testid="stMarkdownContainer"],
[class*="st-key-tonight_dislike_"] button > div,
[class*="st-key-tonight_dislike_"] button [data-testid="stMarkdownContainer"]{
    display:flex !important;align-items:center !important;justify-content:center !important;height:100% !important;margin:0 !important;}
[class*="st-key-dislike_"] button p,
[class*="st-key-tonight_dislike_"] button p{
    display:inline-flex !important;align-items:center !important;justify-content:center !important;
    line-height:1 !important;margin:0 !important;padding:0 !important;}
[class*="st-key-dislike_"] button p::before,
[class*="st-key-tonight_dislike_"] button p::before{align-self:center !important;margin-top:0 !important;margin-bottom:0 !important;
    background-position:center !important;background-repeat:no-repeat !important;background-size:contain !important;}

/* V5.184 — no page flash on Save / Seen: keep content fully visible while it refreshes */
[data-stale="true"],div[data-stale="true"],.stale-element{opacity:1 !important;transition:none !important;filter:none !important;}

/* V5.185 — library tabs: ratings, roomier rows, hover × to remove from Seen */
[class*="st-key-savedcard_"],[class*="st-key-seencard_"]{margin-bottom:1.9rem !important;}
[class*="st-key-seencard_"]{position:relative !important;}
[class*="st-key-seencard_"] [class*="st-key-unseen_"]{
    position:absolute !important;top:.6rem !important;right:.6rem !important;left:auto !important;
    width:auto !important;z-index:6 !important;margin:0 !important;opacity:0;transition:opacity .15s ease;}
[class*="st-key-seencard_"]:hover [class*="st-key-unseen_"],
[class*="st-key-seencard_"] [class*="st-key-unseen_"]:focus-within{opacity:1;}
@media (hover:none){[class*="st-key-seencard_"] [class*="st-key-unseen_"]{opacity:.85;}}
[class*="st-key-unseen_"] button{
    width:2rem !important;height:2rem !important;min-height:2rem !important;padding:0 !important;border-radius:999px !important;
    background:rgba(17,19,21,.82) !important;border:1px solid rgba(243,240,234,.32) !important;backdrop-filter:blur(6px);
    display:flex !important;align-items:center !important;justify-content:center !important;}
[class*="st-key-unseen_"] button:hover{border-color:rgba(243,240,234,.7) !important;background:rgba(17,19,21,.95) !important;}
[class*="st-key-unseen_"] button p{margin:0 !important;font-size:.8rem !important;line-height:1 !important;color:var(--ivory) !important;font-weight:600 !important;}
.library-ratings{margin:.3rem 0 .35rem !important;}

/* V5.186 — Step 2: same heading style and spacing for all three questions; Back buttons match */
.step2-question-next{margin-top:2.1rem !important;}
.step2-question{margin-bottom:.55rem !important;}
.pref-scale-clicks{margin-bottom:0 !important;}
[class*="st-key-back_"] button{min-height:3.55rem !important;border-radius:18px !important;}
[class*="st-key-back_"] button p{font-size:.76rem !important;font-weight:650 !important;}
.st-key-edit_preferences button,.st-key-reset_profile_tab button{min-height:2.4rem !important;border-radius:999px !important;}

/* V5.187 — tighter Step 1 shelf; one shared nav-button style and spacing on every page */
/* Step 1: title/year hug the poster, actions hug the year, roomier gap before the next poster. */
.st-key-step1_shelf [data-testid="stVerticalBlock"]{gap:.45rem !important;}
.st-key-step1_shelf div .poster-caption:not(.library-poster-caption){
    height:auto !important;min-height:0 !important;max-height:none !important;margin:.5rem 0 0 !important;
}
.st-key-step1_shelf [data-testid="stColumn"] [data-testid="stHorizontalBlock"],
.st-key-step1_shelf [data-testid="column"] [data-testid="stHorizontalBlock"]{margin-bottom:.95rem !important;}
/* Nav rows (Back / Continue / Build / Enter): same height, shape, and type everywhere. */
[class*="st-key-nav_row_"] [class*="st-key-"]{margin:0 !important;padding:0 !important;}
[class*="st-key-nav_row_"] [data-testid="stHorizontalBlock"]{align-items:center !important;}
[class*="st-key-nav_row_"] button{
    width:100% !important;height:3.1rem !important;min-height:3.1rem !important;max-height:3.1rem !important;
    padding:0 1rem !important;border-radius:16px !important;
    display:flex !important;align-items:center !important;justify-content:center !important;
}
[class*="st-key-nav_row_"] button *{
    display:flex !important;align-items:center !important;justify-content:center !important;
    margin:0 !important;padding:0 !important;width:auto !important;line-height:1 !important;
    text-align:center !important;white-space:nowrap !important;
    font-size:.78rem !important;font-weight:650 !important;letter-spacing:-.004em !important;
}
/* Same visual gap (~1.25rem) between each page's last element and its nav row. */
.st-key-nav_row_rate{margin-top:1rem !important;}
.st-key-nav_row_taste{margin-top:.25rem !important;}
.st-key-nav_row_more{margin-top:-.9rem !important;}
.st-key-nav_row_profile{margin-top:.15rem !important;}

/* V5.188 — Step 1: smaller posters, and no overlap between the year and the action row.
   Streamlit gives every markdown block a -1rem bottom margin; the old spacer element used to
   absorb it, so without it the buttons slid up over the year. */
.st-key-step1_shelf [data-testid="stMarkdown"],
.st-key-step1_shelf [data-testid="stMarkdownContainer"],
.st-key-step1_shelf [data-testid="stElementContainer"]:has([data-testid="stMarkdown"]){margin-bottom:0 !important;}
.st-key-step1_shelf div .poster-caption:not(.library-poster-caption){margin:.5rem 0 .1rem !important;}
/* V5.189 — five cards per row, full column width, close together; even action row. */
.st-key-step1_shelf > div > [data-testid="stHorizontalBlock"]{column-gap:.8rem !important;}
.st-key-step1_shelf [data-testid="stColumn"] [data-testid="stHorizontalBlock"],
.st-key-step1_shelf [data-testid="column"] [data-testid="stHorizontalBlock"]{
    width:100% !important;max-width:100% !important;column-gap:.32rem !important;gap:.32rem !important;
}
.st-key-step1_shelf [data-testid="stColumn"] [data-testid="stColumn"],
.st-key-step1_shelf [data-testid="column"] [data-testid="column"]{min-width:0 !important;}
.st-key-step1_shelf [class*="st-key-like_"] button,
.st-key-step1_shelf [class*="st-key-fav_"] button,
.st-key-step1_shelf [class*="st-key-shelfskip_"] button{
    width:100% !important;min-width:0 !important;height:1.9rem !important;min-height:1.9rem !important;
    padding:0 .15rem !important;border-radius:999px !important;
}
.st-key-step1_shelf [class*="st-key-like_"] button *,
.st-key-step1_shelf [class*="st-key-fav_"] button *,
.st-key-step1_shelf [class*="st-key-shelfskip_"] button *{
    font-size:.64rem !important;font-weight:690 !important;white-space:nowrap !important;
}
.st-key-step1_shelf .poster-caption-title{font-size:1rem !important;}

/* V5.190 — Step 1 "hamburger" cards: half-height poster crop, one-line titles,
   and three identical action-button slots so every row lines up exactly. */
.st-key-step1_shelf .poster{aspect-ratio:16 / 9 !important;border-radius:14px !important;}
.st-key-step1_shelf .poster.has-image img{
    object-fit:cover !important;object-position:center 30% !important;border-radius:13px !important;
}
.st-key-step1_shelf .poster-caption-title{
    display:block !important;white-space:nowrap !important;overflow:hidden !important;
    text-overflow:ellipsis !important;-webkit-line-clamp:unset !important;
}
.st-key-step1_shelf [class*="st-key-like_"],
.st-key-step1_shelf [class*="st-key-fav_"],
.st-key-step1_shelf [class*="st-key-shelfskip_"]{
    margin:0 !important;padding:0 !important;height:1.9rem !important;min-height:1.9rem !important;
    display:block !important;
}
.st-key-step1_shelf [data-testid="stColumn"] [data-testid="stHorizontalBlock"],
.st-key-step1_shelf [data-testid="column"] [data-testid="stHorizontalBlock"]{align-items:flex-start !important;}
.st-key-step1_shelf [data-testid="stColumn"] [data-testid="stColumn"] [data-testid="stVerticalBlock"],
.st-key-step1_shelf [data-testid="column"] [data-testid="column"] [data-testid="stVerticalBlock"]{gap:0 !important;}
.st-key-step1_shelf [class*="st-key-like_"] button,
.st-key-step1_shelf [class*="st-key-fav_"] button,
.st-key-step1_shelf [class*="st-key-shelfskip_"] button{
    margin:0 !important;box-sizing:border-box !important;line-height:1 !important;
}
.st-key-step1_shelf [class*="st-key-like_"] button *,
.st-key-step1_shelf [class*="st-key-fav_"] button *,
.st-key-step1_shelf [class*="st-key-shelfskip_"] button *{
    display:flex !important;align-items:center !important;justify-content:center !important;
    margin:0 !important;padding:0 !important;line-height:1 !important;
}

/* V5.191 — Step 1 landscape art (16:9) and even section rhythm.
   Every section boundary (shelf → search → selections → Continue) = 1rem flex gap + 1rem. */
.st-key-step1_shelf{margin-bottom:-.95rem !important;}
.st-key-step1_search,.st-key-step1_selections{margin-top:1rem !important;}
.st-key-step1_search [data-testid="stVerticalBlock"],
.st-key-step1_selections [data-testid="stVerticalBlock"]{gap:.6rem !important;}
.st-key-step1_search [data-testid="stMarkdown"],
.st-key-step1_search [data-testid="stMarkdownContainer"],
.st-key-step1_search [data-testid="stElementContainer"]:has([data-testid="stMarkdown"]),
.st-key-step1_selections [data-testid="stMarkdown"],
.st-key-step1_selections [data-testid="stMarkdownContainer"],
.st-key-step1_selections [data-testid="stElementContainer"]:has([data-testid="stMarkdown"]){margin-bottom:0 !important;}
.st-key-step1_search .search-shell{margin:0 !important;}
.st-key-step1_search div[data-testid="stTextInput"]{margin:0 !important;}
.st-key-step1_search .search-results-label{margin:.2rem 0 0 !important;}
.st-key-step1_search .search-selected-card{margin:.2rem 0 0 !important;}
.st-key-step1_selections .selection-area-heading,
.st-key-step1_selections .selection-heading{margin:0 !important;}
.st-key-step1_selections [class*="st-key-selection_card_"]{margin:0 !important;}
.st-key-step1_selections div[data-testid="stCaptionContainer"]{margin:0 !important;}

/* V5.192 — Seen tab "What's next" bubble */
[class*="st-key-whatsnext_"]{margin-top:.15rem !important;}
.whatsnext-kicker{font-family:var(--ui-font);color:var(--muted2);font-size:.62rem;font-weight:760;
    letter-spacing:.08em;text-transform:uppercase;margin:0 0 .6rem;}
.whatsnext-pick{display:flex;gap:.75rem;align-items:flex-start;margin:0 0 .7rem;min-width:15rem;}
.whatsnext-poster{flex:0 0 4.2rem;width:4.2rem;aspect-ratio:2 / 3;border-radius:10px;overflow:hidden;
    border:1px solid var(--border);background:#0F1114;display:flex;align-items:center;justify-content:center;}
.whatsnext-poster img{width:100%;height:100%;object-fit:cover;display:block;}
.whatsnext-noimg{font-family:var(--ui-font);font-size:.5rem;font-weight:700;letter-spacing:.08em;color:rgba(243,240,234,.34);}
.whatsnext-title{font-family:var(--ui-font);color:var(--ivory);font-size:.92rem;font-weight:780;letter-spacing:-.015em;line-height:1.2;}
.whatsnext-meta{font-family:var(--ui-font);color:var(--muted);font-size:.68rem;font-weight:650;margin:.2rem 0 .4rem;}
.whatsnext-why{font-family:var(--ui-font);color:var(--muted);font-size:.7rem;line-height:1.42;font-weight:500;}

/* V5.193 — What's next buttons: small pills scaled to the poster. */
[class*="st-key-whatsnext_save_"] button,[class*="st-key-whatsnext_more_"] button{
    height:1.75rem !important;min-height:1.75rem !important;padding:0 .7rem !important;border-radius:999px !important;
    display:flex !important;align-items:center !important;justify-content:center !important;}
[class*="st-key-whatsnext_save_"] button *,[class*="st-key-whatsnext_more_"] button *{
    font-size:.68rem !important;font-weight:690 !important;line-height:1 !important;margin:0 !important;white-space:nowrap !important;}


/* Home proof strip: the tested 3-like edge, front and center */
.proof-strip{display:flex;align-items:center;gap:1rem;border:1px solid var(--border);border-left:3px solid var(--ai);
  border-radius:14px;background:rgba(255,255,255,.03);padding:.85rem 1.1rem;margin:-1rem 0 1.6rem;max-width:760px}
.proof-big{font-size:1.65rem;font-weight:800;letter-spacing:-.03em;color:var(--ivory);white-space:nowrap}
.proof-copy{color:var(--muted);font-size:.92rem;line-height:1.45}
.proof-copy b{color:var(--ivory);font-weight:650}
@media(max-width:700px){.proof-strip{flex-direction:column;align-items:flex-start;gap:.3rem}}
.proof-copy b{display:block;font-size:1rem;margin-bottom:.15rem}
.proof-sub{display:block;font-size:.82rem;color:var(--muted)}
.proof-strip{padding:.75rem 1.05rem !important}
.proof-note{display:flex !important;align-items:center;gap:1.2rem}
.proof-note .proof-big{font-size:2rem;font-weight:800;letter-spacing:-.035em;color:var(--ivory);white-space:nowrap;line-height:1}
.proof-note strong{display:block !important;margin-bottom:.3rem !important}
.proof-note span{display:block}
@media(max-width:700px){.proof-note{flex-direction:column;align-items:flex-start;gap:.4rem}}
/* Proof note: same UI font as the rest of the app, no italics for data */
.adapt-note.proof-note span{font-family:var(--ui-font) !important;font-style:normal !important;font-size:.95rem !important;color:var(--muted) !important;line-height:1.5 !important}
.adapt-note.proof-note strong{font-family:var(--ui-font) !important}
.adapt-note.proof-note .proof-big{font-family:var(--ui-font) !important}
.match-rank-note{font-family:var(--ui-font);font-size:.72rem;color:var(--muted);margin:-.2rem 0 .55rem}

/* Smooth reload: delayed loader + one-time page fade-in */
@keyframes icn-appear{from{opacity:0}to{opacity:1}}
.icinema-boot-loader{animation:icinema-loader-ring 1.1s linear infinite, icn-appear .25s ease .4s both !important;}
</style>
""", unsafe_allow_html=True)

defaults={
    "screen":"welcome","onboarding_complete":False,"likes":set(),"favorites":set(),"review_priority":50,
    "genres":[],"adventure":50,"more_of":[],"saved":set(),"seen":set(),"dismissed":set(),"disliked":set(),"seen_from_saved":set(),"selection_order":[],
    "custom_like":None,"search_selected_title":None,"search_selected_movie":None,"external_movies":{},
    "shelf_movies":[],"shelf_replacement_pool":[],"shelf_seen_titles":set(),
    "shelf_pool_initialized":False,"shelf_tmdb_loaded":False,
    "analytics_events":[],"showroom_session_id":None,"showroom_session_start":None,
    "showroom_impression_keys":set(),"recommendation_context":{},
    "showroom_slots":{},"showroom_payloads":{},"showroom_row_queues":{},
    "showroom_identity_cache":{},"showroom_watch_cache":{},"showroom_rating_cache":{},
    "streaming_services":[]
}
# Always mounted at the same spot so its iframe (and listeners) persist across reruns.
scroll_keeper()

# Module-level code runs only on full page runs, never on fragment-only reruns.
st.session_state._in_full_run = True
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
        "disliked": sorted(st.session_state.get("disliked") or set()),
        "seen_from_saved": sorted(st.session_state.get("seen_from_saved") or set()),
        "selection_order": list(st.session_state.get("selection_order", [])),
        "external_movies": st.session_state.external_movies,
        "analytics_events": list(st.session_state.get("analytics_events", []))[-2000:],
        "streaming_services": list(st.session_state.get("streaming_services") or []),
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
        st.session_state.disliked = set(data.get("disliked") or [])
        st.session_state.seen_from_saved = set(data.get("seen_from_saved") or [])
        st.session_state.selection_order = list(data.get("selection_order") or [])
        st.session_state.external_movies = dict(data.get("external_movies") or {})
        st.session_state.analytics_events = list(data.get("analytics_events") or [])[-2000:]
        st.session_state.streaming_services = list(data.get("streaming_services") or [])
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
        logo_placeholder = '<div class="icinema-logo">iCinema</div><div class="icinema-boot-loader" aria-label="Loading"></div>'
        st.markdown(logo_placeholder, unsafe_allow_html=True)
        st.session_state._in_full_run = False
        st.stop()
    restored = restore_profile(_stored.get("value")) if _stored.get("value") else False
    st.session_state._storage_hydrated = True
    st.session_state._fade_in_once = True
    st.session_state._last_persisted_profile = json.dumps(profile_snapshot(), sort_keys=True, default=str) if restored else None

# Profile-changing actions queue a snapshot, but we deliberately do NOT mount
# the browser-storage component before the destination page renders. Mounting
# that component at the top of a page transition can briefly expose its iframe
# background as a black strip. The normal persist_profile_if_needed() call at
# the end of the render writes the exact same snapshot silently.
if st.session_state.pop("_fade_in_once", False):
    st.markdown('<style>.stApp [data-testid="stMainBlockContainer"], .stApp .block-container'
                '{animation:icn-appear .25s ease both}</style>', unsafe_allow_html=True)

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

def persist_from_fragment():
    """Save only during fragment-only reruns (e.g. Skip).

    On a full page run the single save at the end of the script handles it, so the
    hidden saver never appears mid-page and shifts the layout between runs.
    """
    if not st.session_state.get("_in_full_run"):
        persist_profile_if_needed()


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

    while len(st.session_state.shelf_movies) < 15:
        replacement = _next_shelf_movie()
        if not replacement:
            break
        st.session_state.shelf_movies.append(replacement)
        st.session_state.shelf_seen_titles.add(_shelf_key(replacement))

def skip_shelf_movie(slot_index):
    """Swap one shelf card for the next recognizable title. Not a dislike, so nothing is logged."""
    replacement = _next_shelf_movie()
    if 0 <= slot_index < len(st.session_state.shelf_movies):
        if replacement:
            st.session_state.shelf_movies[slot_index] = replacement
            st.session_state.shelf_seen_titles.add(_shelf_key(replacement))
        else:
            st.session_state.shelf_movies.pop(slot_index)


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

def live_search_box():
    """Results update as you type (debounced ~0.3s), like a search engine.
    Falls back to the standard text box if the keyup component is unavailable."""
    try:
        from st_keyup import st_keyup
        return st_keyup("Search movies", placeholder="Search by title", debounce=300,
                        label_visibility="collapsed", key="movie_search_live") or ""
    except Exception:
        return st.text_input("Search movies", placeholder="Search by title",
                             label_visibility="collapsed", key="movie_search_query")


def remove_step1_selection(title):
    """Remove a Like/Favorite signal from Step 1 and persist the updated profile."""
    st.session_state.likes.discard(title)
    st.session_state.favorites.discard(title)
    st.session_state.selection_order = [
        item for item in st.session_state.get("selection_order", [])
        if item != title
    ]
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
    st.session_state._app_rerun = True

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

# Streaming services a viewer can pick for Tonight's Pick. Aliases match TMDB/JustWatch
# provider names, including ad tiers and channel variants (e.g. "Netflix basic with Ads").
STREAMING_SERVICES = {
    "Netflix": ("netflix",),
    "Max": ("max", "hbomax"),
    "Hulu": ("hulu",),
    "Prime Video": ("amazonprime", "primevideo"),
    "Disney+": ("disney",),
    "Apple TV+": ("appletvplus",),
    "Peacock": ("peacock",),
    "Paramount+": ("paramount",),
    "Free (Tubi, Pluto & more)": ("tubi", "pluto", "roku", "plex", "freevee", "kanopy", "hoopla"),
}

def _provider_key(name):
    return re.sub(r"[^a-z0-9]", "", str(name).casefold().replace("+", "plus"))

def _on_service(provider, service):
    key = _provider_key(provider)
    return any(key.startswith(alias) for alias in STREAMING_SERVICES.get(service, ()))

_NON_TONE_TAGS = {g.casefold() for g in GENRES} | {
    "animation", "anime", "international", "critically acclaimed", "hidden gem", "hidden gems",
    "classic", "classics", "recent", "recent release", "recent releases", "documentary", "documentaries",
}


def _tone_tags(movie):
    return [t for t in ((movie or {}).get("tags") or []) if str(t).strip() and str(t).casefold() not in _NON_TONE_TAGS]


def with_tone_detail(reasons, movie, avoid=None):
    """Make the tone reason concrete: which tones it shares, and with which liked movie."""
    liked = [m for m, action in _cf_signals() if action in ("favorite", "like", "save")
             and m.get("title") != (movie or {}).get("title")]
    tones = {t.casefold(): t for t in _tone_tags(movie)}
    best, shared, best_key = None, [], None
    for other in liked:
        overlap = [tones[t.casefold()] for t in _tone_tags(other) if t.casefold() in tones]
        if not overlap:
            continue
        sim = item_similarity(movie, other) or 0.0
        key = (len(overlap), other.get("title") != avoid, sim)   # most shared tones, then a different movie, then closest fans
        if best_key is None or key > best_key:
            best, shared, best_key = other.get("title"), overlap, key
    if not best or not shared:
        return reasons
    words = [t.lower() if t[:1].isupper() and not t.isupper() else t for t in shared[:2]]
    phrase = " and ".join(words)
    detail = f"{phrase[:1].upper() + phrase[1:]}, like “{best}”."
    out = []
    for reason in reasons or []:
        if reason.get("label") in ("Feels like your favorites", "Storytelling you like"):
            reason = {**reason, "text": detail}
        out.append(reason)
    return out


FATIGUE_STEP = 0.04     # objective penalty per earlier visit a title was shown and ignored
FATIGUE_CAP = 5         # stop penalizing after five ignored visits
VARIETY_SPREAD = 0.03   # per-visit shuffle among near-ties (stable within a visit)


def impression_fatigue():
    """Earlier visits in which each title was shown but got no Save, Seen, or Skip.

    Impression discounting: returning viewers see fresh options instead of the
    same ignored cards, which shortens the path to something worth watching.
    """
    events = st.session_state.get("analytics_events") or []
    current = st.session_state.get("showroom_session_id")
    acted = {e.get("title") for e in events if e.get("event") in ("save", "seen", "skip", "dislike")}
    visits = {}
    for e in events:
        if e.get("event") != "impression":
            continue
        sid, title = e.get("session_id"), e.get("title")
        if sid and title and sid != current and title not in acted:
            visits.setdefault(title, set()).add(sid)
    return {title: len(sids) for title, sids in visits.items()}


def visit_variety(title):
    """Deterministic value in [-0.5, 0.5] for this visit and title."""
    import hashlib
    key = f"{st.session_state.get('showroom_session_id')}::{title}".encode()
    return int(hashlib.md5(key).hexdigest()[:8], 16) / 0xFFFFFFFF - 0.5


def card_ratings(movie, live_rating):
    """The one set of ratings a card shows and its explanations cite.

    Live OMDb scores first, then the scores stored with the movie. TMDB's viewer
    score is used only when neither IMDb nor Rotten Tomatoes is available.
    """
    movie, live = movie or {}, live_rating or {}
    def pick(key):
        for source in (live, movie):
            value = source.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        return None
    imdb, rt = pick("imdb"), pick("rt")
    tmdb = None if imdb else pick("tmdb_vote")  # viewer score stands in only when IMDb is missing
    return {"imdb": imdb, "rt": rt, "tmdb_vote": tmdb}


def ratings_text(ratings):
    """'IMDb 7.1 · RT 88%', 'IMDb 7.1 · No RT', or 'Viewers 7.9/10 · No RT'."""
    audience = (f"IMDb {ratings['imdb']:.1f}" if ratings.get("imdb") else
                (f"Viewers {ratings['tmdb_vote']:.1f}/10" if ratings.get("tmdb_vote") else None))
    critics = f"RT {int(ratings['rt'])}%" if ratings.get("rt") else "No RT"
    if not audience and critics == "No RT":
        return []  # nothing to show; the card says "Ratings unavailable"
    return [x for x in (audience, critics) if x]


def with_live_ratings(movie, live_rating):
    """Copy of the movie carrying exactly the ratings shown on its card."""
    movie = dict(movie or {})
    ratings = card_ratings(movie, live_rating)
    for key in ("imdb", "rt"):
        if ratings[key]:
            movie[key] = ratings[key]
        else:
            movie.pop(key, None)
    if ratings["tmdb_vote"]:
        movie["tmdb_vote"] = ratings["tmdb_vote"]
    else:
        movie.pop("tmdb_vote", None)  # explanations cite only what the card shows
    return movie


def with_cf_reason(reasons, payload, limit=3):
    """Surface the collaborative-filtering signal, naming the viewer's closest liked movie."""
    cf = (payload or {}).get("cf")
    anchor = (closest_liked((payload or {}).get("movie"), _cf_signals())
              if isinstance(cf, (int, float)) and cf >= 0.65 else None)
    reasons = with_tone_detail(list(reasons or []), (payload or {}).get("movie"), avoid=anchor)
    if isinstance(cf, (int, float)) and cf >= 0.65:
        if anchor:
            # Embedding similarity means the two movies are loved by the same kinds of viewers.
            reason = {"label": f"Loved by fans of “{anchor}”",
                      "text": f"Viewers who loved “{anchor}” tend to love this too."}
        else:
            reason = {"label": "Loved by viewers like you",
                      "text": "Viewers who liked the movies you liked tend to love this too."}
        reasons = [reason] + reasons
    return reasons[:limit]

def _tag_overlap(a, b):
    ta = {str(t).casefold() for t in (a or {}).get("tags") or []}
    tb = {str(t).casefold() for t in (b or {}).get("tags") or []}
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def whats_next_ranking(source, payloads, blocked):
    """Candidates ranked by how well they follow `source`, the movie just watched.

    60% similarity to that movie and 40% the viewer's own personalized match, so each
    pick follows what they watched AND fits their taste. Similarity comes from the
    MovieLens CF embeddings (the same viewers loved both movies). When the watched movie
    is in MovieLens, only candidates with an embedding are compared, so CF and content
    scores are never mixed; otherwise genre and tag overlap stand in.
    Returns [(title, used_cf), ...], best first.
    """
    scored = []
    for t, payload in (payloads or {}).items():
        movie = (payload or {}).get("movie")
        if not movie or t in blocked or t == (source or {}).get("title"):
            continue
        sim = item_similarity(movie, source)
        used_cf = sim is not None
        if sim is None:
            same_genre = 1.0 if movie.get("genre") and movie.get("genre") == (source or {}).get("genre") else 0.0
            sim = 0.5 * same_genre + 0.5 * _tag_overlap(movie, source)
        score = 0.6 * sim + 0.4 * (float(payload.get("match") or 0) / 100.0)
        scored.append((score, t, used_cf))
    if any(cf for _, _, cf in scored):
        scored = [x for x in scored if x[2]]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(t, cf) for _, t, cf in scored]


def whats_next_another(source_title):
    offsets = dict(st.session_state.get("whats_next_offset") or {})
    offsets[source_title] = int(offsets.get(source_title, 0)) + 1
    st.session_state.whats_next_offset = offsets


def service_availability_utility(availability):
    """Availability value that respects the viewer's chosen services.

    A title streaming only on a service the viewer doesn't have is treated like a
    paid rental: still watchable, but less convenient tonight.
    """
    availability = availability or {}
    status = availability.get("status")
    services = list(st.session_state.get("streaming_services") or [])
    if services and status == "streaming" and not movie_on_services(availability, services):
        return availability_utility("rent")
    return availability_utility(status)

# One tap from a recommendation to the service that plays it. Each link opens that
# service's search for the exact title (the closest a public link can get to its
# title page). Services without a dependable public search URL (Max, Peacock,
# Paramount+, Fandango) open TMDB's JustWatch-powered page, which links to them.
PROVIDER_LINKS = [
    ("netflix", "https://www.netflix.com/search?q={q}"),
    ("hulu", "https://www.hulu.com/search?q={q}"),
    ("amazonprime", "https://www.amazon.com/s?k={q}&i=instant-video"),
    ("primevideo", "https://www.amazon.com/s?k={q}&i=instant-video"),
    ("amazonvideo", "https://www.amazon.com/s?k={q}&i=instant-video"),
    ("disney", "https://www.disneyplus.com/search?q={q}"),
    ("appletv", "https://tv.apple.com/search?term={q}"),
    ("tubi", "https://tubitv.com/search/{q}"),
    ("youtube", "https://www.youtube.com/results?search_query={q}"),
    ("googleplay", "https://play.google.com/store/search?q={q}&c=movies"),
]

def provider_watch_url(provider, title, availability=None):
    from urllib.parse import quote_plus
    key = _provider_key(provider)
    for prefix, template in PROVIDER_LINKS:
        if key.startswith(prefix):
            return template.format(q=quote_plus(str(title)))
    fallback = (availability or {}).get("url")
    return fallback or f"https://www.justwatch.com/us/search?q={quote_plus(str(title))}"

def watch_options(availability, title, services=None, limit=2):
    """[(label, provider, url)] for the best ways to watch, the viewer's services first."""
    availability = availability or {}
    services = list(services or [])
    streaming = list(availability.get("providers") or [])
    renting = list(availability.get("rent_providers") or [])
    if services:
        mine = [p for p in streaming if any(_on_service(p, sv) for sv in services)]
        streaming = mine + [p for p in streaming if p not in mine]
    chosen = [("Watch on", p) for p in streaming[:limit]]
    if not chosen:
        chosen = [("Rent on", p) for p in renting[:limit]]
    seen, out = set(), []
    for verb, provider in chosen:
        name = re.sub(r"\s+(basic\s+)?with\s+ads$|\s+amazon\s+channel$|\s+standard\s+with\s+ads$", "", provider, flags=re.IGNORECASE).strip()
        if name.casefold() in seen:
            continue
        seen.add(name.casefold())
        out.append((f"{verb} {name}", name, provider_watch_url(provider, title, availability)))
    return out

def watch_line_html(availability, title, services=None):
    """Streaming line where each service name is a one-tap link to it."""
    availability = availability or {}
    options = watch_options(availability, title, services)
    if not options:
        text = concise_availability_text(availability.get("text") or "Where to watch: availability unavailable")
        return html.escape(text)
    verb = "Streaming" if options[0][0].startswith("Watch") else "Rent"

    def _label(name):
        key = _provider_key(name)
        return f"{name} (free with a library card)" if key.startswith(("kanopy", "hoopla")) else name

    def _links(opts):
        return " · ".join(
            f'<a class="watch-link" href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{html.escape(_label(name))}</a>'
            for _, name, url in opts
        )
    total = len(availability.get("providers") or []) if verb == "Streaming" else len(availability.get("rent_providers") or [])
    more = " + more" if total > len(options) else ""
    picked = [sv for sv in (services or []) if sv in STREAMING_SERVICES]
    if picked and verb == "Streaming":
        mine = [o for o in options if any(_on_service(o[1], sv) for sv in picked)]
        rest = [o for o in options if o not in mine]
        if mine:
            return f"On your services: {_links(mine)}" + (f" · Also on: {_links(rest)}" if rest else "") + more
    return f"{verb}: {_links(options)}{more}"

# Pill-sized forms of long reason labels; the full wording stays in the popover.
_PILL_SHORT = {
    "Feels like your favorites": "Like your favorites",
    "Storytelling you like": "Your kind of story",
    "Critically acclaimed": "Critics' pick",
    "Easy to watch tonight": "Streaming now",
    "International pick": "International",
    "Loved by viewers like you": "Fans like you",
}
PILL_BUDGET = 25  # characters, including "80% · ", that fit a card pill without clipping


def _short_reason(reason, room):
    """Pill-sized version of a reason label, or None if it can't fit without cutting."""
    label = str((reason or {}).get("label") or "").strip()
    if label.startswith("Loved by fans of "):
        fans = "Fans of " + label[len("Loved by fans of "):]
        label = fans if len(fans) <= room else "Fans like you"
    label = _PILL_SHORT.get(label, label)
    if label.startswith("Your kind of ") and len(label) > room:
        label = label[len("Your kind of "):].strip().capitalize() + " pick"
    return label if label and len(label) <= room else None


def fit_head(payload, match):
    """Rank-based fit: where this movie ranks among every movie iCinema scored for you.

    Accurate by construction (it is a rank, not a probability), and it spreads out
    even when the raw scores of top picks sit close together.
    """
    top = (payload or {}).get("fit_top_pct")
    return f"Top {int(top)}%" if isinstance(top, (int, float)) else f"{int(match or 0)}%"


def fit_label(payload, match):
    top = (payload or {}).get("fit_top_pct")
    if not isinstance(top, (int, float)):
        return match_label(match)
    return "Made for you" if top <= 2 else "Strong match" if top <= 10 else "Good match" if top <= 25 else "Worth a look"


def match_pill(match, reasons, limit=None, taken=(), head=None):
    """Percent plus this movie's strongest reason not already shown in its row.

    Returns (pill_text, label_used). Skipping labels other cards in the row already
    use keeps a row varied, e.g. one "Fans of “Spirited Away”" instead of four.
    """
    match = int(match or 0)
    head = head or f"{match}%"
    room = (limit if limit is not None else PILL_BUDGET) - len(f"{head} · ")
    for reason in reasons or []:
        label = _short_reason(reason, room)
        if label and label not in taken:
            return f"{head} · {label}", label
    return f"{head} for you", None


def match_label(match):
    """Plain-language fit instead of a bare percentage; the % stays in the explanation."""
    match = int(match or 0)
    if match >= 70:
        return "Made for you"
    if match >= 55:
        return "Strong match"
    if match >= 42:
        return "Good match"
    return "Worth a look"

def movie_on_services(availability, services):
    """True when a movie streams on one of the viewer's services (or on any service if none chosen)."""
    availability = availability or {}
    if not services:
        return availability.get("status") == "streaming"
    return any(_on_service(p, s) for p in (availability.get("providers") or []) for s in services)

def toggle_streaming_service(name):
    services = list(st.session_state.get("streaming_services") or [])
    if name in services:
        services.remove(name)
    else:
        services.append(name)
    st.session_state.streaming_services = services
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
    if title in st.session_state.saved:
        from_saved = set(st.session_state.get("seen_from_saved") or set())
        from_saved.add(title)
        st.session_state.seen_from_saved = from_saved
    st.session_state.seen.add(title)
    st.session_state.saved.discard(title)
    st.session_state.dismissed.discard(title)
    queue_profile_save()

def remove_from_seen(title):
    """Undo an accidental Seen: drop it and its model signal; restore it to Saved if it came from there."""
    st.session_state.seen.discard(title)
    from_saved = set(st.session_state.get("seen_from_saved") or set())
    if title in from_saved:
        from_saved.discard(title)
        st.session_state.seen_from_saved = from_saved
        st.session_state.saved.add(title)
    _drop_last_event(title, "seen")
    queue_profile_save()


def library_ratings_html(movie, identity, live_map):
    """Same ratings line as the Showroom cards (IMDb · RT, 'No RT', or viewer score)."""
    parts = ratings_text(card_ratings(movie, (live_map or {}).get(movie["title"]) or {}))
    return (f'<div class="ratings library-ratings">{" · ".join(parts)}</div>' if parts
            else '<div class="ratings library-ratings muted">Ratings unavailable</div>')


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
    for key in ("tonight_services_picker", "tonight_last_skip", "tonight_pool", "showroom_undo", "showroom_pill_labels"):
        st.session_state.pop(key, None)
    queue_profile_save()

def reset_profile_from_fragment():
    reset_profile_state()
    st.session_state._app_rerun = True

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
        + f'<div class="{caption_class}"><div class="poster-caption-title" title="{title}">{title}</div>{year_html}</div>',
        unsafe_allow_html=True
    )

def current_profile():
    return build_profile(
        st.session_state.likes, st.session_state.favorites, st.session_state.genres,
        st.session_state.review_priority, st.session_state.more_of,
        st.session_state.saved, st.session_state.dismissed, st.session_state.adventure,
        st.session_state.external_movies, st.session_state.seen,
        disliked_titles=st.session_state.get("disliked") or set(),
    )

def _cf_signals():
    """Collect browser-local actions for the MovieLens-pretrained CF layer."""
    ext = st.session_state.external_movies
    out = []
    for t in st.session_state.likes:
        m = get_movie(t, ext)
        if m: out.append((m, "favorite" if t in st.session_state.favorites else "like"))
    for key, action in (("saved", "save"), ("seen", "seen"), ("dismissed", "skip"), ("disliked", "dislike")):
        for t in st.session_state.get(key) or set():
            m = get_movie(t, ext)
            if m: out.append((m, action))
    return out

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

def clean_movie_copy(text, ensure_terminal=True):
    """Normalize movie copy so UI summaries never end on awkward fragments."""
    value = " ".join(str(text or "").split()).strip()
    if not value:
        return ""

    # Normalize punctuation spacing and repeated punctuation.
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"([,;:]){2,}", r"\1", value)
    value = re.sub(r"\.{2,}", ".", value)
    value = value.strip(" \t\n,;:–—-")

    # Remove dangling connector/article words caused by safe truncation.
    dangling = {
        "a", "an", "the", "and", "or", "but", "with", "to", "of", "in",
        "for", "from", "by", "as", "at", "into", "onto", "on", "its", "his",
        "her", "their", "who", "that", "which"
    }
    words = value.rstrip(".!?").split()
    while words and words[-1].casefold().strip(".,;:") in dangling:
        words.pop()
    value = " ".join(words).rstrip(" ,;:")

    if ensure_terminal and value and value[-1] not in ".!?":
        value += "."
    return value


_HOOK_VERBS = set("""
is are was were be becomes become finds find follows follow discovers discover tries try must has have
gets get enters enter returns return meets meet faces face uncovers uncover struggles struggle begins begin
turns turn joins join grows grow investigates investigate reconnects reconnect attempts attempt receives
receive attends attend moves move prepares prepare realizes realize spends spend fights fight searches search
takes take makes make lives live works work falls fall goes go comes come leads lead learns learn sets set
plans plan hunts hunt runs run seeks seek wants want needs need loses lose wins win tells tell decides decide
agrees agree forms form builds build hides hide escapes escape travels travel embarks embark stumbles stumble
must wakes wake kills kill saves save protects protect helps help leaves leave arrives arrive teams team
tracks track confronts confront battles battle pursues pursue sparks spark unravels unravel navigates navigate
inherits inherit befriends befriend infiltrates infiltrate recruits recruit risks risk chases chase
""".split())
_HOOK_DANGLING_END = {
    "a", "an", "the", "and", "or", "but", "with", "to", "of", "in", "for", "from", "by", "as", "at",
    "into", "onto", "on", "its", "his", "her", "their", "who", "that", "which", "young", "whose", "when",
}
_HOOK_SPLITS = ("; ", " — ", " – ", ": ", ", and ", ", but ", ", who ", ", where ", ", when ", " when ",
                ", while ", ", as ", ", until ", " until ", ", before ", ", after ", ", only to ", " in order to ", " after ", " before ", " while ")


def _hook_is_complete(text, limit, need_verb=True):
    text = clean_movie_copy(text, ensure_terminal=False)
    if not text or len(text) < 24 or len(text) > limit:
        return False
    words = [w.casefold().strip(".,;:!?()[]{}\"'") for w in text.split()]
    if len(words) < 5 or words[-1] in _HOOK_DANGLING_END:
        return False
    if words[0] in {"in", "on", "at", "during", "after", "before", "while", "when", "with", "without",
                    "through", "across", "amid", "following"}:
        return False
    return (not need_verb) or any(w in _HOOK_VERBS for w in words[1:])


_HOOK_LEADS = (r"^(?:in|on|at|during|after|before|following|inside|across|amid|within|when|while|as|once|until|"
               r"years after|decades after|set in|in the)\b[^,]{2,110},\s+(.+)$")
_HOOK_PRONOUN_START = {"he", "she", "they", "it", "his", "her", "their", "its", "this", "these", "there", "but", "and", "then"}


_HOOK_AUX = {"is", "are", "was", "were", "has", "have", "had", "must", "can", "could", "will",
             "would", "should", "may", "might", "does", "did", "gets", "got"}


# Words that start a setup phrase ("Years later,", "Meanwhile,", "All unemployed,").
# A name can never be trimmed because it is never on this list.
_SETUP_OPENERS = {
    "years", "months", "weeks", "days", "decades", "centuries", "hours", "moments", "minutes",
    "meanwhile", "now", "today", "tonight", "soon", "later", "once", "all", "after", "before",
    "during", "following", "since", "still", "suddenly", "eventually", "finally", "together",
    "alone", "newly", "recently", "long", "back", "far", "deep", "high", "just", "one", "two",
    "desperate", "determined", "unemployed", "broke", "orphaned", "widowed", "haunted",
    "estranged", "exiled", "stranded", "trapped", "armed", "fresh", "fed", "tired", "bored",
    "lonely", "unable", "eager", "reluctant", "grieving", "struggling", "having", "faced",
    "facing", "left", "raised", "born", "set",
}


def _is_setup_opener(words):
    first = words[0].strip(".,;:!?\"'") if words else ""
    return first in _SETUP_OPENERS


def _starts_with_subject(text):
    """False when a clause would begin with its verb, or is only an appositive
    ("a young man, is ...") whose real subject was the name before it."""
    words = [w.casefold().strip(".,;:!?\"'") for w in text.split()]
    if not words or words[0] in _HOOK_AUX or words[0] in _HOOK_VERBS:
        return False
    if words[0] in {"a", "an", "the", "his", "her", "their", "its"}:
        comma = text.find(", ")
        if 0 < comma <= 60:
            after = text[comma + 2:].split()
            if after and (after[0].casefold() in _HOOK_AUX or after[0].casefold() in _HOOK_VERBS):
                return False
    return True


def _hook_variants(sentence):
    """(text, is_whole_clause) options: the sentence, its main clause after up to two
    leading setup phrases, and safe clause cuts. Whole clauses are grammatical by
    construction; cuts must also pass the verb check."""
    whole = [sentence]
    current = sentence
    for _ in range(2):
        lead = re.match(_HOOK_LEADS, current, flags=re.IGNORECASE)
        if lead:
            rest = lead.group(1).strip()
            if not _starts_with_subject(rest):
                break  # never leave a clause that begins with its verb
            current = rest
        else:
            # Short verbless opener such as "All unemployed," or "Years later,".
            comma = current.find(", ")
            opener = current[:comma].casefold().split() if 0 < comma <= 30 else None
            if not opener or any(w in _HOOK_VERBS for w in opener) or not _is_setup_opener(opener):
                break  # only clear setup phrases are trimmed; names never are
            rest = current[comma + 2:].strip()
            if not _starts_with_subject(rest):
                break  # "Hana, a young girl, is captured..." keeps its subject
            current = rest
        whole.append(current[:1].upper() + current[1:])
    variants = [(w, True) for w in whole]
    for source in whole:
        for marker in _HOOK_SPLITS:
            pos = source.find(marker)
            if pos > 20 and not (marker.startswith(",") and "," in source[:pos]):
                variants.append((source[:pos], False))
    return variants


_SCENE_SETTING = re.compile(
    r"^(?:it['’]s|it is|it was)\s+(?:the\s+)?(?:\d{4}s?|year|summer|winter|spring|fall|autumn|"
    r"early|late|mid|eve|night|day|end|dawn|future|era|age)\b"
    r"|^the year is\b|^set (?:in|during|against)\b|^welcome to\b|^once upon a time\b",
    re.IGNORECASE,
)


def _is_scene_setting(sentence):
    """Opening narration ("It's the 1940s, and ...") sets a scene but says nothing about the story."""
    return bool(_SCENE_SETTING.match(str(sentence or "").strip()))


def _ends_on_bare_infinitive(text):
    """Cuts like "... hope to join" drop the object and read as unfinished."""
    words = [w.casefold().strip(".,;:!?\"'") for w in str(text or "").split()]
    return len(words) >= 2 and words[-2] == "to"


def quick_card_description(movie, limit=110):
    """One real, specific, complete line about the movie. Never cut mid-sentence.

    Order: the catalog's hand-written hook; the best complete clause from the
    opening sentence; a later self-contained sentence; the opening sentence whole
    if it fits; otherwise a clean prompt to open the synopsis.
    """
    movie = movie or {}
    why = clean_movie_copy(movie.get("why"), ensure_terminal=True)
    if why and len(why) <= limit + 30:
        return why
    full = clean_movie_copy(movie.get("overview") or movie.get("why"), ensure_terminal=False)
    if not full:
        return "Tap for the premise."
    sentences = [s.strip().rstrip(".;:, ") for s in re.split(r"(?<=[.!?])\s+", full) if s.strip()]

    for pos, sentence in enumerate(sentences[:4]):
        if pos > 0 and sentence.split()[0].casefold().strip(",") in _HOOK_PRONOUN_START:
            continue  # later sentences that lean on earlier context read as fragments
        if _is_scene_setting(sentence):
            continue  # scene-setting narration is a last resort, not a hook
        complete = [
            c for c, is_whole in _hook_variants(sentence)
            if _hook_is_complete(c, limit, need_verb=not is_whole)
            and (is_whole or not _ends_on_bare_infinitive(c))
        ]
        if complete:
            return clean_movie_copy(max(complete, key=len), ensure_terminal=True)

    # TMDB's own tagline (fetched with the movie details we already request) beats narration.
    tagline = clean_movie_copy(movie.get("tagline"), ensure_terminal=True)
    if tagline and 12 <= len(tagline) <= limit:
        return tagline

    first = clean_movie_copy(sentences[0] if sentences else full, ensure_terminal=True)
    if len(first) <= limit:
        return first
    return "Tap for the premise."


def tonight_description(movie, limit=160):
    """Tonight's Show line: the one-line hook when it says something about the story,
    otherwise the opening premise in complete sentences (the hero card has room).

    Fixes lines like "It's the 1940s, and the notorious Axe Gang terrorizes Shanghai.",
    scene-setting narration that the hook logic only uses as a last resort.
    """
    hook = quick_card_description(movie, limit=limit)
    full = clean_movie_copy((movie or {}).get("overview"), ensure_terminal=False)
    if not full:
        return hook
    sentences = [x.strip().rstrip(".;:, ") for x in re.split(r"(?<=[.!?])\s+", full) if x.strip()]
    if len(sentences) < 2:
        return hook
    first = clean_movie_copy(sentences[0], ensure_terminal=True)
    weak = hook == "Tap for the premise." or (hook == first and _is_scene_setting(sentences[0]))
    if not weak:
        return hook
    second = sentences[1]
    if len(first) + len(second) > 260:
        # Keep the second sentence's opening clause: after the scene, "...hope to join" reads fine.
        m = re.search(r",\s+(?:but|and|while|until|when|as|only)\b|;\s+|\s+[–—]\s+", second)
        if m and len(second[:m.start()].split()) >= 4:
            second = second[:m.start()]
        else:
            return first
    return f"{first} {clean_movie_copy(second, ensure_terminal=True)}"


def expanded_card_description(movie, max_chars=320):
    """The premise: the opening of the TMDB overview, in complete sentences.

    Always starts at the beginning, since later sentences ("Then, a man...") lean on
    earlier ones. Adds whole sentences while they fit and never cuts one mid-way.
    """
    full = clean_movie_copy(
        (movie or {}).get("overview") or (movie or {}).get("why"),
        ensure_terminal=False,
    )
    if not full:
        return "iCinema does not have a longer premise for this title yet."
    sentences = [
        clean_movie_copy(part, ensure_terminal=True)
        for part in re.split(r"(?<=[.!?])\s+", full)
        if clean_movie_copy(part, ensure_terminal=False)
    ]
    chosen, total = [], 0
    for sentence in sentences[:3]:
        projected = total + len(sentence) + (1 if chosen else 0)
        if chosen and projected > max_chars:
            break
        chosen.append(sentence)  # the first sentence is always kept whole
        total = projected
    return " ".join(chosen).strip()


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


def cached_semantic_scores(movies, profile):
    """TF-IDF + SVD theme similarity, recomputed only when inputs change."""
    signals = tuple((s.get("title"), s.get("weight")) for s in (profile.get("semantic_signals") or []))
    titles = tuple(m.get("title") for m in movies)
    key = (signals, titles)
    cache = st.session_state.get("_semantic_cache")
    if cache and cache[0] == key:
        by_title = cache[1]
    else:
        scores = semantic_similarity_scores(movies, profile)
        by_title = {m.get("title"): scores.get(id(m), 0.5) for m in movies}
        st.session_state._semantic_cache = (key, by_title)
    return {id(m): by_title.get(m.get("title"), 0.5) for m in movies}


def learning_model_for(events):
    """Train the Save/Skip model only when feedback changed since the last run."""
    events = list(events or [])
    signature = (len(events), events[-1].get("timestamp") if events else None)
    cache = st.session_state.get("_learning_model_cache")
    if cache and cache[0] == signature:
        return cache[1]
    result = train_learning_model(events)
    st.session_state._learning_model_cache = (signature, result)
    return result


def training_scale():
    """Human-readable MovieLens training size, read from the results file when available."""
    data = load_offline_results() or {}
    def fmt(n, fallback):
        if isinstance(n, int):
            return f"{n / 1e6:.1f} million" if n >= 1_000_000 else f"{n:,}"
        return fallback
    return {
        "users": fmt(data.get("train_users"), "198,954"),
        "movies": fmt(data.get("train_movies"), "14,407"),
        "positives": fmt(data.get("train_positives"), "15.8 million"),
    }


@st.cache_data(show_spinner=False)
def load_offline_results():
    """MovieLens evaluation written by training/train_cf.py (data/cf_results.json)."""
    try:
        path = Path(__file__).resolve().parent / "data" / "cf_results.json"
        return json.loads(path.read_text())
    except Exception:
        return None


def render_cinema_profile(p, include_insights=False, show_heading=True, tab_heading=False):
    # Plain-language labels; "Your mix" drops lines that repeat "How you choose".
    matters_text = " ".join(p["matters"]).casefold()
    mix = [b for b in p["balance"] if not ("review" in b.casefold() and "review" in matters_text)]
    sections = [
        ("You tend to enjoy", profile_chip_html(p["traits"]), "profile-chip-wrap"),
        ("Top genres", profile_chip_html(p["genres"]), "profile-chip-wrap"),
        ("How you choose", profile_chip_html(p["matters"]), "profile-chip-wrap"),
        ("Show me more", profile_chip_html(p["priorities"]), "profile-chip-wrap"),
        ("Your patterns", profile_chip_html(p["patterns"]), "profile-chip-wrap"),
        ("Your mix", profile_chip_html(mix), "profile-chip-wrap"),
    ]
    sections = [s for s in sections if s[1]]
    section_html = "".join(
        f'<div class="profile-block full"><div class="profile-label">{label}</div><div class="{wrapper_class}">{content}</div></div>'
        for label, content, wrapper_class in sections
    )
    events=list(st.session_state.get("analytics_events") or [])
    insights=analytics_insights(events)
    learned=learning_model_for(events)
    conf=profile_confidence_label(p)
    signals=sum((p.get("behavior_counts") or {}).values()) + len((p.get("controls") or {}).get("selected_genres",[]) or []) + len((p.get("controls") or {}).get("priorities",[]) or [])
    _bc = p.get("behavior_counts") or {}
    _ctl = p.get("controls") or {}
    _parts = [(_bc.get("liked", 0) + _bc.get("favorited", 0), "like"), (_bc.get("saved", 0), "save"),
              (_bc.get("seen", 0), "seen"), (_bc.get("skipped", 0), "skip"), (_bc.get("disliked", 0), "not for me"),
              (len(_ctl.get("selected_genres") or []), "genre pick"), (len(_ctl.get("priorities") or []), "row preference")]
    signal_parts = " · ".join(f"{n} {lbl}{'' if n == 1 or lbl in ('seen', 'not for me') else 's'}" for n, lbl in _parts if n)
    scale = training_scale()
    # What is actually running right now. Collaborative filtering and the content
    # model work from the first like; the personal model needs 50 Save/Skip labels.
    decisions = int(insights.get("saves") or 0) + int(insights.get("skips") or 0)
    if learned.ready:
        personal_html = (f'<div class="model-row"><span class="model-dot on"></span>'
                         f'<span class="model-name">Your personal model</span>'
                         f'<span class="model-note">Active · {html.escape(learned.model_name)} trained on {learned.samples} of your decisions</span></div>')
    else:
        pct = min(100, round(decisions / 50 * 100))
        personal_html = (f'<div class="model-row"><span class="model-dot"></span>'
                         f'<span class="model-name">Your personal model</span>'
                         f'<span class="model-note">Learns from your saves and skips: {min(decisions, 50)} of 50 · '
                         f'{int(insights.get("saves") or 0)} saves, {int(insights.get("skips") or 0)} skips (needs 12+ of each; Seen doesn\'t count)</span>'
                         f'<span class="model-progress"><span style="width:{pct}%"></span></span></div>')
    models_html = (
        '<div class="model-status-panel">'
        '<div class="model-row"><span class="model-dot on"></span>'
        '<span class="model-name">Active now</span>'
        f'<span class="model-note">Collaborative filtering ({scale["users"]} MovieLens viewers) + content model, '
        f'using your {signals} signal{"s" if signals != 1 else ""}'
        + (f' ({html.escape(signal_parts)})' if signal_parts else '') + '</span></div>'
        f'{personal_html}'
        '</div>'
    )

    def _stat(value, title, note):
        return (f'<div class="insight-card"><div class="insight-value">{html.escape(str(value))}</div>'
                f'<div class="insight-title">{html.escape(title)}</div>'
                f'<div class="insight-label">{html.escape(note)}</div></div>')

    def _or_learning(key, fmt):
        v = insights.get(key)
        return "Learning" if v is None else fmt(v)

    insight_cards = [
        _stat(_format_seconds(insights.get("time_to_match_seconds")), "Time to your first save",
              "Median per visit. A visit ends after 30 idle minutes."),
        _stat(_or_learning("avg_skips_before_save", lambda v: f"{v:.1f}"), "Skips before a save",
              "Lower means the first picks are landing."),
        _stat(_or_learning("avg_recommendations_examined_before_save", lambda v: f"{v:.0f}"), "Movies shown before a save",
              "How many picks it took to find one you wanted."),
        _stat(_or_learning("saved_to_seen_rate", lambda v: f"{v*100:.0f}%"), "Saved, then watched",
              "Share of your saves you later marked Seen."),
        _stat(_or_learning("discovery_rate", lambda v: f"{v*100:.0f}%"), "Saves beyond Top Matches",
              "Finds from Critically Acclaimed, Hidden Gems, and Something Different."),
        _stat(conf, "Profile strength", "Grows with every like, save, and skip."),
    ]
    insight_html = "".join(insight_cards)

    ranking=ranking_metrics(events)
    calib=calibration_metrics(events)
    lm=learned.metrics or {}
    offline=load_offline_results()

    def _fmt(v, pct=False):
        if v is None:
            return "Learning"
        return f"{v*100:.0f}%" if pct else f"{v:.2f}"

    def _card(value, label):
        return (f'<div class="insight-card"><div class="insight-value">{html.escape(str(value))}</div>'
                f'<div class="insight-label">{html.escape(label)}</div></div>')

    scale = training_scale()
    # Consumer-facing: what it does and whether it works. Full detail lives in MODEL_CARD.md.
    proof_html = ""
    if offline:
        pop = (offline.get("full") or {}).get("popularity") or {}
        cf3 = (offline.get("three_likes") or {}).get("cf") or {}
        stored = offline.get("lifts_three_likes_vs_popularity") or {}
        def _lift(key):
            # Prefer the lift saved by training, so the app matches the README exactly.
            if isinstance(stored.get(key), (int, float)):
                return int(stored[key])
            a, b = cf3.get(key), pop.get(key)
            return round((a / b - 1) * 100) if a and b else None
        pick_lift, ndcg_lift, recall_lift = _lift("hit@1"), _lift("ndcg@10"), _lift("recall@10")
        users = offline.get("held_out_users")
        # Only claim significance the bootstrap actually found (read from the results file).
        sig = {b.get("metric"): bool(b.get("significant")) for b in offline.get("bootstrap_three_likes_vs_popularity") or []}
        if sig.get("Hit@1") and sig.get("NDCG@10") and sig.get("Recall@10"):
            significance_note = "All three results are statistically significant."
        elif any(sig.values()):
            significance_note = "Some results are statistically significant; see the model card for details."
        else:
            significance_note = "See the model card for confidence intervals."
        cards = []
        if pick_lift is not None:
            cf_hit, pop_hit = cf3.get("hit@1"), pop.get("hit@1")
            hit_note = (f"Its one pick was a movie the viewer rated 4+ stars {cf_hit:.2%} of the time, vs. {pop_hit:.2%} for the most popular pick."
                        if isinstance(cf_hit, (int, float)) and isinstance(pop_hit, (int, float))
                        else "Its one pick is a movie you'll love more often than the most popular pick.")
            cards.append(_stat(f"+{pick_lift}%", "More hits for Tonight’s Show", hit_note))
        if ndcg_lift is not None and recall_lift is not None:
            lo, hi = sorted((ndcg_lift, recall_lift))
            cards.append(_stat(f"+{lo}–{hi}%", "Better Showroom rows",
                               f"More movies you’d love in the top 10 (+{recall_lift}%, Recall@10), ranked closer to the top (+{ndcg_lift}%, NDCG@10)."))
        hit_boot = next((b for b in offline.get("bootstrap_three_likes_vs_popularity") or []
                         if b.get("metric") == "Hit@1"), {})
        share = hit_boot.get("cf_win_share")
        if isinstance(share, (int, float)):
            # Share of bootstrap resamples where iCinema wins -> one-sided bootstrap p-value.
            p_txt = "p < 0.001" if share >= 0.9995 else f"p ≈ {max(1 - share, 0.0005):.3f}"
            wins = "all 2,000" if share >= 0.9995 else f"{share:.0%} of 2,000"
            cards.append(_stat(p_txt, "Not a fluke",
                               f"iCinema beat the popularity pick in {wins} bootstrap resamples of the test viewers."))
        cf_full = (offline.get("full") or {}).get("cf") or {}
        full_note = ""
        if isinstance(cf_full.get("hit@1"), (int, float)) and isinstance(cf3.get("hit@1"), (int, float)) and cf3["hit@1"] > cf_full["hit@1"]:
            full_note = (" Personalizing from just 3 likes is where most recommenders struggle; iCinema’s 3-like picks even beat "
                         "the same model given each viewer’s full history. Stronger comparisons (item-kNN, ALS) are next.")
        else:
            full_note = " Stronger comparisons (item-kNN, ALS) are next."
        if cards and isinstance(users, int):
            proof_html = (
                '<div class="profile-methodology">'
                f'<div class="profile-insights-title">Tested on {users:,} real viewers</div>'
                f'<div class="profile-insights-copy">iCinema saw only 3 movies each MovieLens viewer liked, then predicted the films '
                'they’d rate 4+ stars later, compared with simply recommending what’s popular. '
                f'{significance_note}{full_note}</div>'
                f'<div class="insight-grid proof-grid">{"".join(cards)}</div>'
                '</div>'
            )

    live_html = ""
    if learned.ready:
        auc = lm.get("auc")
        live_html = (
            '<div class="profile-insights-copy live-model-copy">'
            f'Your personal model is active: {html.escape(learned.model_name)}, trained on {learned.samples} of your choices'
            + (f', and it predicts your saves well above chance (AUC {auc:.2f}).' if isinstance(auc, (int, float)) else '.')
            + '</div>'
        )

    methodology_html = (
        '<div class="profile-methodology">'
        '<div class="profile-insights-title">How iCinema works</div>'
        '<div class="methodology-grid how-grid">'
        '<div class="methodology-card">'
        f'<div class="methodology-value">Starts with {scale["users"]} movie fans</div>'
        f'<div class="methodology-label">A model trained on how they rated {scale["movies"]} movies compares your first likes with theirs, '
        'so your first picks are already personal.</div>'
        '</div>'
        '<div class="methodology-card">'
        '<div class="methodology-value">Understands every movie</div>'
        '<div class="methodology-label">A second model reads each film’s plot, tone, genre, and ratings, and weighs them by your setup answers.</div>'
        '</div>'
        '<div class="methodology-card">'
        '<div class="methodology-value">Gives every row a job</div>'
        '<div class="methodology-label">Best fit, critics’ favorites, hidden gems, or something new, and no movie appears twice.</div>'
        '</div>'
        '<div class="methodology-card">'
        '<div class="methodology-value">Learns you over time</div>'
        '<div class="methodology-label">After 50 saves and skips, a third model trained only on your choices joins in. Undo keeps accidental taps out.</div>'
        '</div>'
        '</div>'
        '<div class="profile-insights-copy ratings-note">About ratings: IMDb and Rotten Tomatoes scores come from OMDb. '
        'When IMDb has no score, iCinema shows the viewer rating from TMDB, a large community movie database. '
        '“No RT” means Rotten Tomatoes hasn’t reviewed the movie.</div>'
        '<div class="profile-insights-copy ratings-note">Fresh every visit: movies you passed over step back, and iCinema '
        'searches deeper into your favorite genres, so new picks keep surfacing.</div>'
        f'{live_html}'
        '</div>'
        f'{proof_html}'
    )

    insights_section = (
        f'<div class="profile-insights"><div class="profile-insights-title">iCinema’s Insights</div>'
        f'<div class="profile-insights-copy">How fast iCinema gets you from browsing to a movie worth watching.</div>'
        f'<div class="insight-grid stats-grid">{insight_html}</div></div>'
        f'{methodology_html}'
        if include_insights else ""
    )

    heading_class = "tab-primary-heading profile-heading-aligned" if tab_heading else "profile-heading"
    profile_heading_html = f'<div class="{heading_class}">Your Cinema Profile</div>' if show_heading else ""

    st.markdown(
        f'<div class="profile-wrap">'
        f'{profile_heading_html}'
        f'<div class="profile-heading-gap"></div>'
        f'{models_html}'
        f'<div class="profile-grid">{section_html}</div>'
        f'<div class="profile-summary">{p["summary"]}</div>'
        f'{insights_section}'
        f'</div>', unsafe_allow_html=True
    )



import functools as _functools


def _with_app_rerun(fn):
    """Run a full-app rerun requested by a button callback (callbacks themselves can't)."""
    @_functools.wraps(fn)
    def inner(*args, **kwargs):
        if st.session_state.pop("_app_rerun", False):
            st.rerun(scope="app")
        return fn(*args, **kwargs)
    return inner


@st.fragment(run_every="4s")
@_with_app_rerun
def render_live_profile():
    """Profile tab, refreshed every few seconds.

    Showroom cards rerun on their own (so Skip/Save stay fast), which used to leave this
    tab showing counts from when the Showroom was built. Rebuilding it from current state
    keeps the signals and the "x of 50" progress matching what you just did.
    """
    render_cinema_profile(current_profile(), include_insights=True, show_heading=True, tab_heading=True)


@st.fragment
@_with_app_rerun
def render_shelf_fragment():
    logo()
    st.markdown(
        '<div class="page-top-heading">Step 1 of 3 — Rate the Shelf</div>'
        '<div class="page-top-subtitle">Choose a few titles you already like. Skip any you don’t know, or search for one you enjoy.</div>',
        unsafe_allow_html=True,
    )

    ensure_rotating_shelf()
    shelf_movies = list(st.session_state.shelf_movies)
    missing_posters = tuple(
        (m["title"], int(m.get("year") or 0))
        for m in shelf_movies if not m.get("poster_url")
    )
    shelf_poster_map = get_poster_batch(missing_posters) if missing_posters else {}
    # Landscape key art fits the short shelf cards without cropping; posters are the fallback.
    shelf_landscape_map = get_landscape_batch(tuple(
        (m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in shelf_movies
    ))
    shelf_box = st.container(key="step1_shelf")
    cols=shelf_box.columns(5, gap="small")
    for i,movie in enumerate(shelf_movies):
        title=movie["title"]
        with cols[i%5]:
            movie_thumb(movie, shelf_landscape_map.get(title) or movie.get("poster_url") or shelf_poster_map.get(title))
            b1,b2,b3=st.columns([1,1.3,1], gap="small")
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
            with b3:
                st.button(
                    "Skip",
                    key=f"shelfskip_{i}_{movie.get('tmdb_id') or title}",
                    use_container_width=True,
                    on_click=skip_shelf_movie,
                    args=(i,),
                )

    with st.container(key="step1_search"):
        st.markdown(
            '<div class="search-shell">'
            '<div class="search-shell-title">Don’t see one you like?</div>'
            '<div class="search-shell-copy">Search for a movie you already enjoy</div>'
            '</div>',
            unsafe_allow_html=True
        )

        search_query = live_search_box()

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

    with st.container(key="step1_selections"):
        _selected_set = st.session_state.likes | st.session_state.favorites
        chosen_titles = [t for t in st.session_state.get("selection_order", []) if t in _selected_set]
        chosen_titles += sorted(_selected_set - set(chosen_titles))
        chosen_count = len(chosen_titles)

        if chosen_titles:
            st.markdown(
                '<div class="selection-area-heading">'
                '<div class="selection-heading">Your selections</div>'
                '</div>',
                unsafe_allow_html=True,
            )

            # Keep the familiar compact chip layout while making every item removable.
            selection_cols = st.columns(min(4, len(chosen_titles)), gap="small")
            for idx, title in enumerate(chosen_titles):
                state = "Favorite" if title in st.session_state.favorites else "Liked"
                with selection_cols[idx % len(selection_cols)]:
                    with st.container(key=f"selection_card_{idx}"):
                        st.markdown(
                            f'<div class="selection-card-copy">'
                            f'<div class="selection-title">{html.escape(title)}</div>'
                            f'<div class="selection-state">{html.escape(state)}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        st.button(
                            "×",
                            key=f"remove_selection_{idx}",
                            help=f"Remove {title}",
                            on_click=remove_step1_selection,
                            args=(title,),
                        )

        st.caption(f"{chosen_count} title{'s' if chosen_count!=1 else ''} selected")
    with st.container(key="nav_row_rate"):
        cont, _ = st.columns([1.25, 6], gap="small")
        with cont:
            st.button("Continue →", type="primary", disabled=chosen_count==0, key="continue_rate", use_container_width=True, on_click=go_from_fragment, args=("taste",))


    persist_from_fragment()

@st.fragment
@_with_app_rerun
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

    st.markdown('<div class="step2-question step2-question-next">What do you like to watch?</div>', unsafe_allow_html=True)
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

    st.markdown('<div class="step2-question step2-question-next">How open are you to something different?</div>', unsafe_allow_html=True)

    adventure_scale_map = [15, 32, 50, 68, 85]
    adventure_idx = min(range(5), key=lambda i: abs(adventure_scale_map[i] - st.session_state.adventure))

    adventure_label = [
        "Stay very close to what I like",
        "Stay mostly familiar",
        "Balanced",
        "Explore a little more",
        "Show me something different",
    ][adventure_idx]

    st.markdown(
        '<div class="pref-scale-wrap">'
        '<div class="pref-scale-ends"><span>Stay close to what I like</span><span>Show me something different</span></div>'
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
    with st.container(key="nav_row_taste"):
        back, cont, _ = st.columns([1, 1.25, 5], gap="small")
        with back:
            st.button("← Back", key="back_taste", use_container_width=True, on_click=go_from_fragment, args=("shelf",))
        with cont:
            st.button("Continue →", type="primary", key="continue_taste", use_container_width=True, on_click=go_from_fragment, args=("more",))


    persist_from_fragment()

@st.fragment
@_with_app_rerun
def render_more_fragment():
    logo()
    st.markdown(
        '<div class="page-top-heading">Step 3 of 3 — Shape Your Showroom</div>'
        '<div class="page-top-subtitle step3-subtitle">What should iCinema lean toward? Choose any that you want to see more often</div>',
        unsafe_allow_html=True,
    )

    descriptions = {
        "Hidden Gems": "Less obvious titles that still fit what you like",
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

    with st.container(key="nav_row_more"):
        back, cont, _ = st.columns([1, 2.2, 4], gap="small")
        with back:
            st.button("← Back", key="back_more", use_container_width=True, on_click=go_from_fragment, args=("taste",))
        with cont:
            st.button("Build My Cinema Profile →", type="primary", key="build_profile", use_container_width=True, on_click=go_from_fragment, args=("profile",))

    # Step 3 selections are queued in session state and persisted on the page-level
    # transition to Profile. Avoid rendering the localStorage bridge inside this
    # fragment, which could briefly surface as a dark strip after a card click.


def _showroom_slot_key(row_name, slot_index):
    return f"{row_name}::{int(slot_index)}"

def _advance_showroom_slot(row_name, slot_index):
    """Replace only one visible showroom slot from its already-ranked queue."""
    slot_key = _showroom_slot_key(row_name, slot_index)
    slots = dict(st.session_state.get("showroom_slots") or {})
    queues = st.session_state.get("showroom_row_queues") or {}
    payloads = st.session_state.get("showroom_payloads") or {}
    current_titles = {title for title in slots.values() if title}
    excluded = (
        set(st.session_state.saved)
        | set(st.session_state.seen)
        | set(st.session_state.dismissed)
        | set(st.session_state.get("disliked") or set())
    )

    replacement = None
    for title in queues.get(row_name, []):
        if not title or title in current_titles or title in excluded:
            continue
        if title not in payloads:
            continue
        replacement = title
        break

    if replacement:
        slots[slot_key] = replacement
        st.session_state.showroom_slots = slots
        return True
    return False

def dislike_movie(title, movie=None):
    """Explicit negative feedback: stronger than Skip, and the title never returns."""
    _remember_movie(movie)
    record_event(st.session_state, "dislike", title, _current_recommendation_context(title))
    disliked = set(st.session_state.get("disliked") or set())
    disliked.add(title)
    st.session_state.disliked = disliked
    st.session_state.saved.discard(title)
    queue_profile_save()


def dislike_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    if title:
        dislike_movie(title, payload.get("movie"))
        undo = dict(st.session_state.get("showroom_undo") or {})
        undo[slot_key] = title
        st.session_state.showroom_undo = undo
    _advance_showroom_slot(row_name, slot_index)


def skip_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    movie = payload.get("movie")
    if title:
        skip_movie(title, movie)
        undo = dict(st.session_state.get("showroom_undo") or {})
        undo[slot_key] = title
        st.session_state.showroom_undo = undo
    if not _advance_showroom_slot(row_name, slot_index):
        st.session_state._app_rerun = True

def _mark_showroom_fast():
    st.session_state._showroom_fast = True


def save_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    movie = payload.get("movie")
    if title:
        save_movie(title, movie)
        undo = dict(st.session_state.get("showroom_undo") or {})
        undo.pop(slot_key, None)
        st.session_state.showroom_undo = undo
    _advance_showroom_slot(row_name, slot_index)
    _mark_showroom_fast()

def seen_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    movie = payload.get("movie")
    if title:
        mark_movie_seen(title, movie)
        undo = dict(st.session_state.get("showroom_undo") or {})
        undo.pop(slot_key, None)
        st.session_state.showroom_undo = undo
    _advance_showroom_slot(row_name, slot_index)
    _mark_showroom_fast()

def _showroom_cached_metadata(movie):
    """Use initial batch metadata; fetch only the replacement card on cache miss."""
    title = movie["title"]
    year = int(movie.get("year") or 0)
    tmdb_id = int(movie.get("tmdb_id") or 0)

    identity_cache = dict(st.session_state.get("showroom_identity_cache") or {})
    identity = identity_cache.get(title)
    if identity is None:
        identity = (get_movie_identity_batch(((title, year, tmdb_id),)).get(title) or {})
        identity_cache[title] = identity
        st.session_state.showroom_identity_cache = identity_cache

    watch_cache = dict(st.session_state.get("showroom_watch_cache") or {})
    availability = watch_cache.get(title)
    if availability is None:
        availability = (get_watch_availability_batch(((title, year),), "US").get(title) or {
            "status":"unknown",
            "text":"Where to watch: availability unavailable",
            "url":None,
        })
        watch_cache[title] = availability
        st.session_state.showroom_watch_cache = watch_cache

    rating_cache = dict(st.session_state.get("showroom_rating_cache") or {})
    live_rating = rating_cache.get(title)
    if live_rating is None:
        imdb_id = (identity or {}).get("imdb_id") or ""
        live_rating = (get_live_ratings_batch(((title, year, imdb_id),)).get(title) or {})
        rating_cache[title] = live_rating
        st.session_state.showroom_rating_cache = rating_cache

    return identity or {}, availability or {}, live_rating or {}

@st.fragment
@_with_app_rerun
def render_showroom_card_fragment(row_name, row_index, slot_index):
    """Render one independently-rerunnable card so Skip never refreshes its neighbors."""
    slot_key = _showroom_slot_key(row_name, slot_index)
    title = (st.session_state.get("showroom_slots") or {}).get(slot_key)
    acted = (set(st.session_state.saved) | set(st.session_state.seen) | set(st.session_state.dismissed)
             | set(st.session_state.get("disliked") or set()))
    if title in acted and _advance_showroom_slot(row_name, slot_index):
        title = (st.session_state.get("showroom_slots") or {}).get(slot_key)  # never re-show an acted-on movie
    payload = (st.session_state.get("showroom_payloads") or {}).get(title) or {}
    movie = payload.get("movie")
    if not title or not movie or title in acted:
        st.caption("Refreshing match…")
        return

    match = int(payload.get("match") or 0)
    p = current_profile()
    identity, availability, live_rating = _showroom_cached_metadata(movie)
    availability_value = service_availability_utility(availability)
    comps = score_movie_components(
        movie, p, st.session_state.adventure, st.session_state.review_priority,
        semantic_similarity=float(payload.get("semantic_similarity", .5)),
        availability_score=availability_value,
    )
    context = {
        "row":row_name,
        "position":int(slot_index)+1,
        "match":int(payload.get("model_match") or match),
        "model_score":round(float(comps.get("raw_score",0)),6),
        "decision_utility":round(float(comps.get("decision_utility",comps.get("raw_score",0))),6),
        **{k:round(float(comps.get(k,.5)),6) for k in [
            "genre_affinity","trait_affinity","semantic_similarity","quality_alignment",
            "discovery_alignment","priority_alignment","availability_alignment",
            "vote_confidence","profile_confidence"
        ]},
        "cf_affinity":round(float(payload.get("cf") if payload.get("cf") is not None else 0.5),6),
        "candidate_source":movie.get("candidate_source"),
        "model_version":"v5.191",
    }
    recommendation_context = dict(st.session_state.get("recommendation_context") or {})
    recommendation_context[title] = context
    st.session_state.recommendation_context = recommendation_context
    record_impressions(st.session_state, {title: context})

    with st.container(key=f"showroom_controls_{row_index}_{slot_index}_{title}"):
        undo_title = (st.session_state.get("showroom_undo") or {}).get(slot_key)
        if undo_title:
            match_col, undo_col, skip_col = st.columns([2.75,0.62,0.90], gap="small")
            with undo_col:
                st.button(
                    "↶",
                    key=f"undo_{row_name}_{slot_index}_{title}",
                    help=f"Undo skip · bring back {undo_title}",
                    use_container_width=True,
                    on_click=undo_showroom_slot,
                    args=(row_name, slot_index),
                )
        else:
            match_col, skip_col = st.columns([3.35,0.90], gap="small")
        reasons = with_cf_reason(recommendation_explanation(
            with_live_ratings(movie, live_rating),p,st.session_state.adventure,st.session_state.review_priority,
            semantic_similarity=context.get("semantic_similarity"),
            availability_score=context.get("availability_alignment",0.5),
            components=context,
        ), payload)
        pill_labels = dict(st.session_state.get("showroom_pill_labels") or {})
        row_taken = {label for key, label in pill_labels.items()
                     if key.startswith(f"{row_name}::") and key != slot_key and label}
        pill_text, pill_label = match_pill(match, reasons, taken=row_taken, head=fit_head(payload, match),
                                           limit=19 if undo_title else None)
        pill_labels[slot_key] = pill_label
        st.session_state.showroom_pill_labels = pill_labels
        with match_col:
            with st.popover(pill_text, use_container_width=True):
                st.markdown(
                    f'<div class="match-score"><span class="match-score-value">{fit_head(payload, match)}</span>'
                    f'<span class="match-score-label">for you · {html.escape(fit_label(payload, match))}</span></div>'
                    + (f'<div class="match-rank-note">Ranks in your top {int(payload["fit_top_pct"])}% of '
                       f'{int(payload.get("fit_pool") or 0):,} movies iCinema scored for you.</div>'
                       if isinstance(payload.get("fit_top_pct"), (int, float)) else "") +
                    '<div class="match-explain-title">Why this matches you</div>',
                    unsafe_allow_html=True,
                )
                for reason in reasons:
                    st.markdown(
                        f'<div class="match-reason">'
                        f'<div class="match-reason-label">{html.escape(reason["label"])}</div>'
                        f'<div class="match-reason-copy">{html.escape(reason["text"])}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    '<div class="match-model-note">Top signals ranked from this movie’s personalized model score.</div>',
                    unsafe_allow_html=True,
                )
                st.button(
                    "Not for me",
                    key=f"dislike_{row_name}_{slot_index}_{title}",
                    help="Hide this movie and show fewer like it. Undo brings it back.",
                    on_click=dislike_showroom_slot,
                    args=(row_name, slot_index),
                )
        with skip_col:
            st.button(
                "Skip",
                key=f"skip_{row_name}_{slot_index}_{title}",
                use_container_width=True,
                on_click=skip_showroom_slot,
                args=(row_name, slot_index),
            )

    display_movie = dict(movie)
    if identity.get("display_title"):
        display_movie["title"] = identity["display_title"]
    if identity.get("year"):
        display_movie["year"] = identity["year"]
    movie_thumb(display_movie, identity.get("poster_url") or movie.get("poster_url"))

    rating_parts = ratings_text(card_ratings(movie, live_rating))
    rating_class = "ratings" if rating_parts else "ratings muted"
    rating_text = " · ".join(rating_parts) or "Ratings unavailable"
    st.markdown(f'<div class="{rating_class}">{rating_text}</div>',unsafe_allow_html=True)

    availability_class = "watch-availability muted" if availability.get("status") in {"unknown", "not_configured", "unavailable"} else "watch-availability"
    watch_html = watch_line_html(availability, movie.get("title", ""), st.session_state.get("streaming_services"))
    st.markdown(f'<div class="{availability_class}">{watch_html}</div>', unsafe_allow_html=True)

    quick_desc = quick_card_description(dict(movie, tagline=identity.get("tagline")), limit=92)
    expanded_desc = expanded_card_description(movie)
    summary_id = f"movie-summary-{row_index}-{slot_index}"
    st.markdown(
        f'<div class="movie-summary-toggle">'
        f'<input class="movie-summary-checkbox" type="checkbox" id="{summary_id}">'
        f'<label class="movie-summary-label" for="{summary_id}">{html.escape(quick_desc)}</label>'
        f'<div class="movie-full-description">'
        f'<div class="movie-synopsis-label">Premise</div>'
        f'<div class="movie-synopsis-copy">{html.escape(expanded_desc)}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    # Persist Skip / Undo during this card-only rerun without creating a visible loader.
    persist_from_fragment()


def render_card_actions(row_name, row_index, slot_index):
    """Save / Seen sit outside the card fragment: a click runs the page once, directly,
    so the Saved / Seen tabs update without a second rerun triggered from a fragment."""
    with st.container(key=f"movie_actions_{row_index}_{slot_index}"):
        a, b = st.columns(2, gap="small")
        with a:
            st.button("Save", key=f"save_{row_name}_{slot_index}", use_container_width=True,
                      on_click=save_showroom_slot, args=(row_name, slot_index))
        with b:
            st.button("Seen", key=f"seen_{row_name}_{slot_index}", use_container_width=True,
                      on_click=seen_showroom_slot, args=(row_name, slot_index))

def _drop_last_event(title, event_type):
    """Remove the most recent event of a type for a title (used by Undo)."""
    events = list(st.session_state.get("analytics_events") or [])
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("event") == event_type and events[i].get("title") == title:
            del events[i]
            break
    st.session_state.analytics_events = events


def undo_skip(title):
    """Reverse an accidental Skip or "Not for me" so it neither hides the movie nor trains the model."""
    if not title:
        return
    disliked = set(st.session_state.get("disliked") or set())
    if title in disliked:
        disliked.discard(title)
        st.session_state.disliked = disliked
        _drop_last_event(title, "dislike")
    else:
        st.session_state.dismissed.discard(title)
        _drop_last_event(title, "skip")
    queue_profile_save()


def undo_showroom_slot(row_name, slot_index):
    slot_key = _showroom_slot_key(row_name, slot_index)
    undo = dict(st.session_state.get("showroom_undo") or {})
    title = undo.pop(slot_key, None)
    st.session_state.showroom_undo = undo
    if not title:
        return
    undo_skip(title)
    slots = dict(st.session_state.get("showroom_slots") or {})
    slots[slot_key] = title
    st.session_state.showroom_slots = slots


def _sync_services_from_picker():
    st.session_state.streaming_services = list(st.session_state.get("tonight_services_picker") or [])
    queue_profile_save()


def tonight_skip(title, movie):
    skip_movie(title, movie)
    st.session_state.tonight_last_skip = title


def tonight_dislike(title, movie):
    dislike_movie(title, movie)
    st.session_state.tonight_last_skip = title


def tonight_undo():
    undo_skip(st.session_state.get("tonight_last_skip"))
    st.session_state.tonight_last_skip = None


def _request_showroom_refresh():
    """Save/Seen change the Saved/Seen tabs and counts, which live outside the card."""
    st.session_state._showroom_refresh = True

def _refresh_if_requested():
    if st.session_state.pop("_showroom_refresh", False):
        st.rerun(scope="app")

def tonight_save(title, movie):
    save_movie(title, movie)
    st.session_state.tonight_last_skip = None
    _mark_showroom_fast()
    _request_showroom_refresh()


def tonight_seen(title, movie):
    mark_movie_seen(title, movie)
    st.session_state.tonight_last_skip = None
    _mark_showroom_fast()
    _request_showroom_refresh()


def _render_services_picker(services):
    label = f"Your services · {len(services)}" if services else "Choose your services"
    if "tonight_services_picker" not in st.session_state:
        st.session_state.tonight_services_picker = list(services)
    with st.container(key="services_picker"), st.popover(label, use_container_width=True):
        st.markdown('<div class="services-help">Pick what you subscribe to. Tonight’s Show updates as you tap.</div>',
                    unsafe_allow_html=True)
        options = list(STREAMING_SERVICES)
        if hasattr(st, "pills"):
            st.pills("Your services", options, selection_mode="multi", key="tonight_services_picker",
                     on_change=_sync_services_from_picker, label_visibility="collapsed")
        else:
            st.multiselect("Your services", options, key="tonight_services_picker",
                           on_change=_sync_services_from_picker, label_visibility="collapsed")


@st.fragment
@_with_app_rerun
def render_tonight_pick_fragment():
    """Compact single best match. Services, Skip, and Undo rerun only this card."""
    _refresh_if_requested()
    services = list(st.session_state.get("streaming_services") or [])
    payloads = st.session_state.get("showroom_payloads") or {}
    watch_cache = st.session_state.get("showroom_watch_cache") or {}
    blocked = (set(st.session_state.saved) | set(st.session_state.seen) | set(st.session_state.dismissed)
               | set(st.session_state.get("disliked") or set())
               | {t for t in (st.session_state.get("showroom_slots") or {}).values() if t})
    in_rows = {t for t in (st.session_state.get("showroom_slots") or {}).values() if t}
    acted = blocked - in_rows
    pool = [t for t in (st.session_state.get("tonight_pool") or []) if t in payloads and t not in blocked]
    fits = []
    if services:
        # Look through up to the top 120 ranked movies for ones on the viewer's services,
        # fetching any missing availability in one cached batch.
        deep = [t for t in (st.session_state.get("tonight_deep_pool") or st.session_state.get("tonight_pool") or [])
                if t in payloads and t not in acted]
        missing = [t for t in deep if t not in watch_cache]
        if missing:
            keys = tuple((t, int((payloads[t].get("movie") or {}).get("year") or 0)) for t in missing)
            try:
                fetched = get_watch_availability_batch(keys, "US") or {}
            except Exception:
                fetched = {}
            watch_cache = {**watch_cache, **fetched}
            st.session_state.showroom_watch_cache = watch_cache
        on_services = [t for t in deep if movie_on_services(watch_cache.get(t), services)]
        # Prefer a match not already shown in a row; a row duplicate beats a wrong pick.
        fits = [t for t in on_services if t not in in_rows] + [t for t in on_services if t in in_rows]
    ordered = fits + [t for t in pool if t not in fits]

    if services:
        shown = ", ".join(services[:2]) + (f" +{len(services) - 2}" if len(services) > 2 else "")
        note = (f"Your single best match right now on {shown}" if fits else
                f"None of your top matches stream on {shown} right now, so here’s your best overall match")
    else:
        note = "Your single best match right now"
    head, picker = st.columns([3.4, 1.1], gap="medium", vertical_alignment="bottom")
    with head:
        st.markdown(
            '<div class="showroom-row-header tonight-row-header">'
            '<div class="showroom-row-title">Tonight’s Show</div>'
            f'<div class="row-model-note">{html.escape(note)}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with picker:
        _render_services_picker(services)

    if not ordered:
        st.caption("No pick available right now. Try adding more services or refreshing.")
        return

    title = ordered[0]
    payload = payloads.get(title) or {}
    movie = payload.get("movie") or {}
    match = int(payload.get("match") or 0)
    p = current_profile()
    identity, availability, live_rating = _showroom_cached_metadata(movie)
    comps = score_movie_components(
        movie, p, st.session_state.adventure, st.session_state.review_priority,
        semantic_similarity=float(payload.get("semantic_similarity", .5)),
        availability_score=service_availability_utility(availability),
    )
    context = {
        "row": "Tonight's Show", "position": 1, "match": int(payload.get("model_match") or match),
        "model_score": round(float(comps.get("raw_score", 0)), 6),
        "decision_utility": round(float(comps.get("decision_utility", comps.get("raw_score", 0))), 6),
        **{k: round(float(comps.get(k, .5)), 6) for k in [
            "genre_affinity", "trait_affinity", "semantic_similarity", "quality_alignment",
            "discovery_alignment", "priority_alignment", "availability_alignment",
            "vote_confidence", "profile_confidence"
        ]},
        "cf_affinity": round(float(payload.get("cf") if payload.get("cf") is not None else 0.5), 6),
        "candidate_source": movie.get("candidate_source"),
        "model_version":"v5.191",
    }
    recommendation_context = dict(st.session_state.get("recommendation_context") or {})
    recommendation_context[title] = context
    st.session_state.recommendation_context = recommendation_context
    record_impressions(st.session_state, {title: context})

    display_title = identity.get("display_title") or movie.get("title", "")
    year = identity.get("year") or movie.get("year") or ""
    genre = movie.get("genre") or ""
    poster_url = identity.get("poster_url") or movie.get("poster_url")
    poster_html = (
        f'<div class="poster has-image"><img src="{html.escape(str(poster_url), quote=True)}" '
        f'alt="Poster for {html.escape(str(display_title))}"></div>'
        if poster_url else '<div class="poster"><div class="poster-placeholder-mark">iCINEMA</div></div>'
    )
    ratings = ratings_text(card_ratings(movie, live_rating))
    meta = " · ".join(str(x) for x in [year, genre] + ratings if x)

    watch_html = watch_line_html(availability, movie.get("title", ""), services)
    options = watch_options(availability, movie.get("title", ""), services, limit=1)
    fit = ""  # the streaming line already lists the viewer's services first

    reasons = with_cf_reason(recommendation_explanation(
        with_live_ratings(movie, live_rating), p, st.session_state.adventure, st.session_state.review_priority,
        semantic_similarity=context.get("semantic_similarity"),
        availability_score=context.get("availability_alignment", 0.5),
        components=context,
    ), payload, limit=2)
    why_html = "".join(f'<div class="tonight-why"><strong>{html.escape(r["label"])}</strong> · {html.escape(r["text"])}</div>'
                       for r in reasons)

    tonight_badge = (f"Best on your services · {fit_head(payload, match)} overall" if services
                     else f"{fit_head(payload, match)} for you")
    with st.container(key=f"tonight_hero_{title}"):
        poster_col, info_col = st.columns([1, 6.2], gap="medium")
        with poster_col:
            st.markdown(poster_html, unsafe_allow_html=True)
        with info_col:
            st.markdown(
                '<div class="tonight-stack">'
                f'<div class="tonight-title">{html.escape(str(display_title))}</div>'
                f'<div class="tonight-meta">{html.escape(meta)}</div>'
                f'<div class="tonight-badges"><span class="tonight-match">{tonight_badge}</span>{fit}</div>'
                f'<div class="tonight-line">{watch_html}</div>'
                f'<div class="tonight-hook">{html.escape(tonight_description(dict(movie, tagline=identity.get("tagline")), limit=160))}</div>'
                f'<div class="tonight-whys">{why_html}</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            last_skip = st.session_state.get("tonight_last_skip")
            with st.container(key=f"tonight_actions_{title}"):
                # Save · Seen · Skip · thumbs-down, then Undo when there is something to undo.
                cols = st.columns([1, 1, 1, 0.42, 1, 1.78], gap="small")
                with cols[0]:
                    st.button("Save", key=f"tonight_save_{title}", use_container_width=True,
                              on_click=tonight_save, args=(title, movie))
                with cols[1]:
                    st.button("Seen", key=f"tonight_seen_{title}", use_container_width=True,
                              on_click=tonight_seen, args=(title, movie))
                with cols[2]:
                    st.button("Skip", key=f"tonight_skip_{title}", use_container_width=True,
                              on_click=tonight_skip, args=(title, movie))
                with cols[3]:
                    st.button("Not for me", key=f"tonight_dislike_{title}",
                              help="Not for me: hide this movie and show fewer like it.",
                              on_click=tonight_dislike, args=(title, movie))
                with cols[4]:
                    if last_skip:
                        st.button("↶ Undo", key=f"tonight_undo_{title}", use_container_width=True,
                                  help=f"Bring back {last_skip}", on_click=tonight_undo)
    persist_from_fragment()


def render_showroom_fragment(p):
    # Not a fragment: nesting card fragments inside a Showroom fragment let Streamlit
    # briefly draw the tabs twice after an app rerun.
    ensure_session(st.session_state)
    tabs = st.tabs(["Showroom", "Saved", "Seen", "Profile"])  # tabs8: fixed labels keep the open tab

    # Save / Seen reuse the current ranking: the page reruns so the Saved / Seen tabs
    # update, but the heavy rebuild (candidate fetch, scoring ~700 movies, ranking every
    # row) is skipped. The next navigation or visit re-ranks with the new feedback.
    fast = st.session_state.pop("_showroom_fast", False) and bool(st.session_state.get("showroom_slots"))
    if fast:
        row_choices = {}
        for key in (st.session_state.get("showroom_slots") or {}):
            row, _, idx = key.rpartition("::")
            row_choices.setdefault(row, [])
            while len(row_choices[row]) <= int(idx):
                row_choices[row].append(None)
    else:
        excluded=st.session_state.saved|st.session_state.seen|st.session_state.dismissed|set(st.session_state.get("disliked") or set())

        # Build a deep candidate pool, then rank every candidate with the same iCinema
        # personalization algorithm. TMDB discovery acts only as replenishment: it does not
        # bypass the user's profile, and excluded Save/Seen/Skip titles stay excluded.
        # Rotate deeper into TMDB as a user skips more titles, so the showroom keeps
        # replenishing instead of exhausting one fixed discovery slice.
        # Each return visit starts a little deeper, so the candidate pool keeps changing.
        _events = st.session_state.get("analytics_events") or []
        _current = st.session_state.get("showroom_session_id")
        past_visits = len({e.get("session_id") for e in _events if e.get("event") == "impression"
                           and e.get("session_id") and e.get("session_id") != _current})
        discovery_start_page = 1 + (len(st.session_state.dismissed) // 80) * 8 + (past_visits % 12) * 2
        focus_genres = tuple((p.get("genres") or [])[:2])
        external_pool = []
        if tmdb_catalog_configured():
            try:
                external_pool = discover_movies(640, discovery_start_page, focus_genres=focus_genres)
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
        learning_result=learning_model_for(st.session_state.get("analytics_events", []))
        ranked_movies=[movie for _,movie in ranked]
        semantic_by_id=cached_semantic_scores(ranked_movies,p)
        cf_user=user_vector(_cf_signals())
        cf_by_title={}
        model_match_by_title={}

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
                votes=_safe_num(movie.get("tmdb_vote_count"), -1.0)
                if votes>=0:
                    import math
                    # ~25k votes (a blockbuster) scores near 0; a few hundred scores high.
                    obscurity=0.5*obscurity+0.5*max(0.0,1.0-math.log10(votes+1.0)/4.5)
                return max(0.0,min(1.0,0.40*genre_novelty+0.18*language_novelty+0.10*era_novelty+0.32*obscurity))

            return 1.0

        base_memo={}
        fatigue=impression_fatigue()

        def _row_candidates(row_name, already_used):
            available=[item for item in ranked if item[1]["title"] not in already_used]
            scored=[]
            for display_match,movie in available:
                memo=base_memo.get(id(movie))
                if memo is not None:
                    # Same personalized score in every row; only the row objective differs.
                    base,display_match=memo
                else:
                    components=score_movie_components(movie,p,st.session_state.adventure,st.session_state.review_priority,semantic_similarity=semantic_by_id.get(id(movie),0.5))
                    base=components["raw_score"]
                    # Supervised features stay exactly as logged at training time (pre-CF),
                    # so the Save/Skip model never sees train/serve skew.
                    model_match_by_title[movie["title"]]=display_match
                    ml_context=dict(components)
                    ml_context.update({"model_score":base,"decision_utility":components.get("decision_utility",base),"match":display_match,"position":2})
                    cf=cf_affinity(movie,cf_user)
                    ml_context["cf_affinity"]=cf if cf is not None else 0.5
                    if cf is not None:
                        base=0.65*base+0.35*cf
                        cf_by_title[movie["title"]]=cf
                    learned_probability=predict_success(learning_result,ml_context)
                    if learned_probability is not None:
                        base=0.78*base+0.22*learned_probability
                    # The % shown to users reflects the final blended ranking score.
                    display_match=_calibrated_match_percent(base,p)
                    base_memo[id(movie)]=(base,display_match)
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
                # Freshness for returning viewers: discount ignored repeats, lightly vary near-ties.
                objective-=FATIGUE_STEP*min(fatigue.get(movie["title"],0),FATIGUE_CAP)
                objective+=VARIETY_SPREAD*visit_variety(movie["title"])
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
        row_candidate_queues={name: [] for name in row_order}

        # Tonight's Pick: the single best personalized match, preferring the viewer's
        # own streaming services and falling back to any service when none are chosen.
        top_all=_row_candidates("Top Matches for You",set())
        tonight_pool=top_all[:40]
        tonight_watch=get_watch_availability_batch(
            tuple((m["title"],int(m.get("year") or 0)) for _,m in tonight_pool),"US"
        ) if tonight_pool else {}
        my_services=list(st.session_state.get("streaming_services") or [])
        fits=[item for item in tonight_pool if movie_on_services(tonight_watch.get(item[1]["title"]),my_services)]
        fit_titles={m["title"] for _,m in fits}
        tonight_queue=fits+[item for item in tonight_pool if item[1]["title"] not in fit_titles]
        reserved={tonight_queue[0][1]["title"]} if tonight_queue else set()

        # Pass 1: category-specific ordering with strict cross-row de-duplication.
        # Keep the remaining ranked candidates as a replacement queue so one card can
        # advance without rebuilding the entire Showroom.
        for row_name in row_order:
            if row_name=="Top Matches for You":
                ordered=[item for item in top_all if item[1]["title"] not in reserved]
            else:
                ordered=_row_candidates(row_name,reserved)
            picks=ordered[:4]
            row_choices[row_name].extend(picks)
            row_candidate_queues[row_name].extend(ordered)
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
        visible_titles={movie["title"] for movie in visible_movies}
        warm_backups=[]
        for row_name in row_order:
            for _,candidate in row_candidate_queues.get(row_name,[]):
                if candidate["title"] not in visible_titles:
                    warm_backups.append(candidate)
                    break
        metadata_movies=visible_movies+warm_backups
        # Deduplicate while preserving the ranked order.
        metadata_movies=list({m["title"]:m for m in metadata_movies}.values())
        visible_movie_keys=tuple((movie["title"], int(movie.get("year") or 0)) for movie in metadata_movies)
        visible_identity_keys=tuple((movie["title"], int(movie.get("year") or 0), int(movie.get("tmdb_id") or 0)) for movie in metadata_movies)
        watch_by_title=get_watch_availability_batch(visible_movie_keys,"US")
        for row_name in row_order:
            row_choices[row_name].sort(key=lambda item:0.91*(item[0]/100.0)+0.09*service_availability_utility(watch_by_title.get(item[1]["title"])),reverse=True)

        recommendation_context={}
        for row_name in row_order:
            for position,(match,movie) in enumerate(row_choices.get(row_name,[]),start=1):
                availability_value=service_availability_utility(watch_by_title.get(movie["title"]))
                comps=score_movie_components(
                    movie,p,st.session_state.adventure,st.session_state.review_priority,
                    semantic_similarity=semantic_by_id.get(id(movie),0.5),
                    availability_score=availability_value,
                )
                recommendation_context[movie["title"]]={
                    "row":row_name,"position":position,"match":model_match_by_title.get(movie["title"],match),
                    "model_score":round(float(comps.get("raw_score",0)),6),
                    "decision_utility":round(float(comps.get("decision_utility",comps.get("raw_score",0))),6),
                    **{k:round(float(comps.get(k,.5)),6) for k in ["genre_affinity","trait_affinity","semantic_similarity","quality_alignment","discovery_alignment","priority_alignment","availability_alignment","vote_confidence","profile_confidence"]},
                    "cf_affinity":round(float(cf_by_title.get(movie["title"],0.5)),6),
                    "candidate_source":movie.get("candidate_source"),
                    "model_version":"v5.191",
                }
        st.session_state.recommendation_context=recommendation_context
        record_impressions(st.session_state,recommendation_context)
        identity_by_title=get_movie_identity_batch(visible_identity_keys)
        showroom_poster_map={title: data.get("poster_url") for title, data in identity_by_title.items()}
        live_rating_keys=tuple((movie["title"], int(movie.get("year") or 0), (identity_by_title.get(movie["title"], {}) or {}).get("imdb_id") or "") for movie in metadata_movies)
        live_ratings_by_title=get_live_ratings_batch(live_rating_keys)

        # Persist the ranked queues and current slots. Card fragments use these to
        # replace exactly one movie without rerunning the four-row Showroom.
        payloads={}
        queues={}
        for row_name in row_order:
            queue_titles=[]
            for match,movie in row_candidate_queues.get(row_name,[])[:40]:
                title=movie["title"]
                queue_titles.append(title)
                payloads.setdefault(title,{
                    "match":match,
                    "movie":movie,
                    "semantic_similarity":semantic_by_id.get(id(movie),.5),
                    "cf":cf_by_title.get(movie["title"]),
                    "model_match":model_match_by_title.get(movie["title"],match),
                })
            queues[row_name]=queue_titles
        slots={}
        for row_name in row_order:
            for slot_index,(match,movie) in enumerate(row_choices.get(row_name,[])):
                title=movie["title"]
                slots[_showroom_slot_key(row_name,slot_index)]=title
                payloads.setdefault(title,{
                    "match":match,
                    "movie":movie,
                    "semantic_similarity":semantic_by_id.get(id(movie),.5),
                    "cf":cf_by_title.get(movie["title"]),
                    "model_match":model_match_by_title.get(movie["title"],match),
                })
        st.session_state.tonight_pool=[m["title"] for _,m in tonight_queue]
        # Deeper ranked list so a service filter (e.g. Netflix only) can reach past the top 40.
        deep=top_all[:120]
        st.session_state.tonight_deep_pool=[m["title"] for _,m in deep]
        for match,movie in deep:
            payloads.setdefault(movie["title"],{
                "match":match,
                "movie":movie,
                "semantic_similarity":semantic_by_id.get(id(movie),.5),
                "cf":cf_by_title.get(movie["title"]),
                "model_match":model_match_by_title.get(movie["title"],match),
            })
        st.session_state.showroom_undo={}
        st.session_state.showroom_pill_labels={}
        if tonight_queue:
            for match,movie in tonight_queue:
                payloads.setdefault(movie["title"],{
                    "match":match,
                    "movie":movie,
                    "semantic_similarity":semantic_by_id.get(id(movie),.5),
                    "cf":cf_by_title.get(movie["title"]),
                    "model_match":model_match_by_title.get(movie["title"],match),
                })
        # Rank every scored movie by its final blended score, so "Top N%" is exact.
        _bases = sorted((b for b, _ in base_memo.values()), reverse=True)
        _pool = len(_bases)
        if _pool:
            import bisect
            _asc = sorted(_bases)
            for _pl in payloads.values():
                _memo = base_memo.get(id(_pl.get("movie")))
                if _memo is None:
                    continue
                _above = _pool - bisect.bisect_right(_asc, _memo[0])   # movies scored strictly higher
                _pl["fit_top_pct"] = max(1, -(-100 * (_above + 1) // _pool))
                _pl["fit_pool"] = _pool
        st.session_state.showroom_payloads=payloads
        st.session_state.showroom_row_queues=queues
        st.session_state.showroom_slots=slots
        identity_cache=dict(st.session_state.get("showroom_identity_cache") or {})
        identity_cache.update(identity_by_title)
        st.session_state.showroom_identity_cache=identity_cache
        watch_cache=dict(st.session_state.get("showroom_watch_cache") or {})
        watch_cache.update(tonight_watch)
        watch_cache.update(watch_by_title)
        st.session_state.showroom_watch_cache=watch_cache
        rating_cache=dict(st.session_state.get("showroom_rating_cache") or {})
        rating_cache.update(live_ratings_by_title)
        st.session_state.showroom_rating_cache=rating_cache

    row_specs=["Top Matches for You","Critically Acclaimed","Hidden Gems","Something Different"]

    with tabs[0]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        render_tonight_pick_fragment()
        for row_index,row_name in enumerate(row_specs):
            choices=row_choices.get(row_name,[])
            row_class = "showroom-row first" if row_index == 0 else "showroom-row"
            row_notes={
                "Top Matches for You":"Best overall fits based on your full preference profile",
                "Critically Acclaimed":"Highly rated films that still fit what you like",
                "Hidden Gems":"Strong matches that are less obvious or widely promoted",
                "Something Different":"A little outside your usual picks, but still likely to click",
            }
            st.markdown(
                f'<div class="{row_class} showroom-row-header">'
                f'<div class="showroom-row-title">{row_name}</div>'
                f'<div class="row-model-note">{row_notes[row_name]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if not choices:
                st.caption("Refreshing personalized matches…")
                continue
            cols=st.columns(len(choices))
            for i,_ in enumerate(choices):
                with cols[i]:
                    render_showroom_card_fragment(row_name,row_index,i)
                    render_card_actions(row_name,row_index,i)
        rating_note = "" if omdb_configured() else " IMDb and Rotten Tomatoes ratings require OMDB_API_KEY in Streamlit Secrets."
        st.markdown(
            '<div class="watch-attribution">Streaming availability for the United States. Data by JustWatch via TMDB. '
            'IMDb and Rotten Tomatoes ratings are retrieved through OMDb and cached for 14 days. '
            'This product uses the TMDB API but is not endorsed or certified by TMDB.' + rating_note + '</div>',
            unsafe_allow_html=True
        )

    with tabs[1]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        st.markdown('<div class=\"tab-primary-heading saved-tab-heading\">Saved</div>', unsafe_allow_html=True)
        movies=[m for t in st.session_state.saved if (m := resolve_history_movie(t))]
        saved_identity_keys=tuple((m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in movies)
        saved_identity_map = get_movie_identity_batch(saved_identity_keys)
        saved_poster_map = get_poster_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies))
        saved_watch_map = get_watch_availability_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies), "US") if movies else {}
        saved_live_map = get_live_ratings_batch(tuple((m["title"], int(m.get("year") or 0),
                                                      (saved_identity_map.get(m["title"], {}) or {}).get("imdb_id") or "")
                                                     for m in movies)) if movies else {}
        if not movies:st.caption("Nothing saved yet.")
        else:
            cols=st.columns(4, gap="medium")
            for i,m in enumerate(movies):
                with cols[i % 4]:
                    with st.container(key=f"savedcard_{i}"):
                        identity = saved_identity_map.get(m["title"], {}) or {}
                        display_movie = dict(m)
                        if identity.get("display_title"):
                            display_movie["title"] = identity["display_title"]
                        if identity.get("year"):
                            display_movie["year"] = identity["year"]
                        movie_thumb(display_movie, identity.get("poster_url") or m.get("poster_url") or saved_poster_map.get(m["title"]), compact=True, library_mode="saved")
                        st.markdown(library_ratings_html(m, identity, saved_live_map), unsafe_allow_html=True)
                        st.markdown(f'<div class="watch-availability saved-watch">{watch_line_html(saved_watch_map.get(m["title"]), m["title"], st.session_state.get("streaming_services"))}</div>', unsafe_allow_html=True)
                        saved_actions = st.columns(2, gap="small")
                        with saved_actions[0]:
                            st.button("Mark Seen", key=f"savedseen_{m['title']}", use_container_width=True,
                                      on_click=mark_movie_seen, args=(m["title"], m))
                        with saved_actions[1]:
                            st.button("Remove", key=f"unsave_{m['title']}", use_container_width=True,
                                      on_click=remove_saved_movie, args=(m["title"],))

    with tabs[2]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        st.markdown('<div class=\"tab-primary-heading\">Seen</div>', unsafe_allow_html=True)
        movies=[m for t in st.session_state.seen if (m := resolve_history_movie(t))]
        seen_identity_keys=tuple((m["title"], int(m.get("year") or 0), int(m.get("tmdb_id") or 0)) for m in movies)
        seen_identity_map = get_movie_identity_batch(seen_identity_keys)
        seen_poster_map = get_poster_batch(tuple((m["title"], int(m.get("year") or 0)) for m in movies))
        seen_live_map = get_live_ratings_batch(tuple((m["title"], int(m.get("year") or 0),
                                                     (seen_identity_map.get(m["title"], {}) or {}).get("imdb_id") or "")
                                                    for m in movies)) if movies else {}
        if not movies:st.caption("Nothing marked as seen yet.")
        else:
            # What's next: one personalized follow-up per Seen movie, never the same pick
            # twice on this tab, never something already saved, seen, skipped or disliked.
            wn_payloads = st.session_state.get("showroom_payloads") or {}
            wn_blocked = (set(st.session_state.saved) | set(st.session_state.seen)
                          | set(st.session_state.dismissed) | set(st.session_state.get("disliked") or set()))
            wn_offsets = st.session_state.get("whats_next_offset") or {}
            wn_taken, wn_picks = set(), {}
            for m in movies:
                ranked = [(t, cf) for t, cf in whats_next_ranking(m, wn_payloads, wn_blocked) if t not in wn_taken]
                if ranked:
                    pick = ranked[int(wn_offsets.get(m["title"], 0)) % len(ranked)]
                    wn_picks[m["title"]] = pick
                    wn_taken.add(pick[0])
            wn_identity = st.session_state.get("showroom_identity_cache") or {}
            cols=st.columns(4, gap="medium")
            for i,m in enumerate(movies):
                with cols[i % 4]:
                    with st.container(key=f"seencard_{i}"):
                        identity = seen_identity_map.get(m["title"], {}) or {}
                        display_movie = dict(m)
                        if identity.get("display_title"):
                            display_movie["title"] = identity["display_title"]
                        if identity.get("year"):
                            display_movie["year"] = identity["year"]
                        movie_thumb(display_movie, identity.get("poster_url") or m.get("poster_url") or seen_poster_map.get(m["title"]), compact=True, library_mode="seen")
                        st.markdown(library_ratings_html(m, identity, seen_live_map), unsafe_allow_html=True)
                        # Hover × in the poster's top-right corner: remove an accidental Seen.
                        st.button("✕", key=f"unseen_{m['title']}", help="Remove from Seen",
                                  on_click=remove_from_seen, args=(m["title"],))
                        pick = wn_picks.get(m["title"])
                        if pick:
                            nt, used_cf = pick
                            npay = wn_payloads.get(nt) or {}
                            nmovie = npay.get("movie") or {}
                            nid = wn_identity.get(nt) or {}
                            nposter = nid.get("poster_url") or nmovie.get("poster_url")
                            ntitle = nid.get("display_title") or nmovie.get("title") or nt
                            nyear = nid.get("year") or nmovie.get("year") or ""
                            why = (f"Viewers who loved “{m['title']}” tend to love this too."
                                   if used_cf else f"Shares the genre and tone of “{m['title']}”.")
                            with st.container(key=f"whatsnext_{i}"):
                                with st.popover("What’s next", use_container_width=True):
                                    img = (f'<img src="{html.escape(str(nposter), quote=True)}" alt="">'
                                           if nposter else '<div class="whatsnext-noimg">iCINEMA</div>')
                                    st.markdown(
                                        f'<div class="whatsnext-kicker">Watch next after “{html.escape(m["title"])}”</div>'
                                        f'<div class="whatsnext-pick"><div class="whatsnext-poster">{img}</div>'
                                        f'<div class="whatsnext-info">'
                                        f'<div class="whatsnext-title">{html.escape(str(ntitle))}</div>'
                                        f'<div class="whatsnext-meta">{html.escape(" · ".join(str(x) for x in [nyear, nmovie.get("genre")] if x))}'
                                        f' · {fit_head(npay, npay.get("match"))} for you</div>'
                                        f'<div class="whatsnext-why">{html.escape(why)} It also fits your taste profile.</div>'
                                        f'</div></div>',
                                        unsafe_allow_html=True,
                                    )
                                    # Compact pills, about the poster's width, aligned under the poster.
                                    a, b, _ = st.columns([1, 1.35, 4.2], gap="small")
                                    with a:
                                        st.button("Save", key=f"whatsnext_save_{i}_{nt}", use_container_width=True,
                                                  on_click=save_movie, args=(nt, nmovie))
                                    with b:
                                        st.button("Another pick", key=f"whatsnext_more_{i}_{nt}", use_container_width=True,
                                                  on_click=whats_next_another, args=(m["title"],))

    with tabs[3]:
        st.markdown('<div class="showroom-tab-start"></div>', unsafe_allow_html=True)
        render_live_profile()
        st.markdown('<div class="profile-tab-reset"></div>', unsafe_allow_html=True)
        edit, reset, _ = st.columns([1.5, 1.2, 4], gap="small")
        with edit:
            # Revisit Steps 1-3 with every choice filled in; the models use the new answers on return.
            st.button("Edit my preferences", key="edit_preferences", use_container_width=True, on_click=go, args=("shelf",))
        with reset:
            if st.button("Reset Profile", key="reset_profile_tab", use_container_width=True):
                reset_profile_state()
                st.rerun(scope="app")


    # tabs8: counts beside the fixed tab labels (labels never change, so the open tab stays).
    st.markdown(
        '<style>div[data-testid="stTabs"] button[role="tab"]:nth-of-type(2) p::after{content:" (%d)"}'
        'div[data-testid="stTabs"] button[role="tab"]:nth-of-type(3) p::after{content:" (%d)"}</style>'
        % (len(st.session_state.saved), len(st.session_state.seen)),
        unsafe_allow_html=True,
    )

    pass  # saved once at the end of the full run

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

    _off = load_offline_results() or {}
    _lift = (_off.get("lifts_three_likes_vs_popularity") or {}).get("hit@1")
    _fans = training_scale()["users"]
    if isinstance(_lift, (int, float)):
        st.markdown(
            '<div class="adapt-note proof-note">'
            f'<div class="proof-big">+{int(_lift)}%</div>'
            '<div><strong>Good picks from your first 3 likes. Yours over time.</strong>'
            f'<span>A model trained on {_fans} movie fans finds a first pick you’ll love {int(_lift)}% more often than '
            'just recommending what’s popular. A second model reads every film’s plot and tone, and a third learns from your saves and skips.</span></div>'
            '</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="adapt-note"><strong>Good picks on day one. Yours over time.</strong><br><span>Two models are ready the moment you finish setup. A third learns from your saves and skips, so every return visit gets you to pressing play faster.</span></div>',unsafe_allow_html=True)
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

    with st.container(key="nav_row_profile"):
        back, cont, _ = st.columns([1, 2, 4], gap="small")
        with back:
            st.button("← Back", key="back_profile", use_container_width=True, on_click=go, args=("more",))
        with cont:
            st.button("Enter My Showroom →", type="primary", key="enter_showroom", use_container_width=True, on_click=go, args=("showroom",))

elif screen=="showroom":
    logo()
    p=current_profile()
    st.markdown(
        '<div class="showroom-header">'
        '<div class="showroom-heading">Your Showroom of Movies</div>'
        '<div class="showroom-intro">Picked for you and refined with every save, skip, and title you mark</div>'
        '</div>',
        unsafe_allow_html=True
    )

    render_showroom_fragment(p)

# Persist the latest profile/history after the page has processed this run.
persist_profile_if_needed()
st.session_state._in_full_run = False

# V5.90 is implemented through CSS overrides injected above in the main style block.

# V5.99 tab content alignment polish injected via CSS override.

