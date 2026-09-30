# iCinema — ML Movie Recommendation System

I kept finding myself spending too much time deciding what movie to watch next, so I built iCinema to make that choice faster. It personalizes from your first few likes, keeps learning from what you save, skip, and watch, and turns "what should I watch?" into one confident answer on the services you already have. Please feel free to try it out and share any feedback.

The system combines:
- **Collaborative filtering pretrained on MovieLens** so recommendations are personalized from your first few likes, not weeks of history
- **Hybrid recommendation modeling** using collaborative, behavioral, semantic, quality, and discovery signals
- **Supervised ML** with Logistic Regression and Gradient Boosting trained on each user's Save/Skip feedback
- **TF-IDF + Truncated SVD** for movie theme and tone similarity
- **Multi-source candidate retrieval** across popular titles, hidden gems, recent releases, international films, and classics
- **MMR diversity reranking** to reduce repetitive recommendations
- **Recency-weighted learning** with display position excluded from features
- **Evaluation** offline on MovieLens and live in the app with ROC AUC, Brier score, NDCG, MRR, calibration error, and Time to Match

## How It Works

`candidate retrieval → feature engineering → collaborative + content scoring → personalized ranking → diversity reranking → user feedback → supervised learning → evaluation`

**Cold start is solved with collaborative filtering.** Movie embeddings are learned offline from real MovieLens ratings. Your Step 1 likes place you among viewers with similar taste, so the Showroom is personalized from the first visit. Saves pull recommendations toward similar movies and Skips push away.

**The supervised layer adds per-user learning.** After 50 Save/Skip outcomes (12+ of each), Logistic Regression starts learning from your behavior; after 100 (24+ of each), Gradient Boosting is compared and the better model on a chronological holdout is used. The collaborative-filtering score is one of its features, so it learns how much to trust that signal for you.

**Tonight's Pick** shows your single best match as one large card, preferring the streaming services you choose and falling back to any service so there is always an answer. Your services also make titles you can watch tonight rank as more convenient across every row.

User feedback is stored locally in the browser, so recommendations adapt over time without an account or central user database.

## Results

<!-- Paste the table from data/cf_results.md after running training/train_cf.py -->

**Offline evaluation on MovieLens** (ml-latest-small, time-based split, 601 held-out users, ratings ≥ 4 as positives):

| Model | Recall@10 | NDCG@10 | Hit@1 | Median recs to first loved movie |
|---|---|---|---|---|
| Popularity baseline | 0.067 | 0.062 | 7.5% | 33 |
| Collaborative filtering (full history) | 0.079 | 0.066 | 5.2% | 21 |
| Collaborative filtering (only 3 likes, like onboarding) | 0.089 | 0.081 | 9.2% | 22 |

With only 3 onboarding likes, collaborative filtering beats popularity on every metric and reaches a movie users loved in about one-third fewer recommendations.

## Current Status and Limitations

- Feedback lives in each user's browser, so the supervised model learns from one person's data and there is no cross-user learning from app users yet.
- Very recent releases not yet in MovieLens rely on content signals until they are covered.
- Streaming availability is for the United States.

## Technical Depth

Collaborative filtering (truncated SVD on implicit feedback) · cold-start fold-in from onboarding likes · Bayesian quality adjustment · Decision Utility scoring · profile confidence · calibration tracking · position-bias protection · chronological holdout · session analytics · candidate-source diversity · per-card recommendation updates

## Product Features

- Tonight's Pick with your streaming services
- Personalized movie Showroom
- "Why this match?" explanations
- Live Cinema Profile with model diagnostics
- Save, Seen, and Skip feedback
- Streaming availability
- IMDb and Rotten Tomatoes ratings
- Hidden gems and controlled discovery
- Browser-local preference persistence with no account required

## Retraining the Collaborative-Filtering Model

1. Download a MovieLens dataset from grouplens.org (for example `ml-32m`) into the repo root.
2. Run `python training/train_cf.py --data-dir ml-32m --min-count 20`.
3. Commit `data/cf_model.npz` and paste `data/cf_results.md` into the Results section.

## Stack

Python · Streamlit · scikit-learn · NumPy · SciPy · TF-IDF · Truncated SVD · MovieLens · TMDB · OMDb

[Try iCinema](https://icinema.streamlit.app/)

Uses the MovieLens dataset: F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context. ACM Transactions on Interactive Intelligent Systems 5(4). This product uses the TMDB API but is not endorsed or certified by TMDB.

© 2026 Ishaan Narasimhan. All rights reserved.
