"""Love chance: "If you watch it, how likely are you to love it?"

Read from data/love_chance.json (built by training/evaluate_love_and_learning.py). The table maps a
movie's top-% rank among the movies iCinema scored for you to the share of such movies that
viewers later rated 4+ stars once they watched them. Shown only if the test passed its rule.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

PATH = Path(__file__).resolve().parents[1] / "data" / "love_chance.json"


@lru_cache(maxsize=1)
def _table():
    try:
        d = json.loads(PATH.read_text())
    except (OSError, ValueError):
        return None
    if not d.get("ships"):
        return None
    rows = sorted(d["table"], key=lambda r: r["top_pct"])
    return np.array([r["top_pct"] for r in rows], float), np.array([r["chance"] for r in rows], float)


def love_chance(top_pct):
    """Whole-number percent, rounded down to a multiple of 5 so it never claims more than was
    measured (72.5% shows as 70%), or None if not available."""
    t = _table()
    if t is None or not isinstance(top_pct, (int, float)):
        return None
    return int(5 * np.floor(float(np.interp(float(top_pct), t[0], t[1])) * 100 / 5 + 1e-9))


def love_line(top_pct):
    c = love_chance(top_pct)
    return f"If you watch it: about {c}% chance you'll love it" if c is not None else ""


@lru_cache(maxsize=1)
@lru_cache(maxsize=1)
def fit_floor():
    """Lowest rank (top-%) where a movie is still at least as likely to be loved as an average one.

    Below this line, a pick is worse than a coin flip weighted by the average love rate, so rows
    leave it out instead of padding. Read from the tested table; None if the table didn't ship.
    """
    try:
        d = json.loads(PATH.read_text())
    except (OSError, ValueError):
        return None
    if not d.get("ships"):
        return None
    avg = float(d["average_love_rate"])
    rows = sorted(d["table"], key=lambda r: r["top_pct"])
    for a, b in zip(rows, rows[1:]):
        if a["chance"] >= avg > b["chance"]:
            span = a["chance"] - b["chance"]
            return round(a["top_pct"] + (a["chance"] - avg) / span * (b["top_pct"] - a["top_pct"]), 1)
    return float(rows[-1]["top_pct"]) if rows[-1]["chance"] >= avg else float(rows[0]["top_pct"])
