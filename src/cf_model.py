"""
"Viewers like you" layer for iCinema, pretrained offline on MovieLens 32M.

Two pretrained files, each listing every movie's 100 closest movies by who loved them:
- data/cf_knn.npz (item-kNN): ranks movies for most viewers, and answers "how similar are these
  two movies" for What's next and "Loved by fans of ...".
- data/cf_rank.npz (RP3beta): ranks movies for viewers whose likes are less-loved movies.
Routing between them was tested on viewers no earlier test touched (training/confirm_routing.py):
it beat both models used alone.
- data/cf_full.npz (EASE), only if training/confirm_history_routing.py passed: ranks movies for
  viewers with many likes (for example after a Letterboxd import), where EASE beat item-kNN. If cf_rank.npz is missing, item-kNN ranks for everyone. If both
files are missing, the older SVD embeddings (data/cf_model.npz) are used.

Each viewer's taste is computed on the fly from their browser-local Likes, Favorites, Saves,
Seen, Skips, and "Not for me" choices, so no viewer data ever leaves the browser.
"""
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"
KNN_PATH = DATA / "cf_knn.npz"
RANK_PATH = DATA / "cf_rank.npz"
ROUTING_PATH = DATA / "routing_confirm.json"
FULL_PATH = DATA / "cf_full.npz"
HISTORY_PATH = DATA / "history_routing_confirm.json"
MODEL_PATH = DATA / "cf_model.npz"

# How strongly each action moves the viewer's taste.
WEIGHTS = {"favorite": 2.0, "like": 1.0, "save": 1.0, "seen": 0.5, "skip": -0.2, "dislike": -0.8}
# Only explicit approval can be quoted as "you're a fan": Seen means watched, not loved.
FAN_ACTIONS = ("favorite", "like", "save")


def _norm_title(title):
    title = re.sub(r"[^\w\s]", "", str(title).casefold())
    return " ".join(title.split())


class _Model:
    def __init__(self, path, kind):
        d = np.load(path)
        self.kind = kind
        if kind == "knn":
            self.nbr = d["nbr"].astype(np.int32)
            self.w = d["w"].astype(np.float32)
            self.n = self.nbr.shape[0]
        else:
            self.emb = d["emb"].astype(np.float32)
            self.n = self.emb.shape[0]
        fans = d["popularity"].astype(np.float64) if "popularity" in d.files else np.zeros(self.n)
        self.fan_pct = np.argsort(np.argsort(fans)) / max(len(fans) - 1, 1)   # 0 = fewest fans, 1 = most
        self.titles = [str(x) for x in d["title"]] if "title" in d.files else None
        self.titles_raw = [str(x) for x in d["title_raw"]] if "title_raw" in d.files else None
        self.by_tmdb = {int(t): i for i, t in enumerate(d["tmdb_id"]) if t > 0}
        self.by_title = {}
        for i, (t, y) in enumerate(zip(d["norm_title"], d["year"])):
            self.by_title.setdefault((str(t), int(y)), i)
            self.by_title.setdefault((str(t), 0), i)  # year-less fallback

    def sim(self, i, j):
        """Similarity of two movies: kNN cosine (0 if neither lists the other), or embedding cosine."""
        if self.kind == "knn":
            hit = np.flatnonzero(self.nbr[i] == j)
            if hit.size:
                return float(self.w[i, hit[0]])
            hit = np.flatnonzero(self.nbr[j] == i)
            return float(self.w[j, hit[0]]) if hit.size else 0.0
        a, b = self.emb[i], self.emb[j]
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        return float(a @ b) / denom if denom > 0 else 0.0


@lru_cache(maxsize=1)
def _load():
    if KNN_PATH.exists():
        return _Model(KNN_PATH, "knn")
    if MODEL_PATH.exists():
        return _Model(MODEL_PATH, "svd")
    return None


@lru_cache(maxsize=1)
def _load_rank():
    """Model used to rank movies for a viewer: RP3beta if shipped, else the similarity model."""
    if RANK_PATH.exists() and _load() is not None and _load().kind == "knn":
        return _Model(RANK_PATH, "knn")
    return _load()


@lru_cache(maxsize=1)
def _routing_cut():
    """Fan-percentile cut for routing to RP3beta, or None if routing isn't shipped."""
    try:
        import json
        d = json.loads(ROUTING_PATH.read_text())
        return float(d["niche_cut_fan_percentile"]) if d.get("ship_routing") else None
    except Exception:
        return None


@lru_cache(maxsize=1)
def _history_cut():
    """(EASE model, number of likes at which it takes over), or (None, None) if not shipped."""
    try:
        import json
        d = json.loads(HISTORY_PATH.read_text())
        sim = _load()
        if d.get("ship") and d.get("chosen_cut_likes") and FULL_PATH.exists() and sim is not None and sim.kind == "knn":
            full = _Model(FULL_PATH, "knn")
            if full.n == sim.n:            # must list the same movies in the same order
                return full, int(d["chosen_cut_likes"])
    except Exception:
        pass
    return None, None


