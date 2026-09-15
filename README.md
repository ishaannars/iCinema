# iCinema

**A personalized movie discovery app that learns what you like and helps you find what to watch next.**

[Live App](https://icinema.streamlit.app) · Built with Python, Streamlit, TMDB, and OMDb

## Overview

iCinema was built around a simple problem: finding something to watch often takes longer than it should. Instead of making users scroll through a generic catalog, iCinema builds a lightweight taste profile and continually reshapes recommendations around their choices.

Users begin by rating movies they already know, choose the genres and discovery preferences that matter to them, and then enter a personalized Showroom with four recommendation lanes: **Top Matches, Critically Acclaimed, Hidden Gems, and Something Different**.

The app also supports full movie search, real posters, current ratings, streaming availability, and ongoing feedback through Save, Seen, and Skip actions.

## Personalization

iCinema uses an explainable, feature-based recommendation model built around weighted behavioral data rather than a black-box score. Each movie is represented through genre, descriptive traits, quality signals, release context, and recommendation-category metadata. User actions are projected into the same feature space to build an evolving preference vector.

- **Like:** `+1.0` preference weight
- **Favorite:** `+3.0` weight, making it three times stronger than a Like
- **Selected genre:** `+4.0` prior weight
- **Save:** `+2.5` behavioral weight
- **Seen:** `+0.5` weak history signal because exposure does not necessarily mean preference
- **Skip:** `-2.5` negative signal across matching genres and traits

Saved, Seen, and Skipped titles are stored in browser local storage. When a returning user opens iCinema, that history is restored and re-enters the model immediately, so persistence affects ranking rather than only restoring the interface.

Every onboarding control and later interaction is connected to the ranking model. Likes, Favorites, Saved, Seen, and Skip actions update signed genre and semantic-trait vectors; selected genres act as strong priors; the review-versus-enjoyment prompt controls the blend of critic and audience evidence; the familiarity prompt controls genre, language, popularity, and era novelty; and every Step 3 card contributes directly to a priority-alignment feature.

Each recommendation is scored from an inspectable five-part decomposition: **22% genre affinity, 20% semantic-trait affinity, 23% quality alignment, 17% discovery alignment, and 18% Step 3 priority alignment**. Content affinity uses signed cosine similarity so negative Skip evidence can actively lower similar titles. Quality uses Rotten Tomatoes, IMDb, and TMDB vote data with vote-count confidence shrinkage. TMDB overviews are converted locally into a small semantic-trait feature set, adding descriptive signal without another API call.

The four Showroom lanes use the same underlying score, then apply lane-specific candidate ordering and de-duplication. A deeper TMDB candidate pool replenishes each lane after Save, Seen, or Skip actions so the interface can continue serving algorithmically ranked movies without exhausting the original catalog.

## Product Features

- **Full movie search** through TMDB, including titles outside the original local catalog
- **Personalized Cinema Profile** generated from explicit preferences and ongoing interactions
- **Four distinct recommendation lanes** with continuous replenishment
- **Real movie posters** with full-poster fitting and graceful fallbacks
- **IMDb and Rotten Tomatoes ratings** retrieved through OMDb and cached for 14 days
- **Streaming, rental, and purchase availability** through TMDB watch-provider data powered by JustWatch
- **Saved and Seen libraries** that update recommendation eligibility immediately
- **Browser-local profile persistence** so completed users return directly to their Showroom with preferences and history intact on the same browser
- **Responsive Streamlit interface** designed as a focused consumer product rather than a dashboard

## Technical Approach

**Frontend / app layer:** Streamlit  
**Language:** Python  
**Movie search, metadata, posters, discovery:** TMDB API  
**Watch-provider availability:** TMDB / JustWatch  
**IMDb + Rotten Tomatoes ratings:** OMDb API  
**Caching:** Streamlit resource/data caching with a 14-day ratings/provider strategy  
**Profile persistence:** browser local storage for preferences, Saved/Seen/Skip history, and external movie selections  
**Recommendation engine:** custom weighted content-based model with signed behavioral vectors, cosine feature similarity, confidence-weighted quality evidence, novelty features, and multi-factor ranking in Python

External API calls are limited to the data currently needed by the interface and are cached to keep the app responsive. The recommendation score itself is computed locally from preloaded metadata, so richer feature engineering does not add per-movie network latency. Missing ratings, posters, or provider data degrade gracefully rather than blocking recommendation rendering.

## Project Structure

```text
icinema/
├── app.py                    # Streamlit interface and user flow
├── requirements.txt
└── src/
    ├── recommender.py        # Preference profile + ranking algorithm
    ├── tmdb_catalog.py       # Search, posters, metadata, discovery pool
    ├── watch_providers.py    # Streaming/rental/purchase availability
    └── live_ratings.py       # Cached IMDb + Rotten Tomatoes data
```

## Running Locally

1. Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
```

2. Add your API credentials to `.streamlit/secrets.toml`:

```toml
TMDB_BEARER_TOKEN = "your_tmdb_read_access_token"
OMDB_API_KEY = "your_omdb_api_key"
```

3. Start the app:

```bash
streamlit run app.py
```

API credentials should never be committed to the repository.

## What I Focused On

This project was an exercise in combining **product design, data-driven personalization, API integration, and recommendation logic** into one usable application. The main challenge was turning sparse user feedback into a stable preference vector, combining explicit and behavioral signals without letting any one action dominate, and keeping the resulting ranking interpretable enough to explain and debug.

## Data Attribution

This product uses the TMDB API but is not endorsed or certified by TMDB. Watch-provider availability is supplied through TMDB using JustWatch data. IMDb and Rotten Tomatoes rating data is retrieved through OMDb.

### Current interaction polish
The current build persists the user profile in browser local storage, restores returning users directly into the Showroom, and keeps all four recommendation rows replenished from a deep cached TMDB candidate pool. Candidates within each row are displayed from highest to lowest personalized iCinema Match score, while Save, Seen, and Skip update the behavioral model immediately.


### Deep candidate pool
The Showroom ranks an effective pool of up to **640 cached TMDB candidates** at a time, plus the built-in catalog and user-added titles. Discovery pages are fetched concurrently and cached, while recommendation scoring stays local in Python so the larger pool improves variety without making normal interactions feel heavy.


### iCinema Match calibration

The displayed **iCinema Match %** is derived from the same continuous model score used to rank movies. It is confidence-adjusted based on how much preference evidence the user has supplied, then passed through a logistic calibration so weak, moderate, and strong matches remain visibly separated. New profiles are intentionally prevented from showing overconfident scores before enough feedback exists. The percentage is a compatibility index, not a literal probability that a user will like a movie.


### Showroom objectives

All four Showroom rows share the same learned user model, but optimize for different recommendation objectives. **Top Matches for You** uses the highest overall personalized score. **Critically Acclaimed** blends personalized fit with critic/audience quality. **Hidden Gems** blends personalized fit with lower-popularity and discovery signals. **Something Different** blends personalized fit with novelty across genre, language, era, and popularity. Movies are reserved to one row per render, so sections remain distinct while every recommendation stays connected to the same model.

### Latest interaction polish
The onboarding flow uses callback-based state updates for faster Like/Favorite interactions, a tighter Step 2 layout, and a compact **Preference Analysis** view before entering the Showroom.

## Current UI polish

The Showroom keeps card spacing consistent across recommendations, including aligned action buttons beneath variable-length descriptions. Onboarding CTAs use larger click targets with restrained typography for a cleaner product feel.


<!-- V5.76 interaction note: profile-changing controls use a single Streamlit interaction rerun with silent local-storage persistence to avoid duplicate rerenders. -->

## V5.78 interaction polish
- Uses Streamlit fragments for onboarding selections and Showroom interactions so ordinary button presses rerender only the affected section instead of blanking the full page.
- Keeps full-app reruns only for intentional page navigation such as Continue, Build Profile, and Reset.
- Adds a clearer visual break between the Cinema Profile subtitle and the first analysis section.


### V5.79 persistence fix
Saved, Seen, and Skipped titles from the live TMDB discovery pool now persist their movie metadata with the browser profile, so history tabs remain resolvable after refreshes and restarts.
