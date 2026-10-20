"""Build the shipped "viewers like you" models on all of MovieLens 32M.

    python training/build_knn.py --data-dir ml-32m

For every movie, keeps its 100 closest movies by who loved them (4+ stars):
- data/cf_knn.npz: item-kNN cosine (shrinkage from data/cf_benchmark.json). Used for "similar to
  this movie": What's next and "Loved by fans of ...".
- data/cf_rank.npz: RP3beta (viewer -> movie -> viewer -> movie, divided by fans^beta), built only
  if data/long_tail_confirm.json says it replaced item-kNN for ranking. Used to rank every row.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from train_cf import load, normalize_title  # noqa: E402

TOP = 100
BLOCK = 1000


def _build(X, Xc, fans, n, shrink, beta, meta, norm, path, t0):
    if beta is not None:
        from scipy.sparse import diags
        Pui = (diags(1.0 / np.maximum(np.asarray(X.sum(axis=1)).ravel(), 1)) @ X).tocsc()
        Piu = (diags(1.0 / np.maximum(fans, 1)) @ X.T.tocsr()).tocsr()
        damp = np.power(np.maximum(fans, 1), beta).astype(np.float32)
    nbr = np.zeros((n, TOP), dtype=np.int32)
    wts = np.zeros((n, TOP), dtype=np.float32)
    for start in range(0, n, BLOCK):
        b = np.arange(start, min(start + BLOCK, n))
        if beta is not None:
            sim = (Piu[b] @ Pui).toarray().astype(np.float32) / damp[None, :]
            sim[np.arange(len(b)), b] = 0
        else:
            co = (Xc[:, b].T @ Xc).toarray().astype(np.float32)
            co[np.arange(len(b)), b] = 0
            sim = co / (np.sqrt(np.outer(fans[b], fans)) + shrink)
        keep = np.argpartition(-sim, TOP, axis=1)[:, :TOP]
        kv = np.take_along_axis(sim, keep, axis=1)
        order = np.argsort(-kv, axis=1)
        nbr[b] = np.take_along_axis(keep, order, axis=1)
        wts[b] = np.take_along_axis(kv, order, axis=1)
    np.savez_compressed(
        path, nbr=nbr, w=wts.astype(np.float16), shrink=np.float32(shrink),
        beta=np.float32(beta if beta is not None else -1),
        tmdb_id=meta["tmdbId"].fillna(-1).astype(np.int64).to_numpy(),
        norm_title=np.array([t for t, _ in norm]),
        year=np.array([y or 0 for _, y in norm], dtype=np.int32),
        popularity=fans.astype(np.int32),
    )
    print(f"Saved {path.name} ({path.stat().st_size / 1e6:.1f} MB, {time.time() - t0:.0f}s)", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--min-count", type=int, default=20)
    args = ap.parse_args()
    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    shrink = float(bench["results"]["item-kNN"]["params"][0])
    confirm_path = ROOT / "data" / "long_tail_confirm.json"
    confirm = json.loads(confirm_path.read_text()) if confirm_path.exists() else {}
    beta_rank = float(confirm["beta"]) if confirm.get("replaces_item_knn") else None
    t0 = time.time()
    pos, meta = load(args.data_dir, args.min_count)
    n = len(meta)
    users = pos["userId"].astype("category")
    X = csr_matrix((np.ones(len(pos), dtype=np.float32), (users.cat.codes.to_numpy(), pos["item"].to_numpy())),
                   shape=(users.cat.categories.size, n))
    X.data[:] = 1.0
    del pos
    fans = np.asarray(X.sum(axis=0)).ravel()
    Xc = X.tocsc()
    norm = [normalize_title(t) for t in meta["title"]]
    for beta, name in ((None, "cf_knn.npz"), (beta_rank, "cf_rank.npz")):
        if name == "cf_rank.npz" and beta is None:
            (ROOT / "data" / name).unlink(missing_ok=True)
            continue
        _build(X, Xc, fans, n, shrink, beta, meta, norm, ROOT / "data" / name, t0)
    # Record the shipped model's training size (the app and README read these).
    res_path = ROOT / "data" / "cf_results.json"
    if res_path.exists():
        res = json.loads(res_path.read_text())
        res.update({"train_users": int(X.shape[0]), "train_movies": int(n), "train_positives": int(X.nnz),
                    "shipped_model": (f"RP3beta (beta {beta_rank:g}) for ranking, item-kNN for similar movies" if beta_rank is not None
                                      else "item-kNN, top-100 neighbors per movie") + ", trained on all of MovieLens 32M"})
        res_path.write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
