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


def test_love_chance_follows_its_rule():
    lv = load("love_chance.json")
    assert lv["ships"] == (lv["test_ece"] < 0.03 and lv["brier_ci95"][1] < 0)
    chances = [r["chance"] for r in sorted(lv["table"], key=lambda r: r["top_pct"])]
    assert chances == sorted(chances, reverse=True)      # higher-ranked movies never get a lower chance


def test_learning_curve_follows_its_rule():
    lc = load("learning_curve.json")
    assert lc["claim_allowed"] == (lc["ci95"][0] > 0)


def test_live_test_follows_its_rule():
    import refresh_results as rr
    il = load("interleave_results.json")
    assert il["target_decided_visits"] == 200 and 0 <= il["decided_visits"] <= 200
    if il["status"] != "finished":
        assert not {"routed_wins", "knn_wins", "p_value"} & set(il)   # nothing to peek at
    else:
        assert il["routed_wins"] + il["knn_wins"] == 200
        assert il["significant"] == (il["p_value"] < 0.05 and il["leader"] is not None)
        off = il["significant"] and il["leader"] == "knn" and not any(g["worse"] for g in il["guardrails"].values())
        assert (il["decision"] == "turn routing off") == off
    assert rr.live_test_block() in (ROOT / "README.md").read_text()


def test_beyond_accuracy_table_is_current():
    import refresh_results as rr
    assert rr.beyond_block() in (ROOT / "README.md").read_text()
    path = DATA / "beyond_accuracy.json"
    if path.exists():
        for m in load("beyond_accuracy.json")["models"].values():
            assert 0 < m["catalog_coverage"] <= 1 and 0 <= m["pick_popularity_percentile"] <= 100
            assert 0 <= m["top10_variety"] <= 1


def test_history_routing_follows_its_rule():
    path = DATA / "history_routing_confirm.json"
    if not path.exists():
        return
    hr = load("history_routing_confirm.json")
    if hr.get("chosen_cut_likes") is None:
        assert hr["ship"] is False
    else:
        assert hr["chosen_cut_likes"] in (10, 25, 50, 100)
        expected = hr["many_likes"]["ci95"][0] > 0 and hr["all"]["ci95"][0] > -0.002
        assert hr["ship"] == expected


def test_shelf_and_import_tests_follow_their_rules():
    path = DATA / "shelf_import_confirm.json"
    if not path.exists():
        assert not (DATA / "shelf_titles.json").exists()
        return
    d = load("shelf_import_confirm.json")
    sh = d["shelf"]
    assert sh["picked"] in ("popularity", "popular + HELF", "popular + coverage")   # popular stays on every other card
    if sh["picked"] == "popularity":
        assert sh["ship"] is False
    else:
        assert sh["ship"] == (sh["ci95"][0] > 0 and sh["answerable_drop_points"] <= 1.0
                              and sh["mainstream_ci95"][0] > -0.002)
    assert (DATA / "shelf_titles.json").exists() == sh["ship"]
    for g in d["imports"].values():
        assert g["use"] == (g["ci95_with_signal"][0] > 0 and g["ci95_all"][0] > -0.002)


def test_new_release_and_mood_follow_their_rules():
    for name, key in (("new_release_confirm.json", None), ("mood_confirm.json", None)):
        path = DATA / name
        if not path.exists():
            continue
        d = load(name)
        if name.startswith("new"):
            assert d["ship"] == (d["vs_genres"]["ci95"][0] > 0 and d["vs_popular"]["ci95"][0] > 0)
        else:
            assert d["ship"] == (d["ci95"][0] > 0)


def test_learning_to_rank_follows_its_rule():
    path = DATA / "ltr_confirm.json"
    if not path.exists():
        assert not (DATA / "ltr_model.joblib").exists()
        return
    d = load("ltr_confirm.json")
    assert d["ship"] == (d["ci95"][0] > 0)
    assert (DATA / "ltr_model.joblib").exists() == d["ship"]
    assert abs(sum(d["feature_shares"].values()) - 1) < 0.01 or sum(d["feature_shares"].values()) == 0
