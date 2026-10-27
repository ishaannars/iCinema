"""Build the shipped content model from MovieLens genres and fan tags.

    python training/build_content.py --data-dir ml-32m

Every movie in data/cf_knn.npz gets a 64-number description built from its MovieLens genres and
the tags MovieLens fans gave it (TF-IDF, then truncated SVD). It is the same recipe the offline
tests used (training/evaluate_blends.py), so the app now runs exactly what was tested.

No TMDB content is used to build or run this model: TMDB is used only to display titles,
posters, and where to watch. Writes data/content_ml.npz, row-aligned with data/cf_knn.npz.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from train_cf import normalize_title  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    d = Path(args.data_dir)
    knn = np.load(ROOT / "data" / "cf_knn.npz")
    n = len(knn["norm_title"])
    movies = pd.read_csv(d / "movies.csv")
    links = pd.read_csv(d / "links.csv")
    tags = pd.read_csv(d / "tags.csv", usecols=["movieId", "tag"]).dropna(subset=["tag"])
    tags["tag"] = tags["tag"].astype(str).str.lower().str.replace(r"[^\w\s]", " ", regex=True)
    tag_text = tags.groupby("movieId")["tag"].apply(lambda t: " ".join(str(x) for x in t.head(300)))

    # Match each row of cf_knn.npz to a MovieLens movieId: by TMDB id first, then by title and year.
    by_tmdb = {int(t): int(m) for m, t in zip(links["movieId"], links["tmdbId"].fillna(-1)) if t > 0}
    by_title = {}
    for mid, title in zip(movies["movieId"], movies["title"]):
        by_title.setdefault(normalize_title(title), int(mid))
    row_movie = []
    for i in range(n):
        t = int(knn["tmdb_id"][i])
        mid = by_tmdb.get(t) if t > 0 else None
        if mid is None:
            mid = by_title.get((str(knn["norm_title"][i]), int(knn["year"][i]) or None))
        row_movie.append(mid)

    m = movies.set_index("movieId")
    docs = [(m.loc[mid, "genres"].replace("|", " ") + " ") * 3 + tag_text.get(mid, "")
            if mid is not None and mid in m.index else "" for mid in row_movie]
    has = np.array([bool(doc.strip()) and "(no genres listed)" not in doc for doc in docs])
    X = TfidfVectorizer(min_df=3, max_features=20000, sublinear_tf=True).fit_transform(docs)
    E = TruncatedSVD(64, random_state=7).fit_transform(X).astype(np.float32)
    E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-8
    E[~has] = 0
    np.savez_compressed(ROOT / "data" / "content_ml.npz", vec=E.astype(np.float16), has=has)
    info = {"source": "MovieLens 32M genres and fan tags (TF-IDF + truncated SVD, 64 dimensions)",
            "movies_with_vectors": int(has.sum()), "movies_total": n,
            "tmdb_content_used": False}
    (ROOT / "data" / "content_ml.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
