"""A fresh test of "picks get sharper as you use it," on viewers no earlier test touched.

    python training/confirm_learning_curve.py --data-dir ml-32m

The first learning-curve test (evaluate_love_and_learning.py) compared 10 choices with 3 and the
interval crossed zero, so the app makes no such claim. Its curve kept rising to 50 choices. That
pattern was seen on those viewers, so it can't be tested on them. It is tested here instead, on a
separate 1-in-5 slice of MovieLens users (user ids ending differently from every earlier test),
with both models rebuilt on that slice.

Rule written before running: the claim is allowed only if NDCG@10 with 50 choices beats 3 choices
(paired-bootstrap 95% interval above zero) for viewers with 50+ earlier loves.
Writes data/learning_curve_confirm.json.
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
from train_cf import metrics, paired_bootstrap, time_split  # noqa: E402

OFFSET = 2          # slices 0 and 1 were used by earlier tests
STEPS = (3, 50)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    pos, n = load_sample(args.data_dir, 5, 20, user_offset=OFFSET)
    train, test = time_split(pos)
    X = matrix(train, n)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    users = [u for u in te.index if u in tb.index and len(tb[u]) >= max(STEPS)]
    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    beta = float(json.loads((ROOT / "data" / "long_tail_confirm.json").read_text())["beta"])
    cut = float(json.loads((ROOT / "data" / "routing_confirm.json").read_text())["niche_cut_fan_percentile"])
    rank = routed_scorer(m_knn(X, shrink, top=100)[0], rp3beta(X, beta), pct(X.getnnz(axis=0).astype(float)), cut)
    r = np.random.default_rng(17)
    res = {k: [] for k in STEPS}
    for u in users:
        hist = tb[u]
        order = r.permutation(len(hist))
        for k in STEPS:
            seeds = [hist[i] for i in sorted(order[:k])]
            s = np.asarray(rank(np.asarray(seeds)), dtype=float)
            s[hist] = -np.inf
            top = np.argpartition(-s, 50)[:50]
            res[k].append(metrics(top[np.argsort(-s[top])], te[u]))
    res = {k: np.asarray(v, dtype=float) for k, v in res.items()}
    d, lo, hi, _ = paired_bootstrap(res[50][:, 1], res[3][:, 1], np.mean)
    out = {"method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "), "user_offset": OFFSET, "viewers": len(users),
           "steps": [{"choices": k, "hit@1": round(float(res[k][:, 2].mean()), 4), "ndcg@10": round(float(res[k][:, 1].mean()), 4)}
                     for k in STEPS],
           "ndcg_gain_50_vs_3": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "claim_allowed": bool(lo > 0)}
    (ROOT / "data" / "learning_curve_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
