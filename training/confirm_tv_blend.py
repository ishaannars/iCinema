"""TV shows, second attempt: does "fans like you" blended with popularity beat popularity alone?

    python training/confirm_tv_blend.py --amazon-dir amazon-movies-tv

The first attempt (training/confirm_tv.py) tied with "most popular shows": on Amazon most people
rate only a few shows, mostly the same big ones. A blend of the two is the standard answer to a
strong popularity baseline, so this is one more try, decided by a rule written before running.

Same data, same show/movie matching, same item-kNN. A fresh random group of people (different from
the first attempt) with at least 3 loved movies and 2 loved shows is held out entirely; similarities
come only from everyone else. Each held-out person's loved movies rank every show by
(1 - a) * fans-like-you percentile + a * popularity percentile.
- a is picked from 0.2, 0.4, 0.6, 0.8 on one half of the held-out people, by NDCG@20.
- On the other half, with a fixed, it ships only if it beats "most popular shows" with a
  paired-bootstrap 95% interval above zero.
This is the last attempt with this data: if it fails, TV stays on "coming next" in the README.
If it ships, data/tv_knn.npz is built from everyone, with the blend weight. Writes
data/tv_blend_confirm.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from confirm_tv import K, TOP, cosine_top, load  # noqa: E402
from train_cf import paired_bootstrap  # noqa: E402

WEIGHTS = (0.2, 0.4, 0.6, 0.8)


def ndcg(ranked, truth):
    g = sum(1 / np.log2(k + 2) for k, s in enumerate(ranked[:K]) if s in truth)
    ideal = sum(1 / np.log2(k + 2) for k in range(min(len(truth), K)))
    return g / ideal if ideal else 0.0


def pct(v):
    order = np.argsort(v, kind="stable")
    r = np.empty(len(v))
    r[order] = np.arange(len(v))
    return r / max(len(v) - 1, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amazon-dir", default="amazon-movies-tv")
    args = ap.parse_args()
    X, node_names, names = load(args.amazon_dir)
    is_show = np.array([n.startswith("tv:") for n in node_names])
    shows, movies = np.flatnonzero(is_show), np.flatnonzero(~is_show)
    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    n_movie = np.asarray(X[:, movies].sum(axis=1)).ravel()
    n_show = np.asarray(X[:, shows].sum(axis=1)).ravel()
    eligible = np.flatnonzero((n_movie >= 3) & (n_show >= 2))
    held = np.random.default_rng(31).choice(eligible, min(10000, len(eligible) // 2), replace=False)
    mask = np.ones(X.shape[0], bool)
    mask[held] = False
    sims, fans_tr = cosine_top(X[mask], shows, shrink, rows=movies)
    show_pos = {int(j): k for k, j in enumerate(shows)}
    pop_pct = pct(fans_tr[shows].astype(float))
    pop_rank = list(np.argsort(-pop_pct))
    print(f"{X.shape[0]:,} people, {len(shows):,} shows, {len(held):,} held out", flush=True)

    rows = []
    for u in held:
        row = X.getrow(u).indices
        truth = {show_pos[int(i)] for i in row if is_show[i]}
        s = np.zeros(len(shows))
        for m in row:
            if not is_show[m] and int(m) in sims:
                j, w = sims[int(m)]
                np.add.at(s, [show_pos[int(x)] for x in j], w)
        rows.append((pct(s), truth))

    def run(idx, a):
        return np.asarray([ndcg(list(np.argsort(-((1 - a) * rows[i][0] + a * pop_pct))), rows[i][1]) for i in idx])

    order = np.random.default_rng(37).permutation(len(rows))
    val, tst = order[: len(order) // 2], order[len(order) // 2:]
    val_scores = {a: float(run(val, a).mean()) for a in WEIGHTS}
    a = max(val_scores, key=val_scores.get)
    blend = run(tst, a)
    base = np.asarray([ndcg(pop_rank, rows[i][1]) for i in tst])
    d, lo, hi, _ = paired_bootstrap(blend, base, np.mean)
    out = {"method": " ".join(__doc__.split("\n\n")[1:4]).replace("\n", " "), "people": int(X.shape[0]),
           "shows": int(len(shows)), "held_out": int(len(held)), "validation_ndcg_by_weight": {str(k): round(v, 4) for k, v in val_scores.items()},
           "popularity_weight": a, "ndcg_at_20": {"blend": round(float(blend.mean()), 4), "most popular shows": round(float(base.mean()), 4)},
           "diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "ship": bool(lo > 0 and len(tst) >= 500)}
    path = ROOT / "data" / "tv_knn.npz"
    if out["ship"]:
        sims_all, fans_all = cosine_top(X, shows, shrink, rows=movies)
        nbr = np.full((len(movies), TOP), -1, np.int32)
        w = np.zeros((len(movies), TOP), np.float16)
        for r, i in enumerate(movies):
            if int(i) in sims_all:
                j, v = sims_all[int(i)]
                nbr[r, :len(j)] = [show_pos[int(x)] for x in j]
                w[r, :len(v)] = v
        np.savez_compressed(path, show_names=np.array([names.get(n, n[3:]) for n in node_names[shows]]),
                            show_fans=fans_all[shows].astype(np.int32),
                            movie_rows=np.array([int(n[3:]) for n in node_names[movies]], np.int32),
                            movie_nbr=nbr, movie_w=w, popularity_weight=np.float32(a))
    (ROOT / "data" / "tv_blend_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
