# 0010 Revisit of Monday's low and of the recent lows

**Status:** shipped in 0.2.23 with the recommended options (before the week ends plus 5 and 10 sessions; the lows of the last three complete weeks and months; reached when a session's low trades at or below the level), taken when the founder asked to continue on 2026-11-06; hypothesis H-2026-014 registered before the first run on real data
**Level:** 2 study · **Open work:** W-72

## Problem and decision supported

The founder's thesis (2026-11-05): when the market rises without touching its lows, sooner or later it comes back, at least to Monday's low or to one of the last three lows of the prior week or month. If that holds, a buyer can wait for the return to a known level instead of chasing, and a seller can expect the pull-back. TSIP already measures how soon a prior week's, month's and quarter's low is revisited against equally distant arbitrary levels (`revisit`); it does not measure Monday's low within the week or the recent lows as a group.

## Requirements

- R1. **Monday's low.** For each week, at the close of Tuesday, Wednesday and Thursday (crypto: at the close of each day from Tuesday to Saturday), if price has not traded at or below Monday's low since Monday, record whether it does so before the week ends, and within the next 5 and 10 sessions.
- R2. **The last three lows.** At each period close (week, month), take the lows of the last three complete periods (the one just closed and the two before); record whether price trades at or below the nearest of them below the close, and the lowest of the three (when all three are below the close), within 5, 10 and 20 sessions (weeks) or 10, 20 and 60 sessions (months). Reaching any of them is the same as reaching the nearest.
- R3. Each rate is compared with the same control as the revisit study: from any other close in the same history, how often price reached a level at the same volatility-scaled distance on the same side within the same number of sessions. The graded difference is what the real level adds beyond distance, volatility, drift and the shape of returns.
- R4. The board shows, for today's week, whether Monday's low is still untested, its distance in ATR, the observed and control rates of a return before the week ends, and the grade.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| T1 | A week whose Monday low is traded on Monday itself after the low is set counts from Tuesday only; the event uses only data up to its close | test |
| T2 | On simulated random walks every graded difference is D or weaker | random-walk test |
| T3 | Rates within k sessions use only events with k sessions of data after them | test |
| T4 | A constructed series that always returns to Monday's low on Friday, at a distance where arbitrary levels are rarely reached, is graded A on daily-length history | test |
| T5 | The board states the rate, the control and the grade, and says when the real level adds nothing beyond distance | render and browser check |

## Non-goals

- No entry rule. The figures describe how often and how soon price came back, not whether buying there paid.
- No claim about "liquidity" as such: only revisits, which can be tested.

## Study protocol

- **Units:** week-days after Monday (R1) and period closes (R2); overlapping windows, so the circular block bootstrap uses 8 weeks (weeks) and 6 months (months).
- **Outcome:** reached or not within the window; median time to reach with censoring, as in the revisit study.
- **Control:** distance-matched arbitrary levels (above).
- **Test budget (specification 0009):** R1 adds 3 graded items per market (end of week, 5 and 10 sessions, each pooled over the observation days), R2 adds 6 (nearest and lowest, three windows) per horizon: 15 tests per market. Weeks give about 560 units on the 2016 histories, so A is reachable for R1 and for R2 on weeks; R2 on months (130 units) is B at best.
- **Hypothesis before the run (to be registered when approved):** Monday's low, when untested by Tuesday's close, is reached before the week ends in roughly 40 to 55% of weeks on SPY; the control gives nearly the same share, so the real level adds little beyond distance (difference within 5 points, grade C or weaker).

## Decisions (recommended options taken)

1. **Window for Monday's low:** before the week ends (recommended: it is the question as asked) plus 5 and 10 sessions as context, or only fixed windows.
2. **"The last three lows":** the lows of the last three complete weeks and months (recommended: fixed, comparable across markets), or the three lowest daily lows of the prior week.
3. **"Reached":** the session's low at or below the level (recommended, as in the revisit study), or a close below it.

## Verification

| ID | Result | Evidence |
|---|---|---|
| T1 | pass | `tests/test_recent_lows.py::test_monday_events_start_on_tuesday_and_stop_once_tested` |
| T2 | pass | `tests/test_recent_lows.py::test_random_walk_has_no_edge` (15 items, none A or B) |
| T3 | pass | `tests/test_recent_lows.py::test_windows_only_count_when_fully_observed` |
| T4 | pass | `tests/test_recent_lows.py::test_planted_return_to_monday_low_is_found` (A) |
| T5 | pass | render check, 0 problems on a labelled preview; the Day of the week coordinate shows Monday's low when untested, with the observed and control rates and the grade |
