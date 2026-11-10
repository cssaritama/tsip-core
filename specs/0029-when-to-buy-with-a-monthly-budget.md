# 0029 When and where to buy with a fixed monthly budget

**Status:** approved (founder request, 2026-11-10); protocol fixed before any figure; H-2026-017 registered before the run
**Level:** 2 study · **Open work:** W-124 · **Decisions:** ADR 0064, ADR 0067, ADR 0071

## Problem and decision supported

An investor puts the same amount into an instrument every month and wants to know on which session to buy. The founder's questions: is one weekday better, is the session after a strong fall better, are the sessions that move most better, is it better to buy when price reaches the nearest untested monthly, quarterly or half-year low, or the nearest fair value gap, or on the session of the month when the monthly low usually forms ("power of three")?

The specification 0028 test did not answer this: its pullback rule left money uninvested until the quarter's end, so it bought fewer units in a rising market (also noted in Q-23). Here every rule invests the same amount every month, so the only difference is the price paid.

## Requirements

- R1. **Unit:** one calendar month of one instrument. Instruments SPY, QQQ, GLD, BTC-USD and ETH-USD, daily bars of the course data store (specification 0028, step 1), each analysed on its own and never pooled across instruments.
- R2. **Budget:** one unit of money per month, invested in full within the month at the close of the session the rule selects. If the rule's trigger does not occur, the unit is invested at the close of the month's last session. Every rule therefore buys once a month and pays the same cost.
- R3. **Statistic:** the price advantage of a month, (average close of the month's sessions minus the rule's purchase price) divided by the average close. The average close is the exact expected price of a session drawn at random from the month, so the control has no simulation noise. Reported: mean advantage in percent, share of months with a positive advantage, and the effect on final wealth of buying every month for the whole period.
- R4. **Rules** (every level and indicator computed from data available at that session's close; ATR(14) as in specification 0028):
  - B1 **weekday:** the first Monday, Tuesday, Wednesday, Thursday or Friday of the month (crypto: also Saturday and Sunday);
  - B2 **after a strong fall:** the first session whose close-to-close fall is at least k ATR, k in {1, 1.5, 2}, buying at that close or at the next session's close;
  - B3 **sessions that move most:** the first session whose true range is at or above the 90th percentile of the previous 252 sessions;
  - B4 **nearest untested low:** the first session whose low comes within d ATR, d in {0.25, 0.5}, of the nearest untested low of the prior month, quarter or half-year (untested: not traded since that period closed);
  - B5 **fair value gap:** the first session whose low enters the nearest untested bullish daily gap below the close (a three-session gap with the third session's low above the first session's high);
  - B6 **day of the month of the monthly low:** the session-of-month index where the month's low formed most often in the development period;
  - B7 **below the month's open after the first week:** the first session after the fifth whose close is below the month's open;
  - references: the first session of the month (monthly buying) and the last session.
- R5. **No look-ahead:** a test deletes every session after t and checks that no rule's decision on t changes.

## Study protocol

- **Periods:** development (parameters chosen) up to 2015-12-31 for SPY, QQQ and GLD and up to 2019-12-31 for BTC and ETH; confirmation from the next month to the last complete month of the stored download. The years 2024 to 2026 were seen as prices in specification 0028, though not through these statistics; this is stated with the results. A forward record starts with the first month after the run.
- **Choices in development:** within each family, the variant with the highest mean advantage per instrument (B1 keeps all weekdays, because the question is which day is best). Choices are frozen in a committed file before the confirmation run.
- **Intervals:** circular block bootstrap over months (blocks of 6 months, 2,000 resamples).
- **Test budget (ADR 0067):** in development, 21 variants for each fund and 23 for each crypto instrument (weekends); in confirmation, B1's weekdays plus one variant of each of B2 to B7, by instrument: 11 tests per ETF and 13 per crypto instrument, 59 in total, with Benjamini–Hochberg at q 0.05 across all of them.
- **Random-walk check:** the whole pipeline on random-walk prices with each instrument's drift and volatility: no rule may pass.
- **Hypothesis before the run (H-2026-017):** stated in `registry/hypotheses.json`.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| T1 | No rule's decision on day t changes when every session after t is deleted | test |
| T2 | Every rule invests exactly one unit per month and never more than the money of the month | test |
| T3 | On a flat price the advantage of every rule is zero; on a series with a planted dip on the first Monday of each month, B1 Monday is found | test |
| T4 | On random walks no rule passes after the correction | random-walk run |
| T5 | Confirmation choices are committed before the confirmation run, which records its commit | test and log |

## Non-goals

- No advice on what or whether to buy; no published signals. Results are statistics with their grade.
- Intraday timing (which hour) and costs that differ between rules are out of this version.

## Verification

| ID | Result | Evidence |
|---|---|---|
| T1–T5 | to do | |
