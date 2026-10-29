"""Fetch open movie facts from Wikidata (CC0) for the new-release model.

    python training/fetch_wikidata.py --data-dir ml-32m

For every movie in data/cf_knn.npz (matched through MovieLens links.csv IMDb ids) and for recent
movies (released in the last 3 years, the most-linked first), collects director, cast, production
company, genre, and country. Wikidata content is public domain, so it can be used to train a model;
TMDB content is not used. Results are cached in data/wikidata_cache/ so a rerun only fetches what's
missing. Writes data/wikidata_movies.json. Takes about 15-30 minutes on a first run.
"""
import argparse
import datetime
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from train_cf import normalize_title  # noqa: E402

ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "iCinema-research/1.0 (portfolio project; contact via GitHub)",
           "Accept": "application/sparql-results+json"}
CACHE = ROOT / "data" / "wikidata_cache"
PROPS = {"director": "P57", "cast": "P161", "company": "P272", "genre": "P136", "country": "P495"}
BATCH = 150
RECENT_LIMIT = 4000


def sparql(query, tries=5):
    import requests
    for k in range(tries):
        try:
            r = requests.get(ENDPOINT, params={"query": query, "format": "json"}, headers=HEADERS, timeout=120)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(10 * (k + 1))
                continue
            r.raise_for_status()
            return r.json()["results"]["bindings"]
        except Exception:
            time.sleep(10 * (k + 1))
    raise RuntimeError("Wikidata didn't answer after several tries; run the script again to resume.")


def _features_query(values_clause):
    parts = "\n".join(f"OPTIONAL {{ ?film wdt:{p} ?{name}_ . }}" for name, p in PROPS.items())
    sel = " ".join(f"(GROUP_CONCAT(DISTINCT STRAFTER(STR(?{n}_), 'entity/'); separator='|') AS ?{n})" for n in PROPS)
    return f"""SELECT ?film ?imdb ?tmdb (MIN(?date) AS ?released) {sel} WHERE {{
  {values_clause}
  OPTIONAL {{ ?film wdt:P345 ?imdb . }}
  OPTIONAL {{ ?film wdt:P4947 ?tmdb . }}
  OPTIONAL {{ ?film wdt:P577 ?date . }}
  {parts}
}} GROUP BY ?film ?imdb ?tmdb"""


def _rows(bindings):
    out = []
    for b in bindings:
        g = lambda k: (b.get(k) or {}).get("value", "")
        row = {"qid": g("film").rsplit("/", 1)[-1], "imdb": g("imdb"), "tmdb": int(g("tmdb")) if g("tmdb").isdigit() else 0,
               "year": int(g("released")[:4]) if g("released")[:4].isdigit() else 0}
        for n in PROPS:
            row[n] = [x for x in g(n).split("|") if x]
        out.append(row)
    return out


def fetch_by_imdb(imdb_ids):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "by_imdb.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    todo = [i for i in imdb_ids if i not in done]
    for s in range(0, len(todo), BATCH):
        chunk = todo[s:s + BATCH]
        vals = "VALUES ?imdb { " + " ".join(f'"{i}"' for i in chunk) + " } ?film wdt:P345 ?imdb ."
        for row in _rows(sparql(_features_query(vals))):
            done[row["imdb"]] = row
        for i in chunk:
            done.setdefault(i, None)          # not on Wikidata: don't ask again
        path.write_text(json.dumps(done))
        print(f"  MovieLens movies: {min(s + BATCH, len(todo)):,} of {len(todo):,}", flush=True)
        time.sleep(1.0)
    return done


def fetch_recent():
    since = datetime.date.today().year - 3
    q = f"""SELECT ?film ?sl WHERE {{
  ?film wdt:P31 wd:Q11424 ; wdt:P4947 ?tmdb ; wdt:P577 ?d ; wikibase:sitelinks ?sl .
  FILTER(YEAR(?d) >= {since})
}} ORDER BY DESC(?sl) LIMIT {RECENT_LIMIT}"""
    qids = list(dict.fromkeys(b["film"]["value"].rsplit("/", 1)[-1] for b in sparql(q)))
    rows = []
    for s in range(0, len(qids), BATCH):
        vals = "VALUES ?film { " + " ".join(f"wd:{q}" for q in qids[s:s + BATCH]) + " }"
        rows += _rows(sparql(_features_query(vals)))
        print(f"  Recent movies: {min(s + BATCH, len(qids)):,} of {len(qids):,}", flush=True)
        time.sleep(1.0)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    args = ap.parse_args()
    knn = np.load(ROOT / "data" / "cf_knn.npz")
    links = pd.read_csv(Path(args.data_dir) / "links.csv").dropna(subset=["imdbId"])
    movies = pd.read_csv(Path(args.data_dir) / "movies.csv").set_index("movieId")
    by_tmdb = {int(t): i for i, t in enumerate(knn["tmdb_id"]) if t > 0}
    by_title = {}
    for i, (t, y) in enumerate(zip(knn["norm_title"], knn["year"])):
        by_title.setdefault((str(t), int(y)), i)
    idx_of_imdb = {}
    for mid, imdb, tmdb in zip(links["movieId"], links["imdbId"], links["tmdbId"]):
        i = by_tmdb.get(int(tmdb)) if pd.notna(tmdb) else None
        if i is None and mid in movies.index:
            t, y = normalize_title(movies.loc[mid, "title"])
            i = by_title.get((t, y or 0))
        if i is not None:
            idx_of_imdb[f"tt{int(imdb):07d}"] = i
    print(f"{len(idx_of_imdb):,} MovieLens movies to look up", flush=True)
    found = fetch_by_imdb(sorted(idx_of_imdb))
    ml = [{**row, "cf_index": idx_of_imdb[imdb]} for imdb, row in found.items() if row and imdb in idx_of_imdb]
    recent = [r for r in fetch_recent() if r["tmdb"] and r["tmdb"] not in by_tmdb]
    (ROOT / "data" / "wikidata_movies.json").write_text(json.dumps({"movielens": ml, "recent": recent}))
    print(f"Saved data/wikidata_movies.json: {len(ml):,} MovieLens movies, {len(recent):,} recent movies")


if __name__ == "__main__":
    main()
