# iCinema — ML Movie Recommendation System

I kept finding myself spending too much time deciding what movie to watch next, so I built iCinema to shorten the path from "what should I watch?" to pressing play. It personalizes from your first few likes, keeps learning from what you save, skip, and watch, gives you one confident Tonight's Pick on the services you already have, and takes you to that service in one tap. Please feel free to try it out and share any feedback.

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

**Tonight's Pick** shows your single best match as one compact card with a one-tap **Watch on …** button, preferring the streaming services you choose and falling back to any service so there is always an answer. Your services also make titles you can watch tonight rank as more convenient across every row.

User feedback is stored locally in the browser, so recommendations adapt over time without an account or central user database.

## Results

<!-- RESULTS:START -->
**Offline evaluation** — MovieLens (ml-32m), time-based split, 3,000 held-out users, ratings ≥ 4 as positives.

| Model | Recall@10 | NDCG@10 | Hit@1 (Tonight's Pick) | Median recs to first loved movie |
|---|---|---|---|---|
| Popularity baseline | 0.066 | 0.060 | 5.7% | 32 |
| Collaborative filtering (full history) | 0.071 | 0.061 | 5.8% | 27 |
| Collaborative filtering (only 3 likes, like onboarding) | 0.082 | 0.076 | 8.9% | 29 |

**Is the cold-start win real?** Paired bootstrap over users (2,000 resamples). "Significant" means the 95% interval excludes zero.

| Metric | CF (3 likes) vs popularity | 95% CI | Resamples where CF wins | Significant |
|---|---|---|---|---|
| Recall@10 | +0.016 | +0.008 to +0.023 | 100% | Yes |
| NDCG@10 | +0.016 | +0.009 to +0.023 | 100% | Yes |
| Hit@1 | +3.3% | +2.0% to +4.6% | 100% | Yes |
| Recs to first loved movie (median, fewer is better) | 2 fewer | -2 to 7 fewer | 86% | No |
<!-- RESULTS:END -->

The results above are written automatically by `training/train_cf.py`. See [MODEL_CARD.md](MODEL_CARD.md) for data, limitations, and intended use.

Live per-user diagnostics (model, holdout AUC, Brier score, NDCG, MRR, calibration error) appear in the app's Profile tab once enough feedback exists.

## Current Status and Limitations

- Feedback lives in each user's browser, so the supervised model learns from one person's data and there is no cross-user learning from app users yet.
- Very recent releases not yet in MovieLens rely on content signals until they are covered.
- Streaming availability is for the United States.

## Technical Depth

Collaborative filtering (truncated SVD on implicit feedback) · cold-start fold-in from onboarding likes · Bayesian quality adjustment · Decision Utility scoring · profile confidence · calibration tracking · position-bias protection · chronological holdout · session analytics · candidate-source diversity · per-card recommendation updates

## Product Features

- Tonight's Pick with your streaming services
- One-tap links from any recommendation to the service that streams it
- Personalized movie Showroom
- "Why this match?" explanations
- Live Cinema Profile with model diagnostics
- Save, Seen, and Skip feedback, with Undo for accidental skips
- Streaming availability
- IMDb and Rotten Tomatoes ratings
- Hidden gems and controlled discovery
- Browser-local preference persistence with no account required

## Retraining the Collaborative-Filtering Model

1. Download a MovieLens dataset from grouplens.org (for example `ml-32m`) into the repo root.
2. Run `python training/train_cf.py --data-dir ml-32m --min-count 20`.
3. The script updates the Results section here and in `MODEL_CARD.md` automatically. Commit `data/cf_model.npz` and both docs.

## Stack

Python · Streamlit · scikit-learn · NumPy · SciPy · TF-IDF · Truncated SVD · MovieLens · TMDB · OMDb

[Try iCinema](https://icinema.streamlit.app/)

Uses the MovieLens dataset: F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context. ACM Transactions on Interactive Intelligent Systems 5(4). This product uses the TMDB API but is not endorsed or certified by TMDB.

© 2026 Ishaan Narasimhan. All rights reserved.
