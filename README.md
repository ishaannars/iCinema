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
