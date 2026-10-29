"""The live interleaving test follows the rule written in src/interleave.py."""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from src import interleave as il  # noqa: E402


def test_team_draft_is_balanced_and_keeps_each_order():
    a, b = list("abcdefgh"), list("hgfedcba")
    for seed in range(50):
        merged, teams = il.team_draft(a, b, random.Random(seed), limit=8)
        assert len(merged) == len(set(merged)) == 8
        n_a = sum(1 for t in merged if teams[t] == "routed")
        assert abs(n_a - (8 - n_a)) <= 1
        picked_a = [t for t in merged if teams[t] == "routed"]
        assert picked_a == [t for t in a if t in picked_a]       # routed's picks stay in routed's order


def test_identical_lists_split_credit_by_coin_flips():
    lst = [str(i) for i in range(40)]
    first_team = [il.team_draft(lst, lst, random.Random(s), limit=40)[1]["0"] for s in range(400)]
    share = first_team.count("routed") / len(first_team)
    assert 0.4 < share < 0.6                                     # no built-in edge for either side


def test_runs_out_gracefully():
    merged, teams = il.team_draft(["x"], ["y", "z", "w"], random.Random(1))
    assert set(merged) == {"x", "y", "z", "w"} and teams["x"] == "routed"


def test_binomial_p_values():
    assert il.binomial_two_sided_p(5, 10) == 1.0
    assert abs(il.binomial_two_sided_p(9, 10) - 22 / 1024) < 1e-12
    assert abs(il.binomial_two_sided_p(1, 10) - 22 / 1024) < 1e-12
    assert il.binomial_two_sided_p(115, 200) < 0.05 < il.binomial_two_sided_p(113, 200)


def _visits(n_routed, n_knn, ties=0, empty=0, skips_for_winner=0):
    ev, t = [], 0
    for i in range(n_routed + n_knn + ties + empty):
        s = f"v{i}"
        t += 1
        ev.append({"event": "interleave_shown", "session": s, "timestamp": f"{t:08d}", "viewer": s})
        if i < n_routed:
            saves = ["routed"]
        elif i < n_routed + n_knn:
            saves = ["knn"]
        elif i < n_routed + n_knn + ties:
            saves = ["routed", "knn"]
        else:
            saves = []
        for team in saves:
            t += 1
            ev.append({"event": "save", "team": team, "session": s, "timestamp": f"{t:08d}", "viewer": s})
    for k in range(skips_for_winner):
        ev.append({"event": "skip", "team": "knn", "session": "v0", "timestamp": f"{t + k + 1:08d}"})
    return ev


def test_no_peeking_before_the_fixed_sample():
    r = il.summarize(_visits(150, 10, ties=30, empty=40))
    assert r["status"] == "running" and r["decided_visits"] == 160 and r["interleaved_visits"] == 230
    assert not {"routed_wins", "knn_wins", "p_value", "leader"} & set(r)


def test_decides_on_exactly_the_first_200():
    r = il.summarize(_visits(130, 120, ties=5))
    assert r["status"] == "finished" and r["routed_wins"] + r["knn_wins"] == 200
    assert r["routed_wins"] == 130 and r["decision"] == "keep routing"


def test_knn_win_turns_routing_off_unless_a_guardrail_fails():
    r = il.summarize(_visits(80, 120))
    assert r["significant"] and r["leader"] == "knn" and r["decision"] == "turn routing off"
    r = il.summarize(_visits(80, 120, skips_for_winner=40))
    assert r["guardrails"]["skip"]["worse"] and r["decision"] == "keep routing"


def test_report_reads_posthog_csv(tmp_path):
    import interleave_report as rep
    f = tmp_path / "events.csv"
    f.write_text('event,timestamp,distinct_id,"properties.il_team","properties.il_session"\n'
                 "interleave_shown,2026-11-01T10:00:00,abc,,s1\nsave,2026-11-01T10:01:00,abc,knn,s1\n"
                 "visit,2026-11-01T10:00:00,abc,,\n")
    ev = rep.from_file(f)
    assert [e["event"] for e in ev] == ["interleave_shown", "save"] and ev[1]["team"] == "knn"
    r = il.summarize(ev)
    assert r["interleaved_visits"] == 1 and r["decided_visits"] == 1
