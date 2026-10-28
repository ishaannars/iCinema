"""The love chance shown on cards reads from the tested table and never overclaims."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import love  # noqa: E402


def test_love_line_matches_the_table():
    d = json.loads(love.PATH.read_text())
    if not d["ships"]:
        assert love.love_line(1) == ""
        return
    c = love.love_chance(d["table"][0]["top_pct"])
    assert c % 5 == 0 and 0 <= c <= 100
    assert love.love_chance(1) >= love.love_chance(50)
    assert love.love_line(None) == ""


def test_fit_floor_sits_where_love_chance_meets_the_average():
    d = json.loads(love.PATH.read_text())
    f = love.fit_floor()
    if not d["ships"]:
        assert f is None
        return
    rows = sorted(d["table"], key=lambda r: r["top_pct"])
    assert rows[0]["top_pct"] <= f <= rows[-1]["top_pct"]
    assert love.love_chance(f) in range(int(d["average_love_rate"] * 100) - 5, int(d["average_love_rate"] * 100) + 6)
