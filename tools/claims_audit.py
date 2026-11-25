"""Check every claim the front page and README make against the result files.

    python tools/claims_audit.py

Prints one line per model (PASS, FAIL, NO FLAG, MISSING) and the front-page numbers with where each
comes from. Exit code 1 if any model is not PASS, so "each passed a test" is never said unless true.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.claims import audit  # noqa: E402


def main():
    rows = audit()
    for name, fname, test, status in rows:
        print(f"{status:<8} {name:<22} data/{fname:<30} {test}")
    n = sum(1 for *_x, s in rows if s == "PASS")
    print(f"\n{n} of {len(rows)} models have a passing result file.")
    print("Front page says:", "each passed a test" if n == len(rows) else f"{n} of {len(rows)} passed a test")
    sys.exit(0 if n == len(rows) else 1)


if __name__ == "__main__":
    main()
