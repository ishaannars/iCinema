"""Holm correction across every held-out test in data/: which wins survive testing many things at once?

    python tools/multiple_testing.py

With 15+ tests at the 95% level, about one could pass by luck. Each result file stores a difference and
its paired-bootstrap 95% interval; this recovers an approximate p-value from that interval (normal
approximation), then applies the Holm-Bonferroni step-down correction across all of them at a family-wide
5%. Writes data/multiple_testing.json and prints one line per test.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIFF_KEYS = ("diff", "ndcg_diff_vs_current", "diff_vs_no_variety", "diff_vs_current", "brier_diff_vs_average", "lift")


def found(obj, path=""):
    if isinstance(obj, dict):
        ci = obj.get("ci95") or obj.get("brier_ci95")
        diff = next((obj[k] for k in DIFF_KEYS if isinstance(obj.get(k), (int, float))), None)
        if isinstance(ci, list) and len(ci) == 2 and diff is not None and ci[1] > ci[0]:
            yield path or "result", float(diff), float(ci[0]), float(ci[1])
        for k, v in obj.items():
            if k not in ("ci95", "brier_ci95"):
                yield from found(v, f"{path}/{k}" if path else k)


def p_value(diff, lo, hi):
    se = (hi - lo) / (2 * 1.96)
    if se <= 0:
        return 0.0
    z = abs(diff) / se
    return math.erfc(z / math.sqrt(2))


def main():
    tests = []
    for f in sorted((ROOT / "data").glob("*.json")):
        if f.name == "multiple_testing.json":
            continue
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        for path, diff, lo, hi in found(d):
            tests.append({"test": f"{f.stem}:{path}", "diff": diff, "ci95": [lo, hi], "p": p_value(diff, lo, hi)})
    tests.sort(key=lambda t: t["p"])
    m, still = len(tests), True
    for k, t in enumerate(tests):
        threshold = 0.05 / (m - k)
        still = still and t["p"] <= threshold
        t["holm_threshold"], t["significant_after_holm"] = threshold, bool(still)
        t["significant_alone"] = (t["ci95"][0] > 0) or (t["ci95"][1] < 0)
    survived = sum(t["significant_after_holm"] for t in tests)
    alone = sum(t["significant_alone"] for t in tests)
    out = {"method": "Holm-Bonferroni across all held-out tests, family-wide 5%; p from bootstrap CI (normal approx.)",
           "tests": m, "significant_alone": alone, "significant_after_holm": survived, "results": tests}
    (ROOT / "data" / "multiple_testing.json").write_text(json.dumps(out, indent=1))
    for t in tests:
        print(f"{t['test'][:58]:<58} diff {t['diff']:+.4f}  p {t['p']:.2g}  {'holds' if t['significant_after_holm'] else ('lost after correction' if t['significant_alone'] else 'not significant')}")
    print(f"{alone} of {m} significant on their own; {survived} still significant after Holm correction")


if __name__ == "__main__":
    main()
