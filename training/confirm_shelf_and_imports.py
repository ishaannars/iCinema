"""Two questions about what iCinema asks for and what it reads, tested before either is used.

    python training/confirm_shelf_and_imports.py --data-dir ml-32m

Data. The last 1-in-5 slice of MovieLens 32M users that no earlier test used (user id ending 4).
Unlike the other tests, every star rating is kept, so a viewer's low and middling ratings are
available. Per viewer, the most recent 20% of their 4+ star movies are held out; everything they
rated before that point is history. "Viewers like you" is item-kNN (top-100), rebuilt on this slice
with the shipped settings. Score: NDCG@10 on the held-out movies.

Question A, the Step 1 shelf. Which movies should Step 1 show so a new viewer's few Likes say the
most about them? Research on new users (GroupLens, "Getting to know you") found that asking only
about the most popular movies tells you little, since nearly everyone likes them; balancing how
well known a movie is with how much people disagree about it works better. Popular movies still
matter: most people have seen them, so they're the easiest to answer, and most viewers watch them.
Candidates are the 300 movies with the most fans, so every option stays well known.
Only middle grounds can replace today's shelf: they alternate a popular anchor (the next most
popular movie) with an informative pick (by HELF, the harmonic mean of log-popularity and rating
entropy, or by greedy coverage, where each next movie reaches the most viewers not yet reached),
so every other card is one of the most popular movies. Pure HELF and pure coverage are scored for
reference only and can't be picked. A simulated viewer sees the first 24
shelf movies and likes up to 5 they rated 4+ stars; with no Likes they get popularity picks.
Rule written before running: the strategy is picked on a random half of viewers; it replaces the
shelf only if, on the other half, it isn't popularity and
- beats popularity overall (paired-bootstrap 95% interval above zero),
- doesn't make the first screen harder to answer: the share of viewers who can like at least one
  of the first 15 cards drops by no more than 1 percentage point, and
- doesn't hurt mainstream viewers (likes above the routing cut): NDCG@10 interval lower bound
  above -0.002.
If it ships, data/shelf_titles.json lists the shelf in order.

Question B, imported ratings. An import gives more than loved movies: low ratings (2 stars or
less) and middling ones (2.5 to 3.5 stars, "watched, not loved"). Scored from a viewer's whole
loved history, with the app's existing weights and no tuning: Not for me -0.8, Seen 0.5.
Rule written before running, for each signal separately: it is read from imports only if viewers
who have such ratings improve (interval above zero) and all viewers don't get worse by more than
0.002 NDCG@10. Writes data/shelf_import_confirm.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from build_knn import _display_title  # noqa: E402
from train_cf import FIRST_HIT_DEPTH, metrics, normalize_title, paired_bootstrap  # noqa: E402

OFFSET = 4
SHELF = 24
MAX_LIKES = 5
CANDIDATES = 300
MARGIN = 0.002
W_NEG, W_MID = -0.8, 0.5


def load_all(data_dir, min_fans=20):
    parts = []
    for ch in pd.read_csv(Path(data_dir) / "ratings.csv", chunksize=4_000_000,
                          dtype={"userId": "int32", "movieId": "int32", "rating": "float32", "timestamp": "int64"}):
        parts.append(ch[ch["userId"] % 5 == OFFSET])
    r = pd.concat(parts)
    fans = r[r["rating"] >= 4].groupby("movieId").size()
    r = r[r["movieId"].isin(fans[fans >= min_fans].index)]
    loved = r[r["rating"] >= 4].groupby("userId").size()
    r = r[r["userId"].isin(loved[loved >= 5].index)]
    items = np.sort(r["movieId"].unique())
    return r.assign(item=r["movieId"].map({m: i for i, m in enumerate(items)}).astype(np.int32)), items


def split(r):
    """History = everything rated before the viewer's held-out loved movies; test = those movies."""
    pos = r[r["rating"] >= 4].sort_values(["userId", "timestamp"])
    rank = pos.groupby("userId").cumcount()
    size = pos.groupby("userId")["item"].transform("size")
    is_test = rank >= size - np.maximum(1, (size * 0.2).astype(int))
    cut = pos[is_test].groupby("userId")["timestamp"].min()
    test = pos[is_test].groupby("userId")["item"].apply(set)
    r = r.join(cut.rename("cut"), on="userId")
    hist = r[r["timestamp"] < r["cut"]]
    return hist, test


