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
