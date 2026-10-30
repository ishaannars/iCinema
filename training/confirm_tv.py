"""TV shows from real fan ratings: do "people who loved your movies" predict the shows you love?

    python training/confirm_tv.py --amazon-dir amazon-movies-tv

MovieLens has no TV, so this uses the Movies_and_TV part of Amazon Reviews 2023 (McAuley Lab,
UCSD; 17.3M ratings from 6.5M people, 1996 to Sep 2023, released for research). Each product is
either a show (a TV category or "Season"/"Series" in its title; all seasons of a show count as one
show) or a movie, matched to iCinema's MovieLens movies by title. A 4 or 5 star rating is a "loved."
"Fans like you" is item-kNN, the same cosine-with-shrink model iCinema uses for movies.

Test, written before running: people with at least 3 loved movies and 2 loved shows are split at
random; half are held out entirely, and similarities come only from everyone else. For each held-out
person, their loved movies alone rank every show, as a new iCinema viewer's movie likes would.
Score: NDCG@20 on the shows they really loved, against the most popular shows. Ships only if it
wins with a paired-bootstrap 95% interval above zero, on at least 500 held-out people. If it ships,
the similarities are rebuilt from everyone and saved as data/tv_knn.npz. Writes data/tv_confirm.json.

Download two files into amazon-movies-tv/ (from the McAuley-Lab/Amazon-Reviews-2023 dataset on Hugging
Face): the ratings-only file benchmark/0core/rating_only/Movies_and_TV.csv, and the product details
raw/meta_categories/meta_Movies_and_TV.jsonl (saved as meta_Movies_and_TV.jsonl).
"""
import argparse
import gzip
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from train_cf import paired_bootstrap  # noqa: E402

TOP = 50
MIN_FANS = 10
K = 20
_TV_TITLE = re.compile(r"\b(season|seasons|series|complete series|the complete|volume \d+|vol\. ?\d+|episodes?)\b", re.I)
_CUT = re.compile(r"\s*[:\-–(\[,]\s*(?:the\s+)?(?:complete|season|seasons|series|volume|vol\.|collection|box set|episodes?)\b.*$", re.I)


def _open(path):
    return gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)


def _find(d, stem):
    for ext in (".jsonl", ".jsonl.gz", ".json", ".json.gz"):
        if (d / (stem + ext)).exists():
            return d / (stem + ext)
    raise SystemExit(f"Missing {stem}.jsonl in {d}. See the download note at the top of this file.")


def norm(t):
    return " ".join(re.sub(r"[^\w\s]", " ", str(t).lower()).split())


def show_name(title):
    t = _CUT.sub("", str(title)).strip()
    t = re.sub(r"\s*(season|series)\s*\d+.*$", "", t, flags=re.I).strip()
    return t or str(title).strip()


def is_tv(meta):
    """A show if a category is TV itself (not the whole store's "Movies & TV") or the title says Season/Series."""
    cats = [str(c).strip() for c in (meta.get("categories") or [])]
    tv_cat = any(c == "TV" or c.startswith("TV ") or c in ("TV Series", "Television") for c in cats)
    return tv_cat or bool(_TV_TITLE.search(str(meta.get("title") or "")))


def cosine_top(X, cols_keep, shrink, rows=None, top=TOP):
    """For each node (row of X.T), its `top` most similar nodes among cols_keep, by cosine with shrink."""
    co = (X.T @ X).tocsr()
    fans = np.asarray(X.sum(axis=0)).ravel()
    keep = np.zeros(X.shape[1], bool)
    keep[cols_keep] = True
    out = {}
    for i in (rows if rows is not None else range(X.shape[1])):
        start, end = co.indptr[i], co.indptr[i + 1]
        j, v = co.indices[start:end], co.data[start:end]
        m = keep[j] & (j != i)
        j, v = j[m], v[m]
        if not len(j):
            continue
        s = v / (np.sqrt(fans[i] * fans[j]) + shrink)
        o = np.argsort(-s)[:top]
        out[int(i)] = (j[o].astype(np.int32), s[o].astype(np.float32))
    return out, fans