def knn(X, shrink, top=100):
    co = (X.T @ X).toarray().astype(np.float32)
    n = np.diag(co).copy()
    np.fill_diagonal(co, 0)
    S = co / (np.sqrt(np.outer(n, n)) + shrink)
    keep = np.argpartition(-S, top, axis=1)[:, :top]
    Ss = np.zeros_like(S)
    rows = np.arange(S.shape[0])[:, None]
    Ss[rows, keep] = S[rows, keep]
    return Ss


def ndcg(scores, seen, truth):
    s = scores.astype(np.float64)
    s[list(seen)] = -np.inf
    top = np.argpartition(-s, FIRST_HIT_DEPTH)[:FIRST_HIT_DEPTH]
    return metrics(top[np.argsort(-s[top])], truth)[1]


def helf(hist, fans, n):
    """Harmonic mean of normalized log-popularity and normalized rating entropy, per movie."""
    stars = np.clip(np.round(hist["rating"].to_numpy() * 2).astype(int), 1, 10)
    counts = np.zeros((n, 11))
    np.add.at(counts, (hist["item"].to_numpy(), stars), 1)
    p = counts / np.maximum(counts.sum(1, keepdims=True), 1)
    ent = -(np.where(p > 0, p * np.log2(np.where(p > 0, p, 1)), 0)).sum(1)
    lp = np.log1p(fans)
    a, b = lp / max(lp.max(), 1e-9), ent / max(ent.max(), 1e-9)
    return 2 * a * b / np.maximum(a + b, 1e-9)


def alternate(anchors, picks):
    """Popular anchor, then a pick, then the next anchor..., skipping repeats."""
    out, used, a, b = [], set(), iter(anchors), iter(picks)
    for src in [a, b] * len(anchors):
        for i in src:
            if i not in used:
                out.append(i)
                used.add(i)
                break
        if len(out) >= 60:
            break
    return out


