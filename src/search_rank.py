"""Ranking for the Step 1 title search.

Search-usability research finds exact matches should come first, popularity is a useful tie-
breaker, and misspellings shouldn't end in "no results". TMDB returns matches in its own order,
so iCinema re-ranks them: exact title, then title starting with the query, then every query word
in the title, with how many people rated the movie breaking ties. Movies iCinema's models know get
a small lift, since a Like on them shapes picks right away.
"""
import math
import re


def _norm(s):
    return " ".join(re.sub(r"[^\w\s]", " ", str(s).casefold()).split())


def match_score(query, movie, known=False):
    q, t = _norm(query), _norm(movie.get("title", ""))
    if not q or not t:
        return 0.0
    if t == q:
        text = 3.0
    elif t.startswith(q):
        text = 2.0
    elif all(w in t.split() for w in q.split()):
        text = 1.2
    elif q in t:
        text = 0.8
    else:
        text = 0.0
    votes = float(movie.get("tmdb_vote_count") or 0)
    fame = min(1.0, math.log1p(votes) / math.log1p(50_000))
    return text + 0.9 * fame + (0.25 if known else 0.0)


def rerank(query, movies, known=lambda m: False):
    """Stable re-rank: ties keep TMDB's own order."""
    scored = [(match_score(query, m, known(m)), -i, m) for i, m in enumerate(movies)]
    return [m for _, _, m in sorted(scored, key=lambda x: (x[0], x[1]), reverse=True)]
