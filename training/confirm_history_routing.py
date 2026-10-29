"""Should viewers with many likes get EASE instead of the current routed ranking?

    python training/confirm_history_routing.py --data-dir ml-32m

Why ask. In the benchmark (cf_benchmark.json), item-kNN won from 3 likes, which is why it ships.
But from a viewer's whole history, EASE scored clearly higher (NDCG@10 0.113 vs 0.093). Letterboxd
import gives many viewers hundreds of likes on day one, so the question is whether a viewer's
number of likes should pick the model.

Setup. A 1-in-5 slice of MovieLens 32M users that no earlier test used (user id ending 3; slices
0, 1 and 2 were used before). Models are rebuilt on this slice: the current routed ranking
(item-kNN, RP3beta for less mainstream likes, same settings as shipped) and EASE in the form that
ships (each movie keeps its 100 strongest positive links, lambda from the benchmark). Each viewer
is scored from their whole training history, like an importer would be.

Rule written before running:
- Eligible viewers are split in half at random. The cut N (number of likes at which EASE takes
  over) is chosen on the first half only, from 10, 25, 50, 100 or "never", by mean NDCG@10.
- On the second half, with N fixed: EASE ships for viewers with N or more likes if those viewers
  improve (paired-bootstrap 95% interval above zero) and all viewers don't get worse by more than
  0.002 NDCG@10 (interval lower bound above -0.002).
- If "never" wins on the first half, nothing ships.
Writes data/history_routing_confirm.json. training/build_ease.py builds data/cf_full.npz only if
this test passed.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import load_sample, m_knn, matrix  # noqa: E402
from confirm_routing import routed_scorer  # noqa: E402
from evaluate_long_tail import pct, rp3beta  # noqa: E402
from train_cf import FIRST_HIT_DEPTH, metrics, paired_bootstrap, time_split  # noqa: E402

OFFSET = 3
CUTS = (10, 25, 50, 100)
MARGIN = 0.002
TOP = 100


def ease_positive_top(X, lam, top=TOP):
    """EASE keeping each movie's `top` largest positive weights: exactly what cf_full.npz stores."""
    G = (X.T @ X).toarray().astype(np.float64)
    G[np.diag_indices_from(G)] += lam
    P = np.linalg.inv(G)
    B = (-P / np.diag(P)).astype(np.float32)
    del G, P
    np.fill_diagonal(B, 0)
    B[B < 0] = 0
    keep = np.argpartition(-B, top, axis=1)[:, :top]
    rows = np.arange(B.shape[0])[:, None]
    Bs = np.zeros_like(B)
    Bs[rows, keep] = B[rows, keep]
    return lambda seeds: Bs[seeds].sum(axis=0)


def rank_metrics(f, hist, truth):
    s = np.asarray(f(np.asarray(hist)), dtype=np.float64)
    s[hist] = -np.inf
    top = np.argpartition(-s, FIRST_HIT_DEPTH)[:FIRST_HIT_DEPTH]
    return metrics(top[np.argsort(-s[top])], truth)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    pos, n = load_sample(args.data_dir, 5, 20, user_offset=OFFSET)
    train, test = time_split(pos)
    X = matrix(train, n)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    users = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]

    bench = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    shrink = float(bench["results"]["item-kNN"]["params"][0])
    lam = float(bench["results"]["EASE"]["params"][0])
    beta = float(json.loads((ROOT / "data" / "long_tail_confirm.json").read_text())["beta"])
    cut_fan = float(json.loads((ROOT / "data" / "routing_confirm.json").read_text())["niche_cut_fan_percentile"])
    fan_pct = pct(X.getnnz(axis=0).astype(float))
    current = routed_scorer(m_knn(X, shrink, top=100)[0], rp3beta(X, beta), fan_pct, cut_fan)
    ease = ease_positive_top(X, lam)
    print(f"{len(users):,} viewers, {n:,} movies", flush=True)

    sizes = np.asarray([len(tb[u]) for u in users])
    cur = np.asarray([rank_metrics(current, tb[u], te[u]) for u in users], dtype=float)
    eas = np.asarray([rank_metrics(ease, tb[u], te[u]) for u in users], dtype=float)

    order = np.random.default_rng(17).permutation(len(users))
    val, tst = order[: len(order) // 2], order[len(order) // 2:]

    def routed_ndcg(idx, n_cut):
        use = sizes[idx] >= n_cut
        return np.where(use, eas[idx, 1], cur[idx, 1])

    scores = {str(c): round(float(routed_ndcg(val, c).mean()), 5) for c in CUTS}
    scores["never"] = round(float(cur[val, 1].mean()), 5)
    best = max(scores, key=scores.get)
    out = {"method": " ".join(__doc__.split("\n\n")[1:4]).replace("\n", " "), "user_offset": OFFSET,
           "viewers": len(users), "validation_viewers": len(val), "test_viewers": len(tst),
           "validation_ndcg_by_cut": scores, "chosen_cut_likes": None if best == "never" else int(best),
           "ease_lambda": lam, "ship": False}
    if best != "never":
        c = int(best)
        big = tst[sizes[tst] >= c]
        da, la, ha, _ = paired_bootstrap(routed_ndcg(tst, c), cur[tst, 1], np.mean)
        db, lb, hb, _ = paired_bootstrap(eas[big, 1], cur[big, 1], np.mean)
        out.update({
            "test_viewers_at_or_above_cut": int(len(big)),
            "many_likes": {"current_ndcg": round(float(cur[big, 1].mean()), 4), "ease_ndcg": round(float(eas[big, 1].mean()), 4),
                           "diff": round(db, 4), "ci95": [round(lb, 4), round(hb, 4)]},
            "all": {"current_ndcg": round(float(cur[tst, 1].mean()), 4), "routed_ndcg": round(float(routed_ndcg(tst, c).mean()), 4),
                    "diff": round(da, 4), "ci95": [round(la, 4), round(ha, 4)]},
            "ship": bool(lb > 0 and la > -MARGIN),
        })
    (ROOT / "data" / "history_routing_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