def _fan_count(signals):
    return sum(1 for m, a in signals or [] if a in FAN_ACTIONS and _index(m) is not None)


def _ranker_for(signals):
    """EASE for viewers with many likes (if shipped); else RP3beta when the liked movies are
    mostly less-loved ones, item-kNN otherwise."""
    full, n_cut = _history_cut()
    if full is not None and _fan_count(signals) >= n_cut:
        return full
    return _niche_ranker(signals)


def _niche_ranker(signals):
    sim = _load()
    rank = _load_rank()
    cut = _routing_cut()
    if sim is None or rank is sim or cut is None or sim.kind != "knn":
        return rank
    liked = [i for i in (_index(m) for m, a in signals or [] if a in FAN_ACTIONS) if i is not None]
    if liked and float(np.median(sim.fan_pct[liked])) <= cut:
        return rank
    return sim


def cf_available():
    return _load() is not None


def _index(movie):
    model = _load()
    if model is None or not movie:
        return None
    tmdb_id = int(movie.get("tmdb_id") or 0)
    if tmdb_id and tmdb_id in model.by_tmdb:
        return model.by_tmdb[tmdb_id]
    key = _norm_title(movie.get("title", ""))
    year = int(movie.get("year") or 0)
    for y in (year, year - 1, year + 1, 0):  # tolerate off-by-one release years
        if (key, y) in model.by_title:
            return model.by_title[(key, y)]
    return None


_STOP = {"the", "a", "an", "of", "and", "in", "on", "to"}


def preferred_title(movie, tmdb_title):
    """TMDB's title, unless it names a different release than MovieLens does.

    TMDB sometimes lists a film under a regional or recut title ("Warriors of the Wind" for
    Nausicaä of the Valley of the Wind). When the first real words don't match, the MovieLens
    title, which matches the poster and what fans call it, is shown instead.
    """
    model = _load()
    idx = _index(movie)
    if model is None or idx is None or not model.titles or not tmdb_title:
        return tmdb_title
    ml = model.titles[idx]
    simple = lambda s: " ".join(re.sub(r"[^\w\s]", " ", str(s).casefold()).split())
    if model.titles_raw and simple(tmdb_title) in simple(model.titles_raw[idx]):
        return tmdb_title          # TMDB's title is one of the names MovieLens lists ("Se7en")
    first = lambda s: next((w for w in simple(s).split() if w not in _STOP), "")
    return ml if ml and first(ml) != first(tmdb_title) else tmdb_title


def fan_percentile(movie):
    """Where a movie ranks by MovieLens fans (4+ star ratings): 0 = fewest, 1 = most. None if unknown."""
    model = _load()
    idx = _index(movie)
    if model is None or idx is None:
        return None
    return float(model.fan_pct[idx])


class Taste:
    """A viewer's taste: a score for every movie, plus percentiles for mapping scores to 0-1."""

    def __init__(self, scores):
        self.scores = scores
        self.pos = np.sort(scores[scores > 0])
        self.neg = np.sort(-scores[scores < 0])


def interleave_eligible(signals):
    """True when routing sends this viewer to RP3beta, so routed and item-kNN-only rankings differ.

    For everyone else the two are the same list, and the live interleaving test doesn't run.
    """
    sim = _load()
    rank = _load_rank()
    return (sim is not None and sim.kind == "knn" and rank is not sim
            and _ranker_for(signals) is rank)


def user_vector(signals, force_knn=False):
    """signals: list of (movie_dict, action) pairs, action in WEIGHTS. Returns a Taste or None.

    force_knn=True skips routing and ranks with item-kNN (the comparison side of the live test).
    """
    model = _load() if force_knn else _ranker_for(signals)
    if model is None:
        return None
    if model.kind == "knn":
        scores = np.zeros(model.n, dtype=np.float32)
        used = False
        for movie, action in signals or []:
            idx, w = _index(movie), WEIGHTS.get(action, 0.0)
            if idx is None or w == 0:
                continue
            np.add.at(scores, model.nbr[idx], w * model.w[idx])
            used = used or w > 0
        if not used:
            return None
        for movie, _ in signals or []:  # a movie never counts as evidence for itself
            idx = _index(movie)
            if idx is not None:
                scores[idx] = 0.0
        return Taste(scores)
    total, weight_sum = np.zeros(model.emb.shape[1], dtype=np.float32), 0.0
    for movie, action in signals or []:
        idx, w = _index(movie), WEIGHTS.get(action, 0.0)
        if idx is None or w == 0:
            continue
        total += w * model.emb[idx]
        weight_sum += max(w, 0)
    norm = np.linalg.norm(total)
    if weight_sum == 0 or norm == 0:
        return None
    return Taste((model.emb @ (total / norm)).astype(np.float32))


