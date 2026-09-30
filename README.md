# iCinema — ML Movie Recommendation System

I kept finding myself spending too much time deciding what movie to watch next, so I built iCinema to shorten the path from "what should I watch?" to pressing play. It personalizes from your first few likes, keeps learning from what you save, skip, and watch, gives you one confident Tonight's Show on the services you already have, and takes you to that service in one tap. Please feel free to try it out and share any feedback.

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

**Tonight's Show** shows your single best match as one compact card with a one-tap **Watch on …** button, preferring the streaming services you choose and falling back to any service so there is always an answer. Your services also make titles you can watch tonight rank as more convenient across every row.

User feedback is stored locally in the browser, so recommendations adapt over time without an account or central user database.

## Results

<!-- RESULTS:START -->
**Offline evaluation** — MovieLens (ml-32m), time-based split, 3,000 held-out users, ratings ≥ 4 as positives.

**Headline:** from just 3 likes, Tonight's Show is **+58%** more likely to be a movie the viewer loves than a popularity pick, and Showroom rows are **+24–27%** better (relative lift, computed from unrounded values).

| Model | Recall@10 | NDCG@10 | Hit@1 (Tonight's Show) | Median recs to first loved movie |
|---|---|---|---|---|
| Popularity baseline | 0.066 | 0.060 | 5.67% | 32 |
| Collaborative filtering (full history) | 0.071 | 0.061 | 5.77% | 27 |
| Collaborative filtering (only 3 likes, like onboarding) | 0.082 | 0.076 | 8.93% | 29 |

**Is the cold-start win real?** Paired bootstrap over users (2,000 resamples). "Significant" means the 95% interval excludes zero. Differences are absolute (Hit@1 in percentage points).

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
- Watch links open each service's search for the title, because public links can't open a movie inside Netflix or Hulu directly. Services without a dependable search link (Max, Peacock, Paramount+) open TMDB's watch page, which then links to the service.

## Ranking Details

The Profile tab keeps this short for viewers; here is the full picture.

- **Collaborative filtering.** Truncated SVD on 15.8 million positive MovieLens ratings (4 stars and up) from 198,954 users learns 64-dimension embeddings for 14,407 movies. A viewer's likes, favorites (weighted double), and saves pull their taste vector toward similar movies; skips push it away. Candidates are scored by cosine similarity.
- **Content model.** TF-IDF and Truncated SVD over plot and metadata measure theme and tone. Genre, storytelling traits, Bayesian-adjusted ratings, discovery fit, and Step 2–3 answers complete the content score.
- **Hybrid ranking.** Score = 65% content + 35% collaborative. Each Showroom row blends in its own goal: Critically Acclaimed (30% ratings), Hidden Gems (28% less-popular but well rated), and Something Different (32% novelty in genre, language, and era, plus a mainstream penalty). The blend weights are hand-set design choices. MMR reranking removes near-duplicates, and titles on the viewer's services rank as easier to watch tonight.
- **Behavioral model.** After 50 Save/Skip outcomes (12+ of each), Logistic Regression trains on the viewer's own feedback; Gradient Boosting is compared at 100 and the better model on a chronological holdout is used. It contributes 22% of the score. Recent choices weigh more (120-day half-life), display position is excluded so exposure isn't mistaken for taste, and Undo removes a skip from training data.
- **Freshness for returning viewers.** Impression discounting lowers a title a little for each earlier visit where it was shown but got no Save, Seen, or Skip (capped at five visits), and a small per-visit shuffle varies near-ties. Both are stable within a visit, so rows never jump while browsing. The candidate pool also widens: each return visit starts deeper in TMDB's catalog, and dedicated channels pull the most popular and best-rated titles in the viewer's top two genres.
- **Explicit vs. implicit negatives.** Skip means "not now" and is a weak signal; "Not for me" (in each card's explanation and beside Tonight's Show) is an explicit dislike. It pushes the content profile and collaborative-filtering taste vector away about four times harder, counts as a double-weight negative label for the behavioral model, and the title never returns. Undo reverses either one.
- **Live metrics.** NDCG@4 and MRR appear after 5 Saves; calibration error after 20 Saves and Skips, so a handful of clicks never shows a misleading "perfect" score.
- **Explanations.** Each card's reasons are the components that contributed most to that movie's score. "Loved by fans of …" names only movies the viewer liked, favorited, or saved, never ones merely marked Seen.

## Technical Depth

Collaborative filtering (truncated SVD on implicit feedback) · cold-start fold-in from onboarding likes · Bayesian quality adjustment · Decision Utility scoring · profile confidence · calibration tracking · position-bias protection · chronological holdout · session analytics · candidate-source diversity · per-card recommendation updates

## Product Features

- Tonight's Show with your streaming services
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
