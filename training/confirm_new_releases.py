"""New releases: can open movie facts place a movie that has no fans yet next to the right movies?

    python training/confirm_new_releases.py

MovieLens stops around 2023, so iCinema's "viewers like you" models know nothing about newer
movies. This model learns, from Wikidata facts (director, cast, production company, genre,
country, decade; public domain, see training/fetch_wikidata.py), where a movie sits among the
movies fans love: it predicts the movie's position in iCinema's viewers-like-you space
(data/cf_model.npz) from its facts alone (ridge regression on the facts).

Test, written before running. Movies with Wikidata facts are split at random: 80% train the
model, 20% play "new releases" whose fan data is hidden. For each hidden movie, the model's
predicted position is used to find its 20 nearest movies, and the score is how many of its real
20 closest movies by fans (data/cf_knn.npz) were found (recall@20).
- Baselines: the same model with genres only (what a new movie usually has), and the 20 most
  popular movies.
- The ridge strength is picked on half of the hidden movies; the other half decides.
- Ships if it beats both baselines there (paired-bootstrap 95% interval above zero).
If it ships, the model is retrained on every movie with facts and used to place recent movies
from Wikidata: data/new_releases.npz. The app then scores a new movie by how close that predicted
position is to the movies you liked. Writes data/new_release_confirm.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from train_cf import paired_bootstrap  # noqa: E402

K = 20
ALPHAS = (1.0, 10.0, 100.0)
MIN_COUNT = 3


def tokens(row, genres_only=False):
    toks = [f"g:{x}" for x in row.get("genre") or []]
    if genres_only:
        return toks
    toks += [f"d:{x}" for x in row.get("director") or []]
    toks += [f"c:{x}" for x in (row.get("cast") or [])[:30]]
    toks += [f"co:{x}" for x in row.get("company") or []]
    toks += [f"n:{x}" for x in row.get("country") or []]
    if row.get("year"):
        toks.append(f"y:{row['year'] // 10 * 10}")
    return toks


def design(rows, vocab=None, genres_only=False):
    docs = [tokens(r, genres_only) for r in rows]
    if vocab is None:
        counts = {}
        for d in docs:
            for t in set(d):
                counts[t] = counts.get(t, 0) + 1
        vocab = {t: i for i, t in enumerate(sorted(t for t, c in counts.items() if c >= MIN_COUNT))}
    ri, ci = [], []
    for r, d in enumerate(docs):
        for t in set(d):
            if t in vocab:
                ri.append(r)
                ci.append(vocab[t])
    X = csr_matrix((np.ones(len(ri), np.float32), (ri, ci)), shape=(len(docs), max(len(vocab), 1)))
    norms = np.sqrt(np.asarray(X.multiply(X).sum(axis=1)).ravel())
    X = csr_matrix(X.multiply(1.0 / np.maximum(norms, 1.0)[:, None]))
    return X, vocab


def fit(X, Y, alpha):
    from sklearn.linear_model import Ridge
    return Ridge(alpha=alpha, solver="sparse_cg", fit_intercept=True).fit(X, Y)


def unit(M):
    return M / np.maximum(np.linalg.norm(M, axis=1, keepdims=True), 1e-9)


def recall(pred, emb_unit, warm_idx, truth_sets):
    sims = unit(pred) @ emb_unit[warm_idx].T
    top = np.argpartition(-sims, K, axis=1)[:, :K]
    found = warm_idx[top]
    return np.array([len(set(f.tolist()) & t) / max(len(t), 1) for f, t in zip(found, truth_sets)])


def main():
    wd = json.loads((ROOT / "data" / "wikidata_movies.json").read_text())
    emb = np.load(ROOT / "data" / "cf_model.npz")["emb"].astype(np.float32)
    knn = np.load(ROOT / "data" / "cf_knn.npz")
    nbr, fans = knn["nbr"], knn["popularity"].astype(float)
    rows = [r for r in wd["movielens"] if tokens(r)]
    rows = list({r["cf_index"]: r for r in rows}.values())
    idx = np.array([r["cf_index"] for r in rows])
    emb_unit = unit(emb)
    rng = np.random.default_rng(31)
    perm = rng.permutation(len(rows))
    cold = perm[: len(rows) // 5]
    warm = perm[len(rows) // 5:]
    warm_idx = idx[warm]
    warm_set = set(warm_idx.tolist())
    truth = [set(int(j) for j in nbr[idx[c]][:K] if int(j) in warm_set) for c in cold]
    keep = np.array([len(t) >= 5 for t in truth])
    cold, truth = cold[keep], [t for t, k in zip(truth, keep) if k]
    half = len(cold) // 2
    val, tst = np.arange(half), np.arange(half, len(cold))

    def run(genres_only, alpha):
        Xw, vocab = design([rows[i] for i in warm], genres_only=genres_only)
        Xc, _ = design([rows[i] for i in cold], vocab, genres_only=genres_only)
        model = fit(Xw, emb_unit[warm_idx], alpha)
        return recall(model.predict(Xc), emb_unit, warm_idx, truth)

    val_scores = {a: float(run(False, a)[val].mean()) for a in ALPHAS}
    alpha = max(val_scores, key=val_scores.get)
    g_val = {a: float(run(True, a)[val].mean()) for a in ALPHAS}
    g_alpha = max(g_val, key=g_val.get)
    full, genre = run(False, alpha), run(True, g_alpha)
    popular = warm_idx[np.argsort(-fans[warm_idx])[:K]]
    pop = np.array([len(set(popular.tolist()) & t) / max(len(t), 1) for t in truth])
    dg, lg, hg, _ = paired_bootstrap(full[tst], genre[tst], np.mean)
    dp, lp, hp, _ = paired_bootstrap(full[tst], pop[tst], np.mean)
    out = {"method": " ".join(__doc__.split("\n\n")[1:4]).replace("\n", " "),
           "movies_with_facts": len(rows), "hidden_movies_scored": int(len(tst)), "alpha": alpha,
           "recall_at_20": {"facts model": round(float(full[tst].mean()), 4), "genres only": round(float(genre[tst].mean()), 4),
                            "most popular": round(float(pop[tst].mean()), 4)},
           "vs_genres": {"diff": round(dg, 4), "ci95": [round(lg, 4), round(hg, 4)]},
           "vs_popular": {"diff": round(dp, 4), "ci95": [round(lp, 4), round(hp, 4)]},
           "ship": bool(lg > 0 and lp > 0)}
    path = ROOT / "data" / "new_releases.npz"
    if out["ship"]:
        X_all, vocab = design(rows)
        model = fit(X_all, emb_unit[idx], alpha)
        recent = [r for r in wd["recent"] if tokens(r)]
        Xr, _ = design(recent, vocab)
        pred = unit(model.predict(Xr)) if recent else np.zeros((0, emb.shape[1]))
        np.savez_compressed(path, tmdb_id=np.array([r["tmdb"] for r in recent], dtype=np.int64),
                            emb=pred.astype(np.float16))
        out["recent_movies_placed"] = len(recent)
    else:
        path.unlink(missing_ok=True)
    (ROOT / "data" / "new_release_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
