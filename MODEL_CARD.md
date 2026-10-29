# Model Card: iCinema Recommender

## Overview

iCinema recommends movies to a single viewer and learns from that viewer's feedback. The goal is to shorten the path from "what should I watch?" to pressing play. It is a hybrid system with three learned or scored components:

| Component | What it does | Trained on |
|---|---|---|
| Collaborative filtering (RP3beta for ranking, item-kNN for similar movies) | Scores movies the same viewers loved alongside the viewer's likes, from their first few likes | MovieLens 32M ratings (offline) |
| Content scoring | Genre, traits, theme and tone similarity (MovieLens genres and fan tags, TF-IDF + truncated SVD), quality, discovery, priorities | MovieLens 32M genres and tags. TMDB metadata is used for display only. |
| Behavioral model | Logistic Regression, then Gradient Boosting, predicting Save vs. Skip | The viewer's own Save/Skip feedback |

Final ranking blends collaborative filtering and content scoring with weights tested on held-out MovieLens viewers (`training/evaluate_blends.py`; currently 80% collaborative, 20% content). Once the behavioral model is active, its prediction contributes 22% of the score. MMR reranking then reduces repetition within each row.

## Intended use

- Personal movie recommendations for one viewer in a browser session.
- A portfolio demonstration of cold-start handling, hybrid ranking, and honest offline evaluation.

**Not intended for:** decisions about people, age-appropriateness filtering, or any use where a wrong recommendation causes harm beyond a less enjoyable movie night.

## Data

**MovieLens** (GroupLens, University of Minnesota) provides the ratings used to find which movies the same viewers loved. Each shipped model keeps every movie's 100 closest movies. Item-kNN (cosine with shrinkage) won the main benchmark against popularity, SVD, implicit ALS, and EASE (`training/benchmark_cf.py`). RP3beta matched it overall and did better for less mainstream taste, confirmed on fresh viewers (`training/confirm_long_tail.py`), so it ranks every row while item-kNN finds similar movies. A rating of 4 or higher counts as a positive ("loved it"). Movies with too few positives are dropped (`--min-count`). MovieLens movies are linked to TMDB through the dataset's `links.csv`, and by normalized title and year for the built-in catalog.

**TMDB** provides movie metadata, posters, and streaming availability (via JustWatch). **OMDb** provides IMDb and Rotten Tomatoes ratings.

**Viewer feedback** (likes, saves, skips, seen, chosen streaming services) is stored only in that viewer's browser. It is never sent to a central database.

## Evaluation

**Method.** Ratings are split by time for each user: earlier positives are used for training, the most recent 20% are held out as the test. This mirrors real use, where the model must predict what someone wants *next*. The key scenario gives the model only a user's 3 most recent training likes, matching iCinema's onboarding, and compares it with a popularity baseline that recommends the most-loved movies to everyone.

**Metrics.** Recall@10 and NDCG@10 measure the top 10 recommendations. Hit@1 measures whether the single top recommendation (Tonight's Show) was loved. "Recommendations to first loved movie" measures decision effort.

**Uncertainty.** A paired bootstrap resamples held-out users 2,000 times. A difference is marked significant when its 95% interval excludes zero.

<!-- RESULTS:START -->
**Offline evaluation:** ml-32m (1 in 5 MovieLens 32M users), time-based split, 3,000 held-out users, ratings ≥ 4 as positives.

**Headline:** from 3 random likes, Tonight's Show is **+48%** more likely to be a movie the viewer loves than a popularity pick, and Showroom rows are **+37–39%** better (relative lift, computed from unrounded values).

| Model | Recall@10 | NDCG@10 | Hit@1 (Tonight's Show) | Median recs to first loved movie |
|---|---|---|---|---|
| Popularity baseline | 0.065 | 0.058 | 5.43% | 32 |
| Routed: RP3beta (beta 0.3) for less mainstream taste (full history) | 0.100 | 0.089 | 8.50% | 17 |
| Routed: RP3beta (beta 0.3) for less mainstream taste (3 random likes, like onboarding) | 0.090 | 0.079 | 8.03% | 19 |

**Is the cold-start win real?** Paired bootstrap over users (2,000 resamples). "Significant" means the 95% interval excludes zero. Differences are absolute (Hit@1 in percentage points).

| Metric | Shipped model (3 random likes) vs popularity | 95% CI | Resamples where CF wins | Significant |
|---|---|---|---|---|
| Recall@10 | +0.025 | +0.020 to +0.031 | 100% | Yes |
| NDCG@10 | +0.021 | +0.016 to +0.026 | 100% | Yes |
| Hit@1 | +2.6% | +1.5% to +3.8% | 100% | Yes |
| Recs to first loved movie (median, fewer is better) | 13 fewer | 10 to 16 fewer | 100% | Yes |
<!-- RESULTS:END -->

**Live diagnostics.** Once a viewer has 50 Save/Skip outcomes (12+ of each), the behavioral model is trained with a chronological holdout, and the app's Profile tab reports holdout ROC AUC, Brier score, NDCG, MRR, and calibration error for that viewer.

## Design choices

- **Display position is excluded** from behavioral-model features, so a movie shown first is not mistaken for a movie the viewer prefers.
- **Recent feedback is weighted more** (120-day half-life), since taste drifts.
- **Undo removes the skip from training data**, so an accidental tap does not teach the model a false dislike.
- **The shown Match %** reflects the same blended score used for ranking.

## Limitations

- **One user's data per model.** Feedback stays in each browser, so the behavioral model never learns across users. It only activates after 50 labeled outcomes, which most visitors never reach; collaborative filtering covers personalization before that.
- **Skip is ambiguous by design.** A Skip may mean "already seen" or "not tonight," so it is only a weak negative; the explicit "Not for me" signal carries strong dislikes. Skip reasons were considered and left out to keep feedback to one tap.
- **Coverage gaps.** Movies not in MovieLens, especially recent releases, get no collaborative-filtering score and rely on content signals.
- **Popularity bias.** Movies with many fans have more reliable neighbors, so well-known films can be favored.
- **Offline metrics are not live outcomes.** MovieLens ratings approximate what a viewer would enjoy; they do not measure whether iCinema viewers pressed play.
- **The live test is a screen.** Team-draft interleaving in Top Matches (rule in `src/interleave.py`) compares routed ranking with item-kNN alone, only for viewers with less mainstream likes, by saves within a visit. It doesn't measure retention, and its result is read only after 200 decided visits.
- **Watch links open a search, not the title page.** Public links cannot open a movie inside Netflix or Hulu directly, and some services fall back to TMDB's watch page.
- **United States only** for streaming availability.

## Ethical considerations

The model uses no demographic data and stores no personal data outside the viewer's browser. Recommendations can reinforce existing taste; the "Something Different" and "Hidden Gems" rows, the adventure setting, and MMR diversity reranking are there to counter that.

## Citation

F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context. ACM Transactions on Interactive Intelligent Systems 5(4).
