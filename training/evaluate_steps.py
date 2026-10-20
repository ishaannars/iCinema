"""Test the full iCinema score, with every onboarding step, against "viewers like you" alone.

    python training/evaluate_steps.py --data-dir ml-32m

evaluate_blends.py scored content from liked movies only. The app's content score also uses
Step 2 (genres, reviews vs enjoyment, openness) and Step 3 (what to see more of). Here those
answers are filled in for each MovieLens viewer from their own earlier ratings, the way they'd
likely answer, and scored with the app's real code (src/recommender.py):
- Step 1: 3 random liked movies.
- Step 2 genres: the viewer's 3 most-liked genres. Reviews vs enjoyment: from how highly rated
  their liked movies are. Openness: how often they like movies outside those genres.
- Step 3: Hidden Gems, Classics, Recent Releases, Documentaries, or Critically Acclaimed when
  their liked movies lean that way.
Movies get the app's fields from MovieLens: genres, tags mapped to the app's tone traits,
average rating and rating count as audience score, and fan count as popularity.

Rule written before running: each viewer is ranked over a shared candidate pool (the top 300
"viewers like you" picks plus the 200 most-liked movies in their Step 2 genres). The content
weight is picked on 3,000 validation viewers and scored once on 3,000 test viewers. The app's
weight changes only if the pick beats the current weight on test by a paired-bootstrap
interval above zero. Writes data/steps_results.json.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_knn, matrix  # noqa: E402
from evaluate_blends import content_embeddings  # noqa: E402
from train_cf import metrics, paired_bootstrap, time_split  # noqa: E402
from src.recommender import GENRES, build_profile, score_movie_components  # noqa: E402

GRID = [0.0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0]
# Content parts the app computes. Step 1 feeds genre, tone, and theme; Step 2 feeds quality
# (reviews vs enjoyment) and discovery (openness) and genres; Step 3 feeds priority.
PARTS = ["genre_affinity", "trait_affinity", "semantic_similarity", "quality_alignment",
         "discovery_alignment", "priority_alignment", "popularity_normalized"]
CURRENT = 0.20  # content weight in the app after evaluate_blends.py
TRAIT_TAGS = {
    "suspense": "Suspenseful", "suspenseful": "Suspenseful", "thought-provoking": "Thought-provoking",
    "philosophical": "Thought-provoking", "character study": "Character-driven", "fast paced": "Fast-paced",
    "emotional": "Emotional", "tearjerker": "Emotional", "dark": "Dark", "funny": "Funny", "hilarious": "Funny",
    "visually appealing": "Visually striking", "visually stunning": "Visually striking",
    "beautiful cinematography": "Visually striking", "cerebral": "Cerebral", "intellectual": "Cerebral",
    "twist ending": "Unpredictable", "plot twist": "Unpredictable", "heartwarming": "Heartfelt",
    "feel-good": "Heartfelt", "slow": "Slow-burn", "stylish": "Stylish", "stylized": "Stylish",
    "quirky": "Offbeat", "surreal": "Offbeat", "romantic": "Romantic", "intense": "Intense",
    "lighthearted": "Lighthearted", "epic": "Epic", "realistic": "Grounded", "psychological": "Psychological",
    "nostalgic": "Nostalgic", "satire": "Satirical", "satirical": "Satirical", "tense": "Tense",
    "touching": "Moving", "moving": "Moving",
}
ML_TO_APP = {g: g for g in GENRES}


def app_movies(data_dir, pos, user_mod):
    d = Path(data_dir)
    movies = pd.read_csv(d / "movies.csv").set_index("movieId")
    sums, counts = Counter(), Counter()
    for ch in pd.read_csv(d / "ratings.csv", chunksize=4_000_000, usecols=["userId", "movieId", "rating"]):
        ch = ch[ch["userId"] % user_mod == 0]
        g = ch.groupby("movieId")["rating"].agg(["sum", "count"])
        sums.update(g["sum"].to_dict()); counts.update(g["count"].to_dict())
    tags = pd.read_csv(d / "tags.csv", usecols=["movieId", "tag"]).dropna()
    tags["tag"] = tags["tag"].astype(str).str.lower().str.strip()
    tags = tags[tags["tag"].isin(TRAIT_TAGS)]
    tc = tags.groupby(["movieId", "tag"]).size()
    traits = {}
    for (mid, tag), n in tc.items():
        if n >= 3:
            traits.setdefault(mid, set()).add(TRAIT_TAGS[tag])
    item_movie = pos.drop_duplicates("item").set_index("item")["movieId"].sort_index()
    fans = np.bincount(pos["item"], minlength=len(item_movie))
    med = float(np.median(fans[fans > 0]))
    out = []
    for item, mid in item_movie.items():
        row = movies.loc[mid] if mid in movies.index else None
        gs = [ML_TO_APP[g] for g in (row["genres"].split("|") if row is not None else []) if g in ML_TO_APP]
        title = str(row["title"]) if row is not None else ""
        year = int(title[-5:-1]) if title.endswith(")") and title[-5:-1].isdigit() else 0
        n = counts.get(mid, 0)
        out.append({"title": f"ml{mid}", "year": year, "genre": gs[0] if gs else None,
                    "tags": gs[1:] + sorted(traits.get(mid, ())),
                    "tmdb_vote": 2 * sums[mid] / n if n else None, "tmdb_vote_count": n,
                    "popularity": 20.0 * fans[item] / med, "original_language": "en"})
    return out


def answers(hist, movies, cuts):
    gs = Counter(movies[i]["genre"] for i in hist if movies[i]["genre"])
    top = [g for g, _ in gs.most_common(3)]
    q = np.mean([movies[i]["tmdb_vote"] or 6.5 for i in hist])
    outside = np.mean([movies[i]["genre"] not in top for i in hist])
    pops = np.median([movies[i]["popularity"] for i in hist])
    years = np.median([movies[i]["year"] for i in hist if movies[i]["year"]] or [2000])
    docs = np.mean([movies[i]["genre"] == "Documentary" for i in hist])
    review = 25 if q >= cuts["q_hi"] else 75 if q <= cuts["q_lo"] else 50
    adventure = 75 if outside >= cuts["o_hi"] else 25 if outside <= cuts["o_lo"] else 50
    more = [name for name, ok in (("Hidden Gems", pops <= cuts["pop_lo"]), ("Classics", years <= 1995),
                                  ("Recent Releases", years >= 2015), ("Documentaries", docs >= 0.1),
                                  ("Critically Acclaimed", q >= cuts["q_top"])) if ok]
    return top, review, adventure, more


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--user-sample", type=int, default=5)
    args = ap.parse_args()
    pos, n_items = load_sample(args.data_dir, args.user_sample, 20)
    train, test = time_split(pos)
    X = matrix(train, n_items)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    eligible = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]
    picked = np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False)
    val, tst = list(picked[:N_EVAL]), list(picked[N_EVAL:])
    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    knn, _ = m_knn(X, float(bench["results"]["item-kNN"]["params"][0]), top=100)
    E = content_embeddings(args.data_dir, pos)
    movies = app_movies(args.data_dir, pos, args.user_sample)
    extra = {m["title"]: m for m in movies}
    # Cut points for the simulated answers come from training-period histories only.
    qs = [np.mean([movies[i]["tmdb_vote"] or 6.5 for i in tb[u]]) for u in val]
    os_ = [np.mean([movies[i]["genre"] not in [g for g, _ in Counter(movies[j]["genre"] for j in tb[u] if movies[j]["genre"]).most_common(3)]
                    for i in tb[u]]) for u in val]
    ps = [np.median([movies[i]["popularity"] for i in tb[u]]) for u in val]
    cuts = {"q_hi": np.quantile(qs, 2 / 3), "q_lo": np.quantile(qs, 1 / 3), "q_top": np.quantile(qs, 0.8),
            "o_hi": np.quantile(os_, 2 / 3), "o_lo": np.quantile(os_, 1 / 3), "pop_lo": np.quantile(ps, 0.25)}
    genre_items = {g: [i for i in np.argsort(-X.getnnz(axis=0)) if movies[i]["genre"] == g][:200] for g in GENRES}
    print("data ready", flush=True)

    def features(users, seed=5):
        """Per viewer: candidate pool, CF affinity, content with all steps, content from likes only, truth."""
        rng = np.random.default_rng(seed)
        out = []
        for u in users:
            hist = tb[u]
            seeds = [hist[i] for i in sorted(rng.choice(len(hist), 3, replace=False))]
            top, review, adventure, more = answers(hist, movies, cuts)
            raw = knn(np.asarray(seeds)).astype(np.float64)
            raw[hist] = -np.inf
            pool = set(np.argpartition(-raw, 300)[:300].tolist())
            for g in top[:2]:
                pool.update(genre_items.get(g, [])[:100])
            pool = [i for i in pool if i not in set(hist)]
            posv = np.sort(raw[np.isfinite(raw) & (raw > 0)])
            cf = np.array([0.5 + 0.5 * np.searchsorted(posv, raw[i], side="right") / len(posv) if raw[i] > 0 and len(posv) else 0.5
                           for i in pool])
            sem_vec = E @ E[seeds].mean(axis=0)
            likes = {movies[i]["title"] for i in seeds}
            full_p = build_profile(likes, set(), top, review, more, adventure=adventure, extra_movies=extra)
            likes_p = build_profile(likes, set(), [], 50, [], adventure=50, extra_movies=extra)
            sem = (sem_vec[pool] + 1) / 2
            comps = [score_movie_components(movies[i], full_p, adventure, review, semantic_similarity=s)
                     for i, s in zip(pool, sem)]
            full = np.array([c["raw_score"] for c in comps])
            parts = np.array([[c[k] for k in PARTS] for c in comps])
            only_likes = np.array([score_movie_components(movies[i], likes_p, 50, 50, semantic_similarity=s)["raw_score"]
                                   for i, s in zip(pool, sem)])
            out.append((np.asarray(pool), cf, full, only_likes, te[u], parts))
        return out

    def score(feats, w, content="full"):
        res = []
        for pool, cf, full, only_likes, truth, _ in feats:
            c = full if content == "full" else only_likes
            s = w * c + (1 - w) * cf
            order = pool[np.argsort(-s)][:50]
            res.append(metrics(order, truth))
        return np.asarray(res, dtype=float)

    fv = features(val)
    print("validation features ready", flush=True)
    val_ndcg = {w: float(score(fv, w)[:, 1].mean()) for w in GRID}
    best = max(val_ndcg, key=val_ndcg.get)
    ft = features(tst)
    r_best, r_cur = score(ft, best), score(ft, CURRENT)
    d, lo, hi, _ = paired_bootstrap(r_best[:, 1], r_cur[:, 1], np.mean)
    r_cf, r_full, r_likes = score(ft, 0.0), score(ft, 1.0), score(ft, 1.0, "likes")
    r_cur_likes = score(ft, CURRENT, "likes")
    sd, slo, shi, _ = paired_bootstrap(r_cur[:, 1], r_cur_likes[:, 1], np.mean)
    # Learned ranker: logistic regression on "viewers like you" plus every content part,
    # fit on validation viewers (loved later = 1) and scored once on test viewers.
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    def design(feats, cols):
        Xs, ys = [], []
        for pool, cf, _, _, truth, parts in feats:
            Xs.append(np.column_stack([cf, parts])[:, cols]); ys.append(np.isin(pool, list(truth)).astype(int))
        return Xs, ys

    def learned(cols):
        Xv, yv = design(fv, cols)
        sc = StandardScaler().fit(np.vstack(Xv))
        lr = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(sc.transform(np.vstack(Xv)), np.concatenate(yv))
        Xt, _ = design(ft, cols)
        res = []
        for (pool, _, _, _, truth, _), x in zip(ft, Xt):
            order = pool[np.argsort(-lr.decision_function(sc.transform(x)))][:50]
            res.append(metrics(order, truth))
        names = (["viewers_like_you"] + PARTS)
        return np.asarray(res, dtype=float), {names[c]: round(float(w), 3) for c, w in zip(cols, lr.coef_[0] / sc.scale_)}, sc, lr

    all_cols = list(range(1 + len(PARTS)))
    r_learn, coefs, _, _ = learned(all_cols)
    step1_cols = [0, 1, 2, 3, 7]   # CF, genre, tone, theme, popularity: no Step 2-3 parts
    r_learn_s1, _, _, _ = learned(step1_cols)
    ld, llo, lhi, _ = paired_bootstrap(r_learn[:, 1], r_cur[:, 1], np.mean)
    cd, clo, chi, _ = paired_bootstrap(r_learn[:, 1], r_cf[:, 1], np.mean)
    s23, s23lo, s23hi, _ = paired_bootstrap(r_learn[:, 1], r_learn_s1[:, 1], np.mean)
    learned_out = {"test": {"hit@1": round(float(r_learn[:, 2].mean()), 4), "ndcg@10": round(float(r_learn[:, 1].mean()), 4)},
                   "vs_current": {"ndcg_diff": round(ld, 4), "ci95": [round(llo, 4), round(lhi, 4)]},
                   "vs_viewers_like_you_only": {"ndcg_diff": round(cd, 4), "ci95": [round(clo, 4), round(chi, 4)]},
                   "steps_2_3_value_inside_learned": {"ndcg_diff": round(s23, 4), "ci95": [round(s23lo, 4), round(s23hi, 4)]},
                   "coefficients_per_unit": coefs,
                   "ships": bool(llo > 0 and clo > 0)}
    out = {
        "learned_ranker": learned_out,
        "method": " ".join(__doc__.split("\n\n")[1:4]).replace("\n", " "),
        "validation_ndcg_by_content_weight": {str(k): round(v, 4) for k, v in val_ndcg.items()},
        "best_content_weight": best, "current_content_weight": CURRENT,
        "test": {"best": {"hit@1": round(float(r_best[:, 2].mean()), 4), "ndcg@10": round(float(r_best[:, 1].mean()), 4)},
                 "current": {"hit@1": round(float(r_cur[:, 2].mean()), 4), "ndcg@10": round(float(r_cur[:, 1].mean()), 4)},
                 "viewers_like_you_only": {"hit@1": round(float(r_cf[:, 2].mean()), 4), "ndcg@10": round(float(r_cf[:, 1].mean()), 4)},
                 "content_all_steps_only": {"hit@1": round(float(r_full[:, 2].mean()), 4), "ndcg@10": round(float(r_full[:, 1].mean()), 4)},
                 "content_likes_only": {"hit@1": round(float(r_likes[:, 2].mean()), 4), "ndcg@10": round(float(r_likes[:, 1].mean()), 4)}},
        "ndcg_diff_vs_current": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)],
        "change": bool(best != CURRENT and lo > 0),
        "steps_2_3_value": {"ndcg_diff_all_steps_vs_likes_only": round(sd, 4), "ci95": [round(slo, 4), round(shi, 4)]},
    }
    (ROOT / "data" / "steps_results.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
