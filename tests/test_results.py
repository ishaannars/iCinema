"""Published numbers must match the saved results files, and the benchmark must follow its rule."""
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "training"))


def load(name):
    return json.loads((DATA / name).read_text())


def test_every_python_file_compiles():
    for p in ROOT.rglob("*.py"):
        if not {".venv", "__pycache__", "ml-32m"} & set(p.parts):
            py_compile.compile(str(p), doraise=True)


def test_shipped_model_won_under_the_rule():
    b = load("cf_benchmark.json")
    w = b["winner"]
    boot = b["bootstrap_random3_vs_current"][w]
    assert b["replaces_current"]
    assert boot["hit@1"]["ci95"][0] > 0 and boot["ndcg@10"]["ci95"][0] > 0
    assert b["results"][w]["model_size_mb"] <= 25
    assert load("cf_results.json")["model"] == w


def test_readme_headline_matches_results():
    r, b = load("cf_results.json"), load("cf_benchmark.json")
    readme = (ROOT / "README.md").read_text()
    cf3, pop = r["three_likes"]["cf"], r["three_likes"]["popularity"]
    old = b["results"]["SVD, 64 dims (current)"]["random3"]["hit@1"]
    sooner = pop["median_recs_to_first_hit"] - cf3["median_recs_to_first_hit"]
    assert f"**{cf3['hit@1']:.1%}** of the time, compared with **{pop['hit@1']:.1%}**" in readme
    assert f"(**+{r['lifts_three_likes_vs_popularity']['hit@1']}%**)" in readme
    assert f"by **+{round((cf3['hit@1'] / old - 1) * 100)}%**" in readme
    assert f"**{sooner:.0f} recommendations sooner**" in readme
    assert f"{r['train_positives'] / 1e6:.1f} million" in readme and f"{r['train_users']:,} viewers" in readme
    assert f"{r['train_movies']:,} movies" in readme


def test_readme_tables_are_current():
    import refresh_results as rr
    from train_cf import build_report
    readme = (ROOT / "README.md").read_text()
    assert rr.benchmark_block() in readme
    assert build_report(load("cf_results.json")).strip() in readme
