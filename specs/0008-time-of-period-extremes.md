# 0008 Time of the period's extremes

**Status:** draft; the problem was asked for by the founder on 2026-11-05 (power of three: where and when the month's low forms); criteria to be reviewed before the study runs on real data
**Level:** 2 study · **Open work:** W-63

## Problem and decision supported

Every month and quarter has an open, a high, a low and a close. If a market rises over time, a buyer wants to buy where and when the period's low is most likely to form. TSIP already shows which weekday forms the week's high and low. The trader's next questions: in which week (and which session of the month) does the month's low form, and the quarter's; how often is the low already in after the first week; and, given that the period has not yet made a new low after k sessions, how likely is it that the low is already in.

## Requirements

- R1. For each complete past month and quarter, the report shall record the session (as a share of the period, and as week of the month or month of the quarter) on which the period's low and high were made.
- R2. It shall give the distribution of those times against the distribution expected under a random walk with the same number of sessions (the arcsine law: extremes of a random walk fall near the start and the end more often than in the middle), so that the familiar "lows form early" pattern is not mistaken for an effect.
- R3. For the period in progress after k sessions: the share of past periods whose low (and high) was already set within the first k sessions, conditioned on whether the current low so far was made in the last session or earlier, against the random-walk expectation.
- R4. Graded items: the difference between the observed and the random-walk shares for the first week, the middle and the last week (month), and for each month (quarter).

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| T1 | Ties (equal lows on two sessions) take the first | test |
| T2 | On simulated random walks every graded difference is D or weaker | random-walk test |
| T3 | The random-walk reference is simulated with the same period lengths as the real data | test |
| T4 | The board names the most likely window for the period's low with its grade, and says when the pattern is no different from a random walk | render and browser check |

## Non-goals

- No entry rule; the figures describe past periods.
- No claim about accumulation, manipulation or distribution phases as such: only the timing of the extremes, which can be tested.

## Study protocol

- **Unit:** complete month or quarter after a complete one.
- **Outcome:** session index of the low and of the high, divided by the number of sessions.
- **Control:** the same quantities for random walks with each period's length (10,000 simulated periods per length), not the other periods.
- **Uncertainty:** circular block bootstrap over periods (month 6, quarter 4), most recent 30% held out.
- **Hypothesis before the run:** for SPY, months' lows fall in the first week more often than a random walk would place them only by a small margin; most of the "early low" pattern is the arcsine law.