def cf_affinity(movie, taste):
    """0-1 score for how well a movie fits the viewer's taste, or None if unknown.

    0.5 means no evidence either way. Above 0.5, the movie is near things the viewer loved,
    ranked against every other such movie; below 0.5, near things they turned down.
    """
    if taste is None:
        return None
    idx = _index(movie)
    if idx is None:
        return None  # movie not in MovieLens: fall back to content signals
    s = float(taste.scores[idx])
    if s > 0 and taste.pos.size:
        return 0.5 + 0.5 * float(np.searchsorted(taste.pos, s, side="right")) / taste.pos.size
    if s < 0 and taste.neg.size:
        return 0.5 - 0.5 * float(np.searchsorted(taste.neg, -s, side="right")) / taste.neg.size
    return 0.5


def closest_liked(movie, signals, allowed=FAN_ACTIONS):
    """Title of the viewer's liked/saved movie most similar to this one, or None.

    Makes the reason concrete ("Loved by fans of Parasite") instead of "viewers like you".
    Returns None when no liked movie shares fans with this one.
    """
    model = _load()
    idx = _index(movie)
    if model is None or idx is None:
        return None
    best, best_score = None, 0.0
    for liked, action in signals or []:
        if action not in allowed:
            continue
        j = _index(liked)
        if j is None or j == idx:
            continue
        score = model.sim(idx, j)
        if score > best_score:
            best, best_score = liked.get("title"), score
    return best


def item_similarity(a, b):
    """0-1 similarity between two movies (the same viewers loved both), or None if either is unknown.

    Used by What's next. With kNN, 0.5 means the movies share no close fans; higher means b is
    nearer the top of a's 100 closest movies.
    """
    model = _load()
    i, j = _index(a), _index(b)
    if model is None or i is None or j is None or i == j:
        return None
    if model.kind == "knn":
        hit = np.flatnonzero(model.nbr[i] == j)
        if not hit.size:
            hit = np.flatnonzero(model.nbr[j] == i)
        return 0.5 + 0.5 * (1 - hit[0] / model.nbr.shape[1]) if hit.size else 0.5
    return (model.sim(i, j) + 1.0) / 2.0


def lookup(title, year=0):
    """The MovieLens movie matching a title and year, as a small movie dict, or None.

    Used by the Letterboxd import, where all we have is a title and a year.
    """
    model = _load()
    idx = _index({"title": title, "year": year})
    if model is None or idx is None:
        return None
    if not hasattr(model, "tmdb_by_idx"):
        model.tmdb_by_idx = {i: t for t, i in model.by_tmdb.items()}
    tmdb = model.tmdb_by_idx.get(idx, 0)
    name = model.titles[idx] if model.titles else str(title)
    return {"title": name, "year": int(year or 0), "tmdb_id": int(tmdb), "external": True,
            "candidate_source": "letterboxd"}


def fuzzy_titles(query, n=5, cutoff=0.75):
    """Close spellings of a title among MovieLens movies, best-known first ("interstallar" -> Interstellar).

    Used when title search finds nothing, so a typo never ends in an empty result."""
    import difflib
    model = _load()
    q = _norm_title(query)
    if model is None or len(q) < 3:
        return []
    if not hasattr(model, "_norm_best"):
        best, model._year_of = {}, {}
        for (k, y), i in model.by_title.items():
            if y:
                model._year_of.setdefault(i, y)
                if k not in best or model.fan_pct[i] > model.fan_pct[best[k]]:
                    best[k] = i          # same title, several films: keep the best-known one
        model._norm_best = best
        model._norm_list = sorted(best)
    close = difflib.get_close_matches(q, model._norm_list, n=12, cutoff=cutoff)
    ratio = {k: difflib.SequenceMatcher(None, q, k).ratio() for k in close}
    close.sort(key=lambda k: ratio[k] + 0.15 * float(model.fan_pct[model._norm_best[k]]), reverse=True)
    idx = [model._norm_best[k] for k in close]
    out = []
    for i in idx[:n]:
        m = lookup(model.titles[i] if model.titles else close[0], model._year_of.get(i, 0))
        if m:
            m["year"] = model._year_of.get(i, 0)
            out.append(m)
    return out


def movie_at(i):
    """Movie dict for row i of data/cf_knn.npz (title, year, TMDB id), for candidates found by index."""
    model = _load()
    if model is None or not (0 <= int(i) < model.n):
        return None
    if not hasattr(model, "tmdb_by_idx"):
        model.tmdb_by_idx = {j: t for t, j in model.by_tmdb.items()}
    if not hasattr(model, "_year_by_idx"):
        model._year_by_idx = {}
        for (k, y), j in model.by_title.items():
            if y:
                model._year_by_idx.setdefault(j, y)
    return {"title": model.titles[i] if model.titles else "", "year": int(model._year_by_idx.get(int(i), 0)),
            "tmdb_id": int(model.tmdb_by_idx.get(int(i), 0)), "external": True, "candidate_source": "mood"}
