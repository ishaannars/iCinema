"""Every tuned number the app uses, read from the held-out test results in data/."""
import json
import streamlit as st
from pathlib import Path
from src.recommender import get_movie

ROOT = Path(__file__).resolve().parents[1]   # the repo root, where data/ lives


def _tested_blend_weights():
    """Blend weights picked on held-out MovieLens viewers (training/evaluate_blends.py)."""
    try:
        d = json.loads((ROOT / "data" / "blend_results.json").read_text())
        return float(d["content_blend"]["best_weight"]), float(d["whats_next"]["best_weight"])
    except Exception:
        return 0.65, 0.6


def _tested_knobs():
    """Row mixes and the variety step from training/evaluate_knobs.py (data/knobs_results.json).
    Until that test has run, the original settings stay."""
    out = {"rows": {}, "variety": 0.74}
    try:
        d = json.loads((ROOT / "data" / "knobs_results.json").read_text())
        out["rows"] = {k: float(v["use"]) for k, v in (d.get("rows") or {}).items()}
        out["variety"] = float((d.get("variety") or {}).get("use", 0.74))
    except Exception:
        pass
    return out


def _tested_shelf():
    """Step 1 shelf picked by training/confirm_shelf_and_imports.py, or [] if that test didn't pass."""
    try:
        rows = json.loads((ROOT / "data" / "shelf_titles.json").read_text())["titles"]
    except Exception:
        return []
    out = []
    for r in rows:
        m = get_movie(r["title"])
        out.append(dict(m) if m else {"title": r["title"], "year": int(r.get("year") or 0),
                                      "tmdb_id": int(r.get("tmdb_id") or 0), "external": True,
                                      "candidate_source": "shelf"})
    return out


def _like_rerank_ships():
    """True unless the held-out test (training/confirm_like.py -> data/like_confirm.json) rejected the re-rank."""
    try:
        return bool(json.loads((ROOT / "data" / "like_confirm.json").read_text()).get("ship", True))
    except Exception:
        return True


@st.cache_data(show_spinner=False)
def load_offline_results():
    """MovieLens evaluation written by training/train_cf.py (data/cf_results.json)."""
    try:
        path = ROOT / "data" / "cf_results.json"
        return json.loads(path.read_text())
    except Exception:
        return None


def _similar_weights():
    """(content weight, popularity discount) for "like X", from the held-out test
    (training/confirm_similar.py). If that test kept fans-only ordering, so does the app."""
    try:
        d = json.loads((ROOT / "data" / "similar_confirm.json").read_text())
        if not d.get("ship"):
            return 0.0, 0.0
        c = d.get("chosen") or {}
        return float(c.get("content_weight", 0.5)), float(c.get("popularity_discount", 0.15))
    except Exception:
        return 0.5, 0.15          # until the test is run
