"""One search field for mood and time: "funny, under 2 hours" -> mood "funny", at most 120 minutes.

Time words become a runtime limit (a filter, not a model). Whatever is left goes to the tested mood
model. Movies use their runtime; shows use their episode length. A bare length ("2 hours",
"90 min") means "about that long or less".
"""
import re

# "2 hours", "1.5 hrs", "2h 30m", "2 hours 30 minutes", "90-minute", "an hour", "half an hour"
_DUR = (r"(?:(?P<h>\d+(?:\.\d+)?)\s*-?\s*(?:hours?|hrs?|h)\b(?:\s*(?:and\s*)?(?P<hm>\d+)\s*-?\s*(?:minutes?|mins?|m)\b)?"
        r"|(?P<mo>\d+)\s*-?\s*(?:minutes?|mins?|m)\b"
        r"|(?P<half>half an hour)|(?P<onehalf>an hour and a half|hour and a half)|(?P<one>an hour|one hour))")
_UNDER = re.compile(r"\b(?:under|less than|below|max(?:imum)?|at most|up to|within|no more than)\s*" + _DUR, re.I)
_OVER = re.compile(r"\b(?:over|more than|longer than|at least)\s*" + _DUR, re.I)
_BARE = re.compile(r"(?<![\w.])(?:about\s+|around\s+|roughly\s+)?" + _DUR, re.I)
_WORDS = {"short episodes": ("episodes", 35), "short": ("max", 100), "quick": ("max", 100),
          "something long": ("min", 150), "long": ("min", 150), "epic": ("min", 150)}
_FILLER = {"like", "a", "an", "the", "movie", "movies", "film", "films", "something", "long", "for", "of", "or", "less", "max"}


def _dur_minutes(m):
    if m.group("h"):
        return int(round(float(m.group("h")) * 60 + int(m.group("hm") or 0)))
    if m.group("mo"):
        return int(m.group("mo"))
    if m.group("half"):
        return 30
    if m.group("onehalf"):
        return 90
    return 60


def _cut(q, m):
    return (q[:m.start()] + " " + q[m.end():]).strip()


_LIKE = re.compile(r"(?:\b(?:movies?|films?|shows?|something|anything)\s+)?\b(?:like|similar to)\s+(.+)$", re.I)


def parse(query):
    """-> {"mood": str, "max": minutes or None, "min": minutes or None, "episodes": max episode minutes or None, "label": str}"""
    q = " ".join(str(query or "").split())
    out = {"max": None, "min": None, "episodes": None, "like": None}
    m = _LIKE.search(q)
    if m:
        out["like"] = m.group(1).strip(" ,.;\"“”'")[:80] or None
        q = q[:m.start()].strip(" ,")
    m = _UNDER.search(q)
    if m:
        out["max"] = _dur_minutes(m)
        q = _cut(q, m)
    m = _OVER.search(q)
    if m:
        out["min"] = _dur_minutes(m)
        q = _cut(q, m)
    if out["max"] is None and out["min"] is None:
        m = _BARE.search(q)
        if m:
            out["max"] = _dur_minutes(m)
            q = _cut(q, m)
    low = q.lower()
    for phrase, (kind, mins) in _WORDS.items():
        if re.search(rf"\b{re.escape(phrase)}\b", low):
            if kind == "max" and out["max"] is None:
                out["max"] = mins
            elif kind == "min" and out["min"] is None:
                out["min"] = mins
            elif kind == "episodes":
                out["episodes"] = mins
            low = re.sub(rf"\b{re.escape(phrase)}\b", " ", low)
    mood = " ".join(re.sub(r"[,;]+", " ", low).split())
    mood = re.sub(r"^(and|with)\s+|\s+(and|with)$", "", mood).strip()
    mood = " ".join(w for w in mood.split() if w not in {"movie", "movies", "film", "films"})
    if mood and all(w in _FILLER for w in mood.split()):
        mood = ""
    parts = []
    if out["max"]:
        parts.append(f"under {fmt(out['max'])}")
    if out["min"]:
        parts.append(f"over {fmt(out['min'])}")
    if out["episodes"]:
        parts.append("short episodes")
    if out["like"]:
        parts.insert(0, f"like {out['like']}")
    out["mood"] = mood
    out["label"] = " · ".join(parts)
    return out


def compose(mood="", max_min=None, min_min=None, episodes=None, like=None):
    """Write a spec back as search text that parse() reads the same way ("like X" always goes last)."""
    bits = [mood] if mood else []
    if max_min:
        bits.append(f"under {int(max_min)} min")
    if min_min:
        bits.append(f"over {int(min_min)} min")
    if episodes:
        bits.append("short episodes")
    if like:
        bits.append(f"like {like}")
    return ", ".join(bits)


def chips(query):
    """What the field understood, as removable chips: [(label, text without this chip), ...]."""
    s = parse(query)
    m, mx, mn, ep, lk = s["mood"], s["max"], s["min"], s["episodes"], s["like"]
    out = []
    if lk:
        out.append((f"Like {lk}", compose(m, mx, mn, ep, None)))
    if m:
        out.append((m, compose("", mx, mn, ep, lk)))
    if mx:
        out.append((f"Under {fmt(mx)}", compose(m, None, mn, ep, lk)))
    if mn:
        out.append((f"Over {fmt(mn)}", compose(m, mx, None, ep, lk)))
    if ep:
        out.append(("Short episodes", compose(m, mx, mn, None, lk)))
    return out


def fmt(minutes):
    """Runtimes in plain minutes, the way they read at a glance: "136 min"."""
    if not minutes:
        return ""
    return f"{int(minutes)} min"


def fits(runtime, spec, show=False):
    """True if a runtime (minutes) passes the time limits; unknown runtimes pass only with no limit."""
    lim_max = spec.get("episodes") if show and spec.get("episodes") else spec.get("max")
    lim_min = None if show else spec.get("min")
    if not lim_max and not lim_min:
        return True
    if not runtime:
        return False
    return (not lim_max or runtime <= lim_max) and (not lim_min or runtime >= lim_min)
