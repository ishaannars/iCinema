"""Build the shipped item-kNN model (the benchmark winner) on all of MovieLens 32M.

    python training/build_knn.py --data-dir ml-32m

For every movie, keeps its 100 nearest movies by cosine similarity of who loved them
(4+ stars), with shrinkage so movies with few fans don't look falsely similar. The shrinkage
value comes from data/cf_benchmark.json (chosen on validation users). Writes data/cf_knn.npz.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--min-count", type=int, default=20)
    args = ap.parse_args()
    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    shrink = float(bench["results"]["item-kNN"]["params"][0])
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
    nbr = np.zeros((n, TOP), dtype=np.int32)
    wts = np.zeros((n, TOP), dtype=np.float32)
    print(f"{X.shape[0]:,} users · {n:,} movies · {X.nnz:,} loves · shrink {shrink:g}", flush=True)
    for start in range(0, n, BLOCK):
        b = np.arange(start, min(start + BLOCK, n))
        co = (Xc[:, b].T @ Xc).toarray().astype(np.float32)
        co[np.arange(len(b)), b] = 0
        sim = co / (np.sqrt(np.outer(fans[b], fans)) + shrink)
        keep = np.argpartition(-sim, TOP, axis=1)[:, :TOP]
        kv = np.take_along_axis(sim, keep, axis=1)
        order = np.argsort(-kv, axis=1)
        nbr[b] = np.take_along_axis(keep, order, axis=1)
        wts[b] = np.take_along_axis(kv, order, axis=1)
        print(f"   movies {start:,}-{b[-1]:,} done ({time.time() - t0:.0f}s)", flush=True)
    norm = [normalize_title(t) for t in meta["title"]]
    np.savez_compressed(
        ROOT / "data" / "cf_knn.npz",
        nbr=nbr, w=wts.astype(np.float16), shrink=np.float32(shrink),
        tmdb_id=meta["tmdbId"].fillna(-1).astype(np.int64).to_numpy(),
        norm_title=np.array([t for t, _ in norm]),
        year=np.array([y or 0 for _, y in norm], dtype=np.int32),
        popularity=fans.astype(np.int32),
    )
    # Record the shipped model's training size (the app and README read these).
    res_path = ROOT / "data" / "cf_results.json"
    if res_path.exists():
        res = json.loads(res_path.read_text())
        res.update({"train_users": int(X.shape[0]), "train_movies": int(n), "train_positives": int(X.nnz),
                    "shipped_model": "item-kNN, top-100 neighbors per movie, trained on all of MovieLens 32M"})
        res_path.write_text(json.dumps(res, indent=2))
    size = (ROOT / "data" / "cf_knn.npz").stat().st_size / 1e6
    print(f"Saved data/cf_knn.npz ({size:.1f} MB, {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
