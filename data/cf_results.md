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
