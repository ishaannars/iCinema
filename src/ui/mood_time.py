"""One search field for mood and time: "funny, under 2 hours" -> mood "funny", at most 120 minutes.

Time words become a runtime limit (a filter, not a model). Whatever is left goes to the tested mood
model. Movies use their runtime; shows use their episode length.
"""
import re

_UNDER = re.compile(r"\b(?:under|less than|below|max(?:imum)?|at most|<=?|<)\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", re.I)
_OVER = re.compile(r"\b(?:over|more than|longer than|at least|>=?|>)\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", re.I)
_WORDS = {"short episodes": ("episodes", 35), "short": ("max", 100), "quick": ("max", 100),
          "something long": ("min", 150), "long": ("min", 150), "epic": ("min", 150)}


def _minutes(n, unit):
    n = float(n)
    return int(round(n * 60)) if unit.lower().startswith("h") else int(round(n))


def parse(query):
    """-> {"mood": str, "max": minutes or None, "min": minutes or None, "episodes": max episode minutes or None, "label": str}"""
    q = " ".join(str(query or "").split())
    out = {"max": None, "min": None, "episodes": None}
    m = _UNDER.search(q)
    if m:
        out["max"] = _minutes(m.group(1), m.group(2))
        q = q[:m.start()] + q[m.end():]
    m = _OVER.search(q)
    if m:
        out["min"] = _minutes(m.group(1), m.group(2))
        q = q[:m.start()] + q[m.end():]
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
    parts = []
    if out["max"]:
        parts.append(f"under {fmt(out['max'])}")
    if out["min"]:
        parts.append(f"over {fmt(out['min'])}")
    if out["episodes"]:
        parts.append("short episodes")
    out["mood"] = mood
    out["label"] = " · ".join(parts)
    return out


def fmt(minutes):
    if not minutes:
        return ""
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m:02d}m" if h and m else (f"{h}h" if h else f"{m}m")


def fits(runtime, spec, show=False):
    """True if a runtime (minutes) passes the time limits; unknown runtimes pass only with no limit."""
    lim_max = spec.get("episodes") if show and spec.get("episodes") else spec.get("max")
    lim_min = None if show else spec.get("min")
    if not lim_max and not lim_min:
        return True
    if not runtime:
        return False
    return (not lim_max or runtime <= lim_max) and (not lim_min or runtime >= lim_min)
