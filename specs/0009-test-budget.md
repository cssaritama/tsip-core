# 0009 Test budget

**Status:** shipped (unreleased; tool only, the report and the site are unchanged)
**Level:** 1 feature · **Open work:** W-74

## Problem and decision supported

The founder's list of advanced variables (sessions, momentum, regimes, revisits, extremes, cross-asset) invites crossing them. Each crossing is more tests on the same history, and a history of ten years holds only so many weeks, months and quarters. Before a study crosses conditions, the team needs to know which splits the history can support and how large an effect must be to earn a grade, so that the founder's ideas are tested where they can succeed and are not spent where they cannot.

## Requirements

- R1. A tool shall list, for any report or archived report, the edge tests per instrument and the items by study family and grade.
- R2. For each instrument and horizon (session, week, month, quarter) it shall give the number of complete periods held, the most cells a condition can be split into with every cell able to reach grade A (200 units), and the smallest effect an A grade can detect with 80% power for conditions holding a half, a third and an eighth of the periods.
- R3. The rules for counting tests and for conditions revised after their results were seen shall be stated in `docs/METHODOLOGY.md`.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| T1 | The detectable effect matches the normal approximation (z for alpha divided by the number of tests, plus z for 80% power, times the standard error of a condition's mean against all periods) | test |
| T2 | A condition holding fewer than 200 periods is reported as not reachable for A | test |
| T3 | Periods per horizon are counted from the report's coverage dates; the ledger counts items by family and grade | test |
| T4 | Run on the live report of 2026-11-05 20:18 UTC, the figures are written into the variable catalogue | founder review |

## Non-goals

- No change to grading or to the report: the budget plans studies, it does not grade them.
- The power figures assume independent units and one true effect among the tests; they are planning figures, not results.

## Design notes

- The holdout check of grade A (the most recent 30% alone at p ≤ 0.10) is included as a second threshold; the larger of the two is reported. At these sample sizes the two are close.
- Weeks, months and quarters are counted from calendar dates, so the first and last partial periods may add one; the figure is for planning.
- The tool reads reports only; it needs no provider data and runs anywhere.

## Verification

| ID | Result | Evidence |
|---|---|---|
| T1 | pass | `tests/test_test_budget.py::test_mde_matches_the_normal_approximation` |
| T2 | pass | `tests/test_test_budget.py::test_grade_a_needs_200_units_in_the_condition` |
| T3 | pass | `tests/test_test_budget.py::test_periods_and_ledger_from_a_report` |
| T4 | pass | `tsip-platform/docs/research/VARIABLE_CATALOGUE.md`, run on `reports/2026/11/2026-11-05T2018Z.json.gz` |
