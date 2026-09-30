"""Rebuild the results in README.md and MODEL_CARD.md from data/cf_results.json.

No retraining needed. It saves the exact lift into the results file, then writes
the same numbers everywhere (README, model card, and the app, which reads the file).

    python tools/refresh_results.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
from train_cf import build_report, compute_lifts, replace_between_markers  # noqa: E402


def main():
    path = ROOT / "data" / "cf_results.json"
    results = json.loads(path.read_text())
    results["lifts_three_likes_vs_popularity"] = compute_lifts(results)
    path.write_text(json.dumps(results, indent=2))
    report = build_report(results)
    (ROOT / "data" / "cf_results.md").write_text(report)
    for doc in ("README.md", "MODEL_CARD.md"):
        if replace_between_markers(ROOT / doc, report.strip()):
            print(f"Updated results in {doc}")
    lifts = results["lifts_three_likes_vs_popularity"]
    print(f"Tonight's Show lift: +{lifts.get('hit@1')}%  |  rows: NDCG +{lifts.get('ndcg@10')}%, Recall +{lifts.get('recall@10')}%")


if __name__ == "__main__":
    main()
