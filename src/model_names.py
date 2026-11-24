"""iCinema's models, counted one way everywhere: 10 that pick movies and 1 that sets the odds.

Home, the ready page, the Profile list, and the "why it's here" popup all read the total from here,
so a page can never say 6, 10, or 11 for the same set of models.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The 10 that pick, then the 1 that turns a score into "chance you'll love it".
PICKING = (
    "Learned ranker (gradient boosting)",
    "item-kNN",
    "RP3beta",
    "EASE",
    "Markov chain",
    "TF-IDF + SVD",
    "Ridge regression (new releases)",
    "Fan-tag TF-IDF (mood search)",
    "TV model (item-kNN + popularity)",
    "Personal logistic regression",
)
ODDS = "Isotonic calibration"
MODELS_TOTAL = len(PICKING) + 1      # 11


def odds_model_on():
    """True when the calibration model passed its test and ships (data/love_chance.json)."""
    try:
        return bool(json.loads((ROOT / "data" / "love_chance.json").read_text()).get("ships"))
    except Exception:
        return False
