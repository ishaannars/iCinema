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


@lru_cache(maxsize=1)
def _load_main():
    """The order model for the main ranking, only if data/seq_main_confirm.json passed its held-out test."""
    try:
        conf = json.loads((DATA / "seq_main_confirm.json").read_text())
        if not conf.get("ship"):
            return None
        d = np.load(DATA / "seq_chain.npz")
        return d["nbr"], d["w"], float(conf["weight"])
    except Exception:
        return None


def main_available():
    return _load_main() is not None


def main_weight():
    d = _load_main()
    return d[2] if d else 0.0


def main_vector(recent):
    """0-1 percentile for every movie: how likely it is to be liked next after your 3 most recent likes
    (oldest to newest, weighted 0.25 / 0.5 / 1.0, as tested), or None if the model isn't shipped."""
    d = _load_main()
    recent = [int(i) for i in recent if i is not None][-3:]
    if d is None or not recent:
        return None
    nbr, w, _ = d
    s = np.zeros(nbr.shape[0], dtype=np.float64)
    for wt, i in zip([0.25, 0.5, 1.0][-len(recent):], recent):
        ok = nbr[i] >= 0
        np.add.at(s, nbr[i][ok], wt * w[i][ok])
    ranks = np.argsort(np.argsort(s))
    return ranks / max(len(s) - 1, 1)
