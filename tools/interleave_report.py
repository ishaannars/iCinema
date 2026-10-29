"""Score the live interleaving test and write data/interleave_results.json.

    python tools/interleave_report.py --api                 # pull events from PostHog
    python tools/interleave_report.py --file events.csv     # or a PostHog export (CSV or JSON)
    python tools/interleave_report.py --empty               # reset to "0 of 200" (before launch)

The rule (unit, sample size, test, guardrails, decision) is in src/interleave.py and was written
before any data came in. Until 200 decided visits exist, this prints and saves progress only, so
nobody can peek at who's ahead. Then python tools/refresh_results.py puts it in the README.

--api reads two environment variables, never stored in the repo: POSTHOG_PERSONAL_API_KEY (a
personal key with read access to query) and POSTHOG_PROJECT_ID. POSTHOG_APP_HOST defaults to
https://us.posthog.com.

Known limits: an Undo on Skip removes the skip in the app but PostHog already received it, so
guardrail skip counts can be slightly high for both teams. Turn analytics off in your own browser
(Profile) before testing, so your own visits don't count.
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.interleave import TARGET_DECIDED, summarize  # noqa: E402

OUT = ROOT / "data" / "interleave_results.json"
EVENTS = ("save", "skip", "not_for_me", "interleave_shown")
QUERY = ("SELECT event, properties.il_team, properties.il_session, distinct_id, timestamp FROM events "
         "WHERE properties.il_session IS NOT NULL AND event IN ('save', 'skip', 'not_for_me', 'interleave_shown') "
         "ORDER BY timestamp LIMIT 100000")


def _norm(event, team, session, viewer, ts):
    return {"event": event, "team": team or None, "session": session or None, "viewer": viewer or None,
            "timestamp": str(ts or "")}


def from_api():
    import requests
    key, project = os.environ.get("POSTHOG_PERSONAL_API_KEY"), os.environ.get("POSTHOG_PROJECT_ID")
    if not key or not project:
        sys.exit("Set POSTHOG_PERSONAL_API_KEY and POSTHOG_PROJECT_ID in your shell first.")
    host = os.environ.get("POSTHOG_APP_HOST", "https://us.posthog.com").rstrip("/")
    r = requests.post(f"{host}/api/projects/{project}/query/", timeout=60,
                      headers={"Authorization": f"Bearer {key}"},
                      json={"query": {"kind": "HogQLQuery", "query": QUERY}})
    r.raise_for_status()
    return [_norm(*row) for row in r.json().get("results") or []]


def _pick(row, name):
    """Find a column by name, allowing PostHog's prefixes (properties.il_team, *.il_team)."""
    for k, v in row.items():
        if k == name or str(k).endswith("." + name) or str(k).endswith('"' + name + '"'):
            return v
    return None


def from_file(path):
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        rows = data.get("results", data) if isinstance(data, dict) else data
        out = []
        for e in rows:
            if isinstance(e, list):          # HogQL-style rows, same column order as QUERY
                out.append(_norm(*e[:5]))
                continue
            props = e.get("properties") or {}
            out.append(_norm(e.get("event"), props.get("il_team", e.get("il_team")),
                             props.get("il_session", e.get("il_session")), e.get("distinct_id"), e.get("timestamp")))
        return [e for e in out if e["event"] in EVENTS]
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    out = [_norm(_pick(r, "event"), _pick(r, "il_team"), _pick(r, "il_session"), _pick(r, "distinct_id"), _pick(r, "timestamp"))
           for r in rows]
    return [e for e in out if e["event"] in EVENTS]


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--api", action="store_true")
    src.add_argument("--file")
    src.add_argument("--empty", action="store_true")
    args = ap.parse_args()
    events = [] if args.empty else from_api() if args.api else from_file(args.file)
    result = summarize(events, TARGET_DECIDED)
    result["rule"] = "See src/interleave.py (written before data collection)."
    OUT.write_text(json.dumps(result, indent=1))
    if result["status"] == "running":
        print(f"Live test running: {result['decided_visits']} of {result['target_decided_visits']} decided visits "
              f"({result['interleaved_visits']} visits with interleaving so far). Results stay hidden until then.")
    else:
        print(json.dumps(result, indent=1))
    print(f"Saved {OUT.relative_to(ROOT)}. Next: python tools/refresh_results.py")


if __name__ == "__main__":
    main()
