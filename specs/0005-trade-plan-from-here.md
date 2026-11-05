# 0005 Trade plan from here

**Status:** approved by the founder on 2026-11-05 (ADR 0066); acceptance criteria to be reviewed at delivery; not yet run on real data
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

New cards `{code}.plan.{week|month}`, family `plan`, kind `edge`, unit `ATR`, in a new section "Trade plan from here". Items in order: long to the period's end, long 1:1, long 1:2, short to the period's end, short 1:1, short 1:2. Each item: `observed` (average result in ATR, same state), `baseline` (all periods), `estimate` (difference), and in `extra`: target-first, stop-first and neither shares and the quartiles of the result for both groups. Card `state`: horizon, period, sessions elapsed, state flags, ATR at the start of the period, counts for the same state and all periods.

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

Stops and targets of 1 and 2 ATR match the thresholds of the money study, keep the number of tests small (six per card) and are easy to translate into prices on the trader's platform. The conservative rule for bars that reach both levels biases results against the plans; the bias is the same for the state and for all periods, so it does not create a difference.

## Tasks

1. Path and plan outcomes from intraday bars, with tests (E1–E3).
2. Card, grading and random-walk test (E4).
3. Board tile with the cost applied, finding and documents (E5, E6).
4. Forward evaluation of H-2026-007 and H-2026-008 in the track record (E7, W-35).

## Verification

To be filled at delivery.
