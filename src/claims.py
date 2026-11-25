"""Every model claim on the front page, checked against the result file that proves it.

The front page says how many of the 11 models passed their test against a simpler option. That number is
counted here from the files in data/, never typed by hand, so the page can't claim more than was shown.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

# (model, result file, the test that decides it). A model counts as passed only if its file says so.
EVIDENCE = (
    ("Learned ranker", "ltr_confirm.json", "beat a fixed mix of models on held-out viewers"),
    ("item-kNN", "cf_results.json", "beat the most popular movies on 3,000 held-out viewers"),
    ("RP3beta", "long_tail_confirm.json", "beat item-kNN for viewers with less mainstream likes"),
    ("EASE", "history_routing_confirm.json", "beat the routed fans model for long histories"),
    ("Markov chain", "seq_main_confirm.json", "beat the fan ranking on what people liked next"),
    ("TF-IDF + SVD", "content_ml.json", "content model test"),
    ("Ridge regression", "new_release_confirm.json", "placed new releases better than genre and popularity"),
    ("Fan-tag TF-IDF", "mood_confirm.json", "found movies fans describe with the words, vs chance"),
    ("TV model", "tv_blend_confirm.json", "beat the most popular shows on held-out people"),
    ("Personal model", "seen_thumbs_confirm.json", "learned saves and skips better than chance"),
    ("Isotonic calibration", "love_chance.json", "odds within 3 points and better than guessing the average"),
)


def _passed(d):
    if not isinstance(d, dict):
        return None
    for k in ("ship", "ships", "use"):
        if isinstance(d.get(k), bool):
            return d[k]
    # cf_results.json reports significance instead of a ship flag.
    boots = d.get("bootstrap_three_likes_vs_popularity") or []
    if boots:
        return all(bool(b.get("significant")) for b in boots)
    return None


def audit():
    """[(model, file, test, status)], status in PASS, FAIL, NO FLAG (file has no pass/fail), MISSING."""
    out = []
    for name, fname, test in EVIDENCE:
        try:
            r = _passed(json.loads((DATA / fname).read_text()))
            status = "PASS" if r is True else "FAIL" if r is False else "NO FLAG"
        except Exception:
            status = "MISSING"
        out.append((name, fname, test, status))
    return out


def models_passed():
    return sum(1 for *_x, s in audit() if s == "PASS")
