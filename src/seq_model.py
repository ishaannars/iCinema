"""What fans liked next: each movie's 100 most likely next likes (training/build_sequential.py).

Used by "More like X" only when data/seq_like_confirm.json shows it beat fans alone on held-out
viewers; otherwise nothing here is loaded.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def _load():
    try:
        conf = json.loads((DATA / "seq_like_confirm.json").read_text())
        if not conf.get("ship"):
            return None
        d = np.load(DATA / "seq_chain.npz")
        return d["nbr"], float(conf.get("weight", d["weight"]))
    except Exception:
        return None


def available():
    return _load() is not None


def blend_order(i, fan_order):
    """Re-rank: (1 - a) x fans' closeness rank + a x "liked next" rank, the weight from the held-out test."""
    d = _load()
    if d is None or i is None:
        return list(fan_order)
    nbr, a = d
    nxt = [int(j) for j in nbr[i] if j >= 0]
    def ranks(order):
        size = max(len(order), 1)
        return {int(j): 1 - r / size for r, j in enumerate(order)}
    rf, rn = ranks(fan_order), ranks(nxt)
    cand = list(dict.fromkeys([int(j) for j in fan_order] + nxt))
    return sorted(cand, key=lambda j: -((1 - a) * rf.get(j, 0.0) + a * rn.get(j, 0.0)))
