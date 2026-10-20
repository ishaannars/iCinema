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
