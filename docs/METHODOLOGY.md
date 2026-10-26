# Methodology

Version **2026.10.1** of the grading rules. Any change to the rules increments the version, which is printed in every report.

## 1. Units of observation

Every study reduces bars to time-ordered **units**: days, weeks, months or events. Bitcoin days are UTC calendar days built from 24 hourly bars; incomplete days are dropped. S&P 500 and Nasdaq-100 ETF days (SPY, QQQ) are regular-trading-hours sessions (09:30–16:00 New York time) built from 30-minute bars; half-day sessions are kept for daily statistics and excluded from time-of-day statistics. Index days (SPX, NDX) come from a long daily history and are used for prior-period levels and calendar questions.

Calendar periods are weeks (Monday to Sunday), months, quarters, half-years (January–June and July–December) and years. A period is used only if it is complete: it needs a minimum number of sessions (exchange-traded instruments: 4, 15, 55, 110 and 220; Bitcoin: 7, 28, 89, 180 and 360 days), the first period in the data must start on time, and the last one must have ended. A period still in progress never enters a base rate.

## 2. Two kinds of statistics

| Kind | Question | Graded on |
|---|---|---|
| **Edge** | Is X different from a control or a null? | Evidence, A–F |
| **Base rate** | How often does X happen? | Reliability, A–D |

## 3. Uncertainty

Intervals are 95% percentile intervals from a **circular block bootstrap** (1,000 replicates by default). Blocks preserve short-range dependence: 10 days for intraday studies, 20 days for daily studies, 8 weeks for weekly studies and events, 6 months for monthly studies, 4 quarters for quarterly studies, 2 half-years or 2 years for the longest horizons, 3 months for month-of-year studies.

For proportions, the reported interval is never narrower than the Wilson score interval. A percentile bootstrap collapses to zero width when every unit has the same outcome (for example 0 of 38), which would make a small sample look precise.

The p-value of an edge uses the shift method: the bootstrap distribution is centred and compared with the distance between the estimate and the null.

## 4. Out-of-sample check

Units are split in time order: the first 70% (discovery) and the most recent 30% (holdout). The estimate is reported on both. The holdout is also bootstrapped on its own to obtain a holdout p-value.

The split is descriptive, not a pre-registered test, because the full history is visible when the report is computed. Genuine out-of-sample evidence comes from the [hypothesis register](#8-hypothesis-register).

## 5. Multiple testing

Every edge item in an instrument report (every hour, weekday, session, horizon) is one test. q-values are computed across all of them with the Benjamini–Hochberg procedure, so the expected share of false discoveries among A and B grades is controlled at 5–10%.

## 6. Grades

**Edges**

| Grade | Rule |
|---|---|
| A · Strong | q ≤ 0.05; discovery and holdout share the estimate's sign; holdout p ≤ 0.10; at least 200 units |
| B · Moderate | q ≤ 0.10; discovery and holdout share the sign |
| C · Weak | p ≤ 0.05 and the holdout agrees, but q > 0.10 |
| D · Inconclusive | Not significant and not contradicted |
| F · Contradicted | p ≤ 0.10 but discovery and holdout disagree in sign |
| N/A | Fewer than 30 units |

**Base rates**

| Grade | 95% interval half-width | Discovery vs. holdout |
|---|---|---|
| A | ≤ 2.5 pp | ≤ 3 pp |
| B | ≤ 4 pp | ≤ 6 pp |
| C | ≤ 7.5 pp | ≤ 10 pp |
| D | wider | larger |

## 7. Controls

### Random-walk baseline for timing questions

*Where does the daily high form? Which weekday sets the weekly low?* In a random walk, extremes are much more likely at the start and end of a period (the arcsine law), so a raw distribution of "time of high" is uninformative by itself. Each period's bars are randomly reordered 200 times. Every bar keeps its own return and its high and low relative to its reference. The share of periods whose extreme falls in each window under reordering is the baseline. The edge is the observed share minus the baseline.

### Geometry-matched levels for price-level questions

*When price closes back inside last week's range, which side breaks first?* A close near the top of a range reaches the top first more often for mechanical reasons. For every event, 20 control bands of the same width are placed around the same close. Their relative positions are drawn symmetrically within ±10% of the range around the event's own position; the window narrows near the edges so that it stays symmetric. All bands follow the same future path. The edge is the event's upper-first rate minus the controls' rate.

Monte Carlo checks: 60 simulated random walks with and without drift give a mean edge of −0.03 pp (s.e. 0.09) and −0.01 pp (s.e. 0.10); 60 drifting 44-year daily histories with realistic ranges give −0.10 pp (s.e. 0.04) at 5 sessions and +0.10 pp (s.e. 0.04) at 10 sessions. The control is unbiased to within about 0.1 pp, and across 80 null histories the p-value fell below 0.05 in 6% of cases. An earlier design that drew control positions only between 10% and 90% and compared events by position bins overstated the edge by about 3 pp. Events close to an edge, which are common right after price re-enters a range, were compared with controls further from that edge.

Outcomes: `upper` and `lower` (an open beyond a level resolves the order at the open: a gap, not a fill), `ambiguous` (both levels inside one daily bar from an inside open; the order is unknown without intraday data) and `none`. Events whose horizon is incomplete or crosses a data gap are excluded.

### Where we are now: analog base rates

For each horizon, the period in progress (if any) is described by its state after *k* sessions: whether it has already traded above the prior period's high and below its low, and where the latest close sits against the prior range. Analogs are past complete periods, each following a complete period, observed after the same *k* sessions and in the same state. The card reports what happened to the analogs by the end of their period: how often they traded through the untouched level, and where they closed. Intervals come from a block bootstrap over analogs. Only data available at the latest bar is used, the period in progress is never its own analog, and price levels are not published.

These are conditional base rates, not forecasts. Each card shows how many analogs exist; long horizons often have too few to grade.

### Long daily histories

Index histories from the early decades often repeat the close as the day's high and low, or as the next open. A calendar month fails the range check if fewer than 95% of its days have a high above the low, and the open check if more than half of its opens equal the prior close. Level studies start after the last month that fails the range check; gap and open-based studies (first passage, entry timing, overnight returns) start after the last month that fails either check. The dates are printed with each instrument.

### Entry timing

The baseline buys at the first session's open every month. The rule places a limit order at the prior month's low at the start of the month. It fills at the limit, or at the open if the session opens below it. If it never fills, it buys at the month's last close. Only information available before the order is used.

## 8. Hypothesis register

`registry/hypotheses.json` holds statements written before the evaluation data exist. Each entry is fingerprinted (SHA-256 of its canonical JSON, shown on the site) and its git commit timestamps it. Evaluation uses only data from the stated window.

## 9. What the report does not do

It does not forecast prices, recommend trades, model transaction costs (except where stated), or treat a historical frequency as a probability for tomorrow.

## 10. Known data limitations

* **Daily highs and lows depend on the vendor.** Vendors treat trades with special sale conditions differently. In a comparison of two SPY daily histories over the second half of 2022, opens and closes agreed to within 0.1%, but the high or low differed by more than 0.05% on 7 of 127 days, by up to 1.9%. Level studies are sensitive to such prints, so each instrument uses one source consistently and the source is named on every card.
* **Base rates at long horizons include drift.** The S&P 500 and the Nasdaq-100 rose over most of the sample, so prior highs are taken more often than prior lows. A base rate describes what happened; it does not show that the level itself caused it.
