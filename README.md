# iCinema

[![Tests](https://github.com/ishaannars/iCinema/actions/workflows/tests.yml/badge.svg)](https://github.com/ishaannars/iCinema/actions/workflows/tests.yml)

I kept spending too much time deciding what to watch, so I built iCinema: one place to find your next favorite movie. You like a few movies and answer a few questions, and it picks what you'll love, shows where to watch it tonight, and gets better the more you use it (tested: picks from 50 choices beat picks from 3, on viewers no earlier test touched). It's tested to work for less mainstream likes too, and it needs no account.

<!-- RECRUITER-TOP -->
**[Try iCinema →](https://icinema.streamlit.app/)**

## Results

- From **3 random likes**, the first pick was a movie the viewer later rated 4+ stars **8.0%** of the time, compared with **5.4%** for the most popular movie (**+48%**), on 3,000 MovieLens viewers it never saw.
- That beat the old model by **+83%** on the first pick, and it found a loved movie **13 recommendations sooner** than popularity (median 19 vs 32).
- For viewers with **less mainstream likes**, ranking quality rose **8%** and nobody else got worse. This held on 39,805 brand-new viewers from a separate slice of MovieLens.
- **It gets better the more you use it.** Picks from 50 choices beat picks from 3 (NDCG@10 +0.016, interval +0.014 to +0.018) on viewers no earlier test touched. The first version of this test failed, so the claim waited for a fresh one.
- **Its love chance is honest.** When it says about 75%, viewers who watched those movies loved them about 75% of the time (calibration error under 1 point).
- **Hidden Gems has real evidence.** Ranking less-known movies with the shipped model put a movie the viewer later loved in the top 10 **2.7 times as often** as the most popular less-known movies (11.0% vs 4.1%).

## What I learned

My first headline was +58%, but it came from each viewer's 3 most recent likes. Recent likes sit right next to what someone watches next, so that test was too easy. With 3 random likes, the old SVD model did worse than recommending what's popular. I benchmarked the standard recommenders on the honest test, and item-kNN won by a wide margin.

Then the error analysis showed viewers with less mainstream likes got the worst picks. Penalizing popular movies, ALS, EASE, and blends all made things worse for them. RP3beta, a random-walk model that discounts popularity a little, was the one fix that helped. Its first test was too small to call, so I confirmed it on fresh viewers. It also dipped mainstream viewers slightly, so I tested routing (RP3beta for less mainstream likes, item-kNN otherwise) on a brand-new set of viewers. Routing beat both models used alone, so that's what ships. Testing the blend weights the same way moved the app from 65% content to 20%.

I also tested my own product claims. "Gets better the more you use it" failed its first test, so I took it out of the app and retested on fresh viewers before putting it back. Every claim on the home page now points to a test in this repo, and `python reproduce.py` rebuilds all of them.

## How it works

`candidate retrieval → "viewers like you" score + content score → personalized ranking → diversity reranking → your feedback → personal model`

- **Viewers like you.** Trained on 15.8 million 4+ star ratings from 198,954 viewers across 14,407 movies. Item-kNN ranks movies for most viewers and finds movies similar to one you watched, for What's next and "Loved by fans of …". If your likes are less-loved movies, RP3beta ranks instead: a walk from your likes to the people who loved them and on to what else they loved, with popular movies discounted slightly. Skips and "Not for me" push movies down.
- **Content.** Each movie's MovieLens genres and fan tags become a 64-number description (TF-IDF, then truncated SVD), the same recipe the offline tests used. TMDB is used only to show titles, posters, and where to watch.
- **Personal model.** After 50 Save/Skip outcomes, logistic regression learns from your own choices. Gradient boosting is compared at 100, and the better one on a chronological holdout is used.
- **Your feedback.** Saves, skips, "Not for me," and "Loved it" or "Not for me" on Seen movies all update your picks. "What I like has changed" on the Profile keeps your likes and drops older saves and skips, and returning viewers see how many picks are new since their last visit.
- **Bring your history.** Step 1 can import a Letterboxd or IMDb ratings export: 4 stars become Likes and 4.5 or 5 become Favorites, the same 4+ stars the models treat as "loved." Low and middling ratings are read only if a pre-registered test showed they help. The file stays in your browser.
- **A learned ranker.** One gradient-boosted model weighs six others (the routed ranking, item-kNN, RP3beta, EASE, content, popularity). It replaced the fixed 80/20 mix only because it beat it on 3,000 held-out viewers (`training/confirm_ltr.py`), and the Profile shows how much each model counts.
- **When can I stream it?** Movies still in theaters show labeled estimates for renting at home and streaming, from Omdia's 2025 averages for U.S. wide releases (39 days to rent, 95 to stream; Disney about 62 to rent).
- **New releases.** MovieLens stops around 2023, so a second model places newer movies by open Wikidata facts (director, cast, studio, genre, country), learned from where known movies sit among their fans. It ships only if hidden movies land next to their real closest movies better than genres alone (`training/confirm_new_releases.py`).
- **Mood search.** One box on the Showroom ("slow-burn, twist ending") re-orders Top Matches by a 50/50 mix of fit and match, using only the tags MovieLens fans wrote. It ships only if words from taggers the index never saw find the movie (`training/confirm_mood.py`).
- **Asking about the right movies.** Which movies Step 1 shows decides how much a few Likes reveal. Research on new users found that balancing how well known a movie is with how much people disagree about it beats asking about the most popular ones. Popular movies still anchor the shelf, since most people have seen them and most viewers watch them, so only middle grounds can replace today's shelf: every other card is one of the most popular movies, alternating with a more revealing pick. A new shelf ships only if the first screen stays as easy to answer and mainstream viewers don't lose out (`training/confirm_shelf_and_imports.py`). For viewers with many likes, a separate test decides whether EASE, best from full histories in the benchmark, ranks their picks (`training/confirm_history_routing.py`).
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
| **RP3beta (beta 0.3), top-100 per movie (shipped for less mainstream likes)** | 7.7% | 0.077 | 11.0% | 7.6% | 5 MB |
| **Routed: RP3beta for less mainstream likes, item-kNN otherwise (what the app does)** | 8.0% | 0.079 | 13.1% | 8.5% | 10 MB |

1 in 5 MovieLens 32M users: 39,786 viewers, 8,014 movies, 3,115,576 ratings of 4+ stars. Settings were picked on 3,000 validation viewers and scored once on 3,000 different test viewers. From `training/benchmark_cf.py`.
<!-- CF_BENCHMARK:END -->

## Every part tested

<!-- TESTED:START -->
| Part | Test | Result | In the app |
|---|---|---|---|
| Viewers like you | 9 models, 3 random likes, 3,000 test viewers | item-kNN won: 7.9% first-pick hits vs 5.4% popularity and 4.4% old SVD | ✅ item-kNN for most viewers |
| Less mainstream likes | 12 fixes for popularity bias (popularity penalties, ALS, EASE, blends, RP3beta), then a fresh check on 33,786 untouched viewers | RP3beta (beta 0.3) lifted niche viewers' NDCG +0.0071 (95% CI +0.0045 to +0.0097) with no loss overall (-0.0005, CI -0.0016 to +0.0007). Every other fix made things worse | ✅ Used for less mainstream likes (see routing) |
| Routing between the two | RP3beta for less mainstream likes, item-kNN otherwise, on 39,805 brand-new viewers (a separate slice of MovieLens, models rebuilt, nothing tuned) | Beat RP3beta for everyone (NDCG +0.0026, CI +0.0017 to +0.0035) and item-kNN for everyone (+0.0014, CI +0.0008 to +0.0019) | ✅ What the app does |
| Content vs viewers like you | Every weight from 0% to 100% content | 20% content was best (NDCG 0.075 vs 0.061 at the old 65%). With no floor, 0% was best | ✅ 20% content, 80% viewers like you |
| Every onboarding step (Steps 1–3) | The app's own scoring, with each viewer's Step 2–3 answers filled in from their history | At 20% content, Steps 2–3 didn't move hit rates (NDCG -0.001, 95% CI -0.003 to +0.000). 20% content was best on validation (NDCG 0.0853 vs 0.0841 with no content) | ✅ Kept at 20%, so your answers count at no cost |
| More content for niche likes (on top of RP3beta) | Viewers whose 3 likes are less-loved movies (745 test viewers) | The current 20% was already best for them on validation | No change needed |
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
| Love chance | "If you watch it, how likely are you to love it?" Isotonic calibration on 40,581 later ratings from 2,812 test viewers | Calibration error 0.7 points, AUC 0.58, Brier -0.0071 vs guessing the average (CI -0.0087 to -0.0055). Top-1% picks: 73% loved once watched | ✅ Shown on cards |
| Learns as you use it | Picks from 3 to 50 of a viewer's loves (1,125 test viewers) | NDCG@10 0.093 with 3 choices, 0.099 with 10, 0.106 with 50 (10 vs 3: +0.0051, CI -0.0020 to +0.0114) | ❌ Not claimed |
| Learns as you use it, fresh test | 50 vs 3 choices on 14,687 viewers from a slice no earlier test used | NDCG@10 0.099 → 0.115 (+0.0157, CI +0.0136 to +0.0178) | ✅ Claim allowed |
| Fit floor | Where a pick stops being more likely than average to be loved, read from the love-chance table | Top 23.3%. Rows (except Top Matches) leave out weaker picks instead of padding | ✅ Applied to rows |
| Many likes (Letterboxd import) | EASE takes over at N likes; N picked on half of a fresh slice, confirmed on the other half (rule in `training/confirm_history_routing.py`) | Viewers with 10+ likes: NDCG@10 0.096 → 0.113 (95% CI +0.015 to +0.018), 18,620 fresh viewers | ✅ Ships |
| Step 1 shelf | Which movies to ask about: today's popular shelf vs popular anchors alternating with more revealing picks; picked on half, confirmed on the other half with guardrails for easy answers and mainstream viewers (rule in `training/confirm_shelf_and_imports.py`) | popular + HELF vs popularity: NDCG@10 +0.0012 (95% CI +0.0005 to +0.0021); first screen answerable +0.6 points; mainstream viewers +0.0009 (CI +0.0000 to +0.0017); 39,765 fresh viewers | ✅ Ships |
| Imported low ratings | 2 stars or less read as Not for me (weight -0.8, no tuning) | NDCG@10 -0.0003 for 32,563 viewers with such ratings (95% CI -0.0010 to +0.0003) | ❌ Not used |
| Imported middling ratings | 2.5 to 3.5 stars read as Seen (weight 0.5, no tuning) | NDCG@10 -0.0031 for 38,914 viewers with such ratings (95% CI -0.0036 to -0.0027) | ❌ Not used |
| New releases | Movies with fan data hidden; facts (director, cast, studio, genre, country) must place them next to their real closest movies better than genres alone and than popular movies (rule in `training/confirm_new_releases.py`) | Recall@20 0.097 vs 0.022 (genres) and 0.010 (popular), 1,427 hidden movies | ✅ Ships |
| Mood search | Three words from taggers the index never saw must find the movie in the top 50 of all movies (rule in `training/confirm_mood.py`) | Recall@50 0.637 vs 0.005 for popular movies, 2,000 searches | ✅ Ships |
| Learning to rank | Gradient-boosted trees re-rank each viewer's top 300 using every model's score; trained on 3,000 viewers, judged on 3,000 others (rule in `training/confirm_ltr.py`) | NDCG@10 0.0800 vs 0.0759 today (95% CI +0.0007 to +0.0076); biggest inputs: routed 46%, popularity 27%, content 13% | ✅ Ships |
| TV shows | Amazon Reviews 2023 fans; held-out people's loved movies alone must rank the shows they loved above the most popular shows (rule in `training/confirm_tv.py`) | NDCG@20 0.057 vs 0.056, 5,000 held-out people, 8,120 shows | ❌ Not shipped |
| Routing, live | Team-draft interleaving in Top Matches for viewers with less mainstream likes, first 200 decided visits, two-sided binomial test (rule in `src/interleave.py`) | Running: 0 of 200 decided visits. No result is read before then | Running |
| Fourth row follows Step 3 | Not an accuracy question | Recent Releases, Classics, Documentaries, or International Films become the fourth row when picked. Each shows only its own kind | Design choice |

MovieLens has no onboarding answers, so Step 2–3 answers were filled in from each viewer's own history. Content and personal match always keep at least 20%, so your answers always count. From the scripts in `training/`.
<!-- TESTED:END -->

## Where it's wrong

<!-- ERRORS:START -->
First-pick hit rate for the shipped model from 3 random likes (7.7% overall).

- **Viewers with little history are hardest.** 3.2% for viewers with 3–10 liked movies, 13.3% for 100+. They have fewer later favorites to hit.
- **Niche likes is hardest.** 4.3% for viewers whose later favorites were the least popular movies, 12.7% for the most popular. Movies with few fans have fewer neighbors to draw on.
- New movies that aren't in MovieLens get no "viewers like you" score, so content alone ranks them.
<!-- ERRORS:END -->

## Live test

Offline wins don't always hold up with real people, so routing is also being tested live. Routing only changes the ranking for viewers whose likes are less mainstream, so that's who the test covers. For them, Top Matches mixes picks from the routed ranking and from item-kNN alone (team-draft interleaving). Each card is credited to the ranker that picked it, and whichever earns more saves in a visit wins that visit. I chose interleaving over an A/B test because each viewer is their own control. Teams at Netflix and Microsoft report it needs far fewer users to detect the same difference. It measures engagement within a visit. Long-term retention needs an A/B test once there's enough traffic.

The rule was written before launch, in `src/interleave.py`: the first 200 decided visits, a two-sided binomial test at 0.05, skips and "Not for me" as guardrails, and no peeking. The report shows progress only until all 200 are in.

<!-- LIVE_TEST:START -->
**Running: 0 of 200 decided visits. No result is read before then.**

0 visits have had interleaving on so far. Only visits where one ranker earned more saves count.
<!-- LIVE_TEST:END -->

## Beyond accuracy

Hit rates don't show whether a model keeps recommending the same famous movies. This table shows how much of the catalog each model reaches, how well known its picks are, and how varied a top 10 is.

<!-- BEYOND:START -->
| Model | Catalog reached | Popularity of picks (0 = least known, 100 = most) | Variety in a top 10 |
|---|---|---|---|
| Popularity | 0.8% | 99.9 | 0.80 |
| item-kNN | 14.2% | 98.4 | 0.75 |
| RP3beta | 17.9% | 97.5 | 0.78 |
| **Routed (what the app does)** | 17.5% | 97.7 | 0.76 |

Routed vs item-kNN: popularity of picks -0.74 (95% CI -0.96 to -0.53), variety +0.0103 (CI +0.0083 to +0.0124). Top 10 for the benchmark's 3,000 test viewers from 3 random likes, across 8,014 movies. Descriptive only: nothing was tuned on these numbers. From `training/evaluate_beyond_accuracy.py`.
<!-- BEYOND:END -->

## How iCinema compares

Checked October 2026. iCinema doesn't claim to be the only option.

| Option | What it gives you | What iCinema adds |
|---|---|---|
| JustWatch | Search across streaming services and recommendations based on what people like you watch, free with no account for the basics | One pick for tonight, a published accuracy benchmark, and a personal model that learns from your saves and skips in your browser |
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
| Routed: RP3beta (beta 0.3) for less mainstream likes (full history) | 0.100 | 0.089 | 8.50% | 17 |
| Routed: RP3beta (beta 0.3) for less mainstream likes (3 random likes, like onboarding) | 0.090 | 0.079 | 8.03% | 19 |

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

- **Hybrid score.** Content and "viewers like you" are blended with the tested weights above. Each Showroom row adds its own goal: Critically Acclaimed (30% ratings), Hidden Gems (28% less popular but well rated), and Something Different (32% novelty). Top Matches is strictly your best fits. During the live test, for viewers with less mainstream likes, it interleaves the best fits from two rankers and keeps the drafted order.
- **Personal model.** It contributes 22% of the score. Recent choices weigh more (120-day half-life), and display position is left out so being shown isn’t mistaken for liking something.
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

To rebuild every model and number with one command, download MovieLens 32M into `ml-32m/` and run `python reproduce.py --data-dir ml-32m`. It runs each script in `training/` in order (the list is at the top of `reproduce.py`), then `tools/refresh_results.py`. The live test is scored with `python tools/interleave_report.py --api`.

## Coming next

- Optional sign-in after your first save, so your profile follows you across devices, with one-tap delete.
- TV shows in the same rows, with a Movies · Shows · Both switch.
- A For Critics tab, an "Only my services" mode, and adding likes from the Showroom anytime.
- Run the decision-time test with 20+ people, and keep splitting `app.py`.

## Stack

Python · Streamlit · scikit-learn · NumPy · SciPy · MovieLens · TMDB · OMDb

## Data and credits

- **MovieLens 32M** trains "viewers like you" and the content model (genres and fan tags). Used under the GroupLens research license, non-commercial. F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context. *ACM Transactions on Interactive Intelligent Systems* 5(4): 19:1–19:19.
- **TMDB** supplies titles, posters, and descriptions, used for display only. No model is trained on TMDB content. This product uses the TMDB API but is not endorsed or certified by TMDB.
- **JustWatch** supplies where-to-watch data, through TMDB.
- **OMDb** supplies IMDb and Rotten Tomatoes scores.

iCinema is a free, non-commercial project. © 2026 Ishaan Narasimhan. All rights reserved.
