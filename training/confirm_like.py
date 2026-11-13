"""Does the "like X" re-rank beat ranking by fans alone? Held-out test on MovieLens.

    python training/confirm_like.py --data-dir ml-32m

Same 1-in-5 MovieLens 32M sample, time split, and 3,000 validation / 3,000 test viewers as
training/evaluate_blends.py. Source movie = each viewer's most recent liked movie ("I just watched
X"). Target = the movies they went on to love (held-out ratings of 4+). Rules written before running:

1. A ("fans only"): X's 100 closest movies by item-kNN, in fan order. This is what the app did before.
2. B ("re-rank", shipped in the app): those same 100, scored 0.5 fan rank + 0.5 content rank
   (genres and fan tags, TF-IDF + SVD) - 0.15 popularity percentile.
3. C ("content only"): X's closest movies by genres and fan tags alone, for reference.
4. B stays in the app only if it beats A on test NDCG@10 with a paired-bootstrap 95% interval
   above zero. Otherwise the app goes back to A. The popularity discount is also reported
   separately (B without the discount), so its effect is visible on its own.
5. Descriptive only (it cannot change rule 4): results split by how popular each viewer's loved
   movies are. Offline metrics reward popular picks, so this shows whether B helps viewers who
   go on to love less-known movies, which a single average can hide.
Writes data/like_confirm.json; the app reads its "ship" field.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_knn, matrix  # noqa: E402
from evaluate_blends import content_embeddings, pct  # noqa: E402
from train_cf import FIRST_HIT_DEPTH, metrics, paired_bootstrap, time_split  # noqa: E402


def run(users, tb, te, rank_fn):
    out = []
    for u in users:
        hist = tb[u]
        order = [i for i in rank_fn(hist[-1]) if i not in set(hist)][:FIRST_HIT_DEPTH]
        out.append(metrics(np.asarray(order, dtype=int), te[u]))
    return np.asarray(out, dtype=float)


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
    tst = list(picked[N_EVAL:])
    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    knn, _ = m_knn(X, float(bench["results"]["item-kNN"]["params"][0]), top=100)
    E = content_embeddings(args.data_dir, pos)
    popularity = pct(np.bincount(train["item"], minlength=n_items).astype(float))

    def neighbors(src):
        s = np.asarray(knn(np.asarray([src])), dtype=float).ravel()
        s[src] = -np.inf
        top = np.argpartition(-s, 100)[:100]
        return top[np.argsort(-s[top])]

    def fans_only(src):
        return list(neighbors(src))

    def rerank(discount):
        def f(src):
            near = neighbors(src)
            fan = 1 - np.arange(len(near)) / len(near)
            cos = E[near] @ E[src]
            tag = 1 - np.argsort(np.argsort(-cos)) / len(near)
            score = 0.5 * fan + 0.5 * tag - discount * popularity[near]
            return list(near[np.argsort(-score)])
        return f

    def content_only(src):
        s = E @ E[src]
        s[src] = -np.inf
        return list(np.argsort(-s)[:200])

    rA, rB = run(tst, tb, te, fans_only), run(tst, tb, te, rerank(0.15))
    rB0, rC = run(tst, tb, te, rerank(0.0)), run(tst, tb, te, content_only)
    d, lo, hi, _ = paired_bootstrap(rB[:, 1], rA[:, 1], np.mean)
    ship = bool(lo > 0)
    counts = np.bincount(train["item"], minlength=n_items)
    loved_pop = np.array([np.median(counts[list(te[u])]) for u in tst])
    q1, q3 = np.quantile(loved_pop, [0.25, 0.75])
    bands = {"niche (least popular 25%)": loved_pop <= q1, "middle 50%": (loved_pop > q1) & (loved_pop < q3),
             "mainstream (most popular 25%)": loved_pop >= q3}
    by_band = {name: {"viewers": int(m.sum()), "fans_only": round(float(rA[m, 1].mean()), 4),
                      "rerank": round(float(rB[m, 1].mean()), 4), "rerank_no_discount": round(float(rB0[m, 1].mean()), 4)}
               for name, m in bands.items()}
    out = {
        "method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "),
        "test_viewers": len(tst),
        "ndcg@10": {"fans_only": round(float(rA[:, 1].mean()), 4), "rerank": round(float(rB[:, 1].mean()), 4),
                    "rerank_no_discount": round(float(rB0[:, 1].mean()), 4), "content_only": round(float(rC[:, 1].mean()), 4)},
        "hit@1": {"fans_only": round(float(rA[:, 2].mean()), 4), "rerank": round(float(rB[:, 2].mean()), 4)},
        "rerank_vs_fans_only": {"diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)]},
        "ship": ship,
        "by_popularity_of_loved_movies": by_band,
    }
    print(json.dumps(out, indent=1))
    (ROOT / "data" / "like_confirm.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
