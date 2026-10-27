# iCinema

[![Tests](https://github.com/ishaannars/iCinema/actions/workflows/tests.yml/badge.svg)](https://github.com/ishaannars/iCinema/actions/workflows/tests.yml)

I kept spending too much time deciding what to watch, so I built iCinema for people like me. It gives you one tested pick for tonight from the services you already pay for, starting from your first 3 likes. It's built to reach past what's trending, so viewers with less mainstream taste get better picks too. It keeps learning from what you save, skip, and watch, and it needs no account.

<!-- RECRUITER-TOP -->
**[Try iCinema →](https://icinema.streamlit.app/)**

## Results

- From **3 random likes**, the first pick was a movie the viewer later rated 4+ stars **8.0%** of the time, compared with **5.4%** for the most popular movie (**+48%**), on 3,000 MovieLens viewers it never saw.
- That beat the old model by **+83%** on the first pick, and it found a loved movie **13 recommendations sooner** than popularity (median 19 vs 32).
- For viewers with **less mainstream taste**, ranking quality rose **8%** and nobody else got worse. This held on 39,805 brand-new viewers from a separate slice of MovieLens.
- **Hidden Gems has real evidence.** Ranking less-known movies with the shipped model put a movie the viewer later loved in the top 10 **2.7 times as often** as the most popular less-known movies (11.0% vs 4.1%).

## What I learned

My first headline was +58%, but it came from each viewer's 3 most recent likes. Recent likes sit right next to what someone watches next, so that test was too easy. With 3 random likes, the old SVD model did worse than recommending what's popular. I benchmarked the standard recommenders on the honest test, and item-kNN won by a wide margin.

Then the error analysis showed viewers with less mainstream taste got the worst picks. Penalizing popular movies, ALS, EASE, and blends all made things worse for them. RP3beta, a random-walk model that discounts popularity a little, was the one fix that helped. Its first test was too small to call, so I confirmed it on fresh viewers. It also dipped mainstream viewers slightly, so I tested routing (RP3beta for less mainstream likes, item-kNN otherwise) on a brand-new set of viewers. Routing beat both models used alone, so that's what ships. Testing the blend weights the same way moved the app from 65% content to 20%.

## How it works

`candidate retrieval → "viewers like you" score + content score → personalized ranking → diversity reranking → your feedback → personal model`

- **Viewers like you.** Trained on 15.8 million 4+ star ratings from 198,954 viewers across 14,407 movies. Item-kNN ranks movies for most viewers and finds movies similar to one you watched, for What's next and "Loved by fans of …". If your likes are less-loved movies, RP3beta ranks instead: a walk from your likes to the people who loved them and on to what else they loved, with popular movies discounted slightly. Skips and "Not for me" push movies down.
- **Content.** Each movie's MovieLens genres and fan tags become a 64-number description (TF-IDF, then truncated SVD), the same recipe the offline tests used. TMDB is used only to show titles, posters, and where to watch.
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
| **item-kNN, top-100 per movie (shipped for most viewers and similar movies)** | 7.9% | 0.078 | 13.5% | 8.7% | 6 MB |
| **RP3beta (beta 0.3), top-100 per movie (shipped for less mainstream taste)** | 7.7% | 0.077 | 11.0% | 7.6% | 5 MB |
| **Routed: RP3beta for less mainstream likes, item-kNN otherwise (what the app does)** | 8.0% | 0.079 | 13.1% | 8.5% | 10 MB |

1 in 5 MovieLens 32M users: 39,786 viewers, 8,014 movies, 3,115,576 ratings of 4+ stars. Settings were picked on 3,000 validation viewers and scored once on 3,000 different test viewers. From `training/benchmark_cf.py`.
<!-- CF_BENCHMARK:END -->

## Every part tested

<!-- TESTED:START -->
| Part | Test | Result | In the app |
|---|---|---|---|
| Viewers like you | 9 models, 3 random likes, 3,000 test viewers | item-kNN won: 7.9% first-pick hits vs 5.4% popularity and 4.4% old SVD | ✅ item-kNN for most viewers |
| Less mainstream taste | 12 fixes for popularity bias (popularity penalties, ALS, EASE, blends, RP3beta), then a fresh check on 33,786 untouched viewers | RP3beta (beta 0.3) lifted niche viewers' NDCG +0.0071 (95% CI +0.0045 to +0.0097) with no loss overall (-0.0005, CI -0.0016 to +0.0007). Every other fix made things worse | ✅ Used for less mainstream likes (see routing) |
| Routing between the two | RP3beta for less mainstream likes, item-kNN otherwise, on 39,805 brand-new viewers (a separate slice of MovieLens, models rebuilt, nothing tuned) | Beat RP3beta for everyone (NDCG +0.0026, CI +0.0017 to +0.0035) and item-kNN for everyone (+0.0014, CI +0.0008 to +0.0019) | ✅ What the app does |
| Content vs viewers like you | Every weight from 0% to 100% content | 20% content was best (NDCG 0.075 vs 0.061 at the old 65%). With no floor, 0% was best | ✅ 20% content, 80% viewers like you |
| Every onboarding step (Steps 1–3) | The app's own scoring, with each viewer's Step 2–3 answers filled in from their history | At 20% content, Steps 2–3 didn't move hit rates (NDCG -0.001, 95% CI -0.003 to +0.000). 20% content was best on validation (NDCG 0.0853 vs 0.0841 with no content) | ✅ Kept at 20%, so your answers count at no cost |
| More content for niche taste (on top of RP3beta) | Viewers whose 3 likes are less-loved movies (745 test viewers) | The current 20% was already best for them on validation | No change needed |
| Learned ranker | Logistic regression on viewers like you plus every content part | Worse than the current blend (NDCG -0.002) | ❌ No |
| What's next | Every mix of similarity to the watched movie and personal match | 80% similarity was best (NDCG 0.090 vs 0.083 at the old 60%). With no floor, 100% was best | ✅ 80% similarity, 20% personal match |
| Recency-weighted likes | SVD with newer likes weighted more | 4.6% vs 4.4%, no real gain | ❌ No |
| Row goals (how much each row leans on its kind) | Not testable offline | They define what each row is for | Design choice |
| Personal Save/Skip model (22%) | Needs real app users | Live AUC shows in the Profile tab | Design choice |
| Section order | Not an accuracy question | Your Step 3 picks decide which section comes after Top Matches | Design choice |
| Hidden Gems | Definition | Under 4,000 TMDB votes, or outside the 20% most-loved MovieLens movies when votes are missing, plus a few hand-picked gems | Design choice |
| Card descriptions | Rules checked by unit tests | Each line is scored for being specific, standing on its own, and describing the story. No text is generated | ✅ Rule-based |
| Hidden Gems row | Within movies outside the 20% most-loved movies, vs the most popular of that kind (1,823 viewers) | Found a movie the viewer later loved in its top 10 11.0% of the time vs 4.1% (CI +0.054 to +0.085) | ✅ Supported |
| Critically Acclaimed row | Within movies 4.0+ stars from 500+ ratings, vs the most popular of that kind (1,967 viewers) | Found a movie the viewer later loved in its top 10 51.9% of the time vs 43.7% (CI +0.058 to +0.106) | ✅ Supported |
| Something Different row | Within movies outside your 3 most-liked genres, vs the most popular of that kind (2,478 viewers) | Found a movie the viewer later loved in its top 10 36.5% of the time vs 30.5% (CI +0.042 to +0.078) | ✅ Supported |

MovieLens has no onboarding answers, so Step 2–3 answers were filled in from each viewer's own history. Content and personal match always keep at least 20%, so your answers always count. From the scripts in `training/`.
<!-- TESTED:END -->

## Where it's wrong

<!-- ERRORS:START -->
First-pick hit rate for the shipped model from 3 random likes (7.7% overall).

- **Viewers with little history are hardest.** 3.2% for viewers with 3–10 liked movies, 13.3% for 100+. They have fewer later favorites to hit.
- **Niche taste is hardest.** 4.3% for viewers whose later favorites were the least popular movies, 12.7% for the most popular. Movies with few fans have fewer neighbors to draw on.
- New movies that aren't in MovieLens get no "viewers like you" score, so content alone ranks them.
<!-- ERRORS:END -->

## How iCinema compares

Checked October 2026. iCinema doesn't claim to be the only option.

| Option | What it gives you | What iCinema adds |
|---|---|---|
| JustWatch | Search across streaming services and recommendations based on what people with similar tastes watch, free with no account for the basics | One pick for tonight, a published accuracy benchmark, and a personal model that learns from your saves and skips in your browser |
| Reelgood | Browsing across 150+ services, with recommendations after you create an account and add your services | The same personal picks with no account |
| Your streaming app's home screen | Picks from that one service's catalog | Picks across every service you pay for, with a reason for each one |

## Decision time

<!-- DECISION_TIME:START -->
_Not measured yet. Run `python timing_test.py` with at least one person (protocol in `TIMING_TEST.md`)._
<!-- DECISION_TIME:END -->

The test compares iCinema with browsing a streaming app, timed until a person would press play. Protocol in [TIMING_TEST.md](TIMING_TEST.md).

## Results detail

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

To rebuild everything, download MovieLens 32M into `ml-32m/` and run these in order, each with `--data-dir ml-32m`: `training/benchmark_cf.py`, `training/evaluate_long_tail.py`, `training/confirm_long_tail.py`, `training/confirm_routing.py`, `training/build_knn.py`, `training/evaluate_blends.py`, `training/evaluate_steps.py`, `training/evaluate_rows.py`. Then run `python tools/refresh_results.py`.

## Coming next

- Viewers with very little history still get the weakest picks (see Where it's wrong).
- Run the decision-time test with 20+ people.
- Split `app.py` into modules.
- Product: a For Critics tab, "Only my services" mode, thumbs up or down on Seen movies, and adding likes from the Showroom.

## Stack

Python · Streamlit · scikit-learn · NumPy · SciPy · MovieLens · TMDB · OMDb
