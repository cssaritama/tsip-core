# 0011 Evaluation record for the hypothesis register

**Status:** shipped in 0.2.24
**Level:** 1 feature · **Open work:** W-77

## Problem and decision supported

Registered hypotheses are fingerprinted so that anyone can check they were not changed after the results were seen. Editing an entry to record its outcome would change its fingerprint and break that check. A buyer reading the register needs to see which hypotheses were supported, which were not, and on which archived report.

## Requirements

- R1. Outcomes are recorded in `registry/evaluations.json`, one entry per evaluation: hypothesis id, the fingerprint of the entry evaluated, date, outcome (supported, not supported, inconclusive), result in one sentence, archived report path and fingerprint, version.
- R2. The report attaches an evaluation to its hypothesis only when the fingerprint matches the registered entry; otherwise it is marked not applicable.
- R3. The register page shows the latest valid outcome as the status and each evaluation's result and report.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| T1 | A registered entry and its fingerprint are unchanged by an evaluation | test |
| T2 | An evaluation naming a different fingerprint is marked not applicable | test |
| T3 | Every recorded evaluation in the repository matches its entry | test |
| T4 | The register page shows the outcome and the result | render and browser check |

## Non-goals

- The evaluation itself stays a reviewed step (results document and the founder's review), not an automatic grade.

## Verification

| ID | Result | Evidence |
|---|---|---|
| T1, T2 | pass | `tests/test_report_and_site.py::test_evaluations_attach_only_to_the_registered_fingerprint` |
| T3 | pass | `tests/test_report_and_site.py::test_registered_evaluations_match_the_register` |
| T4 | pass | render check, 0 problems; the register shows "Supported (2026-11-06)" with the result for H-2026-011 and H-2026-014 |
