# iCinema

[![Tests](https://github.com/ishaannars/iCinema/actions/workflows/tests.yml/badge.svg)](https://github.com/ishaannars/iCinema/actions/workflows/tests.yml)

I kept spending too much time deciding what to watch, so I built iCinema to shorten the path from "what should I watch?" to pressing play. It personalizes from your first few likes, keeps learning from what you save, skip, and watch, and gives you one confident pick on the services you already have.

<!-- RECRUITER-TOP -->
**[Try iCinema →](https://icinema.streamlit.app/)**

## Results

- From **3 random likes**, the first pick was a movie the viewer later rated 4+ stars **7.9%** of the time, compared with **5.4%** for the most popular movie (**+45%**), on 3,000 MovieLens viewers it never saw.
- The shipped model beat the old one by **+80%** on that first pick and beat SVD, implicit ALS, and EASE in a head-to-head benchmark.
- It found a loved movie **12 recommendations sooner** than popularity (median 20 vs 32).

## What I learned

My first headline was +58%, but it came from each viewer's 3 most recent likes. Recent likes sit right next to what someone watches next, so that test was too easy. With 3 random likes, the old SVD model did worse than recommending what's popular. I benchmarked the standard recommenders on the honest test, and item-kNN won by a wide margin, so it now powers every row. Testing the blend weights the same way moved the app from 65% content to 20%.

## How it works

`candidate retrieval → "viewers like you" score + content score → personalized ranking → diversity reranking → your feedback → personal model`

- **Viewers like you (item-kNN).** For each of 14,407 movies, the 100 movies most often loved by the same MovieLens viewers, trained on 15.8 million 4+ star ratings from 198,954 viewers. Your likes, favorites, and saves add up their neighbors. Skips and "Not for me" push them down.
- **Content.** TF-IDF and Truncated SVD over plot and metadata measure theme and tone.
- **Personal model.** After 50 Save/Skip outcomes, logistic regression learns from your own choices. Gradient boosting is compared at 100, and the better one on a chronological holdout is used.
- **Every step counts.** Step 1 likes feed both scores. Step 2 (genres, reviews vs enjoyment, openness) and Step 3 (what to see more of) shape the content score and your Profile. Step 3 also picks which section comes after Top Matches.
- **Tonight's Show.** Your single best match on the services you pick, with one-tap links to watch.
- Your feedback stays in your browser. There's no account and no central user database.

## Model benchmark

<!-- CF_BENCHMARK:START -->
| Model | Hit@1, 3 random likes | NDCG@10, 3 random likes | Hit@1, 3 most recent likes | Hit@1, full history | Size |
|---|---|---|---|---|---|
| Popularity | 5.4% | 0.058 | 5.4% | 5.4% | — |
| SVD, 64 dims (old model) | 4.4% | 0.045 | 8.9% | 6.9% | 2 MB |
| SVD, 128 dims | 4.4% | 0.044 | 9.2% | 7.2% | 4 MB |
| SVD 64, recency-weighted (half-life 20 likes) | 4.6% | 0.045 | 9.1% | 7.5% | 2 MB |
| Implicit ALS | 6.9% | 0.070 | 12.9% | 10.2% | 2 MB |
| EASE | 7.2% | 0.074 | 13.4% | 11.5% | 257 MB |
| EASE, top-100 per movie (shippable) | 7.3% | 0.074 | 13.0% | 11.4% | 6 MB |
| item-kNN | 8.2% | 0.082 | 14.4% | 9.5% | 257 MB |
| **item-kNN, top-100 per movie (shipped)** | 7.9% | 0.078 | 13.5% | 8.7% | 6 MB |

1 in 5 MovieLens 32M users: 39,786 viewers, 8,014 movies, 3,115,576 ratings of 4+ stars. Settings were picked on 3,000 validation viewers and scored once on 3,000 different test viewers. From `training/benchmark_cf.py`.
<!-- CF_BENCHMARK:END -->

## Every part tested

<!-- TESTED:START -->
| Part | Test | Result | In the app |
|---|---|---|---|
| Viewers like you | 9 models, 3 random likes, 3,000 test viewers | item-kNN won: 7.9% first-pick hits vs 5.4% popularity and 4.4% old SVD | ✅ item-kNN |
| Content vs viewers like you | Every weight from 0% to 100% content | 20% content was best (NDCG 0.069 vs 0.059 at the old 65%). With no floor, 0% was best | ✅ 20% content, 80% viewers like you |
| Every onboarding step (Steps 1–3) | The app's own scoring, with each viewer's Step 2–3 answers filled in from their history | At 20% content, Steps 2–3 didn't move hit rates (NDCG +0.000, 95% CI -0.001 to +0.001). 0% and 20% content tied on validation (0.0836 vs 0.0835) | ✅ Kept at 20%, so your answers count at no cost |
| Learned ranker | Logistic regression on viewers like you plus every content part | Worse than the current blend (NDCG -0.004) | ❌ No |
| What's next | Every mix of similarity to the watched movie and personal match | 80% similarity was best (NDCG 0.088 vs 0.081 at the old 60%). With no floor, 100% was best | ✅ 80% similarity, 20% personal match |
| Recency-weighted likes | SVD with newer likes weighted more | 4.6% vs 4.4%, no real gain | ❌ No |
| Row goals (Critically Acclaimed, Hidden Gems, Something Different) | Not testable offline | They define what each row is for | Design choice |
| Personal Save/Skip model (22%) | Needs real app users | Live AUC shows in the Profile tab | Design choice |
| Section order | Not an accuracy question | Your Step 3 picks decide which section comes after Top Matches | Design choice |

MovieLens has no onboarding answers, so Step 2–3 answers were filled in from each viewer's own history. Content and personal match always keep at least 20%, so your answers always count. From `training/benchmark_cf.py`, `training/evaluate_blends.py`, and `training/evaluate_steps.py`.
<!-- TESTED:END -->

## Where it's wrong

<!-- ERRORS:START -->
First-pick hit rate for the shipped model from 3 random likes (7.9% overall).

- **Viewers with little history are hardest.** 2.4% for viewers with 3–10 liked movies, 12.9% for 100+. They have fewer later favorites to hit.
- **Niche taste is hardest.** 3.6% for viewers whose later favorites were the least popular movies, 12.3% for the most popular. Movies with few fans have fewer neighbors to draw on.
- New movies that aren't in MovieLens get no "viewers like you" score, so content alone ranks them.
<!-- ERRORS:END -->

## Results detail

<!-- RESULTS:START -->
**Offline evaluation:** ml-32m (1 in 5 MovieLens 32M users), time-based split, 3,000 held-out users, ratings ≥ 4 as positives.

**Headline:** from 3 random likes, Tonight's Show is **+45%** more likely to be a movie the viewer loves than a popularity pick, and Showroom rows are **+34–36%** better (relative lift, computed from unrounded values).

| Model | Recall@10 | NDCG@10 | Hit@1 (Tonight's Show) | Median recs to first loved movie |
|---|---|---|---|---|
| Popularity baseline | 0.065 | 0.058 | 5.43% | 32 |
| item-kNN (full history) | 0.100 | 0.090 | 8.73% | 17 |
| item-kNN (3 random likes, like onboarding) | 0.088 | 0.078 | 7.90% | 20 |

**Is the cold-start win real?** Paired bootstrap over users (2,000 resamples). "Significant" means the 95% interval excludes zero. Differences are absolute (Hit@1 in percentage points).

| Metric | Shipped model (3 random likes) vs popularity | 95% CI | Resamples where CF wins | Significant |
|---|---|---|---|---|
| Recall@10 | +0.023 | +0.017 to +0.029 | 100% | Yes |
| NDCG@10 | +0.020 | +0.015 to +0.025 | 100% | Yes |
| Hit@1 | +2.5% | +1.3% to +3.7% | 100% | Yes |
| Recs to first loved movie (median, fewer is better) | 12 fewer | 10 to 16 fewer | 100% | Yes |
<!-- RESULTS:END -->

See [MODEL_CARD.md](MODEL_CARD.md) for data, limits, and intended use. Live per-user diagnostics (AUC, Brier score, NDCG, MRR, calibration error) appear in the app's Profile tab once there's enough feedback.

## Ranking details

- **Hybrid score.** Content and "viewers like you" are blended with the tested weights above. Each Showroom row adds its own goal: Critically Acclaimed (30% ratings), Hidden Gems (28% less popular but well rated), and Something Different (32% novelty). Top Matches is strictly your best fits.
- **Personal model.** It contributes 22% of the score. Recent choices weigh more (120-day half-life), and display position is left out so being shown isn't mistaken for taste.
- **Freshness.** A title shown on earlier visits with no Save, Seen, or Skip drops a little each visit (up to five visits).
- **Skip vs "Not for me."** Skip is a weak "not now." "Not for me" is a strong dislike, and the title never comes back.
- **What's next.** Under each Seen movie: a tested mix of similarity to that movie and your personal match (see the table above).
- **Explanations.** "Loved by fans of …" only names movies you liked, favorited, or saved.

## Limits

- Feedback lives in each browser, so there's no learning across app users yet.
- New releases not in MovieLens rely on content signals.
- Streaming availability is U.S. only.
- The benchmark uses 1 in 5 MovieLens 32M viewers. The shipped model is retrained on all of them.

## Run it

```sh
pip install -r requirements.txt
streamlit run app.py
python -m pytest -q
```

To rebuild the models, download MovieLens 32M into `ml-32m/`, then run `training/benchmark_cf.py`, `training/build_knn.py`, `training/evaluate_blends.py`, and `training/evaluate_steps.py` (each with `--data-dir ml-32m`), then `python tools/refresh_results.py`.

## Coming next

- Help viewers with little history and niche taste, where the model misses most.
- Split `app.py` into modules.
- Product: a For Critics tab, "Only my services" mode, thumbs up or down on Seen movies, and adding likes from the Showroom.

## Stack

Python · Streamlit · scikit-learn · NumPy · SciPy · MovieLens · TMDB · OMDb
