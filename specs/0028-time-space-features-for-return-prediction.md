# 0028 Do time–space features improve the prediction of future returns?

**Status:** evaluated on 2026-11-10: H-2026-016 not supported (test lift −0.012, interval −0.039 to +0.016; `docs/CAPSTONE.md`, `registry/evaluations.json`); notebook and release (T6) to do
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
| T3 | A series with a planted level effect (drift up for five days after a close below the prior week's low) is found (validation AUC above 0.6) and `SPACE` adds a positive lift over the course features | planted-effect test |
| T4 | The test period is read only by the final evaluation command, which records its commit | test and log |
| T5 | Pullback buying never spends more than the cash available on the day | test |
| T6 | One notebook runs the whole flow from the `.py` modules, in two modes: from stored files and from fresh downloads | run log |

## Non-goals

- No live trading and no signals on the public page. A paper-order example for the broker API is included for the course, clearly labelled.
- Results go into the course write-up and into `docs/research/`; nothing reaches the public board until it has passed the review of ADR 0071.

## Data contract

Data files are never committed. Prices from yfinance are used for the course project only, under their terms; TSIP's public board keeps its own sources (ADR 0055). The private Kibot history is not used.

## Selection rule (fixed 2026-11-10, before the first model was trained)

- Each family is tuned on three expanding, time-ordered folds of the training period (small fixed grids in `tsip.capstone.models.GRIDS`), then fitted on the whole training period and scored once on validation.
- The family carried to the test period is the one with the **highest mean validation AUC over the four feature sets**, so the choice does not favour the time–space sets. Ties go to the simpler family (logistic, then decision tree, XGBoost, random forest).
- Validation lift and its 95% interval (circular block bootstrap over dates, 20-date blocks) are reported for every family as exploratory; only the test-period lift of the selected family is the registered result (H-2026-016).
- Controls on validation: TIME and SPACE columns shuffled within each ticker (the lift should vanish), and the same pipeline on random-walk prices with each ticker's drift and volatility (the lift interval should contain zero).

## Simulation rule (fixed 2026-11-10, before the first simulation)

- **Inputs:** validation predictions of the selected family (logistic regression), for the `LECTURE` and `LECTURE+TIME+SPACE` sets; prices up to 2023-12-31 only. The test period is not read by `simulate.py`.
- **Execution:** a position decided on the close of day t is taken at that close (the convention of the course and of the target); a one-session delay is reported for every chosen strategy as a robustness check. A position in an exchange-traded fund changes only on that fund's trading days. Cash not invested earns the 3-month Treasury bill rate (FRED `DTB3`, known the previous day), accrued by calendar day; short positions earn nothing on their proceeds and pay no borrow fee (not modelled; stated with the results).
- **Capital:** reinvested. Long-only strategies give each of the five instruments a sleeve of one fifth unless stated.
- **Choices made on validation only, by the highest validation Sharpe ratio:** sim1 threshold among the 50th, 60th, 70th, 80th and 90th percentiles of the pooled validation probabilities (recorded as an absolute value); sim2 the same thresholds with at most 1, 3 or 5 positions; sim4 upper thresholds at the 60th to 90th percentiles of the crypto probabilities with the symmetric lower percentile. sim3 takes sim1's threshold with fixed rules: exit when the low reaches 2 ATR(14) below the entry close (filled at that level, or at the open if it gaps below), no new entry while the 20-day volatility is above the 80th percentile of its previous 252 rows, and no re-entry until the signal has switched off.
- **sim5, pullback buying (R10):** one unit deposited on each instrument's first session of each month; triggers: a close at least 1, 2 or 3 ATR(14) below the highest close of the last 63 sessions, or a close at or below the prior calendar month's low; on a trigger all available cash is invested; cash left on the last session of a quarter is invested then. The trigger carried to the test period is the one with the highest mean money-weighted return over the five instruments. Compared with the same deposits invested on arrival, with the whole budget invested at the start, and with cash only.
- **Strategy carried to the test period for the benchmark comparison:** among sim1 to sim3 on both feature sets, the one with the highest validation Sharpe ratio. Benchmarks: equal-weight buy and hold of the five instruments, and SPY with dividends (adjusted close). The rubric's "exceptional returns" point is claimed only if its test CAGR is above both benchmarks; the CAGR difference is reported with a circular block bootstrap interval (20-date blocks).
- Every other strategy figure is exploratory.

## Evaluation rule (fixed 2026-11-10, before the test period was read)

- **Model (founder decision, 2026-11-10):** the logistic regression of step 3, tuned and fitted on the training period only, exactly as it was scored on validation, for the four feature sets. The thresholds frozen in `registry/capstone_choices_h5.json` are absolute probabilities of this model, so it is not refitted for the registered result.
- **Registered statistic (H-2026-016):** pooled test AUC of `LECTURE+TIME+SPACE` minus `LECTURE` for the direction of the next 5 rows, with a circular block bootstrap over dates (20-date blocks, 2,000 resamples). Supported only if the lift is at least 0.02, its 95% interval excludes zero, and both controls show no lift.
- **Controls on the test rows:** (1) permuted: the `TIME` and `SPACE` columns shuffled within each ticker and scored by the fitted `LECTURE+TIME+SPACE` model; its lift over `LECTURE` has the same bootstrap; (2) random walk: the whole pipeline (fit on training, score on test) on random-walk prices (`models.random_walk_frame`, seed 28). A control "shows no lift" when the lower end of its 95% interval is at or below zero.
- **Strategies:** the parameters in `registry/capstone_choices_h5.json`, unchanged, on test prices from 2024-01-01 to the last complete session of the download of 2026-11-10; the strategy carried to the benchmark comparison is sim3 on `LECTURE+TIME+SPACE`; pullback buying with the trigger `prior_month_low` against monthly buying, a lump sum and cash.
- **Exploratory, not registered:** the other feature sets and families' validation choices, the 20-row horizon, and a walk-forward check in which the model is refitted at the start of each test year on all earlier rows (purged at the boundary).
- **Single read:** `python -m tsip.capstone.evaluate` refuses to run from a working tree with uncommitted changes, records its commit, the data fingerprint and the time in `registry/capstone_test_runs.json`, and refuses a second run unless `--rerun "<reason>"` is given; every run stays in the log.

## Data notes (step 1)

- Reference markets: S&P 500, Nasdaq-100, DAX, gold, WTI and Brent oil, Bitcoin and VIX closes, joined from the previous calendar day or earlier, because their closes fall at different hours from the row's own close.
- Macro release lags: 10-year yield and 3-month bill from the next day; federal funds monthly average 3 days after the month ends; CPI 20 days after the month ends.
- The rubric's "more than 1 million records" point is not met by daily data (tens of thousands of rows); it would need intraday or minute bars (for example the Binance archive) and is claimed only if such data are added.

## Verification

| ID | Result | Evidence |
|---|---|---|
| T1 | pass: data layer (`tests/test_capstone_data.py`) and features (`tests/test_capstone_features.py::test_no_feature_changes_when_later_rows_are_removed`) | steps 1 and 2, 2026-11-10 |
| T2 | pass: random-walk prices give no significant lift for any family (`docs/CAPSTONE.md`, step 3) and `tests/test_capstone_models.py::test_random_walk_gives_no_time_space_lift` | 2026-11-10 |
| T3 | pass: `tests/test_capstone_models.py::test_planted_space_effect_is_found` | 2026-11-10 |
| T4 | pass: `split` refuses test rows unless `allow_test=True`; `tests/test_capstone_evaluate.py` (refused from uncommitted code, refused a second time without a logged reason, phase 2 only for the same run and commit, both phases end to end); registered run logged in `registry/capstone_test_runs.json` (commit `393631e`) | 2026-11-10 |
| T5 | pass: `tests/test_capstone_simulate.py::test_accumulation_never_spends_more_than_the_cash` (every rule) and `test_accumulation_on_a_flat_price_returns_the_deposits_less_costs` | 2026-11-10 |
| T6 | to do | |
