# Course project: do time and space improve the prediction of future returns?

Working document of the final project of the Stock Markets Analytics course (specification [0028](../specs/0028-time-space-features-for-return-prediction.md), hypothesis H-2026-016). It is completed step by step; sections not yet built say so. Every figure here names the command that produced it (ADR 0071 of the project's decision record).

## Problem

TSIP describes where price stands in time (calendar coordinates) and in space (against the highs and lows of prior days, weeks, months and quarters). The project tests whether that information improves the out-of-sample prediction of the direction of the next 5 and 20 sessions for SPY, QQQ, GLD, Bitcoin and Ethereum, beyond the course's standard features, and whether a strategy built on the predictions beats buy and hold after costs. The hypothesis and its pass criterion were registered before any model was trained.

## How to run

```sh
pip install -e ".[dev,calendar,capstone]"
python -m tsip.capstone.run_all --mode download   # steps 1-4 with fresh data from yfinance and FRED
python -m tsip.capstone.run_all --mode file       # the same from the stored copy, no network
python -m tsip.capstone.run_all --all-families    # adds decision tree, XGBoost and random forest (slower)
jupyter notebook notebooks/capstone.ipynb          # the same flow step by step, with outputs saved
python -m tsip.capstone.evaluate --markdown       # tables of the single test-period read (step 5)
python -m tsip.capstone.paper_order               # paper-trading order example (dry run; --send with paper keys)
docker build -t tsip-capstone .                   # container: the data folder is mounted at /data
docker run --rm -v "$HOME/tsip_capstone_data:/data" tsip-capstone [--mode download]
```

Data are stored in `~/tsip_capstone_data` (override with `TSIP_CAPSTONE_DATA`) with a manifest that fingerprints each file; nothing is committed to Git and nothing is copied into the container image. The notebook is rebuilt with `python tools/build_capstone_notebook.py` and executed with `python -m nbconvert --to notebook --execute --inplace notebooks/capstone.ipynb`.

## Data (step 1)

Sources: yfinance daily prices for the five instruments and eight reference markets (S&P 500, Nasdaq-100, DAX, gold and oil futures, Bitcoin, VIX); FRED public CSV for the 10-year yield (DGS10), the 3-month bill (DTB3), the federal funds rate (FEDFUNDS) and CPI (CPIAUCSL).

Rules that keep every row honest: reference closes come only from earlier dates (markets close at different hours); macro values are used only after a conservative release lag (daily rates from the next day, federal funds 3 days and CPI 20 days after the month ends); bars dated on or after the download's UTC date are dropped because they may still be open.

First download, 2026-11-10 00:37 UTC (`python -m tsip.capstone.data --mode download` on the founder's computer; read back with `--mode file` using the code of commit `5343d97`, which added this document):

| Item | Value |
|---|---|
| Source rows | 71,800 prices, 36,226 FRED observations |
| Unified frame | 26,759 rows, 20 columns, 2000-01-03 to 2026-11-09 |
| Rows by instrument | SPY 6,754 · QQQ 6,754 · GLD 5,528 · Bitcoin 4,436 · Ethereum 3,287 |

## Features (step 2)

`python -c "from tsip.capstone import data, features; f, s = features.build_features(data.load('file')[0])"` builds 122 columns on the frame above: 4 targets, 60 course features, 11 time features, 40 space features and 5 ticker indicators. No feature on a row changes when later rows are deleted (test `tests/test_capstone_features.py`).

- **TO_PREDICT:** growth over the next 5 and 20 rows of the adjusted close, and whether it is positive.
- **LECTURE:** growth of the instrument over 1, 3, 7, 30, 90 and 365 calendar days; growth of each reference market over 1, 7, 30, 90 and 365 days; macro levels, their 30-day changes and CPI year over year; RSI(14), annualised 20-day volatility, distance to the 50- and 200-day averages, log volume and volume against its 20-day average.
- **TIME:** weekday, day and week of the month, month, quarter, session of the week, month and quarter, days to the month's and quarter's end, last week of the month.
- **SPACE:** ATR(14) in percent; distance from the close to the prior day's, week's, month's and quarter's high and low, in ATR and percent; position of the close in each prior range; whether each prior high and low has been traded in the current period; for the last twelve weeks and months, the nearest high above and low below that has not been traded since, its distance in ATR and percent and its age in rows, and the count of such levels within 1 ATR.
- **DUMMIES:** one indicator per ticker.

Full list:

**TO_PREDICT** (4): `growth_future_5d`, `is_positive_growth_5d`, `growth_future_20d`, `is_positive_growth_20d`

**LECTURE** (60): `growth_1d`, `growth_3d`, `growth_7d`, `growth_30d`, `growth_90d`, `growth_365d`, `growth_btc_usd_1d`, `growth_btc_usd_7d`, `growth_btc_usd_30d`, `growth_btc_usd_90d`, `growth_btc_usd_365d`, `growth_brent_oil_1d`, `growth_brent_oil_7d`, `growth_brent_oil_30d`, `growth_brent_oil_90d`, `growth_brent_oil_365d`, `growth_wti_oil_1d`, `growth_wti_oil_7d`, `growth_wti_oil_30d`, `growth_wti_oil_90d`, `growth_wti_oil_365d`, `growth_gold_1d`, `growth_gold_7d`, `growth_gold_30d`, `growth_gold_90d`, `growth_gold_365d`, `growth_dax_1d`, `growth_dax_7d`, `growth_dax_30d`, `growth_dax_90d`, `growth_dax_365d`, `growth_snp500_1d`, `growth_snp500_7d`, `growth_snp500_30d`, `growth_snp500_90d`, `growth_snp500_365d`, `growth_ndx_1d`, `growth_ndx_7d`, `growth_ndx_30d`, `growth_ndx_90d`, `growth_ndx_365d`, `growth_vix_1d`, `growth_vix_7d`, `growth_vix_30d`, `growth_vix_90d`, `growth_vix_365d`, `macro_ten_year_yield`, `macro_ten_year_yield_change_30d`, `macro_tbill_3m`, `macro_tbill_3m_change_30d`, `macro_fed_funds`, `macro_fed_funds_change_30d`, `macro_cpi`, `macro_cpi_yoy`, `rsi_14`, `volatility_20`, `ma_ratio_50`, `ma_ratio_200`, `ln_volume`, `volume_ratio_20`

**TIME** (11): `weekday`, `day_of_month`, `week_of_month`, `month`, `quarter`, `session_of_week`, `session_of_month`, `session_of_quarter`, `days_to_month_end`, `days_to_quarter_end`, `is_last_week_of_month`

**SPACE** (40): `atr_pct_14`, `space_day_high_dist_atr`, `space_day_low_dist_atr`, `space_day_position`, `space_week_high_dist_atr`, `space_week_low_dist_atr`, `space_week_high_dist_pct`, `space_week_low_dist_pct`, `space_week_position`, `space_week_high_tested`, `space_week_low_tested`, `space_week_untested_above_atr`, `space_week_untested_below_atr`, `space_week_untested_above_pct`, `space_week_untested_below_pct`, `space_week_untested_above_age`, `space_week_untested_below_age`, `space_week_untested_within_1atr`, `space_month_high_dist_atr`, `space_month_low_dist_atr`, `space_month_high_dist_pct`, `space_month_low_dist_pct`, `space_month_position`, `space_month_high_tested`, `space_month_low_tested`, `space_month_untested_above_atr`, `space_month_untested_below_atr`, `space_month_untested_above_pct`, `space_month_untested_below_pct`, `space_month_untested_above_age`, `space_month_untested_below_age`, `space_month_untested_within_1atr`, `space_quarter_high_dist_atr`, `space_quarter_low_dist_atr`, `space_quarter_high_dist_pct`, `space_quarter_low_dist_pct`, `space_quarter_position`, `space_quarter_high_tested`, `space_quarter_low_tested`, `space_untested_within_1atr`

**DUMMIES** (5): `ticker_BTC-USD`, `ticker_ETH-USD`, `ticker_GLD`, `ticker_QQQ`, `ticker_SPY`

Missing values: reference growth is empty before a reference market starts (Bitcoin from 2014); "untested above" is empty when price is at a new high for the lookback (no untested high exists). Models that cannot take empty values receive an indicator and an imputed value; this is stated with each model.

## Models (step 3): validation period only

Commands (each piece resumable; results outside Git):

```sh
python -m tsip.capstone.run_models fit --horizon 5
python -m tsip.capstone.run_models fit --horizon 5 --random-walk
python -m tsip.capstone.run_models summarise --horizon 5 [--random-walk]
```

Training rows up to 2021-12-31, validation 2022-01-01 to 2023-12-31, the last 5 rows of each ticker before each boundary purged. Each family tuned on three expanding time-ordered folds of the training rows (`tsip.capstone.models.GRIDS`). Validation AUC of the direction of the next 5 rows, run on 2026-11-10 with the code of the commit that added this section, on the download of 2026-11-10 (validation base rate 51.8% positive):

| Family | LECTURE | +TIME | +SPACE | +TIME+SPACE | Mean | TIME and SPACE shuffled | Lift of +TIME+SPACE over LECTURE (95% block interval) |
|---|---:|---:|---:|---:|---:|---:|---|
| Logistic regression | 0.555 | 0.561 | 0.548 | 0.553 | **0.554** | 0.537 | −0.002 (−0.039 to +0.036) |
| Decision tree | 0.480 | 0.490 | 0.499 | 0.490 | 0.490 | 0.483 | +0.010 (−0.069 to +0.086) |
| XGBoost | 0.538 | 0.551 | 0.530 | 0.548 | 0.542 | 0.504 | +0.009 (−0.032 to +0.047) |
| Random forest | 0.477 | 0.515 | 0.495 | 0.512 | 0.500 | 0.487 | +0.035 (−0.003 to +0.066) |

Random-walk control (same pipeline, each ticker's prices replaced by a walk with its own drift and volatility; references and macro kept):

| Family | LECTURE | +TIME | +SPACE | +TIME+SPACE | Lift (95% block interval) |
|---|---:|---:|---:|---:|---|
| Logistic regression | 0.489 | 0.488 | 0.509 | 0.506 | +0.017 (−0.011 to +0.048) |
| Decision tree | 0.489 | 0.477 | 0.489 | 0.477 | −0.012 (−0.034 to +0.010) |
| XGBoost | 0.494 | 0.482 | 0.510 | 0.503 | +0.009 (−0.020 to +0.039) |
| Random forest | 0.506 | 0.502 | 0.509 | 0.510 | +0.004 (−0.007 to +0.016) |

Secondary horizon, direction of the next 20 rows (`fit --horizon 20`, `summarise --horizon 20`; validation base rate 51.9% positive; random-walk control not run for this horizon):

| Family | LECTURE | +TIME | +SPACE | +TIME+SPACE | Mean | TIME and SPACE shuffled | Lift (95% block interval) |
|---|---:|---:|---:|---:|---:|---:|---|
| Logistic regression | 0.545 | 0.540 | 0.542 | 0.533 | **0.540** | 0.531 | −0.012 (−0.045 to +0.023) |
| Decision tree | 0.535 | 0.528 | 0.535 | 0.528 | 0.531 | 0.528 | −0.007 (−0.048 to +0.039) |
| XGBoost | 0.541 | 0.536 | 0.541 | 0.497 | 0.529 | 0.491 | −0.044 (−0.099 to +0.013) |
| Random forest | 0.476 | 0.451 | 0.493 | 0.471 | 0.473 | 0.472 | −0.006 (−0.032 to +0.017) |

Reading (exploratory; the registered result is the test period at step 5):

1. **Selected family: logistic regression at both horizons** (highest mean validation AUC over the four sets, rule fixed before the run). The trees overfit: the decision tree and the random forest stay at or below 0.5 on the course features.
2. **No validated lift yet.** Every interval of the lift contains zero, on real prices as on random walks. At 5 rows time features add a little in every family (+0.006 to +0.038) and space features alone do not; at 20 rows neither adds, and the point estimates are negative.
3. **The pipeline is honest:** on random walks every family stays near 0.5 and no lift is significant, and on the real data shuffling the time and space columns lowers the AUC of the logistic and XGBoost models.
4. A validation sample of two years is noisy: on random walks of the same size the AUC spreads by about 0.04 between seeds (checked 2026-11-10). Differences below a few hundredths are not evidence.

## Simulation (step 4): validation period only

The rule was committed before the first simulation (specification 0028, section "Simulation rule", commit `30165b2`). Commands (results outside Git, in `<store>/results/simulation_h5*.json`):

```sh
python -m tsip.capstone.run_models fit --horizon 5 --families logistic               # validation predictions
python -m tsip.capstone.simulate --horizon 5                                          # all strategies, choices, controls
python -m tsip.capstone.run_models fit --horizon 5 --families logistic --feature-sets LECTURE LECTURE+TIME+SPACE --random-walk
python -m tsip.capstone.simulate --horizon 5 --random-walk                            # the same on random walks
python -m tsip.capstone.simulate --horizon 5 [--random-walk] --markdown               # the tables below
```

Run on 2026-11-10 with the code of the commit that added this section, on the download of 2026-11-10. The validation predictions of the logistic model were regenerated for this step and match the step 3 table to the third decimal. Model: logistic regression (selected at step 3), direction of the next 5 rows. Positions taken at the close of the signal; costs 0.02% per side on the funds and 0.10% on crypto; idle cash at the 3-month bill rate; shorts earn nothing on their proceeds and pay no borrow fee (not modelled). Intervals: circular block bootstrap of daily returns, 20-date blocks, 1,000 resamples. Each "Chosen parameters" cell was picked on this same period, so every figure here is in-sample for that choice.

**LECTURE** (period 2022-01-01 to 2023-12-26)

| Strategy | Chosen parameters | CAGR (95% interval) | CAGR minus five equal (95%) | Sharpe | Max drawdown | Rolling 1y min / median | Exposure | Entries | CAGR, Sharpe with one-session delay |
|---|---|---|---|---:|---:|---|---:|---:|---|
| sim1 threshold | quantile 0.900, threshold 0.560 | +10.5% (+3.5 to +19.5) | -25.4 to +43.2 | 1.10 | -3.7% | +3.1% / +5.9% | 0.10 | 86 | +7.7%, 0.77 |
| sim2 top k | quantile 0.900, threshold 0.560, k 5 | +10.5% (+3.5 to +19.5) | -25.4 to +43.2 | 1.10 | -3.7% | +3.1% / +5.9% | 0.10 | 86 | +7.7%, 0.77 |
| sim3 stop and filter | threshold 0.560 | +4.9% (+1.2 to +8.9) | -31.6 to +36.7 | 0.43 | -2.3% | +3.3% / +4.9% | 0.05 | 57 | +5.6%, 0.65 |
| sim4 crypto long-short | quantile 0.900, upper 0.537, lower 0.330 | +39.1% (+9.8 to +92.0) | -11.7 to +109.6 | 1.33 | -11.9% | -2.6% / +52.1% | 0.20 | 108 | +19.9%, 0.72 |
| Buy and hold, five equal | - | -3.2% (-31.9 to +37.2) | - | -0.16 | -39.8% | -37.0% / +11.9% | 1.00 | 5 | - |
| Buy and hold, crypto | - | -14.0% (-64.1 to +104.6) | -36.8 to +72.7 | -0.01 | -68.9% | -66.6% / +12.2% | 1.00 | 2 | - |
| SPY with dividends | - | +1.7% (-21.5 to +28.5) | -18.7 to +23.7 | 0.01 | -24.5% | -19.0% / +9.7% | 1.00 | 1 | - |
| SPY price only | - | +0.1% (-22.9 to +27.1) | -20.5 to +22.1 | -0.07 | -25.4% | -20.3% / +7.9% | 1.00 | 1 | - |

Rotation control of sim1 (100 rotations): median Sharpe -0.28 (95% -1.31 to 1.07); share at or above the actual 0.03. Vector view of sim1: 294 bets of 100, hit rate 55.1%, mean net +0.82 per bet.

**LECTURE+TIME+SPACE** (period 2022-01-01 to 2023-12-26)

| Strategy | Chosen parameters | CAGR (95% interval) | CAGR minus five equal (95%) | Sharpe | Max drawdown | Rolling 1y min / median | Exposure | Entries | CAGR, Sharpe with one-session delay |
|---|---|---|---|---:|---:|---|---:|---:|---|
| sim1 threshold | quantile 0.500, threshold 0.448 | +28.0% (-2.2 to +65.5) | +8.8 to +55.7 | 1.26 | -18.8% | +8.4% / +43.0% | 0.51 | 227 | +16.3%, 0.74 |
| sim2 top k | quantile 0.500, threshold 0.448, k 5 | +28.0% (-2.2 to +65.5) | +8.8 to +55.7 | 1.26 | -18.8% | +8.4% / +43.0% | 0.51 | 227 | +16.3%, 0.74 |
| sim3 stop and filter | threshold 0.448 | +27.5% (+3.1 to +61.0) | +3.2 to +53.2 | 1.79 | -14.7% | +7.4% / +37.1% | 0.31 | 185 | +18.0%, 1.24 |
| sim4 crypto long-short | quantile 0.700, upper 0.490, lower 0.382 | +70.1% (-6.5 to +214.3) | -6.8 to +220.3 | 1.35 | -39.8% | +43.5% / +185.8% | 0.59 | 191 | +68.2%, 1.34 |
| Buy and hold, five equal | - | -3.2% (-31.9 to +37.2) | - | -0.16 | -39.8% | -37.0% / +11.9% | 1.00 | 5 | - |
| Buy and hold, crypto | - | -14.0% (-64.1 to +104.6) | -36.8 to +72.7 | -0.01 | -68.9% | -66.6% / +12.2% | 1.00 | 2 | - |
| SPY with dividends | - | +1.7% (-21.5 to +28.5) | -18.7 to +23.7 | 0.01 | -24.5% | -19.0% / +9.7% | 1.00 | 1 | - |
| SPY price only | - | +0.1% (-22.9 to +27.1) | -20.5 to +22.1 | -0.07 | -25.4% | -20.3% / +7.9% | 1.00 | 1 | - |

Rotation control of sim1 (100 rotations): median Sharpe -0.11 (95% -0.79 to 0.80); share at or above the actual 0.01. Vector view of sim1: 1469 bets of 100, hit rate 55.5%, mean net +0.52 per bet.

Strategy carried to the test period: **sim3 on LECTURE+TIME+SPACE** (validation Sharpe 1.79).

Pullback buying (sim5), money-weighted annual return, one unit deposited each month:

| Rule | BTC-USD | ETH-USD | GLD | QQQ | SPY | Mean |
|---|---:|---:|---:|---:|---:|---:|
| lump_sum | -5.9% | -22.3% | +6.6% | +1.7% | +1.3% | -3.7% |
| monthly | +51.7% | +25.6% | +9.7% | +24.9% | +14.8% | +25.3% |
| cash | +4.5% | +4.5% | +4.5% | +4.5% | +4.5% | +4.5% |
| atr_1 | +51.6% | +25.2% | +9.9% | +25.2% | +15.0% | +25.4% |
| atr_2 | +52.2% | +25.8% | +10.1% | +24.9% | +15.2% | +25.6% |
| atr_3 | +53.1% | +26.1% | +10.3% | +24.1% | +15.1% | +25.7% |
| prior_month_low | +59.3% | +30.5% | +9.5% | +27.0% | +15.9% | +28.4% |

Trigger carried to the test period: **prior_month_low**.

Random-walk control (each ticker's prices replaced by a walk with its own drift and volatility, predictions from the model refitted on those prices; validation AUC 0.489 for LECTURE and 0.506 for LECTURE+TIME+SPACE):

**LECTURE** (period 2022-01-01 to 2023-12-26)

| Strategy | Chosen parameters | CAGR (95% interval) | CAGR minus five equal (95%) | Sharpe | Max drawdown | Rolling 1y min / median | Exposure | Entries | CAGR, Sharpe with one-session delay |
|---|---|---|---|---:|---:|---|---:|---:|---|
| sim1 threshold | quantile 0.600, threshold 0.536 | +31.1% (+2.9 to +70.1) | -64.8 to +23.5 | 1.56 | -15.0% | -2.5% / +33.8% | 0.37 | 170 | +19.7%, 0.99 |
| sim2 top k | quantile 0.600, threshold 0.536, k 3 | +58.5% (+11.1 to +126.9) | -41.9 to +68.5 | 1.85 | -17.0% | +1.5% / +83.0% | 0.49 | 178 | +44.2%, 1.47 |
| sim3 stop and filter | threshold 0.536 | +20.5% (-3.6 to +53.3) | -79.6 to +14.0 | 1.21 | -17.2% | -11.9% / +23.5% | 0.22 | 142 | +13.4%, 0.78 |
| sim4 crypto long-short | quantile 0.600, upper 0.550, lower 0.529 | -0.4% (-56.7 to +125.2) | -139.2 to +93.2 | 0.31 | -70.3% | -46.2% / +80.0% | 0.98 | 163 | -24.4%, -0.16 |
| Buy and hold, five equal | - | +46.3% (+1.7 to +105.3) | - | 1.34 | -23.1% | +4.1% / +27.5% | 1.00 | 5 | - |
| Buy and hold, crypto | - | +85.7% (-19.5 to +332.8) | -27.4 to +232.7 | 1.23 | -41.1% | -25.9% / +65.3% | 1.00 | 2 | - |
| SPY with dividends | - | +10.6% (-12.1 to +41.3) | -102.9 to +22.8 | 0.43 | -24.8% | -8.8% / +10.0% | 1.00 | 1 | - |
| SPY price only | - | +10.6% (-12.1 to +41.3) | -102.9 to +22.8 | 0.43 | -24.8% | -8.8% / +10.0% | 1.00 | 1 | - |

Rotation control of sim1 (100 rotations): median Sharpe 1.28 (95% 0.26 to 2.24); share at or above the actual 0.30. Vector view of sim1: 1175 bets of 100, hit rate 51.8%, mean net +0.91 per bet.

**LECTURE+TIME+SPACE** (period 2022-01-01 to 2023-12-26)

| Strategy | Chosen parameters | CAGR (95% interval) | CAGR minus five equal (95%) | Sharpe | Max drawdown | Rolling 1y min / median | Exposure | Entries | CAGR, Sharpe with one-session delay |
|---|---|---|---|---:|---:|---|---:|---:|---|
| sim1 threshold | quantile 0.600, threshold 0.549 | +40.8% (+14.9 to +70.7) | -58.7 to +36.3 | 2.06 | -11.7% | +8.2% / +30.7% | 0.38 | 181 | +23.4%, 1.22 |
| sim2 top k | quantile 0.600, threshold 0.549, k 5 | +40.8% (+14.9 to +70.7) | -58.7 to +36.3 | 2.06 | -11.7% | +8.2% / +30.7% | 0.38 | 181 | +23.4%, 1.22 |
| sim3 stop and filter | threshold 0.549 | +35.8% (+14.9 to +61.5) | -65.9 to +31.3 | 2.02 | -10.8% | +15.2% / +36.2% | 0.25 | 158 | +20.0%, 1.15 |
| sim4 crypto long-short | quantile 0.700, upper 0.593, lower 0.506 | +7.3% (-45.3 to +101.0) | -125.7 to +66.9 | 0.32 | -53.5% | -43.4% / -15.4% | 0.64 | 144 | +5.2%, 0.27 |
| Buy and hold, five equal | - | +46.3% (+1.7 to +105.3) | - | 1.34 | -23.1% | +4.1% / +27.5% | 1.00 | 5 | - |
| Buy and hold, crypto | - | +85.7% (-19.5 to +332.8) | -27.4 to +232.7 | 1.23 | -41.1% | -25.9% / +65.3% | 1.00 | 2 | - |
| SPY with dividends | - | +10.6% (-12.1 to +41.3) | -102.9 to +22.8 | 0.43 | -24.8% | -8.8% / +10.0% | 1.00 | 1 | - |
| SPY price only | - | +10.6% (-12.1 to +41.3) | -102.9 to +22.8 | 0.43 | -24.8% | -8.8% / +10.0% | 1.00 | 1 | - |

Rotation control of sim1 (100 rotations): median Sharpe 1.14 (95% -0.12 to 2.22); share at or above the actual 0.07. Vector view of sim1: 1175 bets of 100, hit rate 53.4%, mean net +0.90 per bet.

Reading (exploratory; the registered results are those of the test period at step 5):

1. **Two years of validation can make noise look excellent.** On random walks, where the model has no information, the same selection gives Sharpe ratios of 1.2 to 2.1. Sharpe ratios of 1 to 2 over this period are therefore not evidence by themselves.
2. **The rotation control is the useful comparison.** It rotates each instrument's probabilities by a random offset across its own dates, which keeps the exposure and the persistence of the signal and removes only its timing. On random walks the actual run sits inside the rotations (share at or above it 0.30 and 0.07); on real prices it sits at their edge (0.03 for LECTURE, 0.01 for LECTURE+TIME+SPACE). The threshold was chosen among five on the same data, so these shares understate the chance of a fluke by up to five times. A first version of this control shuffled the dates, which breaks the persistence of the signal and made even the random walks look significant; it was replaced by the rotation after that first run, before any figure was recorded.
3. **Most of the value comes from staying out of 2022.** Every buy and hold lost money or stood still over the period (five equal −3.2% a year, crypto −14.0%), and the strategies were invested between 5% and 59% of the time.
4. **Execution matters.** Waiting one session lowers the Sharpe ratio of sim1 from 1.26 to 0.74 on LECTURE+TIME+SPACE: much of the signal is used up within a day, so the result depends on trading at the close.
5. **sim2 chose at most five positions**, which with five instruments is sim1. Concentrated versions (one position) had higher CAGR and deeper drawdowns and lost on Sharpe.
6. **Pullback buying:** with the same monthly deposits, buying only at or below the prior month's low gave the highest mean money-weighted return over the period (+28.4% against +25.3% for investing each deposit on arrival); the ATR triggers fired almost every month and behaved like monthly buying. Two years hold 24 deposits per instrument: this is a choice for the test period, not a finding.
7. Carried to step 5, unchanged: sim3 on LECTURE+TIME+SPACE (threshold, stop and filter above) against buy and hold of the five and SPY with dividends; the pullback trigger at the prior month's low; and every chosen parameter, frozen at full precision in `registry/capstone_choices_h5.json` (written by `simulate --freeze`).

## Evaluation (step 5): the test period, read once

The rule was committed before the first read (specification 0028, section "Evaluation rule", commit `cb5ff00`): the logistic model of step 3, fitted on the training period only (founder decision of 2026-11-10, so the frozen thresholds keep their meaning), the parameters of `registry/capstone_choices_h5.json`, and the H-2026-016 criterion. Commands:

```sh
python -m tsip.capstone.evaluate                 # phase 1: models, controls, verdict (refused if already run)
python -m tsip.capstone.evaluate --strategies    # phase 2 of the same run: frozen strategies
python -m tsip.capstone.evaluate --walk-forward 5   # exploratory checks, 5 and 20 rows
python -m tsip.capstone.evaluate --markdown      # the tables below
```

Each run is logged in `registry/capstone_test_runs.json` before any test row is read (time, commit, data fingerprint). The registered run is commit `393631e` on 2026-11-10 12:06 UTC, on the download of 2026-11-10 (test rows from 2024-01-01; the last rows with a known 5-row target end on 2026-11-03). Validation AUCs recomputed inside the run match step 3, which checks that the model is the same one.

Rows: training 19,534, validation 2,938, test 4,212 (test base rate 55.1% positive).

| Feature set | Test AUC | Validation AUC (refit, check) |
|---|---:|---:|
| LECTURE | 0.552 | 0.555 |
| LECTURE+TIME | 0.534 | 0.561 |
| LECTURE+SPACE | 0.547 | 0.548 |
| LECTURE+TIME+SPACE | 0.540 | 0.553 |

| Statistic | Lift over LECTURE | 95% interval |
|---|---:|---|
| **Registered: LECTURE+TIME+SPACE** | **-0.0122** | -0.0394 to +0.0160 |
| LECTURE+TIME (exploratory) | -0.0182 | -0.0413 to +0.0059 |
| LECTURE+SPACE (exploratory) | -0.0045 | -0.0195 to +0.0112 |
| Control: TIME and SPACE shuffled | -0.0209 | -0.0416 to -0.0015 |
| Control: random walk | -0.0034 | -0.0232 to +0.0165 |

H-2026-016: **rejected** (lift at least 0.02: no; interval excludes zero: no; permuted control shows no lift: yes; random walk control shows no lift: yes).

**Strategies on LECTURE** (test period 2024-01-01 to 2026-11-03, frozen parameters)

| Strategy | CAGR (95%) | CAGR minus five equal (95%) | CAGR minus SPY with dividends (95%) | Sharpe | Max drawdown | Exposure | Entries | One-session delay: CAGR, Sharpe |
|---|---|---|---|---:|---:|---:|---:|---|
| sim1 | +8.3% (+2.3% to +15.3%) | -47.6% to +21.0% | -28.6% to +4.7% | 0.50 | -9.4% | 0.06 | 77 | +10.7%, 0.76 |
| sim2 | +8.3% (+2.3% to +15.3%) | -47.6% to +21.0% | -28.6% to +4.7% | 0.50 | -9.4% | 0.06 | 77 | +10.7%, 0.76 |
| sim3 | +5.9% (+1.9% to +10.2%) | -50.3% to +18.6% | -31.2% to +2.4% | 0.42 | -5.6% | 0.03 | 60 | +6.3%, 0.57 |
| sim4 | -8.0% (-28.1% to +13.8%) | -71.8% to +15.2% | -53.4% to +0.6% | -0.58 | -36.3% | 0.11 | 92 | +4.7%, 0.12 |
| buy_hold_equal | +17.7% (-12.6% to +56.0%) | - | -26.2% to +30.0% | 0.59 | -26.4% | 1.00 | 5 | - |
| buy_hold_crypto | +11.4% (-40.3% to +100.9%) | -32.2% to +50.0% | -57.1% to +75.4% | 0.39 | -58.6% | 1.00 | 2 | - |
| spy_total_return | +19.0% (+2.0% to +38.4%) | -30.0% to +26.2% | - | 0.93 | -18.8% | 1.00 | 1 | - |
| spy_price_only | +17.7% (+0.9% to +36.7%) | -31.3% to +24.5% | -2.1% to -0.7% | 0.86 | -19.0% | 1.00 | 1 | - |

Rotation control of sim1: median Sharpe 0.31 (95% -0.63 to 1.17); share at or above the actual 0.38.

**Strategies on LECTURE+TIME+SPACE** (test period 2024-01-01 to 2026-11-03, frozen parameters)

| Strategy | CAGR (95%) | CAGR minus five equal (95%) | CAGR minus SPY with dividends (95%) | Sharpe | Max drawdown | Exposure | Entries | One-session delay: CAGR, Sharpe |
|---|---|---|---|---:|---:|---:|---:|---|
| sim1 | +7.8% (-5.5% to +23.0%) | -43.5% to +18.4% | -28.0% to +4.7% | 0.32 | -16.2% | 0.33 | 299 | +8.5%, 0.37 |
| sim2 | +7.8% (-5.5% to +23.0%) | -43.5% to +18.4% | -28.0% to +4.7% | 0.32 | -16.2% | 0.33 | 299 | +8.5%, 0.37 |
| sim3 | +0.7% (-9.9% to +13.2%) | -51.4% to +11.0% | -36.4% to -1.4% | -0.35 | -13.8% | 0.22 | 233 | +1.8%, -0.24 |
| sim4 | -7.5% (-44.7% to +57.0%) | -93.7% to +63.5% | -71.7% to +43.6% | -0.07 | -54.7% | 0.66 | 261 | -22.3%, -0.45 |
| buy_hold_equal | +17.7% (-12.6% to +56.0%) | - | -26.2% to +30.0% | 0.59 | -26.4% | 1.00 | 5 | - |
| buy_hold_crypto | +11.4% (-40.3% to +100.9%) | -32.2% to +50.0% | -57.1% to +75.4% | 0.39 | -58.6% | 1.00 | 2 | - |
| spy_total_return | +19.0% (+2.0% to +38.4%) | -30.0% to +26.2% | - | 0.93 | -18.8% | 1.00 | 1 | - |
| spy_price_only | +17.7% (+0.9% to +36.7%) | -31.3% to +24.5% | -2.1% to -0.7% | 0.86 | -19.0% | 1.00 | 1 | - |

Rotation control of sim1: median Sharpe 0.46 (95% -0.47 to 1.19); share at or above the actual 0.63.

Benchmark comparison (registered strategy sim3 on LECTURE+TIME+SPACE): CAGR +0.7% against +17.7% (five equal) and +19.0% (SPY with dividends): **not above both**; the rubric's exceptional-returns point is not claimed.

Pullback buying, money-weighted annual return (frozen trigger: prior_month_low):

| Rule | BTC-USD | ETH-USD | GLD | QQQ | SPY | Mean |
|---|---:|---:|---:|---:|---:|---:|
| lump_sum | +20.1% | -3.6% | +27.3% | +20.7% | +19.0% | +16.7% |
| monthly | -0.1% | -13.5% | +20.4% | +17.6% | +16.4% | +8.2% |
| cash | +4.0% | +4.0% | +4.0% | +4.0% | +4.0% | +4.0% |
| atr_1 | +0.2% | -13.4% | +20.1% | +17.7% | +16.4% | +8.2% |
| atr_2 | +0.5% | -13.3% | +20.1% | +17.7% | +16.3% | +8.3% |
| atr_3 | +0.3% | -13.5% | +19.6% | +17.3% | +16.1% | +7.9% |
| prior_month_low (frozen) | -3.9% | -16.7% | +18.7% | +16.1% | +15.5% | +5.9% |

Walk-forward check (exploratory; refitted at the start of each test year on all earlier rows):

| Horizon | AUC LECTURE | AUC +TIME+SPACE | Lift (95%) |
|---|---:|---:|---|
| 5 rows | 0.533 | 0.526 | -0.0075 (-0.0329 to +0.0178) |
| 20 rows | 0.588 | 0.571 | -0.0173 (-0.0470 to +0.0141) |

Reading:

1. **H-2026-016 is not supported.** Adding the time and space features lowered the pooled test AUC by 0.012 (interval −0.039 to +0.016); the criterion needed at least +0.02 with the interval above zero. Neither block helps alone (time −0.018, space −0.005), and refitting every year gives the same answer at 5 and 20 rows. The evaluation is recorded in `registry/evaluations.json`, without editing the registered entry.
2. **The course features carry a weak signal of their own:** pooled test AUC 0.552 against 0.490 on random walks; by instrument from 0.509 (Bitcoin) to 0.556 (GLD). Part of a pooled AUC comes from different base rates between instruments, so the per-instrument figures are the fairer reading.
3. **The validation advantage of the strategies did not survive.** The registered strategy (sim3 on LECTURE+TIME+SPACE) made +0.7% a year against +17.7% for the five instruments held equally and +19.0% for SPY with dividends; the rotation control places sim1's timing at the 38th and 63rd percentile of random timings. This is what step 4 warned: on two years of validation, random walks reached Sharpe ratios of 2. The rubric's exceptional-returns point is not claimed.
4. **Pullback buying lost to buying on arrival and to a lump sum** in a rising market: the frozen trigger (prior month's low) earned a mean money-weighted +5.9% a year against +8.2% for monthly buying and +16.7% for the lump sum; cash earned +4.0%. Waiting for a pullback cost time in the market.
5. **The controls behaved:** on random walks the lift interval contains zero; with the time and space columns shuffled the lift is negative, as columns without information should be.
6. The result is negative and it is published as it is. What the project shows is a pipeline that cannot fool itself: every choice fixed before the test, one logged read, and controls that would have exposed a false edge.

## Rubric map

Where each item of the course rubric is answered, and what is not claimed.

| Criterion | Evidence in this repository | Status |
|---|---|---|
| Problem description | "Problem" above; README release section; specification 0028 | done |
| Data sources | yfinance (5 instruments, 8 reference markets) and FRED (4 series), two modes, fingerprinted store outside Git (step 1, `tsip.capstone.data`) | done |
| Twenty or more features, documented | 122 columns in named sets with a dictionary (step 2) and a no-look-ahead test | done |
| More than one million records | Not met: daily data give 26,759 rows | not claimed |
| Transformations and exploratory analysis | Point-in-time joins with release lags (step 1); notebook section "Exploratory view" | done |
| Models and tuning | Decision tree, random forest, logistic regression and XGBoost tuned on time-ordered folds; selection rule fixed before training (step 3) | done |
| Probability thresholds | Thresholds chosen on validation and frozen (`registry/capstone_choices_h5.json`, step 4) | done |
| Two or more strategies, vector and exact simulation | sim1 to sim5, vector view and an exact account with costs, cash at the bill rate, one-session delay (steps 4 and 5) | done |
| Benchmark with dividends | Five-instrument buy and hold and SPY with dividends (adjusted close), with block-bootstrap intervals | done |
| Stop loss and a new strategy | sim3 (2 ATR stop and a volatility filter); pullback buying with monthly deposits (sim5) | done |
| Deep analysis | Rotation and random-walk controls, validation against test, walk-forward check (steps 4 and 5) | done |
| Exceptional returns | The registered strategy did not beat either benchmark on the test period (step 5) | not claimed |
| Scripts and dependencies | `pyproject.toml` extra `capstone`; one command, `tsip.capstone.run_all`, in two modes | done |
| Incremental data outside GitHub | Data store outside Git with a fingerprinted manifest; steps reuse saved results | done |
| Scheduled run | The public report runs every day in GitHub Actions; the course flow itself is not scheduled | partial |
| Modular code | `src/tsip/capstone/` modules with their tests (`tests/test_capstone_*.py`); the notebook only calls them | done |
| Broker API | `tsip.capstone.paper_order`: orders to Alpaca's paper endpoint only, with simulated money | done (dry run verified; sending needs the founder's paper keys) |
| Container | `Dockerfile`; not built in the environment where this release was prepared | written, not yet built |
| Deployment | The project's public report on GitHub Pages | done |
