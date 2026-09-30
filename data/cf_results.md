**Offline evaluation** — MovieLens (ml-latest-small), time-based split, 601 held-out users, ratings ≥ 4 as positives.

| Model | Recall@10 | NDCG@10 | Hit@1 (Tonight's Pick) | Median recs to first loved movie |
|---|---|---|---|---|
| Popularity baseline | 0.067 | 0.062 | 7.5% | 33 |
| Collaborative filtering (full history) | 0.079 | 0.066 | 5.2% | 21 |
| Collaborative filtering (only 3 likes, like onboarding) | 0.089 | 0.081 | 9.2% | 22 |
