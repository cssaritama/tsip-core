"""Test budget: how many conditions the history can support, and how many tests a report runs.

    python tools/test_budget.py --report report.json            # or an archived report.json.gz
    python tools/test_budget.py --report report.json --markdown

For each instrument the tool prints the ledger of graded tests in the report (by study family and
grade) and, for each horizon, the number of complete periods held, the most cells a condition can
be split into while each cell can still reach grade A (at least 200 units), and the smallest
effect, in standard deviations of the outcome, that an A grade can detect with 80% power.

The power figures are approximations for planning, not results: they assume independent units
(overlapping or clustered outcomes need larger effects), a single true effect among the report's
tests (the Benjamini-Hochberg threshold for the first discovery is alpha / tests), and a
comparison of one condition's periods against all periods, as the studies do. Methodology:
``docs/METHODOLOGY.md`` section 5, "Test budget".
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import sys
from datetime import date
from pathlib import Path
from statistics import NormalDist

MIN_UNITS_A = 200  # grade A needs at least this many units in the condition
HOLDOUT = 0.3  # most recent share of units held out
DAYS_PER = {"week": 7.0, "month": 365.25 / 12, "quarter": 365.25 / 4}

_Z = NormalDist().inv_cdf


def mde(n: int, share: float, tests: int, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest difference (condition mean minus all-period mean, in outcome SDs) detected at
    two-sided level ``alpha / tests`` with the given power, when the condition holds ``share`` of
    ``n`` independent units."""
    if n <= 0 or not 0 < share < 1 or tests < 1:
        return math.inf
    z = _Z(1 - alpha / (2 * tests)) + _Z(power)
    return z * math.sqrt((1 - share) / (share * n))


def holdout_mde(n: int, share: float, alpha: float = 0.10, power: float = 0.8) -> float:
    """The same for the holdout check of grade A: the most recent 30% on its own at p <= 0.10."""
    return mde(int(n * HOLDOUT), share, 1, alpha=alpha, power=power)


def grade_a_mde(n: int, share: float, tests: int) -> float | None:
    """Effect an A grade can detect: the larger of the two thresholds, or None when the condition
    cannot hold 200 units."""
    if share * n < MIN_UNITS_A:
        return None
    return max(mde(n, share, tests), holdout_mde(n, share))


def max_cells(n: int) -> int:
    """Most equal cells a condition can split the history into with every cell able to reach A."""
    return n // MIN_UNITS_A


def periods(start: str, end: str, rows: int, horizon: str) -> int:
    """Complete periods between two dates (sessions for the daily horizon)."""
    if horizon == "session":
        return int(rows)
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    return int(days // DAYS_PER[horizon])


def load(path: Path) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def ledger(report: dict) -> list[dict]:
    """Graded tests per instrument: total edge tests, grades, and items per study family."""
    out = []
    for ins in report.get("instruments", []):
        families: collections.Counter = collections.Counter()
        grades: collections.Counter = collections.Counter()
        for section in ins.get("sections", []):
            for card in section.get("cards", []):
                for item in card.get("items", []):
                    families[card.get("family", "?")] += 1
                    grades[item.get("grade", "?")] += 1
        daily = (ins.get("coverage") or {}).get("daily") or {}
        out.append(
            {
                "code": ins.get("code"),
                "edge_tests": (ins.get("grading") or {}).get("edge_tests"),
                "grades": dict(grades),
                "families": dict(families),
                "daily": daily,
            }
        )
    return out


def budget_rows(daily: dict, tests: int) -> list[dict]:
    rows = []
    if not daily:
        return rows
    for horizon in ("session", "week", "month", "quarter"):
        n = periods(daily["start"], daily["end"], daily["rows"], horizon)
        rows.append(
            {
                "horizon": horizon,
                "periods": n,
                "max_cells": max_cells(n),
                "mde_half": grade_a_mde(n, 0.5, tests),
                "mde_third": grade_a_mde(n, 1 / 3, tests),
                "mde_eighth": grade_a_mde(n, 1 / 8, tests),
            }
        )
    return rows


def _fmt(x: float | None) -> str:
    return "not reachable" if x is None else f"{x:.2f}"


def render(report: dict, markdown: bool) -> str:
    lines = []
    for entry in ledger(report):
        tests = int(entry["edge_tests"] or 0)
        graded = sum(v for k, v in entry["grades"].items() if k != "N/A")
        if markdown:
            lines.append(f"### {entry['code']}\n")
            lines.append(f"Edge tests: {tests}. Items: {sum(entry['grades'].values())}, of which graded {graded}.\n")
            lines.append("| Horizon | Periods | Cells that can reach A | A detects, half | a third | an eighth |")
            lines.append("|---|---:|---:|---:|---:|---:|")
        else:
            lines.append(f"{entry['code']}: {tests} edge tests, grades {entry['grades']}")
        for r in budget_rows(entry["daily"], max(tests, 1)):
            cells = (r["mde_half"], r["mde_third"], r["mde_eighth"])
            if markdown:
                lines.append(
                    f"| {r['horizon']} | {r['periods']} | {r['max_cells']} | "
                    + " | ".join(_fmt(c) for c in cells)
                    + " |"
                )
            else:
                lines.append(
                    f"  {r['horizon']:<8} periods {r['periods']:>6}  cells {r['max_cells']:>3}  "
                    + "  ".join(_fmt(c) for c in cells)
                )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)
    print(render(load(args.report), args.markdown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
