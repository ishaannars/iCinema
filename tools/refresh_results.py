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


BSTART, BEND = "<!-- CF_BENCHMARK:START -->", "<!-- CF_BENCHMARK:END -->"


def benchmark_block():
    b = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    order = ["Popularity", "SVD, 64 dims (current)", "SVD, 128 dims", "SVD 64, recency-weighted (half-life 20 likes)",
             "Implicit ALS", "EASE", "EASE, top-100 per movie (shippable)", "item-kNN", "item-kNN, top-100 per movie (shippable)"]
    names = {"SVD, 64 dims (current)": "SVD, 64 dims (old model)"}
    lines = ["| Model | Hit@1, 3 random likes | NDCG@10, 3 random likes | Hit@1, 3 most recent likes | Hit@1, full history | Size |",
             "|---|---|---|---|---|---|"]
    for n in order:
        r = b["results"][n]
        label = names.get(n, n)
        if n == b["winner"]:
            label = f"**{label.replace(' (shippable)', '')} (shipped)**"
        size = "—" if n == "Popularity" else f"{r['model_size_mb']:.0f} MB"
        lines.append(f"| {label} | {r['random3']['hit@1']:.1%} | {r['random3']['ndcg@10']:.3f} | "
                     f"{r['last3']['hit@1']:.1%} | {r['full']['hit@1']:.1%} | {size} |")
    d = b["dataset"]
    lines += ["", f"{d['user_sample']}: {d['users']:,} viewers, {d['movies']:,} movies, {d['positives']:,} ratings of 4+ stars. "
              f"Settings were picked on {d['validation_users']:,} validation viewers and scored once on {d['test_users']:,} different test viewers. "
              "From `training/benchmark_cf.py`."]
    return "\n".join(lines)


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
    readme = ROOT / "README.md"
    body = readme.read_text()
    if BSTART in body:
        i, j = body.index(BSTART) + len(BSTART), body.index(BEND)
        readme.write_text(body[:i] + "\n" + benchmark_block() + "\n" + body[j:])
        print("Updated benchmark table in README.md")
    lifts = results["lifts_three_likes_vs_popularity"]
    print(f"Tonight's Show lift: +{lifts.get('hit@1')}%  |  rows: NDCG +{lifts.get('ndcg@10')}%, Recall +{lifts.get('recall@10')}%")


if __name__ == "__main__":
    main()
