"""The page between onboarding and the Showroom: what iCinema starts from, in three short cards.

The app passes in the few app-level helpers this page needs (ctx), the same pattern as src/ui/shows.py.
"""
import html

import streamlit as st

from src.model_names import MODELS_TOTAL
from src.recommender import get_movie
from src.tmdb_catalog import get_poster_batch


def _plain_list(items, limit=3):
    """“A, B and C”, or “A, B, C + 2 more” past the limit."""
    items = [str(x) for x in items if x]
    if len(items) > limit:
        return ", ".join(items[:limit]) + f" + {len(items) - limit} more"
    return items[0] if len(items) == 1 else (" and ".join([", ".join(items[:-1]), items[-1]]) if items else "")


def _ready_models(ctx):
    """The models that are actually running for this viewer right now: (name, technique, five-word job)."""
    from src import cf_model as _cfm
    from src import ltr as _ltr_mod
    from src import seq_model as _seqm
    from src.new_releases import available as _nr_on
    from src.tv import available as _tv_on
    sig = ctx["signals"]()
    full_m, _ = _cfm._history_cut()
    rk = _cfm._ranker_for(sig) if sig else None
    fans_tech = ("EASE" if full_m is not None and rk is full_m else
                 "RP3beta" if rk is not None and rk is _cfm._load_rank() and rk is not _cfm._load() else "item-kNN")
    out = []
    if _ltr_mod.available():
        out.append(("Best-of-all ranker", "gradient boosting", "Weighs every model for you"))
        out.append(("Fans like you", "item-kNN · RP3beta · EASE", "Three models find similar fans"))
    else:
        out.append(("Fans like you", fans_tech, "People who loved your picks"))
    if _seqm.main_available() and sig:
        out.append(("What you liked last", "Markov chain", "What fans watched right after"))
    out.append(("What each movie is like", "TF-IDF + SVD", "Matches genres and fan tags"))
    if _nr_on():
        out.append(("New releases", "ridge regression", "Places new films by filmmakers"))
    if _tv_on():
        out.append(("Shows", "item-kNN + popularity", "Shows loved by your fans"))
    learned = ctx["learning_model_for"](st.session_state.get("analytics_events") or [])
    if getattr(learned, "ready", False):
        out.append(("Your own choices", str(learned.model_name).lower(), "Learns from your saves, skips"))
    from src.model_names import odds_model_on
    if odds_model_on():
        out.append(("Your odds", "isotonic calibration", "Turns each score into odds"))
    return out


def _models_running(models):
    """How many of the 11 models are on: the fan row holds three when the ranker runs."""
    return sum(3 if tech == "item-kNN · RP3beta · EASE" else 1 for _nm, tech, _job in models)


def render_ready_summary(ctx):
    """The page between onboarding and the Showroom: what iCinema starts from, in three cards.
    Starting from: your movies as posters. Your answers: genres, reviews, discovery and more-of, as one short spec.
    How picks are made: only the models running for you now. The in-depth version stays in the Profile tab."""
    ss = st.session_state
    liked = [t for t in (ss.get("selection_order") or []) if t in ss.likes] + sorted(set(ss.likes) - set(ss.get("selection_order") or []))
    # Starting from: up to four posters of the movies you picked, then the count.
    movies = [m for m in (get_movie(t, ss.external_movies) for t in liked[:4]) if m]
    need = tuple((m["title"], int(m.get("year") or 0)) for m in movies if not m.get("poster_url"))
    posters = get_poster_batch(need) if need else {}
    imgs = [u for u in (m.get("poster_url") or posters.get(m["title"]) for m in movies) if str(u or "").startswith("https://")]
    stack = "".join(f'<img src="{html.escape(u, quote=True)}" alt="">' for u in imgs)
    n = len(liked)
    count_note = f"{n} movie{'s' if n != 1 else ''} you like"
    # Your answers: every genre you chose (in the order picked), then the other three answers.
    genres = list(ss.get("genres") or [])
    genre_text = _plain_list(genres, 5) or "Every genre"
    rp, adv = int(ss.get("review_priority") or 50), int(ss.get("adventure") or 50)
    # Same words as the Step 2 buttons, so the answer reads back exactly as it was given.
    reviews = ("Great reviews" if rp < 24 else "Lean great reviews" if rp < 41 else "Balanced" if rp <= 59
               else "Lean easy to enjoy" if rp <= 76 else "Easy to enjoy")
    discovery = ("Familiar" if adv < 24 else "Mostly familiar" if adv < 41 else "Balanced" if adv <= 59
                 else "More new" if adv <= 76 else "Surprise me")
    more = list(ss.get("more_of") or [])
    spec = [("Genres", genre_text), ("Priority", reviews), ("Adventure", discovery), ("More of", _plain_list(more, 3) or "Nothing extra")]
    spec_html = "".join(f'<div class="ready-spec-row"><span>{html.escape(k)}</span><span>{html.escape(v)}</span></div>' for k, v in spec)
    # How picks are made: only the models running now, each with its technique and a five-word job.
    models = _ready_models(ctx)
    models_html = "".join(
        f'<div class="ready-model" title="{html.escape(tech)}"><span class="pf-dot on"></span>'
        f'<span class="ready-model-name">{html.escape(nm)}</span>'
        f'<span class="ready-model-job">{html.escape(job)}</span></div>' for nm, tech, job in models)
    st.markdown(
        '<div class="page-top-heading">Your Showroom is ready</div>'
        '<div class="page-top-subtitle">What iCinema starts from. Change anything later in Profile.</div>'
        '<div class="ready-grid">'
        '<div class="ready-card"><div class="ready-kicker">Starting from</div>'
        + (f'<div class="ready-posters">{stack}</div>' if stack else "")
        + f'<div class="ready-value">{html.escape(count_note)}</div></div>'
        '<div class="ready-card"><div class="ready-kicker">Your answers</div>'
        f'<div class="ready-spec">{spec_html}</div></div>'
        f'<div class="ready-card"><div class="ready-kicker">{_models_running(models)} of {MODELS_TOTAL} models running</div>'
        f'<div class="ready-models">{models_html}</div>'
        '</div>'
        '</div>', unsafe_allow_html=True)
