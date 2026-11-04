# 0003 Money terms: all horizons side by side, gross grades and cost profiles

**Status:** draft, for the founder's approval · supersedes part of 0001 when shipped
**Level:** 2 study (change of graded items) · **Open work:** W-48 · **Decisions:** ADR 0065 (proposed)

## Problem and decision supported

Version 0.2.13 shows one horizon at a time behind a week, month and quarter switch, and grades "ended more than costs above the close" with one fixed cost per instrument kind (0.02% for ETFs, 0.20% for crypto). The founder could not tell which horizon to choose or what 0.20% meant, and the fee check of 2026-11-04 (`tsip-platform/docs/strategy/BENCHMARK_2026-11-04.md`) shows that one cost cannot be right for every reader: a round trip costs 0.20% on Binance but 1.20% on Coinbase Advanced and 1.60% on Kraken Pro at the lowest tier with market orders, and European ETF investors pay a fixed fee per order. Comparable products show forward horizons side by side and publish probabilities gross; trading tools let the user set costs.

## Requirements

- R1. The board shall show week, month and quarter side by side, each with the number of past periods it rests on, without a switch.
- R2. Graded items shall not depend on any cost assumption: "ended above the close" and "ended below the close" replace the cost-based items.
- R3. The report shall publish, for each horizon and for both groups (same state and other states), the share of past periods whose change to the period's end exceeded each of a fixed set of thresholds above and below the close: 0, 0.1, 0.2, 0.5, 1.0, 1.5, 2.0 and 3.0%.
- R4. The page shall offer cost profiles, each with its source and date (Binance 0.20%, Coinbase Advanced 1.20%, Kraken Pro 1.60%, EU broker EUR 2 per round trip on a chosen order size, US zero-commission broker, custom), and show the share of past periods that ended beyond the chosen cost, read from the published thresholds and labelled descriptive (not graded). The choice is remembered in the viewer's browser only.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| B1 | No graded item uses a cost; the cost-based items are gone | test on the card items |
| B2 | Thresholds are published for both groups and both directions, and the share at 0% equals the graded "ended above" share | test |
| B3 | The random-walk test still gives no A or B | `test_money_random_walk_has_no_edge` |
| B4 | The board shows the three horizons in one table at 1440 px and stacked at 390 px, with no overlap | render check |
| B5 | The cost selector lists each profile with its source and date, and a custom value; the shown share is the published share at the nearest threshold not below the cost | render check and a test of the lookup |
| B6 | The methodology and design documents describe the profiles and say that costs are descriptive | review |

## Non-goals

- No per-user grading of costs; grades stay on gross moves.
- No financing, taxes or slippage models.

## Data contract

Card `state.net_thresholds`: `{"pct": [0, 0.1, 0.2, 0.5, 1, 1.5, 2, 3], "same": {"above": [...], "below": [...]}, "others": {"above": [...], "below": [...]}}` in percent of past periods. Items 5 and 6 become `end_up` = "Ended the {h} above the close" and `end_down` = "Ended the {h} below the close" (threshold 0). `cost_pct` leaves the card.

## Tasks

1. Change the study and its tests (B1–B3).
2. Board table and cost selector (B4, B5).
3. Documents (B6); approval of the cost profiles' sources by the founder.

## Verification

To be filled at delivery.
