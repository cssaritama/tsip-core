# 0005 Trade plan from here

**Status:** shipped (0.2.18), approved by the founder on 2026-11-05 (ADR 0066); first real results with the first 0.2.18 report, independent review to follow
**Level:** 2 study · **Open work:** W-56 · **Decisions:** ADR 0066

## Problem and decision supported

The board describes how far and when price has moved from situations like today's, but not the result of a trade taken from here. A trader deciding whether to act needs, for a simple plan with a stop and a target, how often the target came first, how often the stop came first, and the average result, against what happens anyway, after his own costs. Costs decide small edges, which is why they belong here rather than on the money tile (`tsip-platform/docs/reviews/DECISION_READINESS_2026-11-05.md`).

## Requirements

- R1. For each period in progress (week and month), from the close of the latest complete session k, the report shall evaluate six plans: long and short, each held to the period's last close, with a stop at 1 ATR and a target at 1 ATR, and with a stop at 1 ATR and a target at 2 ATR. The ATR is the 14-session ATR at the start of the period, the yardstick of the money study.
- R2. For each plan, the report shall give the share of past periods in which the target came first, the stop came first, or neither (exit at the period's last close), and the average and quartiles of the result in ATR, for the periods in the same state and for all periods at the same point.
- R3. The graded items shall be the average result of each plan, in the same state minus all periods (six items per card). The shares are descriptive.
- R4. The order of stop and target shall be resolved with intraday bars (30 minutes for SPY and QQQ, one hour for crypto). A bar that reaches both counts as the stop. A session that opens beyond a level fills at the open, not at the level.
- R5. The page shall subtract the reader's round-trip cost, converted into ATR of the period, from the average results, and label the net figures descriptive. Grades use gross results only.
- R6. Under a random walk without drift every average result is zero gross; no item may be graded A or B on simulated random walks.
- R7. One trading cost applies to the whole board, chosen once at its top and kept in the viewer's browser only. When a plan item is graded A, the Today panel shows it before the money fact.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| E1 | Only bars after the close of session k enter the path; the current period never enters its own analogs | test with a constructed path |
| E2 | A bar touching stop and target counts as the stop; a gap through a level fills at the open | tests |
| E3 | Target-first, stop-first and neither shares add up to 100% for every plan and group | test |
| E4 | No A or B on simulated random walks, long and short | random-walk test |
| E5 | Net result equals gross minus the cost in ATR of the period; shown as descriptive | browser check |
| E6 | Board and finding render at 390 to 1920 px without overlap or clipping | render check |
| E7 | The pre-registered hypotheses H-2026-007 and H-2026-008 are evaluated forward from their evaluation start, not on the history used to propose them | registry review |

## Non-goals

- No advice, entry signal, position sizing or order; the figures describe past periods.
- No financing, borrowing cost for shorts, taxes or slippage beyond the reader's round-trip cost.
- No quarter: too few periods in the same state to grade.
- No live entry: the starting point is the latest complete session's close.

## Data contract

New cards `{code}.plan.{week|month}`, family `plan`, kind `edge`, unit `ATR`, in a new section "Trade plan from here". Items in order (`extra.plan`): `long_hold`, `long_1_1`, `long_1_2`, `short_hold`, `short_1_1`, `short_1_2`. Each item: `observed` (average result in ATR, same state), `baseline` (all periods), `estimate` (difference), and `extra.same` and `extra.all` with `target_first`, `stop_first`, `neither` and `win` (shares in percent) and `q1`, `median`, `q3` of the result in ATR. Card `state`: horizon, period, sessions elapsed, typical sessions, session unit, state flags, `atr_start_pct`, `stop_atr`, `analogs`, `all_periods`, `path_from` (first intraday date) and `as_of`. Cards without analogs in today's state are not published.

## Study protocol

- **Unit:** one complete past period that follows a complete period and lasts more than k sessions.
- **State at k:** prior period's high and low traded or not in the first k sessions (as in the money study).
- **Path:** intraday bars from the first bar after the close of session k to the period's last bar.
- **Outcome per plan:** result in ATR of the start of the period: +target or −stop at the first level reached (stop on a bar that reaches both; at the open on a gap), otherwise the change to the period's last close.
- **Control:** all periods at the same point. Statistic: average result in the state minus the average over all periods.
- **Uncertainty:** circular block bootstrap over periods (week 8, month 6), most recent 30% held out, Benjamini–Hochberg across the market's report.
- **Expected under a random walk:** zero for every plan, long and short.
- **Pre-registration:** H-2026-007 (SPY, long to the week's end after an early break of the prior week's high) and H-2026-008 (SPY, fewer such weeks reach 1 ATR below), registered 2026-11-05 from the money result seen that day and evaluated on weeks from 2026-11-09.

## Design notes

Stops and targets of 1 and 2 ATR match the thresholds of the money study, keep the number of tests small (six per card) and are easy to translate into prices on the trader's platform. The conservative rule for bars that reach both levels biases results against the plans; the bias is the same for the state and for all periods, so it does not create a difference. A long and a short held to the period's end are exact opposites, and the two 1:1 plans nearly so; both sides are shown because a reader asks the question for one side, at the cost of a few extra tests in the multiple-testing adjustment. The cost selector moves from the money tile to the top of the board, so that one cost applies to the plan, where it decides small edges, and to the money table's cost rows.

## Tasks

1. Path and plan outcomes from intraday bars, with tests (E1–E3).
2. Card, grading and random-walk test (E4).
3. Board tile with the cost applied, finding and documents (E5, E6).
4. Forward evaluation of H-2026-007 and H-2026-008 in the track record (E7, W-35).

## Verification

| ID | Result | Evidence |
|---|---|---|
| E1 | passed | `test_plan_events_use_only_bars_after_the_observation_point`: a dip on the observation day does not stop the long; the target reached two days later counts |
| E2 | passed | `test_bracket_counts_a_bar_reaching_both_levels_as_the_stop`, `test_bracket_gaps_fill_at_the_open_and_order_is_respected` |
| E3 | passed | `test_plan_card_compares_with_all_periods`: shares add up to 100 for every plan and group; estimate equals observed minus baseline; long and short held are opposites |
| E4 | passed | `test_plan_random_walk_has_no_edge`: hourly and 30-minute random walks, week and month cards, no A or B |
| E5 | passed | browser check on a synthetic 0.2.18 report: with a cost of 0.40% on SPY (0.21 ATR) and 1.60% on Bitcoin (0.25 ATR) every "after cost" figure equals the gross result minus the cost in ATR; no figure without a cost; a custom cost is kept after a reload |
| E6 | passed | render check at 390 to 1920 px, both schemes, on the synthetic 0.2.18 report and on the live report of 2026-11-05 10:06 UTC |
| E7 | open | H-2026-007 and H-2026-008 are evaluated from 2026-11-09 by the track record (W-35) |
