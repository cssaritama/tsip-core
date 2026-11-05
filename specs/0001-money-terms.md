# 0001 Money terms: from here to the end of the period

**Status:** shipped (0.2.13); items 5 and 6, the cost assumption and the horizon switch superseded by `0003` in 0.2.16; the control (the complement) superseded by `0006` in 0.2.17
**Level:** 2 study · **Open work:** W-07, W-43 · **Decisions:** ADR 0064 (way of working)

## Problem and decision supported

The board says how far a market moves, when, where it stands and which levels are in reach, but not what can be made or lost from the current point. A trader sizing a stop or a target needs to know how far price travelled above and below the close, and where it ended, in past periods that stood in the same place at the same point in time, and whether that differs from what happens anyway.

## Requirements

- R1. For each period in progress (week, month, quarter), the report shall describe, for past complete periods observed after the same number of sessions and in the same state (prior high traded or not, prior low traded or not), the excursion above and below the close of that session and the change to the period's last close.
- R2. Excursions shall be measured in percent and in multiples of the 14-session ATR known at the start of the period, so that the current period's own moves do not change the yardstick.
- R3. The report shall grade, against other periods at the same point, the share that travelled at least 1 and 2 ATR above and below the close, and the share that ended more than a round-trip cost above or below it.
- R4. The round-trip cost shall be an explicit, published assumption per instrument kind.
- R5. The page shall answer "What can be made or lost from here?" on the board with one figure, one visual against its control and the grades, and link to the full finding.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| A1 | Excursions and the final change are computed from the session after the observation point to the period's last session only; the current period never enters its own analogs | `test_money_events_use_only_the_forward_window` |
| A2 | The ATR yardstick is the value at the last session of the prior period | `test_money_events_use_only_the_forward_window` |
| A3 | On a simulated random walk, no item is graded A or B | `test_money_random_walk_has_no_edge` |
| A4 | Each card carries six items, observed against other periods at the same point, and the medians and quartiles of the excursions for both groups | `test_money_card_for_the_current_period` |
| A5 | A report with OHLC and close-only instruments serialises without non-finite numbers; close-only series produce no money card | `test_money_skips_close_only_series` and the pre-release report check |
| A6 | The board tile shows the typical move above and below in ATR and percent, the four threshold shares with their controls and grades, and links to the finding; it is absent when no period is in progress | Render check at 1440 and 390 px; founder review (product review screen 6) |

## Non-goals

- No entry or exit rule, no position sizing and no advice. The figures describe past periods.
- No intraday entry point: the observation point is the close of the latest complete session.
- No costs beyond one round trip (no financing, borrowing, taxes or slippage beyond the assumption).

## Data contract

New cards `{code}.money.{week|month|quarter}`, family `money`, kind `edge`, unit `pp`, in the new section `money` ("From here to the period's end"). Items, in order:

1. Reached 1 ATR above the close before the period ended
2. Reached 1 ATR below the close before the period ended
3. Reached 2 ATR above the close
4. Reached 2 ATR below the close
5. Ended more than costs above the close
6. Ended more than costs below the close

Each item: `observed` (share of analogs in the same state, %), `baseline` (share of other periods at the same point, %), `estimate` (difference, pts). Card `state`: horizon, period, sessions elapsed, typical sessions, state flags, ATR at the start of the period (`atr_start_pct`), round-trip cost (`cost_pct`), analog counts (`analogs`, `others`), and `excursions` with the median and quartiles of `up_atr`, `down_atr`, `net_atr`, `up_pct`, `down_pct`, `net_pct` for `same` and `others`.

## Study protocol

- **Unit:** one complete period that follows a complete period and lasts more than k sessions, where k is the number of sessions of the current period so far.
- **State at k:** whether the prior period's high and low have been traded in the first k sessions (the same states as "Where we are now").
- **Outcomes:** from session k + 1 to the period's last session: maximum high and minimum low against the close of session k, and the last close against it, divided by the ATR at the start of the period.
- **Control:** periods at the same point in a different state (the complement). Statistic: share in the state minus share in the complement, per item.
- **Uncertainty:** circular block bootstrap over periods (week 8, month 6, quarter 4), most recent 30% held out, Benjamini–Hochberg across the report.
- **Expected under a random walk:** zero for every item, because the state carries no information about future increments and the yardstick is fixed before the state is observed.
- **Costs:** 0.02% round trip for ETFs and 0.20% for crypto, published with the card.

## Design notes

The ATR at the start of the period is used instead of today's ATR because the state itself depends on the current period's ranges: a period that has already traded through both prior extremes has wider recent ranges, so dividing by today's ATR would shrink its excursions mechanically and fake an effect. The board shows the yardstick in percent next to every ATR figure.

## Tasks

1. Study `tsip.studies.money` with events, card and tests (A1–A5).
2. Section, headline and report wiring.
3. Board tile and finding rendering (A6).
4. Methodology, design, changelog.

## Verification

| ID | Result | Evidence |
|---|---|---|
| A1 | passed | `tests/test_money.py` |
| A2 | passed | `tests/test_money.py` |
| A3 | passed | `tests/test_money.py` (two simulated markets, no A or B) |
| A4 | passed | `tests/test_money.py` |
| A5 | passed | `tests/test_money.py`; pre-release report with OHLC and close-only instruments serialised with `allow_nan=False` |
| A6 | passed on a synthetic report built by 0.2.13 (render check at 390 to 1920 px, both schemes); real values with the first 0.2.13 run; founder review pending | `tools/render_check.py`, screenshots of 2026-11-04 |
