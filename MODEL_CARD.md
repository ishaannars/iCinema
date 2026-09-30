# Model Card — iCinema Recommender

## Overview

iCinema recommends movies to a single viewer and learns from that viewer's feedback. The goal is to shorten the path from "what should I watch?" to pressing play. It is a hybrid system with three learned or scored components:

| Component | What it does | Trained on |
|---|---|---|
| Collaborative filtering | Places a viewer among people with similar taste from their first few likes | MovieLens ratings (offline) |
| Content scoring | Genre, traits, theme and tone similarity (TF-IDF + Truncated SVD), quality, discovery, priorities | Movie metadata from TMDB |
| Behavioral model | Logistic Regression, then Gradient Boosting, predicting Save vs. Skip | The viewer's own Save/Skip feedback |

Final ranking blends collaborative filtering (35%) with content scoring (65%). Once the behavioral model is active, its prediction contributes 22% of the score. MMR reranking then reduces repetition within each row.

## Intended use

- Personal movie recommendations for one viewer in a browser session.
- A portfolio demonstration of cold-start handling, hybrid ranking, and honest offline evaluation.

**Not intended for:** decisions about people, age-appropriateness filtering, or any use where a wrong recommendation causes harm beyond a less enjoyable movie night.

## Data

**MovieLens** (GroupLens, University of Minnesota) provides the ratings used to learn movie embeddings. A rating of 4 or higher counts as a positive ("loved it"). Movies with too few positives are dropped (`--min-count`). MovieLens movies are linked to TMDB through the dataset's `links.csv`, and by normalized title and year for the built-in catalog.

**TMDB** provides movie metadata, posters, and streaming availability (via JustWatch). **OMDb** provides IMDb and Rotten Tomatoes ratings.

**Viewer feedback** (likes, saves, skips, seen, chosen streaming services) is stored only in that viewer's browser. It is never sent to a central database.

## Evaluation

**Method.** Ratings are split by time for each user: earlier positives are used for training, the most recent 20% are held out as the test. This mirrors real use, where the model must predict what someone wants *next*. The key scenario gives the model only a user's 3 most recent training likes, matching iCinema's onboarding, and compares it with a popularity baseline that recommends the most-loved movies to everyone.

**Metrics.** Recall@10 and NDCG@10 measure the top 10 recommendations. Hit@1 measures whether the single top recommendation (Tonight's Show) was loved. "Recommendations to first loved movie" measures decision effort.

**Uncertainty.** A paired bootstrap resamples held-out users 2,000 times. A difference is marked significant when its 95% interval excludes zero.

<!-- RESULTS:START -->
**Offline evaluation** — MovieLens (ml-32m), time-based split, 3,000 held-out users, ratings ≥ 4 as positives.

| Model | Recall@10 | NDCG@10 | Hit@1 (Tonight's Show) | Median recs to first loved movie |
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

**Live diagnostics.** Once a viewer has 50 Save/Skip outcomes (12+ of each), the behavioral model is trained with a chronological holdout, and the app's Profile tab reports holdout ROC AUC, Brier score, NDCG, MRR, and calibration error for that viewer.

## Design choices

- **Display position is excluded** from behavioral-model features, so a movie shown first is not mistaken for a movie the viewer prefers.
- **Recent feedback is weighted more** (120-day half-life), since taste drifts.
- **Undo removes the skip from training data**, so an accidental tap does not teach the model a false dislike.
- **The shown Match %** reflects the same blended score used for ranking.

## Limitations

- **One user's data per model.** Feedback stays in each browser, so the behavioral model never learns across users. It only activates after 50 labeled outcomes, which most visitors never reach; collaborative filtering covers personalization before that.
- **Every Skip is treated as a dislike.** A skip might mean "already seen it" or "not tonight." Skip reasons were considered and left out to keep the interface to one tap.
- **Coverage gaps.** Movies not in MovieLens, especially recent releases, get no collaborative-filtering score and rely on content signals.
- **Popularity bias.** Movies with many ratings have more reliable embeddings, so well-known films can be favored.
- **Offline metrics are not live outcomes.** MovieLens ratings approximate what a viewer would enjoy; they do not measure whether iCinema viewers pressed play.
- **Watch links open a search, not the title page.** Public links cannot open a movie inside Netflix or Hulu directly, and some services fall back to TMDB's watch page.
- **United States only** for streaming availability.

## Ethical considerations

The model uses no demographic data and stores no personal data outside the viewer's browser. Recommendations can reinforce existing taste; the "Something Different" and "Hidden Gems" rows, the adventure setting, and MMR diversity reranking are there to counter that.

## Citation

F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context. ACM Transactions on Interactive Intelligent Systems 5(4).
