"""Confirm the long-tail result on viewers no earlier test has touched.

    python training/confirm_long_tail.py --data-dir ml-32m

evaluate_long_tail.py picked RP3beta (beta 0.3) on validation viewers. On its 3,000 test viewers
(745 niche), niche viewers improved but the interval crossed zero, so that test was too small to
decide. Here the same two models, with no retuning, are scored on every other eligible viewer in
the sample (none of them were used to pick anything). Rule written before running:
- RP3beta replaces item-kNN if niche viewers improve (paired-bootstrap 95% interval above zero)
  and all viewers don't get worse by more than 0.002 NDCG@10 (interval lower bound above -0.002).
If it replaces item-kNN, RP3beta is also scored on the benchmark's own 3,000 test viewers, so the
README headline compares the shipped model with popularity on the same viewers as every other model.
Writes data/long_tail_confirm.json (and data/cf_results.json when the shipped model changes).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from benchmark_cf import N_EVAL, evaluate, load_sample, m_knn, m_popularity, matrix, summary as bsummary  # noqa: E402
from evaluate_long_tail import pct, rp3beta  # noqa: E402
from train_cf import FIRST_HIT_DEPTH, metrics, paired_bootstrap, time_split  # noqa: E402

BETA, MARGIN = 0.3, 0.002


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--user-sample", type=int, default=5)
    args = ap.parse_args()
    pos, n = load_sample(args.data_dir, args.user_sample, 20)
    train, test = time_split(pos)
    X = matrix(train, n)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    eligible = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]
    used = set(np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False).tolist())
    fresh = [u for u in eligible if u not in used]
    lt = json.loads((ROOT / "data" / "long_tail_results.json").read_text())
    cut = lt["niche_cut_fan_percentile"]
    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    fans = X.getnnz(axis=0).astype(float)
    fan_pct = pct(fans)
    head = fan_pct >= 0.8
    knn, _ = m_knn(X, shrink, top=100)
    rp3 = rp3beta(X, BETA)
    rng = np.random.default_rng(11)
    res = {"item-kNN": [], "RP3beta": []}
    tail_share = {"item-kNN": [], "RP3beta": []}
    niche = []
    for u in fresh:
        hist = tb[u]
        seeds = [hist[i] for i in sorted(rng.choice(len(hist), 3, replace=False))]
        niche.append(float(np.median(fan_pct[seeds])) <= cut)
        for name, f in (("item-kNN", knn), ("RP3beta", rp3)):
            s = np.asarray(f(np.asarray(seeds)), dtype=np.float64)
            s[hist] = -np.inf
            top = np.argpartition(-s, FIRST_HIT_DEPTH)[:FIRST_HIT_DEPTH]
            top = top[np.argsort(-s[top])]
            res[name].append(metrics(top, te[u]))
            tail_share[name].append(float(np.mean(~head[top[:10]])))
    niche = np.asarray(niche)
    r = {k: np.asarray(v, dtype=float) for k, v in res.items()}

    def seg(mask):
        return {k: {"hit@1": round(float(v[mask, 2].mean()), 4), "ndcg@10": round(float(v[mask, 1].mean()), 4)} for k, v in r.items()}

    da, la, ha, _ = paired_bootstrap(r["RP3beta"][:, 1], r["item-kNN"][:, 1], np.mean)
    dn, ln, hn, _ = paired_bootstrap(r["RP3beta"][niche, 1], r["item-kNN"][niche, 1], np.mean)
    dh, lh, hh, _ = paired_bootstrap(r["RP3beta"][niche, 2], r["item-kNN"][niche, 2], np.mean)
    out = {"method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "),
           "fresh_viewers": len(fresh), "fresh_niche_viewers": int(niche.sum()), "beta": BETA,
           "all": seg(np.ones(len(fresh), bool)), "niche": seg(niche), "others": seg(~niche),
           "top10_less_known_share": {k: round(float(np.mean(v)), 4) for k, v in tail_share.items()},
           "all_ndcg_diff": round(da, 4), "all_ci95": [round(la, 4), round(ha, 4)],
           "niche_ndcg_diff": round(dn, 4), "niche_ci95": [round(ln, 4), round(hn, 4)],
           "niche_hit1_diff": round(dh, 4), "niche_hit1_ci95": [round(lh, 4), round(hh, 4)],
           "replaces_item_knn": bool(ln > 0 and la > -MARGIN)}
    if out["replaces_item_knn"]:
        tst = list(np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False))[N_EVAL:]
        pop_score, _ = m_popularity(X)
        raw = {}
        bench_rows = {}
        for name, f in (("RP3beta", rp3), ("Popularity", pop_score)):
            bench_rows[name] = {}
            for mode in ("random3", "last3", "full"):
                raw[(name, mode)] = evaluate(f, tst, tb, te, mode)
                bench_rows[name][mode] = bsummary(raw[(name, mode)])
        out["rp3beta_on_benchmark_test"] = bench_rows["RP3beta"]
        w3, p3 = raw[("RP3beta", "random3")], raw[("Popularity", "random3")]
        boot = []
        for label, col in (("Recall@10", 0), ("NDCG@10", 1), ("Hit@1", 2)):
            d, lo, hi, share = paired_bootstrap(w3[:, col], p3[:, col], np.mean)
            fmt = "{:+.1%}" if label == "Hit@1" else "{:+.3f}"
            boot.append({"metric": label, "difference": fmt.format(d), "ci95": f"{fmt.format(lo)} to {fmt.format(hi)}",
                         "cf_win_share": share, "significant": bool(lo > 0)})
        d, lo, hi, share = paired_bootstrap(p3[:, 3], w3[:, 3], np.median)
        boot.append({"metric": "Recs to first loved movie (median, fewer is better)", "difference": f"{d:.0f} fewer",
                     "ci95": f"{lo:.0f} to {hi:.0f} fewer", "cf_win_share": share, "significant": bool(lo > 0)})
        res_path = ROOT / "data" / "cf_results.json"
        old_res = json.loads(res_path.read_text())
        new_res = {k: old_res[k] for k in ("dataset", "seed_type", "held_out_users", "benchmark_users", "benchmark_movies",
                                           "benchmark_positives") if k in old_res}
        new_res.update({"model": f"RP3beta (beta {BETA}), top-100 per movie",
                        "full": {"popularity": bench_rows["Popularity"]["full"], "cf": bench_rows["RP3beta"]["full"]},
                        "three_likes": {"popularity": bench_rows["Popularity"]["random3"], "cf": bench_rows["RP3beta"]["random3"]},
                        "bootstrap_three_likes_vs_popularity": boot})
        new_res["lifts_three_likes_vs_popularity"] = {
            k: round((bench_rows["RP3beta"]["random3"][k] / bench_rows["Popularity"]["random3"][k] - 1) * 100)
            for k in ("hit@1", "ndcg@10", "recall@10")}
        res_path.write_text(json.dumps(new_res, indent=2))
    (ROOT / "data" / "long_tail_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
