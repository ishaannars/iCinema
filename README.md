# iCinema — ML Movie Recommendation System

I kept finding myself spending too much time deciding what movie to watch next, so I built iCinema to try to make that choice a little easier. It’s an ML system that learns from what each user likes, saves, skips, and watches to personalize what they see over time. Please feel free to try it out and share any feedback.

The system combines:
- **Hybrid recommendation modeling** using behavioral, semantic, quality, and discovery signals
- **Supervised ML** with Logistic Regression and Gradient Boosting trained on real Save/Skip feedback
- **TF-IDF + Truncated SVD** for movie theme and tone similarity
- **Multi-source candidate retrieval** across popular titles, hidden gems, recent releases, international films, and classics
- **MMR diversity reranking** to reduce repetitive recommendations
- **Recency-weighted, bias-aware learning**
- **Evaluation** with ROC AUC, log loss, Brier score, NDCG, MRR, and Time to Match

## How It Works

`candidate retrieval → feature engineering → personalized ranking → diversity reranking → user feedback → supervised learning → evaluation`

The app works immediately with a cold-start analytical model. Once enough explicit feedback exists, the supervised ML layer begins learning from the user’s behavior.

User feedback is stored locally in the browser, so recommendations can adapt over time without requiring an account or central user database.

## Technical Depth

Bayesian quality adjustment · Decision Utility scoring · profile confidence · calibration tracking · position-bias protection · session analytics · candidate-source diversity · per-card recommendation updates

## Product Features

- Personalized movie Showroom
- “Why this match?” explanations
- Live Cinema Profile
- Save, Seen, and Skip feedback
- Streaming availability
- IMDb and Rotten Tomatoes ratings
- Hidden gems and controlled discovery
- Browser-local preference persistence with no account required

## Stack

Python · Streamlit · scikit-learn · NumPy · TF-IDF · Truncated SVD · TMDB · OMDb

[Try iCinema](https://icinema.streamlit.app/)

© 2026 Ishaan Narasimhan. All rights reserved.
