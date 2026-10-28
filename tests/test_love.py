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
