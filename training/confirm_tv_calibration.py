"""Can a show card say "about N% chance you'll love it" the way movie cards do?

    python training/confirm_tv_calibration.py --amazon-dir amazon-movies-tv

Until now show cards printed the shipped blend score (a rank percentile) as "N% match", right next to
movie cards whose percent is a tested chance. Same look, different meaning. This test decides which one
a show card is allowed to show.

Same data, matching, item-kNN, and blend as training/confirm_tv_blend.py. A fresh random group of people
(seed 41) with 3+ loved movies and 1+ rated show is held out; similarities come only from everyone else.
Each held-out person's loved movies rank every show, exactly as the app does. Every show the person
rated (any stars) is a data point: its top-% rank, and whether they gave it 4+ stars ("if you watch it,
how likely are you to love it?"). Isotonic regression maps rank to chance, fit on half the people and
checked once on the other half.

Rules, written before running:
- Validity: the ranking must tell loved from not-loved shows. AUC on the test half, with a person-level
  bootstrap 95% interval whose lower bound is above 0.5. If not, the odds don't count.
- Ships only if: test calibration error (ECE) is at most 2 points, AND its Brier score beats always
  guessing the average (paired-bootstrap interval below zero), AND at least 500 test people.
- If it fails, show cards show their rank only ("#1 for you"), never a percent.

Writes data/tv_calibration.json (the app reads it). Prints the result to paste back.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from confirm_tv import MIN_FANS, _find, _open, cosine_top, is_tv, norm, show_name  # noqa: E402
from confirm_tv_blend import pct  # noqa: E402
from evaluate_love_and_learning import BANDS, ece  # noqa: E402
from train_cf import paired_bootstrap  # noqa: E402

ECE_MAX = 0.02
MIN_TEST_PEOPLE = 500


def load_with_ratings(amazon_dir):
    """confirm_tv.load, plus every show rating (any stars) kept per person."""
    import re
    d = Path(amazon_dir)
    knn = np.load(ROOT / "data" / "cf_knn.npz")
    best = {}
    for i, (t, p) in enumerate(zip(knn["norm_title"], knn["popularity"])):
        k = norm(t)
        if k not in best or p > knn["popularity"][best[k]]:
            best[k] = i
    node_of = {}
    with _open(_find(d, "meta_Movies_and_TV")) as f:
        for line in f:
            m = json.loads(line)
            asin, title = m.get("parent_asin"), m.get("title")
            if not asin or not title:
                continue
            if is_tv(m):
                node_of[asin] = "tv:" + norm(show_name(title))
            else:
                row = best.get(norm(re.sub(r"\s*[\(\[].*?[\)\]]", "", title)))
                if row is not None:
                    node_of[asin] = f"mv:{row}"
    users, nodes, ui, ni = {}, {}, [], []
    show_ratings = defaultdict(dict)        # user row -> {show node: best rating}

    def add(user, asin, rating):
        node = node_of.get(asin)
        if node is None:
            return
        r = float(rating or 0)
        u = users.setdefault(user, len(users))
        if node.startswith("tv:"):
            show_ratings[u][node] = max(r, show_ratings[u].get(node, 0.0))
        if r >= 4:
            ui.append(u)
            ni.append(nodes.setdefault(node, len(nodes)))

    csv_path = next((d / n for n in ("Movies_and_TV.csv", "Movies_and_TV.csv.gz") if (d / n).exists()), None)
    if csv_path is not None:
        with _open(csv_path) as f:
            for r in csv.DictReader(f):
                add(r.get("user_id"), r.get("parent_asin"), r.get("rating"))
    else:
        with _open(_find(d, "Movies_and_TV")) as f:
            for line in f:
                r = json.loads(line)
                add(r.get("user_id"), r.get("parent_asin"), r.get("rating"))
    X = csr_matrix((np.ones(len(ui), np.float32), (ui, ni)), shape=(len(users), len(nodes)))
    X.sum_duplicates()
    X.data[:] = 1.0
    fans = np.asarray(X.sum(axis=0)).ravel()
    keep = np.flatnonzero(fans >= MIN_FANS)
    X = X[:, keep].tocsr()
    node_names = np.array(list(nodes))[keep]
    return X, node_names, show_ratings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amazon-dir", default="amazon-movies-tv")
    args = ap.parse_args()
    X, node_names, show_ratings = load_with_ratings(args.amazon_dir)
    is_show = np.array([n.startswith("tv:") for n in node_names])
    shows, movies = np.flatnonzero(is_show), np.flatnonzero(~is_show)
    col_of = {n: i for i, n in enumerate(node_names)}
    show_pos = {int(j): k for k, j in enumerate(shows)}
    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    a = float(json.loads((ROOT / "data" / "tv_blend_confirm.json").read_text())["popularity_weight"])

    n_movie = np.asarray(X[:, movies].sum(axis=1)).ravel()
    rated_n = np.array([sum(1 for n in show_ratings.get(u, {}) if n in col_of) for u in range(X.shape[0])])
    eligible = np.flatnonzero((n_movie >= 3) & (rated_n >= 1))
    held = np.random.default_rng(41).choice(eligible, min(10000, len(eligible) // 2), replace=False)
    mask = np.ones(X.shape[0], bool)
    mask[held] = False
    sims, fans_tr = cosine_top(X[mask], shows, shrink, rows=movies)
    pop_pct = pct(fans_tr[shows].astype(float))
    print(f"{X.shape[0]:,} people, {len(shows):,} shows, {len(held):,} held out, blend weight {a}", flush=True)

    points = []          # (person, top-% rank, loved)
    for u in held:
        s = np.zeros(len(shows))
        for m in X.getrow(u).indices:
            if not is_show[m] and int(m) in sims:
                j, w = sims[int(m)]
                np.add.at(s, [show_pos[int(x)] for x in j], w)
        if not s.any():
            continue
        blend = (1 - a) * pct(s) + a * pop_pct
        order = np.argsort(-blend)
        top_pct = np.empty(len(shows))
        top_pct[order] = (np.arange(len(shows)) + 1) / len(shows) * 100
        for node, rating in show_ratings.get(int(u), {}).items():
            c = col_of.get(node)
            if c is not None and int(c) in show_pos:
                points.append((int(u), float(top_pct[show_pos[int(c)]]), float(rating >= 4)))

    people = np.unique([p for p, _, _ in points])
    split = set(np.random.default_rng(43).permutation(people)[: len(people) // 2].tolist())
    pv = [p for p in points if p[0] in split]
    pt = [p for p in points if p[0] not in split]
    iso = IsotonicRegression(increasing=False, y_min=0.0, y_max=1.0, out_of_bounds="clip")
    iso.fit([x for _, x, _ in pv], [y for _, _, y in pv])
    ut = np.array([p for p, _, _ in pt]); xt = np.array([x for _, x, _ in pt]); yt = np.array([y for _, _, y in pt])
    pred = iso.predict(xt)
    base = float(np.mean([y for _, _, y in pv]))
    ids = np.unique(ut)
    b_model = np.array([np.mean((pred[ut == u] - yt[ut == u]) ** 2) for u in ids])
    b_base = np.array([np.mean((base - yt[ut == u]) ** 2) for u in ids])
    d, lo, hi, _ = paired_bootstrap(b_model, b_base, np.mean)
    err = ece(pred, yt)

    # Validity: person-level bootstrap of the ranking's AUC (lower rank % = predicted more loved).
    auc = float(roc_auc_score(yt, -xt)) if 0 < yt.mean() < 1 else 0.5
    rows_of = {u: np.flatnonzero(ut == u) for u in ids}
    rng = np.random.default_rng(47)
    boots = []
    for _ in range(500):
        idx = np.concatenate([rows_of[u] for u in rng.choice(ids, len(ids), replace=True)])
        if 0 < yt[idx].mean() < 1:
            boots.append(roc_auc_score(yt[idx], -xt[idx]))
    auc_lo = float(np.percentile(boots, 2.5)) if boots else 0.5
    valid = auc_lo > 0.5
    ships = bool(valid and err <= ECE_MAX and hi < 0 and len(ids) >= MIN_TEST_PEOPLE)

    out = {"method": " ".join(__doc__.split("\n\n")[2:4]).replace("\n", " "),
           "validation_points": len(pv), "test_points": len(pt), "test_people": int(len(ids)),
           "average_love_rate": round(base, 4),
           "test_auc": round(auc, 4), "test_auc_ci95_low": round(auc_lo, 4), "valid": bool(valid),
           "test_ece": round(err, 4), "ece_max": ECE_MAX,
           "brier_diff_vs_average": round(d, 5), "brier_ci95": [round(lo, 5), round(hi, 5)],
           "table": [{"top_pct": b, "chance": round(float(iso.predict([b])[0]), 4)} for b in BANDS],
           "ships": ships}
    (ROOT / "data" / "tv_calibration.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))
    print("SHIPS: show cards get calibrated odds." if ships else "DOES NOT SHIP: show cards show rank only.")


if __name__ == "__main__":
    main()
