# 0030 Buy timing against a drift-neutral control

**Status:** approved (founder, 2026-11-10: proceed with Q-44); protocol fixed and H-2026-018 registered before any figure
**Level:** 2 study · **Open work:** W-125 · **Decisions:** ADR 0064, ADR 0067, ADR 0071 · **Repairs:** specification 0029

## Problem and decision supported

Specification 0029 compared each buy-timing rule with the month's average price. On rising prices that control favours any rule that buys early and penalises any rule that waits, and the random-walk check exposed it (3 of 59 tests passed on random walks). The decision is the same: on which session should an investor with a fixed monthly amount buy? The question here is whether any rule beats random sessions taken at the same positions in the month as its own purchases, which removes the advantage of buying early or late.

## Requirements

- R1. Same data, instruments, months, rules, frozen parameters (`registry/capstone_timing_choices.json`, commit `5b96f02`), one purchase per month and fallback as specification 0029. No new choice is made.
- R2. **Matched-position control:** for a rule, let w(k) be the share of its confirmation-period purchases made on the k-th session of the month. In month m the control price is the w-weighted average of that month's adjusted closes at positions k (a position beyond the month's length takes the month's last session). The advantage of month m is (control price minus price paid) divided by the control price.
- R3. A rule that always buys at the same session index has an advantage of exactly zero; such rules (B6 and the first-session reference) are reported and counted, but cannot pass. The last session of the month is not a fixed index (months have 19 to 23 sessions), so its advantage need not be zero. (Clarified on 2026-11-10 before any figure.)
- R4. Statistic, intervals and correction as specification 0029: mean advantage, circular block bootstrap over months (6-month blocks, 2,000 resamples), Benjamini–Hochberg at q 0.05 across the same 59 confirmation tests.

## Study protocol

- **Period:** the confirmation months of specification 0029. They were read on 2026-11-10 with the month-average control, so this is a re-analysis of seen data with a corrected control, not an independent test; it is labelled as such. A forward record from 2026-11 onwards, with the same rules and control, is the independent check.
- **Random-walk check:** the whole pipeline (development choices and confirmation, as in specification 0029) on random-walk prices with each instrument's drift and volatility; with the drift-neutral control no test may pass.
- **Hypothesis before the run (H-2026-018):** stated in `registry/hypotheses.json`.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| T1 | A rule that always buys at the same session index has zero advantage | test |
| T2 | On a random walk with a strong upward drift, early-buying rules have no significant advantage | test |
| T3 | A planted dip on the first Monday of each month is still found by the Monday rule | test |
| T4 | On random walks no test passes | random-walk run |
| T5 | The run is logged once (`registry/capstone_test_runs.json`, kind `timing_matched`) with its commit | test and log |

## Non-goals

Same as specification 0029.

## Verification

| ID | Result | Evidence |
|---|---|---|
| T1–T5 | to do | |