def coverage_order(loved_sets, cands, k):
    reached, order, left = set(), [], list(cands)
    for _ in range(min(k, len(left))):
        best = max(left, key=lambda i: len(loved_sets[i] - reached))
        order.append(best)
        reached |= loved_sets[best]
        left.remove(best)
    return order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    r, items = load_all(args.data_dir)
    n = len(items)
    hist, test = split(r)
    loved = hist[hist["rating"] >= 4]
    users = sorted(set(test.index) & set(loved["userId"].unique()))
    codes = loved["userId"].astype("category")
    X = csr_matrix((np.ones(len(loved), np.float32), (codes.cat.codes.to_numpy(), loved["item"].to_numpy())),
                   shape=(codes.cat.categories.size, n))
    X.data[:] = 1.0
    fans = np.asarray(X.sum(axis=0)).ravel()
    shrink = float(json.loads((ROOT / "data" / "cf_benchmark.json").read_text())["results"]["item-kNN"]["params"][0])
    S = knn(X, shrink)
    pop_scores = fans.astype(np.float32)
    by_user = {u: g for u, g in hist.groupby("userId")}
    print(f"{len(users):,} viewers, {n:,} movies", flush=True)

    # Question A: the shelf
    cands = np.argsort(-fans)[:CANDIDATES]
    loved_sets = {int(i): set() for i in cands}
    for u, i in zip(loved["userId"].to_numpy(), loved["item"].to_numpy()):
        if int(i) in loved_sets:
            loved_sets[int(i)].add(int(u))
    h = helf(hist, fans, n)
    pop_order = [int(i) for i in cands]
    helf_order = [int(i) for i in cands[np.argsort(-h[cands])]]
    cov_order = coverage_order(loved_sets, pop_order, 60)
    orders = {"popularity": pop_order, "HELF": helf_order, "coverage": cov_order,
              "popular + HELF": alternate(pop_order, helf_order), "popular + coverage": alternate(pop_order, cov_order)}
    shelves = {k: v[:SHELF] for k, v in orders.items()}
    shelf_scores = {k: [] for k in shelves}
    answerable = {k: [] for k in shelves}
    fan_pct = np.argsort(np.argsort(fans)) / max(n - 1, 1)
    cut = float(json.loads((ROOT / "data" / "routing_confirm.json").read_text())["niche_cut_fan_percentile"])
    mainstream = []
    for u in users:
        g = by_user[u]
        lv = set(g.loc[g["rating"] >= 4, "item"].tolist())
        seen = set(g["item"].tolist())
        mainstream.append(float(np.median(fan_pct[list(lv)])) > cut)
        for k, shelf in shelves.items():
            likes = [i for i in shelf if i in lv][:MAX_LIKES]
            s = S[likes].sum(axis=0) if likes else pop_scores
            shelf_scores[k].append(ndcg(s, seen, test[u]))
            answerable[k].append(any(i in lv for i in shelf[:15]))
    A = {k: np.asarray(v) for k, v in shelf_scores.items()}
    Q = {k: np.asarray(v, dtype=float) for k, v in answerable.items()}
    mainstream = np.asarray(mainstream)
    order = np.random.default_rng(23).permutation(len(users))
    val, tst = order[: len(order) // 2], order[len(order) // 2:]
    eligible = ("popularity", "popular + HELF", "popular + coverage")      # popular movies stay on every other card
    picked = max(eligible, key=lambda k: A[k][val].mean())
    shelf_out = {"validation_ndcg": {k: round(float(v[val].mean()), 4) for k, v in A.items()}, "picked": picked,
                 "ship": False}
    if picked != "popularity":
        d, lo, hi, _ = paired_bootstrap(A[picked][tst], A["popularity"][tst], np.mean)
        ms = tst[mainstream[tst]]
        dm, lm, hm, _ = paired_bootstrap(A[picked][ms], A["popularity"][ms], np.mean) if len(ms) else (0.0, 0.0, 0.0, 0.0)
        drop = float(Q["popularity"][tst].mean() - Q[picked][tst].mean())
        shelf_out.update({"test_ndcg": {k: round(float(v[tst].mean()), 4) for k, v in A.items()},
                          "diff_vs_popularity": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)],
                          "can_like_one_of_first_15": {k: round(float(v[tst].mean()), 4) for k, v in Q.items()},
                          "answerable_drop_points": round(drop * 100, 2),
                          "mainstream_viewers": int(len(ms)),
                          "mainstream_diff": round(dm, 4), "mainstream_ci95": [round(lm, 4), round(hm, 4)],
                          "ship": bool(lo > 0 and drop * 100 <= 1.0 and lm > -MARGIN)})
    if shelf_out["ship"]:
        movies = pd.read_csv(Path(args.data_dir) / "movies.csv").set_index("movieId")
        links = pd.read_csv(Path(args.data_dir) / "links.csv").set_index("movieId")
        full = orders[picked][:60]
        rows = []
        for i in full:
            mid = int(items[i])
            raw = movies.loc[mid, "title"] if mid in movies.index else ""
            _, year = normalize_title(raw)
            tmdb = links.loc[mid, "tmdbId"] if mid in links.index else None
            rows.append({"title": _display_title(raw), "year": int(year or 0),
                         "tmdb_id": int(tmdb) if pd.notna(tmdb) else 0})
        (ROOT / "data" / "shelf_titles.json").write_text(json.dumps({"strategy": picked, "titles": rows}, indent=1))
    else:
        (ROOT / "data" / "shelf_titles.json").unlink(missing_ok=True)

    # Question B: low and middling ratings from an import
    base, with_neg, with_mid, has_neg, has_mid = [], [], [], [], []
    for u in users:
        g = by_user[u]
        it, rt = g["item"].to_numpy(), g["rating"].to_numpy()
        seen = set(it.tolist())
        lv, neg, mid = it[rt >= 4], it[rt <= 2], it[(rt > 2) & (rt < 4)]
        b = S[lv].sum(axis=0)
        base.append(ndcg(b, seen, test[u]))
        with_neg.append(ndcg(b + W_NEG * S[neg].sum(axis=0), seen, test[u]) if len(neg) else base[-1])
        with_mid.append(ndcg(b + W_MID * S[mid].sum(axis=0), seen, test[u]) if len(mid) else base[-1])
        has_neg.append(len(neg) > 0)
        has_mid.append(len(mid) > 0)
    base, with_neg, with_mid = map(np.asarray, (base, with_neg, with_mid))
    has_neg, has_mid = np.asarray(has_neg), np.asarray(has_mid)

    def judge(alt, mask):
        ds, ls, hs, _ = paired_bootstrap(alt[mask], base[mask], np.mean)
        da, la, ha, _ = paired_bootstrap(alt, base, np.mean)
        return {"viewers_with_signal": int(mask.sum()), "diff_with_signal": round(ds, 4), "ci95_with_signal": [round(ls, 4), round(hs, 4)],
                "diff_all": round(da, 4), "ci95_all": [round(la, 4), round(ha, 4)], "use": bool(ls > 0 and la > -MARGIN)}

    out = {"method": " ".join(__doc__.split("\n\n")[1:5]).replace("\n", " "), "user_offset": OFFSET,
           "viewers": len(users), "movies": int(n), "shelf": shelf_out,
           "imports": {"low_ratings_as_not_for_me": judge(with_neg, has_neg),
                       "middling_ratings_as_seen": judge(with_mid, has_mid)}}
    (ROOT / "data" / "shelf_import_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
