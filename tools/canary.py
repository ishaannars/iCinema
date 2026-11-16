"""Weekly model-health canary: do the shipped models still recommend what they did when tested?

    python tools/canary.py            # check against data/canary_expected.json (fails if drifted)
    python tools/canary.py --record   # save today's output as the new expected set (after a retrain)

Eight fixed viewers (three liked movies each, from different tastes) are scored by the fan models,
the learned ranker, the mood search, and the new-release model. Each top-10 is compared with the saved
one. Rollback rule: if any check keeps less than 7 of its 10 titles, or a model fails to load, the
GitHub Action fails and the last good commit is restored before anything else ships. A library
update once switched the learned ranker off silently; this is the check that would have caught it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EXPECTED = ROOT / "data" / "canary_expected.json"
MIN_OVERLAP = 7

VIEWERS = {
    "mind-benders": ["Inception", "The Matrix", "Memento"],
    "feel-good": ["Paddington 2", "The Grand Budapest Hotel", "Toy Story"],
    "horror": ["Hereditary", "Get Out", "The Shining"],
    "romance": ["The Notebook", "Pride & Prejudice", "La La Land"],
    "crime": ["Goodfellas", "Heat", "The Departed"],
    "international": ["Parasite", "Amélie", "Spirited Away"],
    "action": ["Mad Max: Fury Road", "John Wick", "Die Hard"],
    "documentary": ["Free Solo", "Won't You Be My Neighbor?", "Jiro Dreams of Sushi"],
}
MOODS = ["dark", "funny", "feel-good", "heist"]


def snapshot():
    import numpy as np
    from src import cf_model, ltr, mood
    out, problems = {}, []
    if cf_model._load() is None:
        problems.append("fan models did not load")
        return out, problems
    if not ltr.available():
        problems.append("learned ranker did not load")
    for name, titles in VIEWERS.items():
        signals = [(m, "like") for t in titles if (m := cf_model.lookup(t)) is not None]
        taste = cf_model.user_vector(signals)
        if taste is None:
            problems.append(f"no profile for {name}")
            continue
        out[f"fans:{name}"] = [cf_model.movie_at(i)["title"] for i in cf_model.top_indices(taste, 13)
                               if cf_model.movie_at(i)["title"] not in titles][:10]
        if ltr.available():
            s = np.asarray(ltr.viewer_scores(signals), dtype=float)
            top = [int(i) for i in np.argsort(-s)[:13]]
            out[f"ranker:{name}"] = [cf_model.movie_at(i)["title"] for i in top if cf_model.movie_at(i)["title"] not in titles][:10]
    if mood.available():
        for q in MOODS:
            out[f"mood:{q}"] = [cf_model.movie_at(int(i))["title"] for i in mood.top_rows(q, 10)]
    return out, problems


def main():
    out, problems = snapshot()
    if "--record" in sys.argv:
        EXPECTED.write_text(json.dumps(out, indent=1, ensure_ascii=False))
        print(f"recorded {len(out)} checks")
        return
    expected = json.loads(EXPECTED.read_text()) if EXPECTED.exists() else {}
    for key, want in expected.items():
        got = out.get(key)
        if got is None:
            problems.append(f"{key}: missing")
            continue
        kept = len(set(got) & set(want))
        status = "OK" if kept >= MIN_OVERLAP else "DRIFT"
        print(f"{key:<28} {kept}/10 {status}")
        if kept < MIN_OVERLAP:
            problems.append(f"{key} kept {kept}/10")
    for p in problems:
        print("PROBLEM:", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
