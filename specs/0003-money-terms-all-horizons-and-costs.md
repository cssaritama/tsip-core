# 0003 Money terms: all horizons side by side, gross grades and cost profiles

**Status:** shipped (0.2.16), approved by the founder on 2026-11-05 · supersedes items 5 and 6 and the cost of 0001
**Level:** 2 study (change of graded items) · **Open work:** W-48 · **Decisions:** ADR 0065

## Problem and decision supported

Version 0.2.13 shows one horizon at a time behind a week, month and quarter switch, and grades "ended more than costs above the close" with one fixed cost per instrument kind (0.02% for ETFs, 0.20% for crypto). The founder could not tell which horizon to choose or what 0.20% meant, and the fee check of 2026-11-04 (`tsip-platform/docs/strategy/BENCHMARK_2026-11-04.md`) shows that one cost cannot be right for every reader: a round trip costs 0.20% on Binance but 1.20% on Coinbase Advanced and 1.60% on Kraken Pro at the lowest tier with market orders, and European ETF investors pay a fixed fee per order. Comparable products show forward horizons side by side and publish probabilities gross; trading tools let the user set costs.

## Requirements

- R1. The board shall show week, month and quarter side by side, each with the number of past periods it rests on and its yardstick (1 ATR at the start of the period, in percent), without a switch.
- R2. Graded items shall not depend on any cost assumption: "ended above the close" and "ended below the close" replace the cost-based items.
- R3. The report shall publish, for each horizon and for both groups (same state and other states), the share of past periods whose change to the period's end exceeded each of a fixed set of thresholds above and below the close, in ATR at the start of each period: 0 to 0.5 ATR in steps of 0.025, 0.55 to 1 ATR in steps of 0.05, then 1.25, 1.5, 1.75, 2, 2.5 and 3 ATR.
- R4. The page shall offer cost profiles, each with its source and date (crypto: Binance 0.20% and 0.15% with BNB, Coinbase Advanced 0.80% limit and 1.20% market, Kraken Pro 0.80% limit and 1.60% market; ETFs: an EU broker at EUR 1 per order on EUR 500, 1,000 or 5,000; for both: no costs, or the reader's own figure up to 3%), convert the chosen cost into ATR with each period's starting ATR, and show the share of past periods that ended beyond it, read from the published thresholds and labelled descriptive (not graded). The choice is remembered in the viewer's browser only.
- R5. Percentages shown next to ATR multiples shall be the multiple at the period's starting ATR, so that multiple times yardstick equals the percentage shown.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| B1 | No graded item uses a cost; the cost-based items are gone | test on the card items |
| B2 | Thresholds are published in ATR for both groups and both directions, the share at 0 equals the graded "ended above" share, and a change is compared with each period's own yardstick | tests |
| B3 | The random-walk test still gives no A or B | `test_money_random_walk_has_no_edge` |
| B4 | The board shows the three horizons in one table, without overlap or clipping at 390 to 1920 px; on a phone the table scrolls sideways inside the tile with the row labels in view | render check and a browser check |
| B5 | The cost selector lists each profile with its source and date, and a custom value; the shown share is the published share at the first threshold at or above the cost in ATR of the period | browser check against the report |
| B6 | The methodology and design documents describe the profiles and say that costs are descriptive | review |

## Non-goals

- No per-user grading of costs; grades stay on gross moves.
- No financing, taxes or slippage models.

## Data contract

Card `state.net_thresholds`: `{"atr": [0, 0.025, …, 3], "same": {"above": [...], "below": [...]}, "others": {"above": [...], "below": [...]}}`, 37 thresholds in ATR at the start of the period, shares in percent of past periods (`above`: change > threshold; `below`: change < −threshold). Items 5 and 6 become `end_up` = "Ended the {h} above the close" and `end_down` = "Ended the {h} below the close" (threshold 0). `cost_pct` leaves the card.

## Design notes

The first version of this specification (before publication) published thresholds in percent of price. Review of the page against the real report of 2026-11-05 showed why that is wrong for this study: the excursions are measured in ATR so that calm and volatile pasts are comparable, and a fixed percentage is easy to clear in a volatile past and hard in a calm present. In the report of 2026-11-05, Ether's ATR was 3.6% against a median of 5.7% since 2016 (12th percentile), so the share of past weeks beyond a 1.2% cost in percent would overstate what the same cost means today; QQQ's was 2.1% against a median of 1.4%, so for QQQ the error would run the other way. Converting the cost with the current period's own yardstick keeps the cost rows consistent with the rest of the tile. The first threshold at or above the cost is used, so a share never flatters the cost; the step of 0.025 ATR below 0.5 ATR, where costs fall, keeps that rounding small (0.03% for SPY, 0.09% for Ether at their ATR of 2026-11-05).

## Tasks

1. Change the study and its tests (B1–B3).
2. Board table and cost selector (B4, B5).
3. Documents (B6); approval of the cost profiles' sources by the founder.

## Verification

| ID | Result | Evidence |
|---|---|---|
| B1 | passed | `test_money_card_for_the_current_period`: no item label or state field mentions a cost |
| B2 | passed | same test: thresholds in ATR for both groups and sides, decreasing, and the 0 share equals the graded "ended above" and "ended below" shares; `test_net_thresholds_are_in_atr_of_each_period`: two weeks with the same percent change count differently against the same ATR threshold |
| B3 | passed | `test_money_random_walk_has_no_edge` |
| B4 | passed | render check at 390 to 1920 px on the published report of 2026-11-05 02:53 UTC and on a synthetic 0.2.16 report: no overlap, no clipped tile, no horizontal page scroll; browser check at 390 px: after scrolling the table 200 px the row labels stay at the tile's edge, in both colour schemes |
| B5 | passed | browser check on the synthetic 0.2.16 report: Coinbase Advanced taker, Kraken Pro taker, Binance with BNB and a custom 0.33% on Bitcoin, and a custom 3% on SPY, each reading the expected published share and threshold for every horizon; the choice is remembered after a reload; ETFs list the EU broker profiles |
| B6 | passed | `docs/METHODOLOGY.md` and `docs/DESIGN.md` updated |
