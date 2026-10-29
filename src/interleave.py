"""Live interleaving test: routed ranking vs item-kNN only, in Top Matches.

What it compares. Routing sends a viewer to RP3beta when their liked movies are mostly less-loved
ones, and to item-kNN otherwise. For everyone else the two rankings are the same list, so the test
only runs for viewers whose likes route them to RP3beta. It answers one question: for viewers with
less mainstream likes, does the routed ranking (RP3beta) or item-kNN alone get more saves within a
visit? It is a screen. It says nothing about long-term retention, which needs an A/B test once
traffic allows.

How a visit is built (team draft, Radlinski et al. 2008). Each step, the team with fewer picks so
far adds its best movie not already shown; when both have the same number, a coin flip decides who
goes first. Each card remembers which team put it there. Cards show the score and love chance from
the model that picked them, and Top Matches keeps the interleaved order (no re-sorting), so neither
team gets a better position or a better-looking label.

Rule, written before any data was collected:
- Unit: one Showroom visit with interleaving on. Only saves earn credit; views don't.
- A visit is decided when one team earned more saves than the other. Visits with no saves, or a
  tie, don't count.
- Sample size is fixed in advance: the first 200 decided visits, in time order. No result is shown
  or read before then (the report prints progress only).
- Test: two-sided exact binomial test that routed wins half of decided visits, alpha 0.05.
- Guardrails, read at the same time: skips and "Not for me" taps credited to each team in those
  same visits, each with the same two-sided binomial test. A winner that is significantly worse
  on either guardrail doesn't ship.
- Decision: if item-kNN wins significantly and passes the guardrails, routing is turned off.
  Otherwise routing stays (it already passed its offline test on 39,805 new viewers), and a
  non-significant result is reported as "no detectable difference."
- Also reported, not used for the decision: one vote per anonymous viewer (their majority across
  visits), since one person can contribute several visits.
"""
from math import comb

TEAMS = ("routed", "knn")
TARGET_DECIDED = 200
ALPHA = 0.05


def team_draft(a, b, rng, limit=None):
    """Interleave two ranked lists of ids. Returns (merged ids, {id: team}).

    rng needs a random() method (random.Random). Each list keeps its own order; an id already
    picked by the other team is skipped. When one list runs out, the other keeps picking.
    """
    a, b = list(a), list(b)
    limit = len(set(a) | set(b)) if limit is None else int(limit)
    merged, teams, used = [], {}, set()
    ia = ib = 0
    count = {"routed": 0, "knn": 0}

    def next_from(lst, i):
        while i < len(lst) and lst[i] in used:
            i += 1
        return i

    while len(merged) < limit:
        ia, ib = next_from(a, ia), next_from(b, ib)
        a_left, b_left = ia < len(a), ib < len(b)
        if not a_left and not b_left:
            break
        a_turn = count["routed"] < count["knn"] or (count["routed"] == count["knn"] and rng.random() < 0.5)
        if a_left and (a_turn or not b_left):
            item, team, ia = a[ia], "routed", ia + 1
        else:
            item, team, ib = b[ib], "knn", ib + 1
        merged.append(item)
        teams[item] = team
        used.add(item)
        count[team] += 1
    return merged, teams


def binomial_two_sided_p(k, n):
    """Exact two-sided binomial p-value for k successes in n trials at p = 0.5."""
    if n <= 0:
        return 1.0
    probs = [comb(n, i) / 2 ** n for i in range(n + 1)]
    cutoff = probs[k] * (1 + 1e-9)
    return min(1.0, sum(p for p in probs if p <= cutoff))


def visit_tallies(events):
    """events: dicts with session, team, event ('save', 'skip', 'not_for_me', 'interleave_shown'),
    timestamp (sortable), and optional viewer. Returns {session: tally} in time order."""
    out = {}
    for e in sorted(events, key=lambda e: str(e.get("timestamp") or "")):
        s = e.get("session")
        if not s:
            continue
        t = out.setdefault(s, {"first": e.get("timestamp"), "viewer": e.get("viewer"),
                               "save": {"routed": 0, "knn": 0}, "skip": {"routed": 0, "knn": 0},
                               "not_for_me": {"routed": 0, "knn": 0}})
        kind, team = e.get("event"), e.get("team")
        if kind in ("save", "skip", "not_for_me") and team in TEAMS:
            t[kind][team] += 1
    return out


def winner(tally):
    s = tally["save"]
    if s["routed"] > s["knn"]:
        return "routed"
    if s["knn"] > s["routed"]:
        return "knn"
    return None


def _guardrail(decided, kind, win_team):
    lose_team = "knn" if win_team == "routed" else "routed"
    w = sum(t[kind][win_team] for t in decided)
    l_ = sum(t[kind][lose_team] for t in decided)
    p = binomial_two_sided_p(w, w + l_)
    return {"winner": w, "other": l_, "p_value": round(p, 4), "worse": bool(p < ALPHA and w > l_)}


def summarize(events, target=TARGET_DECIDED):
    """Progress while running; the full result only once the fixed sample is reached (no peeking)."""
    tallies = visit_tallies(events)
    decided = [t for t in tallies.values() if winner(t)]
    out = {"target_decided_visits": target, "interleaved_visits": len(tallies),
           "decided_visits": min(len(decided), target), "status": "running"}
    if len(decided) < target:
        return out
    decided = decided[:target]
    routed = sum(1 for t in decided if winner(t) == "routed")
    p = binomial_two_sided_p(routed, target)
    lead = "routed" if routed * 2 > target else "knn" if routed * 2 < target else None
    significant = bool(p < ALPHA and lead)
    guard = {k: _guardrail(decided, k, lead) for k in ("skip", "not_for_me")} if lead else {}
    passes = significant and not any(g["worse"] for g in guard.values())
    votes = {}
    for t in decided:
        if t.get("viewer"):
            votes.setdefault(t["viewer"], []).append(winner(t))
    viewer_wins = [max(set(v), key=v.count) for v in votes.values() if v.count("routed") != v.count("knn")]
    out.update({
        "status": "finished", "routed_wins": routed, "knn_wins": target - routed,
        "routed_win_share": round(routed / target, 4), "p_value": round(p, 4),
        "significant": significant, "leader": lead, "guardrails": guard,
        "decision": ("turn routing off" if passes and lead == "knn" else "keep routing"),
        "one_vote_per_viewer": {"viewers": len(viewer_wins), "routed": viewer_wins.count("routed"),
                                "knn": viewer_wins.count("knn")},
    })
    return out
