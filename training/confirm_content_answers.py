"""Does the content model earn its 20% once it carries your Step 2 genre answers?

    python training/confirm_content_answers.py --data-dir ml-32m

Why this test exists: training/evaluate_blends.py showed content did not beat fans alone when it only
saw 3 liked movies. But in the app, content is also the only model that reads your Step 2 answers (the
genres you pick). MovieLens has no Step 2 answers, so that job was never tested. This test simulates it.
The earlier result stays reported in the README either way.

Setup (same MovieLens 32M 1-in-5 sample and time split as evaluate_blends.py, fresh viewers):
- 3,000 viewers drawn with a new seed (53) and none of the viewers evaluate_blends.py used.
- The app sees 3 random liked movies, exactly as before.
- Simulated Step 2 answer: the viewer's 2 most-liked genres across their whole TRAINING history (what a
  person knows about their own taste). Their held-out future loves are never used to build the answer.
- Content score = similarity to the 3 likes plus similarity to the stated genres, through the same
  TF-IDF + SVD model the app uses. Fans = the app's shipped "viewers like you" ranking.
- A = fans alone. B = 80% fans + 20% content (the app's real mix).

Rules, written before running:
- Validity: the simulated answers must carry real signal: the share of held-out loves in the stated
  genres must be higher than those genres' share of all movies (paired bootstrap lower bound above 0).
  If not, the test does not count.
- Content earns its 20% only if B beats A on NDCG@10 by at least 2% relative AND the paired-bootstrap
  95% interval of the difference is above zero.
- Reported, not used for the decision: hit@1, and how many of the top 10 match the stated genres.

Writes data/content_answers_confirm.json ("ships": true or false). Prints the result to paste back.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, matrix  # noqa: E402
from evaluate_blends import pct  # noqa: E402
from evaluate_long_tail import shipped_ranker  # noqa: E402
from train_cf import FIRST_HIT_DEPTH, metrics, paired_bootstrap, time_split  # noqa: E402

WEIGHT = 0.20
MIN_REL_GAIN = 0.02
SEED = 53


def content_space(data_dir, pos):
    """The app's content model (TF-IDF + SVD over genres and fan tags), keeping the fitted pieces so a
    genre answer can be placed in the same space."""
    d = Path(data_dir)
    movies = pd.read_csv(d / "movies.csv")
    tags = pd.read_csv(d / "tags.csv", usecols=["movieId", "tag"]).dropna(subset=["tag"])
    tags["tag"] = tags["tag"].astype(str).str.lower().str.replace(r"[^\w\s]", " ", regex=True)
    tag_text = tags.groupby("movieId")["tag"].apply(lambda t: " ".join(str(x) for x in t.head(300)))
    item_movie = pos.drop_duplicates("item").set_index("item")["movieId"].sort_index()
    m = movies.set_index("movieId")
    genres = [m.loc[mid, "genres"].split("|") if mid in m.index else [] for mid in item_movie.values]
    docs = [(" ".join(g) + " ") * 3 + tag_text.get(mid, "") if g else "" for g, mid in zip(genres, item_movie.values)]
    tf = TfidfVectorizer(min_df=3, max_features=20000, sublinear_tf=True)
    svd = TruncatedSVD(64, random_state=7)
    E = svd.fit_transform(tf.fit_transform(docs)).astype(np.float32)
    E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-8

    def embed_genres(gs):
        v = svd.transform(tf.transform([(" ".join(gs) + " ") * 3]))[0].astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-8)

    return E, genres, embed_genres


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
    used = set(np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False).tolist())   # evaluate_blends.py
    fresh = [u for u in eligible if u not in used]
    viewers = list(np.random.default_rng(SEED).choice(fresh, N_EVAL, replace=False))
    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    rank = shipped_ranker(X, float(bench["results"]["item-kNN"]["params"][0]))
    E, genres, embed_genres = content_space(args.data_dir, pos)
    all_genre_share = Counter(g for gs in genres for g in gs)
    n_movies = len(genres)
    print(f"{len(viewers):,} fresh viewers, content space ready", flush=True)

    rng = np.random.default_rng(5)
    rows_a, rows_b, sig_in, sig_base, match_a, match_b = [], [], [], [], [], []
    for u in viewers:
        hist = tb[u]
        seeds = np.asarray([hist[i] for i in sorted(rng.choice(len(hist), 3, replace=False))])
        stated = [g for g, _ in Counter(g for i in hist for g in genres[i] if g != "(no genres listed)").most_common(2)]
        fans = pct(np.asarray(rank(seeds), dtype=np.float64))
        q = E[seeds].mean(axis=0)
        q = q / (np.linalg.norm(q) + 1e-8) + (embed_genres(stated) if stated else 0)
        content = pct(E @ q)
        for score, rows, match in ((fans, rows_a, match_a), ((1 - WEIGHT) * fans + WEIGHT * content, rows_b, match_b)):
            s = score.copy()
            s[hist] = -np.inf
            top = np.argpartition(-s, FIRST_HIT_DEPTH)[:FIRST_HIT_DEPTH]
            top = top[np.argsort(-s[top])]
            rows.append(metrics(top, te[u]))
            match.append(np.mean([bool(set(genres[i]) & set(stated)) for i in top[:10]]) if stated else 0.0)
        loves = list(te[u])
        if stated and loves:
            sig_in.append(np.mean([bool(set(genres[i]) & set(stated)) for i in loves]))
            sig_base.append(sum(all_genre_share[g] for g in stated) / n_movies)

    a, b = np.asarray(rows_a, float), np.asarray(rows_b, float)
    dv, lov, hiv, _ = paired_bootstrap(np.asarray(sig_in), np.minimum(np.asarray(sig_base), 1.0), np.mean)
    valid = bool(lov > 0)
    d, lo, hi, _ = paired_bootstrap(b[:, 1], a[:, 1], np.mean)
    base = float(a[:, 1].mean())
    rel = d / base if base else 0.0
    ships = bool(valid and rel >= MIN_REL_GAIN and lo > 0)
    out = {"method": " ".join(__doc__.split("\n\n")[1:4]).replace("\n", " "),
           "viewers": len(viewers), "content_weight": WEIGHT,
           "validity_answer_signal": {"loves_in_stated_genres": round(float(np.mean(sig_in)), 4),
                                      "stated_genres_share_of_movies": round(float(np.mean(sig_base)), 4),
                                      "ci95_low": round(lov, 4), "valid": valid},
           "fans_alone": {"ndcg@10": round(base, 4), "hit@1": round(float(a[:, 2].mean()), 4),
                          "top10_in_stated_genres": round(float(np.mean(match_a)), 4)},
           "fans_plus_content_20": {"ndcg@10": round(float(b[:, 1].mean()), 4), "hit@1": round(float(b[:, 2].mean()), 4),
                                    "top10_in_stated_genres": round(float(np.mean(match_b)), 4)},
           "ndcg_diff": round(d, 5), "ndcg_ci95": [round(lo, 5), round(hi, 5)], "relative_gain": round(rel, 4),
           "min_relative_gain": MIN_REL_GAIN, "ships": ships}
    (ROOT / "data" / "content_answers_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))
    print("SHIPS: content earns its 20% with your answers." if ships else
          "DOES NOT SHIP: content stays at 20% as a product choice, reported as not an accuracy gain.")


if __name__ == "__main__":
    main()
