"""Decision-time test: how long until someone has picked a movie they'd actually watch?

    python timing_test.py           run one participant (both methods, random order)
    python timing_test.py --report  rewrite the README result from the saved runs

Method A: iCinema. Open the app (already set up) and stop when you'd press play on a pick.
Method B: Browse. Open your usual streaming app's home screen and stop when you'd press play.
Each participant does both, in random order, and rates how happy they are with the pick (1-5).
Results go to data/decision_time_results.csv and the README section between the
DECISION_TIME markers. See TIMING_TEST.md for the full protocol.
"""
import csv
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "data" / "decision_time_results.csv"
README = ROOT / "README.md"
START, END = "<!-- DECISION_TIME:START -->", "<!-- DECISION_TIME:END -->"
HEADER = ["participant", "method", "seconds", "happiness_1_to_5", "order"]
STEPS = {
    "icinema": ["Open iCinema (you finished setup earlier).", "Look at Tonight's Show and the rows.",
                "Stop the moment you'd press play on something."],
    "browse": ["Open your usual streaming app's home screen.", "Browse however you normally would.",
               "Stop the moment you'd press play on something."],
}
NAMES = {"icinema": "iCinema", "browse": "Browsing a streaming app"}


def stopwatch(method):
    print(f"\n=== {NAMES[method]} ===")
    for s in STEPS[method]:
        print(" -", s)
    input("\nPress Enter to START, then do the task.")
    t0 = time.monotonic()
    input("Press Enter to STOP the moment you'd press play.")
    sec = round(time.monotonic() - t0)
    while True:
        h = input("How happy are you with that pick? 1 (not at all) to 5 (very): ").strip()
        if h in {"1", "2", "3", "4", "5"}:
            return sec, int(h)


def rows():
    if not CSV.exists():
        return []
    with CSV.open() as f:
        return list(csv.DictReader(f))


def report():
    data = rows()
    by = {m: [r for r in data if r["method"] == m] for m in STEPS}
    if not all(by.values()):
        text = "_Not measured yet. Run `python timing_test.py` with at least one person (protocol in `TIMING_TEST.md`)._"
    else:
        med = {m: statistics.median(int(r["seconds"]) for r in v) for m, v in by.items()}
        happy = {m: statistics.mean(int(r["happiness_1_to_5"]) for r in v) for m, v in by.items()}
        n = len({r["participant"] for r in data})
        text = (f"- **Time to a pick you'd press play on:** {med['icinema']:.0f} s with iCinema vs {med['browse']:.0f} s "
                f"browsing a streaming app (median, {n} participant{'s' if n != 1 else ''}, each did both in random order).\n"
                f"- **Happiness with the pick (1-5):** {happy['icinema']:.1f} with iCinema vs {happy['browse']:.1f} browsing.")
        pairs = {}
        for r in data:
            pairs.setdefault(r["participant"], {})[r["method"]] = int(r["seconds"])
        paired = [(p["icinema"], p["browse"]) for p in pairs.values() if len(p) == 2]
        if len(paired) >= 10:
            from scipy.stats import wilcoxon
            pval = wilcoxon([a for a, _ in paired], [b for _, b in paired]).pvalue
            text += f"\n- **Paired Wilcoxon test:** p = {pval:.3f} across {len(paired)} people."
        else:
            text += "\n- Small sample. A significance test runs automatically once 10 people have done both."
    body = README.read_text()
    i, j = body.index(START) + len(START), body.index(END)
    README.write_text(body[:i] + "\n" + text + "\n" + body[j:])
    print(text)


def main():
    if "--report" in sys.argv:
        report()
        return
    pid = input("Participant id (initials or number): ").strip() or f"p{len(rows()) // 2 + 1}"
    order = random.sample(list(STEPS), 2)
    print("Order for this person:", " then ".join(NAMES[m] for m in order))
    new = []
    for k, m in enumerate(order, 1):
        sec, h = stopwatch(m)
        new.append({"participant": pid, "method": m, "seconds": sec, "happiness_1_to_5": h, "order": k})
    write_header = not CSV.exists()
    CSV.parent.mkdir(exist_ok=True)
    with CSV.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        if write_header:
            w.writeheader()
        w.writerows(new)
    report()


if __name__ == "__main__":
    main()
