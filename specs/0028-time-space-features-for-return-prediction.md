# 0028 Do time–space features improve the prediction of future returns?

**Status:** approved (founder, 2026-11-09); hypothesis H-2026-016 registered before any model is trained
**Level:** 2 study · **Open work:** W-121 (course final project, release 1.0.0) · **Decisions:** ADR 0064, ADR 0071

## Problem and decision supported

TSIP measures time (calendar coordinates) and space (price against prior periods' highs and lows). Its central claim is that this information helps a trader decide. The direct test: does adding time–space features to a standard feature set improve out-of-sample predictions of future returns, and does a strategy built on those predictions do better than buy and hold after costs? A second question from the founder is tested on the same data: does buying on pullbacks beat buying on a schedule or all at once, with idle cash accounted for?

The answer is useful whichever way it goes. A lift, confirmed against controls and out of sample, is public, reproducible evidence; no lift says where not to look.

## Requirements

- R1. **One data frame** for SPY, QQQ, GLD, BTC-USD and ETH-USD, daily, with the course's sources (yfinance prices; FRED macro series) and TSIP's sources where they add data (Coinbase, Binance archive). Columns are grouped into named feature sets: `TO_PREDICT`, `LECTURE` (course features), `TIME`, `SPACE`, `DUMMIES`.
- R2. **Targets:** `growth_future_5d` (close in 5 sessions over today's close) and `is_positive_growth_5d`; also 20 sessions as a secondary horizon.
- R3. **LECTURE features:** growth over 1, 3, 7, 30, 90 and 365 days of the instrument and of reference markets (S&P 500, Nasdaq-100, DAX, gold, oil, Bitcoin), macro series (10-year yield, federal funds rate, CPI), momentum and volatility indicators, ticker dummies.
- R4. **TIME features:** weekday, session of the week, session and week of the month, month, quarter, sessions elapsed and remaining in the week, month and quarter, the volatility-clock percentile of the weekday and month, distance to the next exchange holiday.
- R5. **SPACE features:** distance in ATR and in percent from the close to the prior day's, week's, month's and quarter's high and low; position of the close in the prior period's range; whether each level has been traded since the period closed and for how many sessions it has stayed untested; nearest untested level above and below; count of untested levels within 1 ATR (confluence).
- R6. **Every feature uses only data available at that day's close.** No feature is computed from a window that includes a later session.
- R7. **Models:** decision tree, random forest, logistic regression and XGBoost, each with hyperparameters tuned on time-ordered folds of the training period only.
- R8. **Ablation:** each model is trained on four feature sets: `LECTURE`, `LECTURE+TIME`, `LECTURE+SPACE`, `LECTURE+TIME+SPACE`.
- R9. **Strategies (vector and exact simulations, reinvested capital):** sim1 long when the predicted probability is above a threshold chosen on validation data; sim2 at most 1, 3 or 5 concurrent positions ranked by probability; sim3 sim1 with a stop loss in ATR and a volatility filter; sim4 long-short on crypto; sim5 pullback buying (R10). Costs per side: 0.02% on ETFs, 0.10% on crypto. Benchmarks: buy and hold of each instrument and of SPY with dividends.
- R10. **Pullback buying (founder's question):** the same monthly budget invested (a) all at once at the start, (b) on the first session of each month, (c) only after a fall of k ATR from the last high or at a prior period's low, with uninvested cash earning the 3-month Treasury bill rate (FRED `DTB3`) and unspent cash invested at the end of each quarter. No rule may use the number of future signals to size purchases.
- R11. **Reported per model, feature set and market:** ROC AUC, precision at the highest-probability decile against the base rate, and for strategies CAGR, Sharpe ratio, maximum drawdown, rolling 1-year returns, exposure and number of trades; all with block-bootstrap intervals.

## Study protocol

- **Periods:** training up to 2021-12-31; validation 2022-01-01 to 2023-12-31 (thresholds, model choice); test from 2024-01-01 to the last available session, used once, after every choice is fixed and committed. Walk-forward check: the model is refitted every year on all data before that year.
- **Controls:**
  1. *Random-walk series:* the same pipeline on simulated prices with the same drift and volatility; any lift there is an artefact.
  2. *Permuted blocks:* the `TIME` and `SPACE` columns of the test set shuffled within each market; the lift must disappear.
  3. *Base rate:* share of positive 5-session periods in the test set.
- **Statistic:** lift = AUC(`LECTURE+TIME+SPACE`) minus AUC(`LECTURE`), pooled over markets, with a circular block bootstrap interval (block of 20 sessions, 2,000 resamples).
- **Test budget:** 4 models × 4 feature sets × 5 markets × 2 horizons = 160 comparisons. Only the pooled 5-session lift of the model chosen on validation data is the registered test; every other figure is reported as exploratory and corrected with Benjamini–Hochberg.
- **Hypothesis before training (H-2026-016):** stated in `registry/hypotheses.json`.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| T1 | No feature on day t changes when every session after t is deleted | test |
| T2 | On random-walk series the pooled lift interval contains zero | random-walk test |
| T3 | A series with a planted level effect (price returns to the prior week's high more than chance) gives a positive lift for `SPACE` | planted-effect test |
| T4 | The test period is read only by the final evaluation command, which records its commit | test and log |
| T5 | Pullback buying never spends more than the cash available on the day | test |
| T6 | One notebook runs the whole flow from the `.py` modules, in two modes: from stored files and from fresh downloads | run log |

## Non-goals

- No live trading and no signals on the public page. A paper-order example for the broker API is included for the course, clearly labelled.
- Results go into the course write-up and into `docs/research/`; nothing reaches the public board until it has passed the review of ADR 0071.

## Data contract

Data files are never committed. Prices from yfinance are used for the course project only, under their terms; TSIP's public board keeps its own sources (ADR 0055). The private Kibot history is not used.

## Verification

| ID | Result | Evidence |
|---|---|---|
| T1–T6 | to do | |
