# iCinema

[![Tests](https://github.com/ishaannars/iCinema/actions/workflows/tests.yml/badge.svg)](https://github.com/ishaannars/iCinema/actions/workflows/tests.yml)

**Every service. Ranked for you.** iCinema brings together what's on the services you pay for, ranks it around what you like, and gets sharper with every save and skip. Ten tested recommendation models, plus a calibrated model for the odds. First pick loved 48% more often than the most popular movie, and 39% more loved movies in each row, on 3,000 movie fans the models never saw. No account needed.

I built iCinema because I had this recurring problem of spending too much time deciding what to watch. Every model in it was tested on viewers it had never seen before it shipped, and the ones that didn't beat a simple baseline are reported below too.

**[Try iCinema →](https://icinema.streamlit.app/)**

| At a glance | |
|---|---|
| Problem | US viewers spend about 12 minutes per session deciding what to watch, up from 10.5 in 2023 (Gracenote, a Nielsen company, *State of Play* 2025). |
| What it does | Two quick steps, then one best pick tonight on your services, with a calibrated chance you'll love it. Search by mood, length, or a movie. |
| Proof | First pick loved by 80 in 1,000 test viewers vs 54 in 1,000 for the most popular movie (+48%), on 3,000 MovieLens viewers it never saw. |
| Models | Ten recommendation models plus a calibrated model for the odds, each kept only if it beat a simpler baseline on held-out viewers. The losses are in [What I tried that lost](#what-i-tried-that-lost). |
| Stack | Python · Streamlit · NumPy · SciPy · scikit-learn · MovieLens 32M · Amazon Reviews 2023 · Wikidata · TMDB (display only) |

## Results

- From **3 random likes**, the first pick was a movie the viewer later rated 4+ stars **8.0%** of the time, compared with **5.4%** for the most popular movie (**+48%**), on 3,000 MovieLens viewers it never saw.
- That beat the old model by **+83%** on the first pick, and it found a loved movie **13 recommendations sooner** than popularity (median 19 vs 32).
- For viewers with **less mainstream likes**, ranking quality rose **8%** and nobody else got worse. This held on 39,805 brand-new viewers from a separate slice of MovieLens.
- **It gets better the more you use it.** Picks from 50 choices beat picks from 3 (NDCG@10 +0.016, interval +0.014 to +0.018) on viewers no earlier test touched. The first version of this test failed, so the claim waited for a fresh one.
- **The models’ odds hold up.** When they say about 75%, viewers who watched those movies loved them about 75% of the time (calibration error under 1 point).
- **Hidden Gems has real evidence.** Ranking less-known movies with the shipped model put a movie the viewer later loved in the top 10 **2.7 times as often** as the most popular less-known movies (11.0% vs 4.1%).

## What I learned

My first headline was +58%, but it came from each viewer's 3 most recent likes. Recent likes sit right next to what someone watches next, so that test was too easy. With 3 random likes, the old SVD model did worse than recommending what's popular. I benchmarked the standard recommenders on the honest test, and item-kNN won by a wide margin.

Then the error analysis showed viewers with less mainstream likes got the worst picks. Penalizing popular movies, ALS, EASE, and blends all made things worse for them. RP3beta, a random-walk model that discounts popularity a little, was the one fix that helped. Its first test was too small to call, so I confirmed it on fresh viewers. It also dipped mainstream viewers slightly, so I tested routing (RP3beta for less mainstream likes, item-kNN otherwise) on a brand-new set of viewers. Routing beat both models used alone, so that's what ships. Testing the blend weights the same way moved the app from 65% content to 20%.

I also tested my own product claims. "Gets better the more you use it" failed its first test, so I took it out of the app and retested on fresh viewers before putting it back. Every claim on the home page now points to a test in this repo, and `python reproduce.py` rebuilds all of them.

## How it works

`candidate retrieval → "viewers like you" score + content score → learned ranker → row rules and fit floor → your feedback → personal model`

- **Viewers like you.** Trained on 15.8 million 4+ star ratings from 198,954 viewers across 14,407 movies. Item-kNN ranks movies for most viewers and finds movies similar to one you watched, for What's next and "Loved by fans of …". If your likes are less-loved movies, RP3beta ranks instead: a walk from your likes to the people who loved them and on to what else they loved, with popular movies discounted slightly. Skips and "Not for me" push movies down.
- **Content.** Each movie's MovieLens genres and fan tags become a 64-number description (TF-IDF, then truncated SVD), the same recipe the offline tests used. TMDB is used only to show titles, posters, and where to watch.
- **Personal model.** After 50 Save/Skip outcomes, logistic regression learns from your own choices. Gradient boosting is compared at 100, and the better one on a chronological holdout is used.
- **Your feedback.** Saves, skips, "Not for me," and "Loved it" or "Not for me" on Seen movies all update your picks. "What I like has changed" on the Profile keeps your likes and drops older saves and skips, and returning viewers see how many picks are new since their last visit.
- **Bring your history.** Step 1 can import a Letterboxd or IMDb ratings export: 4 stars become Likes and 4.5 or 5 become Favorites, the same 4+ stars the models treat as "loved." Low and middling ratings are read only if a pre-registered test showed they help. The file stays in your browser.
- **A learned ranker.** One gradient-boosted model weighs six others (the routed ranking, item-kNN, RP3beta, EASE, content, popularity). It replaced the fixed 80/20 mix only because it beat it on 3,000 held-out viewers (`training/confirm_ltr.py`), and the Profile shows how much each model counts.
- **When can I stream it?** Movies still in theaters show labeled estimates for renting at home and streaming, from Omdia's 2025 averages for U.S. wide releases (39 days to rent, 95 to stream; Disney about 62 to rent).
- **TV shows.** MovieLens has no TV, so shows use Amazon Reviews 2023 (Movies & TV): people who loved your movies, and the shows they loved. The first model tied with "most popular shows" and didn't ship; a blend with popularity (80/20, weight picked on half of a fresh held-out group) beat it by 20% on the other half (`training/confirm_tv_blend.py`). The Showroom is one unified guide like the Apple TV app's Home: Tonight's Show, Top Picks, Shows for You, and More to explore, with no toggles.
- **One search, four states.** Nothing typed, a mood or length, a movie, or "like" a movie. One written rule (`SEARCH_RULE` in `app.py`) decides what every row shows in each state. A movie search puts the movie first with the three movies its fans love most beside it, and Tonight's Show, Top Picks and Shows for You all follow fans of that movie. A row with nothing that fits is hidden, never left empty.
- **"Nothing too violent" is a filter, not a model.** A movie leaves if fans tag it strongly with any word they use for violence (violence, brutal, gore, bloody), or if a rating board lists violence among its official descriptors (for example the Dutch Kijkwijzer, via TMDB); a show leaves if its keywords say so, or its US TV rating carries the V (violence) descriptor (TV-MA counts only when no descriptors are listed, since TV-MA can be for language or sex alone).
- **A mood never lowers the bar.** Within a mood search, movies below a quality line leave first: IMDb 6.3, RT 55% or TMDB 6.3 (7.0 / 75% / 7.0 if you asked for strong reviews or Critically Acclaimed), or, with no scores, outside the top 45% of MovieLens fan favorites. This is a rule, not a tested model, and it only applies when at least four movies still pass.
- **Mood and time in one field.** "funny, under 2 hours": the mood goes to the tested fan-tag model, and the time becomes a runtime filter (episode length for shows), applied to every row while the models keep their order.
- **New releases.** MovieLens stops around 2023, so a second model places newer movies by open Wikidata facts (director, cast, studio, genre, country), learned from where known movies sit among their fans. It ships only if hidden movies land next to their real closest movies better than genres alone (`training/confirm_new_releases.py`).
- **Mood search.** One box on the Showroom ("slow-burn, twist ending") re-orders Top Matches by a 50/50 mix of fit and match, using only the tags MovieLens fans wrote. It ships only if words from taggers the index never saw find the movie (`training/confirm_mood.py`).
- **Asking about the right movies.** Which movies Step 1 shows decides how much a few Likes reveal. Research on new users found that balancing how well known a movie is with how much people disagree about it beats asking about the most popular ones. Popular movies still anchor the shelf, since most people have seen them and most viewers watch them, so only middle grounds can replace today's shelf: every other card is one of the most popular movies, alternating with a more revealing pick. A new shelf ships only if the first screen stays as easy to answer and mainstream viewers don't lose out (`training/confirm_shelf_and_imports.py`). For viewers with many likes, a separate test decides whether EASE, best from full histories in the benchmark, ranks their picks (`training/confirm_history_routing.py`).
- **Every step counts.** Step 1 likes feed both scores. Step 2 (genres, reviews vs enjoyment, openness, and what to see more of) shapes the content score and your Profile. Your “show me more” picks also decide which section comes after Top Matches.
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
| Section order | Not an accuracy question | Your “show me more” picks decide which section comes after Top Matches | Design choice |
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
| TV shows, second try | Fans like you blended with popularity (weight 0.2 picked on half of a fresh held-out group, judged on the other half; rule in `training/confirm_tv_blend.py`) | NDCG@20 0.072 vs 0.060 (95% CI +0.0084 to +0.0159) | ✅ Ships |
| Routing, live | Team-draft interleaving in Top Matches for viewers with less mainstream likes, first 200 decided visits, two-sided binomial test (rule in `src/interleave.py`) | Running: 0 of 200 decided visits. No result is read before then | Running |
| Fourth row follows your picks | Not an accuracy question | Recent Releases, Classics, Documentaries, or International Films become the fourth row when picked. Each shows only its own kind | Design choice |

MovieLens has no onboarding answers, so Step 2–3 answers were filled in from each viewer's own history. Content and personal match always keep at least 20%, so your answers always count. From the scripts in `training/`.
<!-- TESTED:END -->

## Where it's wrong

<!-- ERRORS:START -->
First-pick hit rate for the shipped model from 3 random likes (7.7% overall).

- **Viewers with little history are hardest.** 3.2% for viewers with 3–10 liked movies, 13.3% for 100+. They have fewer later favorites to hit.
- **Niche likes is hardest.** 4.3% for viewers whose later favorites were the least popular movies, 12.7% for the most popular. Movies with few fans have fewer neighbors to draw on.
- New movies that aren't in MovieLens get no "viewers like you" score, so content alone ranks them.
<!-- ERRORS:END -->

## What I tried that lost

Every idea had to beat what was already shipping, on viewers the models never saw, with the rule written before the test ran. These lost, and the app kept the simpler option.

| Idea | Result on held-out viewers | Decision |
|---|---|---|
| "More like X": re-rank fans' picks with genres and fan tags, minus a popularity discount | NDCG@10 0.085 vs 0.099 for fans alone (95% CI −0.017 to −0.011); it lost in every popularity band, niche fans included | Kept fans alone |
| Content model (TF-IDF + SVD) at a fixed 20% of each pick | Adding content did not beat fans alone on validation viewers (`tools/claims_audit.py` reads `data/blend_results.json`) | Kept at 20% on purpose, so your genre and "more of" answers shape picks. A product choice, not an accuracy gain |
| Content with your Step 2 genre answers (20% of each pick) | On 3,000 fresh viewers, picks matched the stated genres far more (94% of the top 10 vs 65%), but NDCG@10 fell 15% (0.070 vs 0.082, 95% CI −0.018 to −0.007). The answers carried real signal (72% of future loves were in those genres vs 63% by chance), so the test counted | Did not earn its 20% as accuracy. Kept for control: your answers visibly steer the picks. A lower weight is a new question for a future test, rule written first |
| Show odds: a calibrated "chance you'll love it" for shows, like movies have | Failed its validity check before odds could count. On 5,000 held-out Amazon reviewers, the show ranking could not tell loved shows from the rest of the shows they rated (AUC 0.498, 95% CI low 0.483). 90% of show ratings were 4+ stars, so there was almost nothing to separate | Show cards show their rank ("#1 for you"), never a percent |
| Hidden Gems row: 28% weight on how little-known a movie is | 1.1% of the row's top 10 were loved, vs 12.5% when your fit decides the order | Fit decides the order |
| Critically Acclaimed row: 30% weight on critics' score | 49.5% vs 52.0% loved in the top 10 with fit deciding the order | Fit decides the order |
| Variety step that spreads out similar movies | Every setting cost 2.6 to 4.1 points of loved-in-top-10 (all significant) | Turned off; a live test can revisit it, since users often prefer variety |
| Content model alone | NDCG@10 0.031, a third of fans alone | Used only inside the blend |
| "Chance you'll love it" on shows | Ranking couldn't tell loved shows from the rest: AUC 0.498 (95% lower bound 0.483) on 5,000 held-out Amazon reviewers. They rated 90% of their shows 4+ stars, so a flat "about 90%" scored a low calibration error (0.5 points) while saying nothing. The validity rule, written before the run, caught it | Show cards show their rank, never a percent |

**Testing many things at once.** With this many tests, one could pass by luck. `tools/multiple_testing.py` applies a Holm-Bonferroni correction across every stored result: 21 of 22 results (wins and the losses above) were significant on their own, and all 21 still are after the correction. The TV model alone (+0.001, p 0.64) was never significant, which is why shows use the tested fans-plus-popularity blend.

**Order of likes (shipped).** A first-order Markov chain over each viewer's time-ordered likes ("what people like next") won both of its pre-registered tests on 3,000 held-out viewers. Main ranking from the 3 most recent likes, blended 80/20 with the shipped fan ranking: NDCG@10 0.127 vs 0.110 (95% CI +0.012 to +0.021), first pick loved 13.9% vs 12.7%. It ranks Top Picks and Tonight's Show. It is now the tenth model; `training/build_sequential.py` built it on all of MovieLens 32M.

**A test it won that didn't ship.** Blended 60/40 with fans, the order model also won a test for "More like X" (NDCG@10 0.105 vs 0.099, CI +0.003 to +0.009). It isn't used there. That test scored whether a pick was what the viewer liked next, but "more like X" asks for movies similar to X. Winning the wrong target doesn't count, so "More like X" ranks by fans' closest movies to X alone, closest first.

## Monitoring and rollback

A GitHub Action runs `tools/canary.py` every Monday. It scores eight fixed viewers and four moods with every shipped model and compares each top 10 with the saved set in `data/canary_expected.json`. If any check keeps fewer than 7 of its 10 titles, or a model fails to load, the job fails, and the last good commit is restored before anything else ships. This exists because a library update once switched the learned ranker off without an error; the canary would have flagged it the same week. After an intentional retrain, `python tools/canary.py --record` saves the new expected set.

## Live test

Offline wins don't always hold up with real people, so routing is also being tested live. Routing only changes the ranking for viewers whose likes are less mainstream, so that's who the test covers. For them, Top Matches mixes picks from the routed ranking and from item-kNN alone (team-draft interleaving). Each card is credited to the ranker that picked it, and whichever earns more saves in a visit wins that visit. I chose interleaving over an A/B test because each viewer is their own control. Teams at Netflix and Microsoft report it needs far fewer users to detect the same difference. It measures engagement within a visit. Long-term retention needs an A/B test once there's enough traffic.

The rule was written before launch, in `src/interleave.py`: the first 200 decided visits, a two-sided binomial test at 0.05, skips and "Not for me" as guardrails, and no peeking. The report shows progress only until all 200 are in.

<!-- LIVE_TEST:START -->

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

<!-- DECISION_TIME:START -->
<!-- DECISION_TIME:END -->

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

## Why this problem

Three questions every project has to pass before it's built. Each one maps to one part of iCinema.

| Question | Evidence | What iCinema does about it |
|---|---|---|
| **Painful?** | US viewers spend 12 minutes deciding what to watch, up from 10.5 in 2023, and the longer it takes, the less they enjoy it. 49% would cancel a service if they can't find something (Gracenote State of Play 2025, 3,000 viewers in six countries). | **Ranked for you:** your best match first, then a Showroom of strong backups, each with the models' odds and why. First pick loved 48% more often; 39% more loved movies per row. |
| **Shared?** | 90% of US households pay for at least one streaming service, about four on average (Deloitte Digital Media Trends 2025). 46% (51% in the US) say the number of services makes it harder; 66% want one guide for all of them (Gracenote 2025). | **All your services:** where every pick is streaming, your apps marked on each card, and a switch to show only what's on them. |
| **Recurring?** | The decision comes back every movie night, and catalogs don't learn. | **Sharper every time:** saves, skips, Seen, and moods train your own model, tested to improve picks as choices add up. |

The people who pay for discovery problems are the streaming services: hard discovery drives cancellations. iCinema stays a free portfolio project; any business would start there.

## Recent test results

- **"More Like X," tuned to your taste: shipped.** On 3,000 held-out viewers, ordering by closeness (80%) plus your fit (20%) beat closeness alone: NDCG@10 0.1019 vs 0.0992 (+2.75%, 95% interval +0.0002 to +0.0053), keeping 98.8% of the closeness. Reported because it matters: the first pick was loved slightly less often (11.1% vs 12.1%); the gain is across the top 10, not the first slot. Weight chosen on separate validation viewers (0.2 vs 0.4 and 0.6).
- **Seen thumbs teaching the personal model: shipped (simulation).** Version 1 "passed" but both arms scored about 0.5 AUC (chance), so it couldn't have detected harm, and I didn't count it. Version 2 gave the simulated personal model real signals and a validity rule set before running (the saves-and-skips model must reach 0.55 AUC). It did: 0.657. Adding Seen thumbs raised AUC to 0.668 (+0.011, 95% interval +0.007 to +0.016) on 2,026 held-out MovieLens viewers, clearing the no-worse rule and landing above zero. It's a simulation until real users exist; thumbs now also teach the personal model.
- **Mood search with meaning: didn't ship.** Adding a word-embedding model (model2vec potion-base-8M) to fan-tag search lowered recall@50 from 63.8% to 59.8% (−3.95 points, 97.5% interval −5.5 to −2.4) and didn't help rare words (53.1% vs 52.5%, interval −3.9 to +2.8). Fans' own tag words beat general word meaning for finding movies, so mood search stays on fan tags.

- **Odds on show cards: didn't ship.** The same calibration that works for movies was tried on shows, with the rule written first. On 5,000 held-out Amazon reviewers the ranking couldn't tell loved shows from the rest (AUC 0.498). Reviewers rated 90% of their shows 4+ stars, because people mostly review what they already chose to watch. A flat "about 90%" would have passed on calibration error alone (0.5 points), which is why a validity check comes first. Show cards keep their rank: the show model does pick which shows fans watch better than popularity, it just can't promise you'll love them.

## Waiting on a test


## Coming next

- A For Critics tab, adding likes from the Showroom anytime, and one-tap links that open a movie straight in its streaming app.
- Run the decision-time test with 20+ people, and keep splitting `app.py`.

## Stack

Python · Streamlit · scikit-learn · NumPy · SciPy · MovieLens · TMDB · OMDb

## Data and credits

- **MovieLens 32M** trains "viewers like you" and the content model (genres and fan tags). Used under the GroupLens research license, non-commercial. F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context. *ACM Transactions on Interactive Intelligent Systems* 5(4): 19:1–19:19.
- **TMDB** supplies titles, posters, and descriptions, used for display only. No model is trained on TMDB content. This product uses the TMDB API but is not endorsed or certified by TMDB.
- **JustWatch** supplies where-to-watch data, through TMDB.
- **OMDb** supplies IMDb and Rotten Tomatoes scores.

iCinema is a free, non-commercial project. © 2026 Ishaan Narasimhan. All rights reserved.
