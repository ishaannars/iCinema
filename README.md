# iCinema — Personalized Movie Discovery

iCinema is an explainable hybrid recommendation and decision-optimization system built to help people find something worth watching faster. The consumer experience stays intentionally simple while the ranking engine combines behavioral signals, content features, NLP, statistical adjustment, diversity optimization, and browser-local supervised learning.

## Product objective

The north-star objective is **time to a satisfying choice**. iCinema measures **Time to Match** as the time from entering the Showroom to the first Save, then tracks skips before Save and whether Saved recommendations later become Seen.

## Recommendation system

### Cold-start + continuous profile
Step 1 Likes/Favorites, Step 2 quality/discovery controls, Step 3 Showroom priorities, and ongoing Save/Seen/Skip behavior all alter the learned profile. Favorites and Saves are stronger positive evidence; Skip is signed negative evidence; Seen is deliberately weaker historical evidence.

### Feature engineering
Candidate features include genre, behavioral traits, latent semantic similarity, critic/audience quality, vote confidence, popularity, language, release era, discovery characteristics, Step 3 priorities, and real streaming availability. Heavy-tailed numeric inputs such as popularity and vote count are log-normalized.

### NLP / latent semantic representation
Movie descriptions, genres, and tags are vectorized with TF-IDF n-grams and projected with Truncated SVD to create latent semantic vectors. Cosine similarity between the signed user taste representation and candidate vectors captures thematic relationships beyond one-hot genres.

### Bayesian quality
Sparse ratings are shrunk toward a conservative catalog prior using vote-count evidence so a tiny sample cannot dominate a well-established title.

### Hybrid score + Decision Utility
The model combines genre affinity, trait affinity, semantic similarity, quality alignment, discovery alignment, and Step 3 priority alignment. A second hidden **Decision Utility** objective includes evidence confidence and streaming availability to decide which recommendations deserve limited screen space.

### Diversity and exploration
Maximum Marginal Relevance (MMR) penalizes redundant visible choices. “Something Different” acts as controlled exploration: farther from the taste center, but still constrained by personalized fit.

## Learning layer

iCinema logs browser-local recommendation impressions and explicit Save/Seen/Skip outcomes. Once at least 24 real labeled interactions with both positive and negative classes exist, it trains and evaluates:

- Logistic Regression (interpretable baseline)
- Gradient Boosting classifier

A stratified held-out split compares ROC AUC, accuracy, and log loss. The better model is refit on the available labeled data and blended into live ranking. Before enough labels exist, the analytical hybrid recommender remains the honest cold-start model; iCinema never fabricates training outcomes.

## Evaluation
The evaluation layer supports Precision@K, Recall@K, Hit Rate@K, NDCG@K, Mean Reciprocal Rank, Match-score calibration bands, Time to Match, skips before Save, Saved→Seen conversion, and discovery behavior.

## Explainability
Consumers can open **Why this match?** on any recommendation. The Cinema Profile exposes Profile Confidence and **Your iCinema Insights** without turning the interface into an analytics dashboard.

## Data and APIs
- TMDB: search, posters, metadata, discovery candidates, provider data
- OMDb: IMDb and Rotten Tomatoes ratings
- JustWatch data via TMDB: U.S. streaming availability

This product uses the TMDB API but is not endorsed or certified by TMDB. Streaming-provider data is powered by JustWatch through TMDB.

## Stack
Python, Streamlit, NumPy, scikit-learn, requests, TMDB, OMDb, browser localStorage.

## Local setup
Install dependencies:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit Secrets:

```toml
TMDB_BEARER_TOKEN = "your_token"
OMDB_API_KEY = "your_key"
```

No API credentials are committed to the repository.
