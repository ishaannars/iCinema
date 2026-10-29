"""Build data/cf_full.npz (EASE, 100 strongest positive links per movie) on all of MovieLens 32M.

    python training/build_ease.py --data-dir ml-32m

Runs only if training/confirm_history_routing.py passed its rule; otherwise it removes any old
cf_full.npz so the app keeps the current ranking for everyone. Same movie order and fields as
data/cf_knn.npz, so the app loads it the same way. Needs about 3 GB of free memory.
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
from build_knn import _display_title  # noqa: E402
from train_cf import load, normalize_title  # noqa: E402

TOP = 100
OUT = ROOT / "data" / "cf_full.npz"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--min-count", type=int, default=20)
    args = ap.parse_args()
    conf_path = ROOT / "data" / "history_routing_confirm.json"
    conf = json.loads(conf_path.read_text()) if conf_path.exists() else {}
    if not conf.get("ship"):
        OUT.unlink(missing_ok=True)
        print("History routing did not pass its test, so no EASE file is shipped.")
        return
    t0 = time.time()
    pos, meta = load(args.data_dir, args.min_count)
    n = len(meta)
    users = pos["userId"].astype("category")
    X = csr_matrix((np.ones(len(pos), dtype=np.float32), (users.cat.codes.to_numpy(), pos["item"].to_numpy())),
                   shape=(users.cat.categories.size, n))
    X.data[:] = 1.0
    del pos
    fans = np.asarray(X.sum(axis=0)).ravel()
    G = (X.T @ X).toarray().astype(np.float32)
    G[np.diag_indices_from(G)] += np.float32(conf["ease_lambda"])
    P = np.linalg.inv(G)
    del G
    B = -P / np.diag(P)
    del P
    np.fill_diagonal(B, 0)
    B[B < 0] = 0
    keep = np.argpartition(-B, TOP, axis=1)[:, :TOP]
    kv = np.take_along_axis(B, keep, axis=1)
    order = np.argsort(-kv, axis=1)
    nbr = np.take_along_axis(keep, order, axis=1).astype(np.int32)
    w = np.take_along_axis(kv, order, axis=1)
    del B
    w = w / max(float(w.max()), 1e-9)        # scale to 0-1 so float16 keeps precision
    norm = [normalize_title(t) for t in meta["title"]]
    np.savez_compressed(
        OUT, nbr=nbr, w=w.astype(np.float16), shrink=np.float32(-1), beta=np.float32(-1),
        tmdb_id=meta["tmdbId"].fillna(-1).astype(np.int64).to_numpy(),
        norm_title=np.array([t for t, _ in norm]),
        title=np.array([_display_title(t) for t in meta["title"]]),
        title_raw=np.array([str(t) for t in meta["title"]]),
        year=np.array([y or 0 for _, y in norm], dtype=np.int32),
        popularity=fans.astype(np.int32),
    )
    print(f"Saved {OUT.name} ({OUT.stat().st_size / 1e6:.1f} MB, {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
