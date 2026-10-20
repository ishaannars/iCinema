"""Can niche viewers get RP3beta without mainstream viewers paying for it?

    python training/confirm_routing.py --data-dir ml-32m

RP3beta helped viewers with less mainstream taste but dipped mainstream viewers slightly
(confirm_long_tail.py). The obvious fix is to route: RP3beta when a viewer's likes are less-loved
movies, item-kNN otherwise. Deciding that after seeing the earlier results would be fishing, so
it is tested on a completely new set of viewers: a different 1-in-5 slice of MovieLens 32M users
(user id ending differently), with both models rebuilt on that slice. Nothing was tuned here.
The niche cut (median fan percentile of the 3 likes) is the one set on the first validation set.

Rule written before running: ship routing if, against RP3beta for everyone, all viewers improve
(paired-bootstrap 95% interval above zero) and niche viewers don't get worse by more than 0.002
NDCG@10 (interval lower bound above -0.002). If it ships, the routed model is also scored on the
benchmark's own 3,000 test viewers (first slice), so the README headline compares it with
popularity on the same viewers as every other model. Writes data/routing_confirm.json (and
data/cf_results.json when routing ships).
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

MARGIN = 0.002


def routed_scorer(knn, rp3, fan_pct, cut):
    def score(seeds):
        f = rp3 if float(np.median(fan_pct[np.asarray(seeds)])) <= cut else knn
        return f(seeds)
    return score


def headline(data_dir, beta, shrink, cut):
    """Routed model and popularity on the benchmark's 3,000 test viewers, in cf_results.json format."""
    pos, n = load_sample(data_dir, 5, 20)
    train, test = time_split(pos)
    X = matrix(train, n)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    eligible = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]
    tst = list(np.random.default_rng(7).choice(eligible, 2 * N_EVAL, replace=False))[N_EVAL:]
    fan_pct = pct(X.getnnz(axis=0).astype(float))
    routed = routed_scorer(m_knn(X, shrink, top=100)[0], rp3beta(X, beta), fan_pct, cut)
    pop, _ = m_popularity(X)
    raw, rows = {}, {}
    for name, f in (("routed", routed), ("Popularity", pop)):
        rows[name] = {}
        for mode in ("random3", "last3", "full"):
            raw[(name, mode)] = evaluate(f, tst, tb, te, mode)
            rows[name][mode] = bsummary(raw[(name, mode)])
    w3, p3 = raw[("routed", "random3")], raw[("Popularity", "random3")]
    boot = []
    for label, col in (("Recall@10", 0), ("NDCG@10", 1), ("Hit@1", 2)):
        d, lo, hi, share = paired_bootstrap(w3[:, col], p3[:, col], np.mean)
        fmt = "{:+.1%}" if label == "Hit@1" else "{:+.3f}"
        boot.append({"metric": label, "difference": fmt.format(d), "ci95": f"{fmt.format(lo)} to {fmt.format(hi)}",
                     "cf_win_share": share, "significant": bool(lo > 0)})
    d, lo, hi, share = paired_bootstrap(p3[:, 3], w3[:, 3], np.median)
    boot.append({"metric": "Recs to first loved movie (median, fewer is better)", "difference": f"{d:.0f} fewer",
                 "ci95": f"{lo:.0f} to {hi:.0f} fewer", "cf_win_share": share, "significant": bool(lo > 0)})
    return rows, boot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--user-offset", type=int, default=1, help="slice not used by any earlier test (earlier: 0)")
    args = ap.parse_args()
    pos, n = load_sample(args.data_dir, 5, 20, user_offset=args.user_offset)
    train, test = time_split(pos)
    X = matrix(train, n)
    tb = train.sort_values("timestamp").groupby("userId")["item"].apply(list)
    te = test.groupby("userId")["item"].apply(set)
    users = [u for u in te.index if u in tb.index and len(tb[u]) >= 3]
    conf = json.loads((ROOT / "data" / "long_tail_confirm.json").read_text())
    cut = json.loads((ROOT / "data" / "long_tail_results.json").read_text())["niche_cut_fan_percentile"]
    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    fan_pct = pct(X.getnnz(axis=0).astype(float))
    knn, _ = m_knn(X, shrink, top=100)
    rp3 = rp3beta(X, float(conf["beta"]))
    rng = np.random.default_rng(13)
    res = {"item-kNN": [], "RP3beta": [], "routed": []}
    niche = []
    for u in users:
        hist = tb[u]
        seeds = [hist[i] for i in sorted(rng.choice(len(hist), 3, replace=False))]
        is_niche = float(np.median(fan_pct[seeds])) <= cut
        niche.append(is_niche)
        ranks = {}
        for name, f in (("item-kNN", knn), ("RP3beta", rp3)):
            s = np.asarray(f(np.asarray(seeds)), dtype=np.float64)
            s[hist] = -np.inf
            top = np.argpartition(-s, FIRST_HIT_DEPTH)[:FIRST_HIT_DEPTH]
            ranks[name] = metrics(top[np.argsort(-s[top])], te[u])
            res[name].append(ranks[name])
        res["routed"].append(ranks["RP3beta"] if is_niche else ranks["item-kNN"])
    niche = np.asarray(niche)
    r = {k: np.asarray(v, dtype=float) for k, v in res.items()}

    def seg(mask):
        return {k: {"hit@1": round(float(v[mask, 2].mean()), 4), "ndcg@10": round(float(v[mask, 1].mean()), 4)} for k, v in r.items()}

    da, la, ha, _ = paired_bootstrap(r["routed"][:, 1], r["RP3beta"][:, 1], np.mean)
    dn, ln, hn, _ = paired_bootstrap(r["routed"][niche, 1], r["RP3beta"][niche, 1], np.mean)
    dk, lk, hk, _ = paired_bootstrap(r["routed"][:, 1], r["item-kNN"][:, 1], np.mean)
    dkn, lkn, hkn, _ = paired_bootstrap(r["routed"][niche, 1], r["item-kNN"][niche, 1], np.mean)
    out = {"method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "), "user_offset": args.user_offset,
           "viewers": len(users), "niche_viewers": int(niche.sum()), "niche_cut_fan_percentile": cut,
           "all": seg(np.ones(len(users), bool)), "niche": seg(niche), "others": seg(~niche),
           "routed_vs_rp3_all": {"ndcg_diff": round(da, 4), "ci95": [round(la, 4), round(ha, 4)]},
           "routed_vs_rp3_niche": {"ndcg_diff": round(dn, 4), "ci95": [round(ln, 4), round(hn, 4)]},
           "routed_vs_knn_all": {"ndcg_diff": round(dk, 4), "ci95": [round(lk, 4), round(hk, 4)]},
           "routed_vs_knn_niche": {"ndcg_diff": round(dkn, 4), "ci95": [round(lkn, 4), round(hkn, 4)]},
           "ship_routing": bool(la > 0 and ln > -MARGIN)}
    if out["ship_routing"]:
        rows, boot = headline(args.data_dir, float(conf["beta"]), shrink, cut)
        out["routed_on_benchmark_test"] = rows["routed"]
        res_path = ROOT / "data" / "cf_results.json"
        old = json.loads(res_path.read_text())
        new = {k: old[k] for k in ("dataset", "seed_type", "held_out_users", "benchmark_users", "benchmark_movies",
                                   "benchmark_positives", "train_users", "train_movies", "train_positives") if k in old}
        new.update({"model": f"Routed: RP3beta (beta {conf['beta']:g}) for less mainstream taste, item-kNN otherwise",
                    "full": {"popularity": rows["Popularity"]["full"], "cf": rows["routed"]["full"]},
                    "three_likes": {"popularity": rows["Popularity"]["random3"], "cf": rows["routed"]["random3"]},
                    "bootstrap_three_likes_vs_popularity": boot})
        new["lifts_three_likes_vs_popularity"] = {
            k: round((rows["routed"]["random3"][k] / rows["Popularity"]["random3"][k] - 1) * 100) for k in ("hit@1", "ndcg@10", "recall@10")}
        res_path.write_text(json.dumps(new, indent=2))
    (ROOT / "data" / "routing_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
