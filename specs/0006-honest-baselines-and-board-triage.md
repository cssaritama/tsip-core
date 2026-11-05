# 0006 Honest baselines and board triage

**Status:** shipped (0.2.17), approved by the founder on 2026-11-05 (ADR 0066)
**Level:** 2 study (change of the money control) and 1 feature (board) · **Open work:** W-54, W-55 · **Decisions:** ADR 0066

## Problem and decision supported

The review of 2026-11-05 (`tsip-platform/docs/reviews/DECISION_READINESS_2026-11-05.md`) found three things that weaken the board as a decision tool:

1. The money tile compares periods in today's state with the periods in the other states. A trader reads the comparison line as "what normally happens", but it is the opposite group: for SPY, where the two groups are about the same size, every difference looks about twice as large as against all periods at the same point (ended the week above the close: 63.8% against 52.4% for the other weeks, but 58.2% for all weeks).
2. Every cell carries the same weight. The month and quarter columns are mostly "no reliable difference" or "too little history", and the board has no line that says what applies today.
3. With no cost chosen, the two cost rows repeat the graded rows.

The decision supported is the same as before (timing, stop and target sizes, levels in reach); this change makes the figures honest in size and puts the few that are graded first.

## Requirements

- R1. Money cards shall compare the past periods in the same state with all past periods at the same point (the same state and every other state together). The comparison figure (`baseline`) is the share over all periods; the difference (`estimate`), its interval, holdout and grade come from the same block bootstrap of that difference.
- R2. Money cards shall publish the number of all periods at the same point, and the excursion summaries and cost thresholds for all periods, besides those for the same state and the other states.
- R3. The board shall open with a "Today" panel of at most three facts that apply to the current position, each with its figure, its grade (or "measured, not graded" for a measurement) and a link to the tile it comes from: the strongest A item of the money cards for the periods in progress (week first); the size of the current or next slot of the clock when it is graded A; and the volatility regime (ATR and its percentile). Only strong evidence leads the board: a B can rest on one half of the history (the Ether week of 2026-11-05). When no A applies, the panel says so.
- R4. In the money table, every horizon after the first that has no item graded A, B or C shall be folded into one line naming it and the reason ("no reliable difference" or "too little history to grade"), with a control that shows the folded columns.
- R5. The two cost rows shall be shown only when a cost above zero is chosen.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| D1 | Baseline is the share over all periods at the same point (the analog-weighted mean of the same and other states), the estimate is the observed share minus it, and the count of all periods equals analogs plus others | test |
| D2 | On simulated random walks no money item is graded A or B | `test_money_random_walk_has_no_edge` |
| D3 | Excursions and thresholds are published for the same state, the other states and all periods; the 0 ATR share for all periods equals the graded baseline of "ended above" | test |
| D4 | The Today panel shows one to three facts, every graded one A, each linking to an existing tile; with no A it shows the fallback line | browser check on the live and on a synthetic report |
| D5 | With the live report of 2026-11-05, SPY shows the week and folds the month and the quarter with their reasons; the control shows them; a market whose week is all D still shows the week | browser check |
| D6 | With "No costs" the cost rows are absent; after choosing a profile they appear with the shares beyond it | browser check |
| D7 | No overlap, clipped tile or horizontal scroll at 390 to 1920 px in both colour schemes | `tools/render_check.py` |
| D8 | Methodology and design documents describe the control and the panel | review |

## Non-goals

- Calendar studies keep comparing a day or month with the others: the comparison group is four of five days or eleven of twelve months, so the difference against all days is 80% to 92% of the figure shown, and the convention is standard in that literature.
- No new graded items.

## Data contract

Money card `state`: new `all_periods` (count), `excursions.all`, `net_thresholds.all` (`above`, `below`). Items: `baseline` is the share over all periods; `estimate` is `observed − baseline`. `contrast` becomes "all {horizon}s at the same point". Existing `others`, `excursions.others` and `net_thresholds.others` remain.

## Study protocol (change)

- **Control:** all periods at the same point (previously: the complement). Statistic: share in the state minus share over all periods. Testing the state against the complement and against the pooled periods examines the same null hypothesis (the state carries no information); the estimate shrinks by the share of the complement in the pool, which is what a reader should see.
- **Random-walk expectation:** zero for every item; unchanged.

## Tasks

1. Study, tests and headline wording (D1–D3).
2. Board: Today panel, folded horizons, cost rows on demand (D4–D7).
3. Methodology and design (D8).

## Verification

| ID | Result | Evidence |
|---|---|---|
| D1 | passed | `test_money_card_for_the_current_period`: all periods = analogs + others, the baseline equals the analog-weighted share of both groups, every estimate equals observed minus baseline, and the contrast reads "all weeks at the same point" |
| D2 | passed | `test_money_random_walk_has_no_edge` |
| D3 | passed | same test: thresholds for the same state, the other states and all periods, decreasing, and the 0 ATR share for all periods equals the graded baseline |
| D4 | passed | browser check on the live report of 2026-11-05 09:02 UTC: SPY shows three facts (the week's A, the A of the next half-hour, the ATR as a measurement); QQQ, Bitcoin and Ether two, because their week has no A (QQQ and Ether have B); every link resolves to a tile; on a synthetic random-walk report the fallback line appears |
| D5 | passed | same check: SPY folds the month ("no reliable difference", 61 past months) and the quarter ("too little history to grade", 29 past quarters); the control shows and hides them; Bitcoin keeps its week, all D |
| D6 | passed | same check: no cost rows with "No costs"; two rows after choosing a profile; none again after returning to "No costs" |
| D7 | passed | render check at 390 to 1920 px, both schemes, on the live report and on a synthetic 0.2.17 report: no overlap, clipped tile or horizontal scroll |
| D8 | passed | `docs/METHODOLOGY.md` and `docs/DESIGN.md` updated |
