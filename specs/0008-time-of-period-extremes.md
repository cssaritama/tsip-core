# 0008 Time of the period's extremes

**Status:** ready for approval (criteria proposed on 2026-11-06; the study does not run on real data before the founder approves them)
**Level:** 2 study · **Open work:** W-63

## Problem and decision supported

Every month and quarter has an open, a high, a low and a close. If a market rises over time, a buyer wants to buy where and when the period's low is most likely to form. TSIP already shows which weekday forms the week's high and low. The trader's next questions: in which week (and which session of the month) does the month's low form, and the quarter's; how often is the low already in after the first week; and, given that the period has not yet made a new low after k sessions, how likely is it that the low is already in.

## Requirements

- R1. For each complete past month and quarter, the report shall record the session (as a share of the period, and as week of the month or month of the quarter) on which the period's low and high were made.
- R2. It shall compare those times with what the same market would show if the order of its days inside each period did not matter (control below), so that the familiar "lows form early" pattern, which drift and the arcsine law of random walks produce on their own, is not mistaken for a timing effect.
- R3. For the period in progress after k sessions: the share of past periods whose low (and high) was already set within the first k sessions, conditioned on whether the current low so far was made in the last session or earlier, against the same control.
- R4. Graded items: the difference between the observed and the control shares for the first week, the middle and the last week (month), and for each month (quarter), for the low and for the high.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| T1 | Ties (equal values on two sessions) take the first | test |
| T2 | On simulated random walks every graded difference is D or weaker | random-walk test |
| T3 | The control keeps each period's own daily returns and length and changes only their order | test |
| T4 | The board names the most likely window for the period's low with its grade, says "B at best with this history" where the test budget says so, and says when the pattern is no different from the control | render and browser check |
| T5 | A constructed series whose lows are placed on the first session of every month is graded A on the first-week item (NDX length) | test |

## Non-goals

- No entry rule; the figures describe past periods.
- No claim about accumulation, manipulation or distribution phases as such: only the timing of the extremes, which can be tested.

## Study protocol

- **Unit:** complete calendar month or quarter of sessions (exchange sessions for SPY, QQQ, NDX; UTC days for Bitcoin and Ether).
- **Outcome:** session index of the low and of the high, divided by the number of sessions. Windows: first week = first 5 sessions (crypto: 7 days), last week = last 5 sessions (crypto: 7 days), middle = the rest; quarter windows = its three months.
- **Price used (proposed):** closing prices for the graded items in every market, so that one definition holds everywhere, including NDX (close only); for SPY, QQQ, Bitcoin and Ether the day of the intraday low and high is shown beside it as context, not graded.
- **Control (proposed):** within each period, the period's own daily returns shuffled 10,000 times; the share of shuffles placing the extreme in each window is the expected share. This keeps the market's drift, volatility and fat tails and removes only the order of the days, so a difference means that *when* in the month the moves happen matters. A driftless random walk (the arcsine law) is shown as a second reference line.
- **Uncertainty:** circular block bootstrap over periods (month 6, quarter 4), most recent 30% held out.
- **Sample and test budget (specification 0009):** the histories from 2016 hold about 130 months and 43 quarters, so no item on them can reach grade A (200 units); they are graded B at best and shown as such. The graded monthly test that can reach A uses the NDX daily history from 1986 (about 490 months); quarters (163 on NDX) are B at best everywhere. Each market adds 3 month items (first week, middle, last week) and 3 quarter items (one per month) for the low, and as many for the high (12 tests), counted in the instrument's tests.
- **Hypothesis before the run (to be registered as H-2026-011 when approved):** on NDX, the share of months whose closing low falls in the first five sessions is within 3 percentage points of the shuffled control (no timing effect beyond drift); most of the "early low" pattern is drift plus the arcsine law. Expected grades: D or C on most items, B at most on one.

## Decisions for the founder

1. **Control:** shuffle each period's own days (proposed) or a plain random walk. The shuffle answers "does the timing matter beyond the fact that the market rises", which is the useful question for a buyer.
2. **Price:** closing prices graded everywhere, intraday lows as context (proposed), or intraday lows graded on the markets that have them.
3. **Windows:** first five sessions, middle, last five sessions (proposed), or calendar weeks of the month.
