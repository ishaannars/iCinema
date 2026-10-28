"""Model health: do live saves match what the love chance predicts?

    python tools/model_health.py events.csv

Export events from PostHog (Activity → Export → CSV, last 30 days) and pass the file here. For each
fit band (top 1%, top 5%, top 20%, below top 20%), it compares the share of shown-and-acted-on
cards that were saved with the love chance iCinema predicted for that band. Saves should fall as
the band widens, the same direction the offline test found. A band that inverts is a warning.
Small samples are flagged rather than judged.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANDS = ["top 1%", "top 5%", "top 20%", "below top 20%"]
MIN_EVENTS = 30


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python tools/model_health.py events.csv")
    acted, saved = Counter(), Counter()
    with open(sys.argv[1], newline="") as f:
        for row in csv.DictReader(f):
            props = row.get("properties") or "{}"
            try:
                band = json.loads(props).get("fit_band")
            except ValueError:
                band = row.get("properties.fit_band")
            event = row.get("event")
            if band in BANDS and event in {"save", "skip", "not_for_me"}:
                acted[band] += 1
                saved[band] += event == "save"
    table = json.loads((ROOT / "data" / "love_chance.json").read_text())["table"]
    predicted = {"top 1%": 1, "top 5%": 5, "top 20%": 20, "below top 20%": 50}
    chance = {b: next(r["chance"] for r in table if r["top_pct"] == p) for b, p in predicted.items()}
    print(f"{'Band':<16}{'Acted on':>10}{'Saved':>9}{'Predicted':>11}")
    for b in BANDS:
        n = acted[b]
        rate = f"{saved[b] / n:.0%}" if n else "-"
        flag = "" if n >= MIN_EVENTS else "  (too few to judge)"
        print(f"{b:<16}{n:>10}{rate:>9}{chance[b]:>11.0%}{flag}")
    print("Saves are a stricter signal than 'loved once watched', so live rates run lower. Watch the direction, not the level.")


if __name__ == "__main__":
    main()
