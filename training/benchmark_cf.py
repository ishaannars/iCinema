"""Benchmark iCinema's "viewers like you" model against the standard recommender baselines.

    python training/benchmark_cf.py --data-dir ml-32m --user-sample 5

Rule written before running:
- Same MovieLens positives (4+ stars), same per-user time split, same users for every model.
- Models: popularity, the current SVD embeddings (64 dims), SVD 128 dims, item-kNN (cosine with
  shrinkage), implicit ALS, EASE (closed-form linear), and top-100-neighbor versions of item-kNN and
  EASE that are small enough to ship.
- Hyperparameters are chosen on 3,000 validation users. Results are reported on 3,000 different
  test users, once.
- Onboarding is scored with 3 RANDOM likes from each viewer's history (the honest case). The
  last-3 version used before is also reported, because recent likes sit closest to what comes next.
- A model replaces the current SVD in the app only if, on random-3 seeds, it beats it on Hit@1 and
  NDCG@10 with paired-bootstrap 95% intervals above zero, and its model file is under 25 MB.
Writes data/cf_benchmark.json.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from train_cf import fit_embeddings, metrics, paired_bootstrap, time_split, FIRST_HIT_DEPTH  # noqa: E402

N_EVAL = 3000
SHIP_LIMIT_MB = 25


def load_sample(data_dir, user_mod, min_count):
    parts = []
    for ch in pd.read_csv(Path(data_dir) / "ratings.csv", chunksize=4_000_000,
                          dtype={"userId": "int32", "movieId": "int32", "rating": "float32", "timestamp": "int64"}):
        ch = ch[(ch["rating"] >= 4.0) & (ch["userId"] % user_mod == 0)]
        parts.append(ch[["userId", "movieId", "timestamp"]])
    pos = pd.concat(parts)
    counts = pos["movieId"].value_counts()
    pos = pos[pos["movieId"].isin(counts[counts >= min_count].index)]
    uc = pos["userId"].value_counts()
    pos = pos[pos["userId"].isin(uc[uc >= 5].index)]
    items = np.sort(pos["movieId"].unique())
    return pos.assign(item=pos["movieId"].map({m: i for i, m in enumerate(items)}).astype(np.int32)), len(items)


def matrix(train, n_items):
    users = train["userId"].astype("category")
    X = csr_matrix((np.ones(len(train), dtype=np.float32), (users.cat.codes.to_numpy(), train["item"].to_numpy())),
                   shape=(users.cat.categories.size, n_items))
    X.data[:] = 1.0
    return X


# ---------------------------------------------------------------- models (each: fit -> scorer(seed_items))
def m_popularity(X):
    pop = np.asarray(X.sum(axis=0)).ravel().astype(np.float32)
    return lambda seeds: pop.copy(), 0.0


def m_svd(train, n_items, dim):
    emb = fit_embeddings(train, n_items, dim)
    return (lambda seeds: emb @ emb[seeds].mean(axis=0)), emb.nbytes / 1e6


def m_svd_recency(train, n_items, dim, half_life):
    emb = fit_embeddings(train, n_items, dim)
    def score(seeds):
        w = 0.5 ** (np.arange(len(seeds))[::-1] / half_life)  # seeds are in time order; newest weighs most
        return emb @ (w[:, None] * emb[seeds]).sum(axis=0)
    return score, emb.nbytes / 1e6


def m_knn(X, shrink, top=None):
    co = (X.T @ X).toarray().astype(np.float32)
    n = np.diag(co).copy()
    np.fill_diagonal(co, 0)
    S = co / (np.sqrt(np.outer(n, n)) + shrink)
    del co
    size = S.nbytes / 1e6
    if top:
        keep = np.argpartition(-S, top, axis=1)[:, :top]
        Ss = np.zeros_like(S)
        rows = np.arange(S.shape[0])[:, None]
        Ss[rows, keep] = S[rows, keep]
        S, size = Ss, S.shape[0] * top * 8 / 1e6  # stored as (index int32, weight float32) pairs
    return (lambda seeds: S[seeds].sum(axis=0)), size


def m_ease(X, lam, top=None):
    G = (X.T @ X).toarray().astype(np.float64)
    G[np.diag_indices_from(G)] += lam
    P = np.linalg.inv(G)
    B = (-P / np.diag(P)).astype(np.float32)
    np.fill_diagonal(B, 0)
    del G, P
    size = B.nbytes / 1e6
    if top:
        keep = np.argpartition(-np.abs(B), top, axis=1)[:, :top]
        Bs = np.zeros_like(B)
        rows = np.arange(B.shape[0])[:, None]
        Bs[rows, keep] = B[rows, keep]
        B, size = Bs, B.shape[0] * top * 8 / 1e6  # stored as (index int32, weight float32) pairs
    return (lambda seeds: B[seeds].sum(axis=0)), size


def m_als(X, factors=64, alpha=20.0, reg=10.0, iters=8, seed=3):
    rng = np.random.default_rng(seed)
    n_u, n_i = X.shape
    U = rng.normal(0, 0.01, (n_u, factors)).astype(np.float32)
    V = rng.normal(0, 0.01, (n_i, factors)).astype(np.float32)
    Xt = X.T.tocsr()
    I = np.eye(factors, dtype=np.float32)

    def solve(A, Y, out):
        YtY = Y.T @ Y
        for r in range(A.shape[0]):
            idx = A.indices[A.indptr[r]:A.indptr[r + 1]]
            if len(idx) == 0:
                continue
            Yi = Y[idx]
            M = YtY + alpha * (Yi.T @ Yi) + reg * I
            out[r] = np.linalg.solve(M, (1 + alpha) * Yi.sum(axis=0))
    for _ in range(iters):
        solve(X, V, U)
        solve(Xt, U, V)
    VtV = V.T @ V

    def score(seeds):
        Vi = V[seeds]
        u = np.linalg.solve(VtV + alpha * (Vi.T @ Vi) + reg * I, (1 + alpha) * Vi.sum(axis=0))
        return V @ u
    return score, V.nbytes / 1e6


# ---------------------------------------------------------------- evaluation
def evaluate(score, users, train_by_user, test_by_user, mode, rng_seed=5):
    rng = np.random.default_rng(rng_seed)
    out = []
    for u in users:
        hist = train_by_user[u]
        if mode == "last3":
            seeds = hist[-3:]
        elif mode == "random3":
            seeds = sorted(rng.choice(len(hist), 3, replace=False))
            seeds = [hist[i] for i in seeds]
        else:
            seeds = hist
        s = np.asarray(score(np.asarray(seeds)), dtype=np.float64)
        s[hist] = -np.inf
        top = np.argpartition(-s, FIRST_HIT_DEPTH)[:FIRST_HIT_DEPTH]
        top = top[np.argsort(-s[top])]
        out.append(metrics(top, test_by_user[u]))
    return np.asarray(out, dtype=float)


def summary(raw):
    return {"hit@1": float(raw[:, 2].mean()), "recall@10": float(raw[:, 0].mean()),
            "ndcg@10": float(raw[:, 1].mean()), "median_recs_to_first_hit": float(np.median(raw[:, 3]))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--user-sample", type=int, default=5, help="keep users whose id is divisible by this")
    ap.add_argument("--min-count", type=int, default=20)
    args = ap.parse_args()
    t0 = time.time()
    pos, n_items = load_sample(args.data_dir, args.user_sample, args.min_count)
    train, test = time_split(pos)
    X = matrix(train, n_items)
    train_by_user = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    test_by_user = test.groupby("userId")["item"].apply(set)
    eligible = [u for u in test_by_user.index if u in train_by_user.index and len(train_by_user[u]) >= 3]
    rng = np.random.default_rng(7)
    picked = rng.choice(eligible, 2 * N_EVAL, replace=False)
    val_users, test_users = list(picked[:N_EVAL]), list(picked[N_EVAL:])
    print(f"{len(pos):,} positives · {X.shape[0]:,} users · {n_items:,} movies · {time.time() - t0:.0f}s", flush=True)

    def val_ndcg(score):
        return summary(evaluate(score, val_users, train_by_user, test_by_user, "random3"))["ndcg@10"]

    grid = {
        "SVD, 64 dims (current)": [((), lambda: m_svd(train, n_items, 64))],
        "SVD, 128 dims": [((), lambda: m_svd(train, n_items, 128))],
        "item-kNN": [((s,), (lambda s=s: m_knn(X, s))) for s in (0, 20, 100)],
        "Implicit ALS": [((a,), (lambda a=a: m_als(X, alpha=a))) for a in (10, 40)],
        "EASE": [((l,), (lambda l=l: m_ease(X, l))) for l in (250, 1000, 4000)],
    }
    chosen, val_log = {}, {}
    for name, options in grid.items():
        best = None
        for params, build in options:
            score, size = build()
            v = val_ndcg(score)
            val_log[f"{name} {params}"] = round(v, 4)
            print(f"  validation {name} {params}: NDCG@10 {v:.4f} ({time.time() - t0:.0f}s)", flush=True)
            if best is None or v > best[0]:
                best = (v, params, score, size)
        chosen[name] = best
    lam = chosen["EASE"][1][0]
    chosen["EASE, top-100 per movie (shippable)"] = (None, (lam, 100), *m_ease(X, lam, top=100))
    shr = chosen["item-kNN"][1][0]
    chosen["item-kNN, top-100 per movie (shippable)"] = (None, (shr, 100), *m_knn(X, shr, top=100))
    chosen["Popularity"] = (None, (), *m_popularity(X))
    chosen["SVD 64, recency-weighted (half-life 20 likes)"] = (None, (20,), *m_svd_recency(train, n_items, 64, 20))

    results, raw = {}, {}
    for name, (_, params, score, size) in chosen.items():
        results[name] = {"params": list(params), "model_size_mb": round(size, 1)}
        for mode in ("random3", "last3", "full"):
            r = evaluate(score, test_users, train_by_user, test_by_user, mode)
            raw[(name, mode)] = r
            results[name][mode] = summary(r)
        print(f"  test {name}: {results[name]['random3']} ({time.time() - t0:.0f}s)", flush=True)

    cur = "SVD, 64 dims (current)"
    boot = {}
    for name in results:
        if name == cur:
            continue
        b = {}
        for col, key in ((2, "hit@1"), (1, "ndcg@10"), (0, "recall@10")):
            d, lo, hi, win = paired_bootstrap(raw[(name, "random3")][:, col], raw[(cur, "random3")][:, col], np.mean)
            b[key] = {"difference": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "win_share": round(win, 3)}
        boot[name] = b
    pop_vs = {}
    for name in results:
        if name == "Popularity":
            continue
        p = results["Popularity"]["random3"]
        pop_vs[name] = {k: round(results[name]["random3"][k] / p[k] - 1, 4) for k in ("hit@1", "ndcg@10", "recall@10") if p[k] > 0}
    winner = None
    for name, b in boot.items():
        if name == "Popularity":
            continue
        ok = (b["hit@1"]["ci95"][0] > 0 and b["ndcg@10"]["ci95"][0] > 0
              and results[name]["model_size_mb"] <= SHIP_LIMIT_MB)
        if ok and (winner is None or results[name]["random3"]["ndcg@10"] > results[winner]["random3"]["ndcg@10"]):
            winner = name
    out = {
        "method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "),
        "dataset": {"positives": int(len(pos)), "users": int(X.shape[0]), "movies": int(n_items),
                    "user_sample": f"1 in {args.user_sample} MovieLens 32M users", "validation_users": N_EVAL, "test_users": N_EVAL},
        "validation_ndcg_random3": val_log, "results": results,
        "bootstrap_random3_vs_current": boot, "lift_random3_vs_popularity": pop_vs,
        "winner": winner or cur, "replaces_current": winner is not None,
    }
    (ROOT / "data" / "cf_benchmark.json").write_text(json.dumps(out, indent=1))

    # The shipped model's honest onboarding result, in the format the app, README, and model card read.
    ship = out["winner"]
    w3, pop3 = raw[(ship, "random3")], raw[("Popularity", "random3")]
    rows = []
    for label, col in (("Recall@10", 0), ("NDCG@10", 1), ("Hit@1", 2)):
        d, lo, hi, share = paired_bootstrap(w3[:, col], pop3[:, col], np.mean)
        fmt = "{:+.1%}" if label == "Hit@1" else "{:+.3f}"
        rows.append({"metric": label, "difference": fmt.format(d), "ci95": f"{fmt.format(lo)} to {fmt.format(hi)}",
                     "cf_win_share": share, "significant": bool(lo > 0)})
    d, lo, hi, share = paired_bootstrap(pop3[:, 3], w3[:, 3], np.median)
    rows.append({"metric": "Recs to first loved movie (median, fewer is better)", "difference": f"{d:.0f} fewer",
                 "ci95": f"{lo:.0f} to {hi:.0f} fewer", "cf_win_share": share, "significant": bool(lo > 0)})
    compat = {"dataset": f"{Path(args.data_dir).name} ({out['dataset']['user_sample']})", "model": ship,
              "seed_type": "3 random likes from each viewer's history",
              "held_out_users": N_EVAL, "benchmark_users": out["dataset"]["users"], "benchmark_movies": n_items,
              "benchmark_positives": out["dataset"]["positives"],
              "full": {"popularity": results["Popularity"]["full"], "cf": results[ship]["full"]},
              "three_likes": {"popularity": results["Popularity"]["random3"], "cf": results[ship]["random3"]},
              "bootstrap_three_likes_vs_popularity": rows}
    compat["lifts_three_likes_vs_popularity"] = {
        k: round((results[ship]["random3"][k] / results["Popularity"]["random3"][k] - 1) * 100) for k in ("hit@1", "ndcg@10", "recall@10")}
    (ROOT / "data" / "cf_results.json").write_text(json.dumps(compat, indent=2))
    print("WINNER:", out["winner"], "| replaces current:", out["replaces_current"], f"({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
