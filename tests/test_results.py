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
    shipped = load("cf_results.json")["model"]
    confirm = load("long_tail_confirm.json")
    routing = load("routing_confirm.json")
    assert (shipped == w or (confirm["replaces_item_knn"] and shipped.startswith("RP3beta"))
            or (routing["ship_routing"] and shipped.startswith("Routed")))


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
    rc = load("routing_confirm.json")
    gain = round(rc["routed_vs_knn_niche"]["ndcg_diff"] / rc["niche"]["item-kNN"]["ndcg@10"] * 100)
    assert f"rose **{gain}%** and nobody else got worse" in readme and f"{rc['viewers']:,} brand-new viewers" in readme
    assert rc["others"]["routed"]["ndcg@10"] >= rc["others"]["item-kNN"]["ndcg@10"]


def test_readme_tables_are_current():
    import refresh_results as rr
    from train_cf import build_report
    readme = (ROOT / "README.md").read_text()
    assert rr.benchmark_block() in readme
    assert build_report(load("cf_results.json")).strip() in readme


def test_blend_weights_follow_their_rule():
    b = load("blend_results.json")
    for part, floor_ok in (("content_blend", lambda w: w >= 0.2), ("whats_next", lambda a: a <= 0.8)):
        r = b[part]
        assert floor_ok(r["best_weight"])
        assert r["change"] == (r["best_weight"] != r["current_weight"] and r["ci95"][0] > 0)
    cb = b["content_blend"]
    assert f"from {cb['current_weight']:.0%} content to {cb['best_weight']:.0%}" in (ROOT / "README.md").read_text()


def test_tested_and_error_tables_are_current():
    import refresh_results as rr
    readme = (ROOT / "README.md").read_text()
    assert rr.tested_block() in readme and rr.errors_block() in readme


def test_steps_test_follows_its_rule():
    st = load("steps_results.json")
    assert st["change"] == (st["best_content_weight"] != st["current_content_weight"] and st["ci95"][0] > 0)
    lr = st["learned_ranker"]
    assert lr["ships"] == (lr["vs_current"]["ci95"][0] > 0 and lr["vs_viewers_like_you_only"]["ci95"][0] > 0)


def test_decision_time_section_exists():
    readme = (ROOT / "README.md").read_text()
    assert "<!-- DECISION_TIME:START -->" in readme and "<!-- DECISION_TIME:END -->" in readme


def test_long_tail_confirmation_follows_its_rule():
    c = load("long_tail_confirm.json")
    assert c["replaces_item_knn"] == (c["niche_ci95"][0] > 0 and c["all_ci95"][0] > -0.002)
    assert c["fresh_viewers"] > 10000


def test_routing_follows_its_rule():
    rc = load("routing_confirm.json")
    assert rc["ship_routing"] == (rc["routed_vs_rp3_all"]["ci95"][0] > 0 and rc["routed_vs_rp3_niche"]["ci95"][0] > -0.002)
    assert rc["user_offset"] != 0          # a slice no earlier test used


def test_rows_and_hidden_gems_claim():
    rr = load("rows_results.json")["rows"]
    for v in rr.values():
        assert v["supported"] == (v["ci95"][0] > 0)
    g = rr["Hidden Gems"]
    times = g["hit@10_shipped"] / g["hit@10_popular_of_that_kind"]
    assert f"**{times:.1f} times as often**" in (ROOT / "README.md").read_text()