def load(amazon_dir, min_fans=MIN_FANS):
    d = Path(amazon_dir)
    knn = np.load(ROOT / "data" / "cf_knn.npz")
    best = {}
    for i, (t, p) in enumerate(zip(knn["norm_title"], knn["popularity"])):
        k = norm(t)
        if k not in best or p > knn["popularity"][best[k]]:
            best[k] = i
    node_of, names = {}, {}
    with _open(_find(d, "meta_Movies_and_TV")) as f:
        for line in f:
            m = json.loads(line)
            asin, title = m.get("parent_asin"), m.get("title")
            if not asin or not title:
                continue
            if is_tv(m):
                name = show_name(title)
                node_of[asin] = "tv:" + norm(name)
                names.setdefault("tv:" + norm(name), name)
            else:
                row = best.get(norm(re.sub(r"\s*[\(\[].*?[\)\]]", "", title)))
                if row is not None:
                    node_of[asin] = f"mv:{row}"
    users, nodes = {}, {}
    ui, ni = [], []

    def add(user, asin, rating):
        if float(rating or 0) < 4:
            return
        node = node_of.get(asin)
        if node is None:
            return
        ui.append(users.setdefault(user, len(users)))
        ni.append(nodes.setdefault(node, len(nodes)))

    csv_path = next((d / n for n in ("Movies_and_TV.csv", "Movies_and_TV.csv.gz") if (d / n).exists()), None)
    if csv_path is not None:                     # the small ratings-only file (user_id,parent_asin,rating,timestamp)
        import csv
        with _open(csv_path) as f:
            for r in csv.DictReader(f):
                add(r.get("user_id"), r.get("parent_asin"), r.get("rating"))
    else:
        with _open(_find(d, "Movies_and_TV")) as f:
            for line in f:
                r = json.loads(line)
                add(r.get("user_id"), r.get("parent_asin"), r.get("rating"))
    X = csr_matrix((np.ones(len(ui), np.float32), (ui, ni)), shape=(len(users), len(nodes)))
    X.data[:] = 1.0
    X.sum_duplicates()
    X.data[:] = 1.0
    fans = np.asarray(X.sum(axis=0)).ravel()
    keep = np.flatnonzero(fans >= min_fans)
    X = X[:, keep].tocsr()
    node_names = np.array(list(nodes))[keep]
    return X, node_names, names


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
    rng = np.random.default_rng(29)
    held = rng.choice(eligible, len(eligible) // 2, replace=False) if len(eligible) else np.array([], int)
    held = held[:5000]
    mask = np.ones(X.shape[0], bool)
    mask[held] = False
    Xtr = X[mask]
    sims, fans_tr = cosine_top(Xtr, shows, shrink, rows=movies)
    pop_rank = shows[np.argsort(-fans_tr[shows])][:K]
    print(f"{X.shape[0]:,} people, {len(shows):,} shows, {len(movies):,} matched movies, {len(held):,} held out", flush=True)

    def ndcg(ranked, truth):
        g = sum(1 / np.log2(k + 2) for k, s in enumerate(ranked[:K]) if s in truth)
        ideal = sum(1 / np.log2(k + 2) for k in range(min(len(truth), K)))
        return g / ideal if ideal else 0.0

    model, base = [], []
    for u in held:
        row = X.getrow(u).indices
        liked_movies = [i for i in row if not is_show[i]]
        truth = set(i for i in row if is_show[i])
        s = {}
        for m in liked_movies:
            if m in sims:
                for j, w in zip(*sims[m]):
                    s[int(j)] = s.get(int(j), 0.0) + float(w)
        ranked = sorted(s, key=s.get, reverse=True)
        ranked += [int(j) for j in pop_rank if j not in s]       # fall back to popular shows
        model.append(ndcg(ranked, truth))
        base.append(ndcg([int(j) for j in pop_rank], truth))
    model, base = np.asarray(model), np.asarray(base)
    out = {"method": " ".join(__doc__.split("\n\n")[1:3]).replace("\n", " "), "people": int(X.shape[0]),
           "shows": int(len(shows)), "matched_movies": int(len(movies)), "held_out": int(len(held)), "ship": False}
    if len(held) >= 500:
        d, lo, hi, _ = paired_bootstrap(model, base, np.mean)
        out.update({"ndcg_at_20": {"fans like you": round(float(model.mean()), 4), "most popular shows": round(float(base.mean()), 4)},
                    "diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "ship": bool(lo > 0)})
    path = ROOT / "data" / "tv_knn.npz"
    if out["ship"]:
        sims_all, fans_all = cosine_top(X, shows, shrink)
        show_pos = {int(j): k for k, j in enumerate(shows)}
        def pack(rows):
            nbr = np.full((len(rows), TOP), -1, np.int32)
            w = np.zeros((len(rows), TOP), np.float16)
            for r, i in enumerate(rows):
                if int(i) in sims_all:
                    j, v = sims_all[int(i)]
                    nbr[r, :len(j)] = [show_pos[int(x)] for x in j]
                    w[r, :len(v)] = v
            return nbr, w
        m_nbr, m_w = pack(movies)
        s_nbr, s_w = pack(shows)
        np.savez_compressed(path, show_names=np.array([names.get(n, n[3:]) for n in node_names[shows]]),
                            show_fans=fans_all[shows].astype(np.int32),
                            movie_rows=np.array([int(n[3:]) for n in node_names[movies]], np.int32),
                            movie_nbr=m_nbr, movie_w=m_w, show_nbr=s_nbr, show_w=s_w)
    else:
        path.unlink(missing_ok=True)
    (ROOT / "data" / "tv_confirm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
