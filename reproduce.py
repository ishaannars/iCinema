"""Rebuild every model and every number in the README, in order, with one command.

    python reproduce.py --data-dir ml-32m

Download MovieLens 32M into ml-32m/ first (https://grouplens.org/datasets/movielens/).
Each step is a script in training/ with its rule written in its docstring. Stops at the first
failure. The full run takes a while on a laptop; --from lets you resume at a step.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    "benchmark_cf.py",              # 9 models, honest 3-random-likes test
    "evaluate_long_tail.py",        # 12 fixes for less mainstream likes
    "confirm_long_tail.py",         # RP3beta on fresh viewers
    "confirm_routing.py",           # routing on a brand-new slice
    "build_knn.py",                 # shipped models on all of MovieLens 32M
    "confirm_history_routing.py",   # EASE for viewers with many likes, fresh slice
    "build_ease.py",                # ships cf_full.npz only if that test passed
    "confirm_shelf_and_imports.py", # which Step 1 movies to ask about, which imported ratings to read
    "build_content.py",             # content model from genres and fan tags
    "evaluate_blends.py",           # content vs viewers-like-you weights, What's next
    "evaluate_steps.py",            # every onboarding step
    "evaluate_rows.py",             # each Showroom row within its kind
    "evaluate_love_and_learning.py",  # love chance and first learning-curve test
    "confirm_learning_curve.py",    # fresh learning-curve test
    "evaluate_beyond_accuracy.py",  # coverage, popularity of picks, variety
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ml-32m")
    ap.add_argument("--from", dest="start", default=None, help="script name to start from")
    args = ap.parse_args()
    steps = STEPS[STEPS.index(args.start):] if args.start else STEPS
    for i, script in enumerate(steps, 1):
        print(f"[{i}/{len(steps)}] {script}", flush=True)
        if subprocess.run([sys.executable, str(ROOT / "training" / script), "--data-dir", args.data_dir]).returncode:
            sys.exit(f"Stopped at {script}. Fix it, then rerun with --from {script}")
    subprocess.run([sys.executable, str(ROOT / "tools" / "refresh_results.py")], check=True)
    print("All numbers rebuilt and the README refreshed.")


if __name__ == "__main__":
    main()
