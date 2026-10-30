"""Learning to rank: can one model that combines all the others beat today's fixed blend?

    python training/confirm_ltr.py --data-dir ml-32m

Today every pick is a fixed mix: 80% "viewers like you" (the routed ranking) and 20% content.
Stacking many recommenders with gradient-boosted trees is a standard way to beat any single one
in recommender-system challenges, so this tests it on iCinema's own models.

Setup: the same 1-in-5 MovieLens 32M sample, time split, and 3,000 + 3,000 viewers as
training/evaluate_blends.py; each viewer is scored from 3 random likes, like a new user. For each
viewer, the 300 movies today's blend ranks highest are re-ranked. Features for each movie, all as
percentiles within that viewer: the routed ranking, item-kNN, RP3beta, EASE, the content model,
and popularity. The ranker (scikit-learn HistGradientBoostingClassifier, label = the viewer later
rated it 4+ stars) is trained on the first 3,000 viewers only.

Rule written before running: on the other 3,000 viewers, it ships only if NDCG@10 beats today's
blend with a paired-bootstrap 95% interval above zero. Either way the result is reported, along
with how much each model contributes (drop in NDCG@10 when that feature is shuffled). If it
ships, data/ltr_model.joblib is saved for the app. Writes data/ltr_confirm.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, load_sample, m_ease, m_knn, matrix  # noqa: E402
from evaluate_blends import content_embeddings, pct  # noqa: E402
from evaluate_long_tail import rp3beta, shipped_ranker  # noqa: E402
from train_cf import FIRST_HIT_DEPTH, metrics, paired_bootstrap, time_split  # noqa: E402

CANDIDATES = 300
FEATURES = ["routed", "item_knn", "rp3beta", "ease", "content", "popularity"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    pos, n = load_sample(args.data_dir, 5, 20)
    train, test = time_split(pos)
    X = matrix(train, n)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    eligible = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]
    picked = np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False)
    val, tst = list(picked[:N_EVAL]), list(picked[N_EVAL:])

    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    shrink = float(bench["results"]["item-kNN"]["params"][0])
    lam = float(bench["results"]["EASE"]["params"][0])
    beta = float(json.loads((ROOT / "data" / "long_tail_confirm.json").read_text())["beta"])
    w_content = float(json.loads((ROOT / "data" / "blend_results.json").read_text())["content_blend"]["best_weight"])
    routed = shipped_ranker(X, shrink)
    knn = m_knn(X, shrink, top=100)[0]
    rp3 = rp3beta(X, beta)
    ease = m_ease(X, lam, top=100)[0]
    E = content_embeddings(args.data_dir, pos)
    pop = pct(np.asarray(X.sum(axis=0)).ravel().astype(float))
    print("models ready", flush=True)

    def viewer_rows(users, seed=5):
        rng = np.random.default_rng(seed)
        out = []
        for u in users:
            hist = tb[u]
            seeds = np.asarray([hist[i] for i in sorted(rng.choice(len(hist), 3, replace=False))])
            f = {"routed": pct(np.asarray(routed(seeds), float)), "item_knn": pct(np.asarray(knn(seeds), float)),
                 "rp3beta": pct(np.asarray(rp3(seeds), float)), "ease": pct(np.asarray(ease(seeds), float)),
                 "content": pct(E @ E[seeds].mean(axis=0)), "popularity": pop}
            base = w_content * f["content"] + (1 - w_content) * f["routed"]
            base[hist] = -np.inf
            cand = np.argpartition(-base, CANDIDATES)[:CANDIDATES]
            cand = cand[np.argsort(-base[cand])]
            feats = np.stack([f[k][cand] for k in FEATURES], axis=1)
            labels = np.asarray([c in te[u] for c in cand], dtype=int)
            out.append((cand, feats, labels, base[cand], te[u]))
        return out

    def ndcg_of(rows, scorer):
        res = []
        for cand, feats, _, base, truth in rows:
            s = scorer(feats, base)
            top = cand[np.argsort(-s)[:FIRST_HIT_DEPTH]]
            res.append(metrics(top, truth)[1])
        return np.asarray(res)

    from sklearn.ensemble import HistGradientBoostingClassifier
    tr_rows, ts_rows = viewer_rows(val), viewer_rows(tst)
    Xtr = np.concatenate([r[1] for r in tr_rows])
    ytr = np.concatenate([r[2] for r in tr_rows])
    model = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
                                           l2_regularization=1.0, random_state=11).fit(Xtr, ytr)
    current = ndcg_of(ts_rows, lambda feats, base: base)
    learned = ndcg_of(ts_rows, lambda feats, base: model.predict_proba(feats)[:, 1])
    d, lo, hi, _ = paired_bootstrap(learned, current, np.mean)

    rng = np.random.default_rng(13)
    importance = {}
    for j, name in enumerate(FEATURES):
        def shuffled(feats, base, j=j):
            g = feats.copy()
            g[:, j] = rng.permutation(g[:, j])
            return model.predict_proba(g)[:, 1]
        importance[name] = max(0.0, float(learned.mean() - ndcg_of(ts_rows, shuffled).mean()))
    total = sum(importance.values()) or 1.0
    shares = {k: round(v / total, 3) for k, v in importance.items()}

    out = {"method": " ".join(__doc__.split("\n\n")[1:4]).replace("\n", " "), "viewers_train": len(val),
           "viewers_test": len(tst), "candidates_per_viewer": CANDIDATES, "features": FEATURES,
           "ndcg_current_blend": round(float(current.mean()), 4), "ndcg_learned": round(float(learned.mean()), 4),
           "diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "ship": bool(lo > 0),
           "feature_shares": shares}
    path = ROOT / "data" / "ltr_model.joblib"
    if out["ship"]:
        import joblib
        joblib.dump({"model": model, "features": FEATURES, "candidates": CANDIDATES}, path)
    else:
        path.unlink(missing_ok=True)
    (ROOT / "data" / "ltr_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
