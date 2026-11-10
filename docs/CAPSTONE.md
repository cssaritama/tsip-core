# Course project: do time and space improve the prediction of future returns?

Working document of the final project of the Stock Markets Analytics course (specification [0028](../specs/0028-time-space-features-for-return-prediction.md), hypothesis H-2026-016). It is completed step by step; sections not yet built say so. Every figure here names the command that produced it (ADR 0071 of the project's decision record).

## Problem

TSIP describes where price stands in time (calendar coordinates) and in space (against the highs and lows of prior days, weeks, months and quarters). The project tests whether that information improves the out-of-sample prediction of the direction of the next 5 and 20 sessions for SPY, QQQ, GLD, Bitcoin and Ethereum, beyond the course's standard features, and whether a strategy built on the predictions beats buy and hold after costs. The hypothesis and its pass criterion were registered before any model was trained.

## How to run

```sh
pip install -e ".[dev,calendar,capstone]"
python -m tsip.capstone.run_all --mode download --store ~/tsip_capstone_data_new   # steps 1-4 with fresh data, in a new folder
python -m tsip.capstone.run_all --mode file       # the same from the stored copy, no network
python -m tsip.capstone.run_all --mode update --store ~/tsip_capstone_data_new   # only the new days (not on the protected store)
python -m tsip.capstone.run_all --all-families    # adds decision tree, XGBoost and random forest (slower)
jupyter notebook notebooks/capstone.ipynb          # the same flow step by step, with outputs saved
python -m tsip.capstone.evaluate --markdown       # tables of the single test-period read (step 5)
python -m tsip.capstone.paper_order               # paper-trading order example (dry run; --send with paper keys)
docker build -t tsip-capstone .                   # container: the data folder is mounted at /data
docker run --rm -v "$HOME/tsip_capstone_data:/data" tsip-capstone [--mode download]
```

Data are stored in `~/tsip_capstone_data` (override with `TSIP_CAPSTONE_DATA` or `--store`) with a manifest that fingerprints each file; nothing is committed to Git and nothing is copied into the container image. A store whose fingerprint appears in `registry/capstone_test_runs.json` is never overwritten: a fresh download goes to another folder, so the registered test read stays reproducible. The notebook is rebuilt with `python tools/build_capstone_notebook.py` and executed with `python -m nbconvert --to notebook --execute --inplace notebooks/capstone.ipynb`.

## Data (step 1)

Sources: yfinance daily prices for the five instruments and eight reference markets (S&P 500, Nasdaq-100, DAX, gold and oil futures, Bitcoin, VIX); FRED public CSV for the 10-year yield (DGS10), the 3-month bill (DTB3), the federal funds rate (FEDFUNDS) and CPI (CPIAUCSL).

Rules that keep every row honest: reference closes come only from earlier dates (markets close at different hours); macro values are used only after a conservative release lag (daily rates from the next day, federal funds 3 days and CPI 20 days after the month ends); bars dated on or after the download's UTC date are dropped because they may still be open.

First download, 2026-11-10 00:37 UTC (`python -m tsip.capstone.data --mode download` on the founder's computer; read back with `--mode file` using the code of commit `5343d97`, which added this document):

| Item | Value |
|---|---|
| Source rows | 71,800 prices, 36,226 FRED observations |
| Unified frame | 26,759 rows, 20 columns, 2000-01-03 to 2026-11-09 |
| Rows by instrument | SPY 6,754 · QQQ 6,754 · GLD 5,528 · Bitcoin 4,436 · Ethereum 3,287 |

### Second source: Coinbase (Bitcoin and Ether)

`python -m tsip.capstone.extra_sources download` adds Coinbase's public daily candles (no key) for Bitcoin and Ether, stored in `<store>/coinbase/` with their own fingerprinted manifest; `run_all` fetches them in download and update modes. They give what the aggregate does not: one exchange's own close and volume. Three features come from them, each known at that day's close: `cb_premium_bps` (Coinbase close over the aggregate close), `cb_volume_share` (Coinbase's share of the aggregate dollar volume) and `cb_volume_share_change_20d`. The two sources are cross-checked against each other. The features are exploratory and not used by the registered models; `python -m tsip.capstone.extra_sources --markdown` prints the cross-check and their correlation with the target (tables in "Exploratory analysis and diagnostics" once downloaded).

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

## Reproducibility: a second, independent download

The founder ran `python -m tsip.capstone.run_all --mode download --store <new folder>` on his computer on 2026-11-10 (steps 1 to 4 from scratch on fresh data). `python -m tsip.capstone.reproduce <first store> <second store> --markdown` compares the two:

Downloads: 2026-11-10T00:37:33+00:00 (71,800 price rows) and 2026-11-10T13:21:20+00:00 (71,808 price rows). Largest validation AUC difference: 0.0007.

| Horizon | Feature set | AUC, first | AUC, second | Difference |
|---|---|---:|---:|---:|
| 5 | LECTURE | 0.5549 | 0.5545 | -0.0004 |
| 5 | LECTURE+TIME | 0.5609 | 0.5607 | -0.0001 |
| 5 | LECTURE+SPACE | 0.5477 | 0.5481 | +0.0004 |
| 5 | LECTURE+TIME+SPACE | 0.5533 | 0.5538 | +0.0004 |
| 20 | LECTURE | 0.5448 | 0.5453 | +0.0005 |
| 20 | LECTURE+TIME | 0.5396 | 0.5395 | -0.0001 |
| 20 | LECTURE+SPACE | 0.5418 | 0.5417 | -0.0001 |
| 20 | LECTURE+TIME+SPACE | 0.5329 | 0.5335 | +0.0007 |

| Feature set | Strategy | Chosen, first | Chosen, second | Same choice |
|---|---|---|---|---|
| LECTURE | sim1 | quantile 0.9000, threshold 0.5598 | quantile 0.9000, threshold 0.5573 | yes |
| LECTURE | sim2 | quantile 0.9000, threshold 0.5598, k 5 | quantile 0.5000, threshold 0.4597, k 3 | **no** |
| LECTURE | sim3 | threshold 0.5598, stop_atr 2.0000 | threshold 0.5573, stop_atr 2.0000 | yes |
| LECTURE | sim4 | quantile 0.9000, upper 0.5373, lower 0.3299 | quantile 0.9000, upper 0.5350, lower 0.3289 | yes |
| LECTURE+TIME+SPACE | sim1 | quantile 0.5000, threshold 0.4485 | quantile 0.5000, threshold 0.4487 | yes |
| LECTURE+TIME+SPACE | sim2 | quantile 0.5000, threshold 0.4485, k 5 | quantile 0.5000, threshold 0.4487, k 5 | yes |
| LECTURE+TIME+SPACE | sim3 | threshold 0.4485, stop_atr 2.0000 | threshold 0.4487, stop_atr 2.0000 | yes |
| LECTURE+TIME+SPACE | sim4 | quantile 0.7000, upper 0.4897, lower 0.3821 | quantile 0.7000, upper 0.4901, lower 0.3821 | yes |

Strategy carried to the test period: sim3 on LECTURE+TIME+SPACE (validation Sharpe 1.79) and sim3 on LECTURE+TIME+SPACE (1.95); pullback trigger prior_month_low and prior_month_low.

Reading: the models reproduce to the fourth decimal, and the strategy carried to the test period and the pullback trigger are the same. One validation choice flipped (sim2 on the course features) and the validation Sharpe ratio of sim3 moved from 1.79 to 1.95 with data revisions this small: validation choices among close alternatives are fragile, which agrees with what the test period showed. The registered test read used the first store, which is protected from being overwritten.

## A second study: when to buy with a fixed monthly budget

Founder's question after step 5, fixed before any figure in specification 0029 with hypothesis H-2026-017 (commit `f874ded`); code and tests committed before the first real run; choices frozen on the development period (commit `5b96f02`); one logged confirmation (`registry/capstone_test_runs.json`, kind `timing_confirmation`). Every rule buys once a month, so all rules invest the same money; the statistic is the price paid against the month's average adjusted close, the expected price of a random session of the month.

```sh
python -m tsip.capstone.timing develop      # development: all variants, choices frozen
python -m tsip.capstone.timing confirm      # single logged confirmation and the random-walk run
python -m tsip.capstone.timing --markdown   # the tables below
```

**Development** (mean price advantage against a random session of the month; for B2 and B4 the chosen variant, listed in `registry/capstone_timing_choices.json`)

| Instrument | Months | B1 best day | B2 | B3 | B4 | B5 | B6 | B7 | First session | Last session |
|---|---:|---|---|---|---|---|---|---|---|---|
| SPY | 191 | Tue +0.05% | +0.31% | -0.00% | +0.09% | +0.16% | -0.01% | +0.18% | -0.01% | -0.14% |
| QQQ | 191 | Tue +0.05% | +0.12% | +0.34% | +0.42% | -0.17% | -0.02% | +0.15% | -0.02% | +0.07% |
| GLD | 133 | Thu +0.22% | -0.22% | +0.31% | -0.05% | +0.41% | +0.18% | -0.08% | +0.18% | -0.39% |
| BTC-USD | 63 | Mon +1.09% | +0.65% | +2.23% | -0.68% | -0.52% | +1.99% | -1.52% | +1.99% | -2.05% |
| ETH-USD | 25 | Wed -1.03% | +0.26% | +3.72% | +3.28% | -2.99% | -2.50% | +0.40% | -2.50% | +3.03% |

**Confirmation** (59 tests, Benjamini–Hochberg across all; passes: mean advantage at least 0.20% and q below 0.05)

| Instrument | Test | Rule | Months | Mean advantage (95%) | Share of months positive | Wealth vs random | q | Passes |
|---|---|---|---:|---|---:|---:|---:|---|
| SPY | B1_Mon | weekday Mon | 130 | +0.39% (-0.07% to +0.87%) | 67% | +0.30% | 0.183 | no |
| SPY | B1_Tue | weekday Tue | 130 | +0.39% (-0.04% to +0.78%) | 70% | +0.37% | 0.150 | no |
| SPY | B1_Wed | weekday Wed | 130 | +0.33% (-0.09% to +0.71%) | 69% | +0.33% | 0.184 | no |
| SPY | B1_Thu | weekday Thu | 130 | +0.40% (+0.02% to +0.71%) | 64% | +0.41% | 0.047 | yes |
| SPY | B1_Fri | weekday Fri | 130 | +0.37% (+0.07% to +0.65%) | 63% | +0.36% | 0.059 | no |
| SPY | B2 | after fall (k 1.0, buy next) | 130 | -0.28% (-0.69% to +0.11%) | 46% | -0.38% | 1.000 | no |
| SPY | B3 | high range | 130 | -0.00% (-0.37% to +0.35%) | 49% | -0.01% | 0.686 | no |
| SPY | B4 | prior low (horizon quarter, d 0.5) | 130 | -0.45% (-0.75% to -0.13%) | 35% | -0.44% | 1.000 | no |
| SPY | B5 | fvg | 130 | +0.60% (+0.33% to +0.88%) | 69% | +0.59% | 0.015 | yes |
| SPY | B6 | month low session (session 0) | 130 | +0.52% (+0.10% to +0.92%) | 69% | +0.48% | 0.047 | yes |
| SPY | B7 | below month open | 130 | -0.07% (-0.40% to +0.26%) | 50% | -0.09% | 0.838 | no |
| QQQ | B1_Mon | weekday Mon | 130 | +0.50% (-0.11% to +1.06%) | 68% | +0.37% | 0.183 | no |
| QQQ | B1_Tue | weekday Tue | 130 | +0.43% (-0.15% to +0.95%) | 64% | +0.42% | 0.184 | no |
| QQQ | B1_Wed | weekday Wed | 130 | +0.42% (-0.18% to +0.96%) | 65% | +0.42% | 0.197 | no |
| QQQ | B1_Thu | weekday Thu | 130 | +0.56% (+0.09% to +0.98%) | 63% | +0.60% | 0.047 | yes |
| QQQ | B1_Fri | weekday Fri | 130 | +0.60% (+0.24% to +0.96%) | 62% | +0.62% | 0.015 | yes |
| QQQ | B2 | after fall (k 1.5, buy same) | 130 | -0.71% (-1.12% to -0.33%) | 40% | -0.78% | 1.000 | no |
| QQQ | B3 | high range | 130 | -0.43% (-0.94% to +0.05%) | 45% | -0.39% | 1.000 | no |
| QQQ | B4 | prior low (horizon quarter, d 0.25) | 130 | -0.49% (-0.91% to -0.06%) | 37% | -0.53% | 1.000 | no |
| QQQ | B5 | fvg | 130 | +0.51% (+0.05% to +0.95%) | 65% | +0.40% | 0.079 | no |
| QQQ | B6 | month low session (session 0) | 130 | +0.62% (+0.03% to +1.17%) | 67% | +0.57% | 0.070 | no |
| QQQ | B7 | below month open | 130 | -0.05% (-0.46% to +0.37%) | 51% | -0.06% | 0.777 | no |
| GLD | B1_Mon | weekday Mon | 130 | +0.43% (+0.03% to +0.83%) | 58% | +0.33% | 0.106 | no |
| GLD | B1_Tue | weekday Tue | 130 | +0.32% (-0.03% to +0.69%) | 58% | +0.26% | 0.183 | no |
| GLD | B1_Wed | weekday Wed | 130 | +0.32% (-0.05% to +0.69%) | 58% | +0.29% | 0.183 | no |
| GLD | B1_Thu | weekday Thu | 130 | +0.31% (-0.08% to +0.71%) | 56% | +0.26% | 0.194 | no |
| GLD | B1_Fri | weekday Fri | 130 | +0.31% (-0.08% to +0.69%) | 58% | +0.22% | 0.197 | no |
| GLD | B2 | after fall (k 1.0, buy same) | 130 | +0.02% (-0.24% to +0.26%) | 49% | +0.05% | 0.667 | no |
| GLD | B3 | high range | 130 | +0.20% (-0.19% to +0.64%) | 51% | +0.06% | 0.402 | no |
| GLD | B4 | prior low (horizon month, d 0.25) | 130 | +0.11% (-0.23% to +0.44%) | 55% | +0.19% | 0.523 | no |
| GLD | B5 | fvg | 130 | +0.35% (-0.01% to +0.71%) | 58% | +0.33% | 0.129 | no |
| GLD | B6 | month low session (session 0) | 130 | +0.51% (+0.09% to +0.93%) | 58% | +0.45% | 0.070 | no |
| GLD | B7 | below month open | 130 | -0.21% (-0.53% to +0.08%) | 51% | -0.18% | 1.000 | no |
| BTC-USD | B1_Mon | weekday Mon | 82 | +0.56% (-2.03% to +2.99%) | 54% | +0.34% | 0.571 | no |
| BTC-USD | B1_Tue | weekday Tue | 82 | +0.63% (-1.80% to +2.77%) | 59% | -0.05% | 0.539 | no |
| BTC-USD | B1_Wed | weekday Wed | 82 | +0.41% (-1.77% to +2.27%) | 52% | +0.29% | 0.572 | no |
| BTC-USD | B1_Thu | weekday Thu | 82 | +0.31% (-1.70% to +2.04%) | 49% | -0.14% | 0.604 | no |
| BTC-USD | B1_Fri | weekday Fri | 82 | +1.32% (-0.84% to +3.32%) | 57% | +0.85% | 0.287 | no |
| BTC-USD | B1_Sat | weekday Sat | 82 | +1.17% (-1.01% to +3.13%) | 59% | +0.90% | 0.348 | no |
| BTC-USD | B1_Sun | weekday Sun | 82 | +0.96% (-1.47% to +3.12%) | 59% | +1.31% | 0.465 | no |
| BTC-USD | B2 | after fall (k 1.0, buy next) | 82 | -2.26% (-3.78% to -0.81%) | 43% | -2.14% | 1.000 | no |
| BTC-USD | B3 | high range | 82 | -0.49% (-2.51% to +1.51%) | 43% | -2.57% | 0.856 | no |
| BTC-USD | B4 | prior low (horizon month, d 0.25) | 82 | -1.89% (-3.91% to +0.15%) | 49% | -3.50% | 1.000 | no |
| BTC-USD | B5 | fvg | 82 | +0.46% (-1.23% to +2.12%) | 52% | +0.38% | 0.539 | no |
| BTC-USD | B6 | month low session (session 0) | 82 | +0.88% (-1.68% to +3.16%) | 56% | +0.89% | 0.469 | no |
| BTC-USD | B7 | below month open | 82 | -1.01% (-2.71% to +0.64%) | 50% | -2.00% | 1.000 | no |
| ETH-USD | B1_Mon | weekday Mon | 82 | +0.08% (-2.79% to +2.73%) | 55% | +0.29% | 0.667 | no |
| ETH-USD | B1_Tue | weekday Tue | 82 | +0.08% (-2.55% to +2.27%) | 52% | +0.01% | 0.667 | no |
| ETH-USD | B1_Wed | weekday Wed | 82 | -0.20% (-2.72% to +1.95%) | 48% | +1.82% | 0.738 | no |
| ETH-USD | B1_Thu | weekday Thu | 82 | +0.06% (-2.21% to +1.91%) | 54% | +1.41% | 0.667 | no |
| ETH-USD | B1_Fri | weekday Fri | 82 | +1.00% (-1.54% to +3.38%) | 52% | +1.44% | 0.465 | no |
| ETH-USD | B1_Sat | weekday Sat | 82 | +0.78% (-1.99% to +3.48%) | 52% | +2.63% | 0.539 | no |
| ETH-USD | B1_Sun | weekday Sun | 82 | +0.55% (-2.26% to +3.13%) | 52% | +2.77% | 0.572 | no |
| ETH-USD | B2 | after fall (k 2.0, buy same) | 82 | -2.26% (-4.69% to -0.07%) | 46% | -6.50% | 1.000 | no |
| ETH-USD | B3 | high range | 82 | +0.13% (-2.13% to +2.80%) | 51% | -2.15% | 0.667 | no |
| ETH-USD | B4 | prior low (horizon quarter, d 0.25) | 82 | -1.79% (-3.78% to +0.10%) | 48% | -2.54% | 1.000 | no |
| ETH-USD | B5 | fvg | 82 | -0.14% (-2.43% to +1.73%) | 51% | +1.35% | 0.731 | no |
| ETH-USD | B6 | month low session (session 0) | 82 | +0.71% (-2.35% to +3.64%) | 55% | +3.23% | 0.539 | no |
| ETH-USD | B7 | below month open | 82 | -2.23% (-4.28% to -0.27%) | 50% | -6.13% | 1.000 | no |

| Instrument | Reference | Mean advantage (95%) |
|---|---|---|
| SPY | first session | +0.52% (+0.10% to +0.92%) |
| SPY | last session | -0.47% (-0.74% to -0.17%) |
| QQQ | first session | +0.62% (+0.03% to +1.17%) |
| QQQ | last session | -0.65% (-1.04% to -0.24%) |
| GLD | first session | +0.51% (+0.09% to +0.93%) |
| GLD | last session | -0.18% (-0.54% to +0.19%) |
| BTC-USD | first session | +0.88% (-1.68% to +3.16%) |
| BTC-USD | last session | -1.45% (-3.53% to +0.48%) |
| ETH-USD | first session | +0.71% (-2.35% to +3.64%) |
| ETH-USD | last session | -1.64% (-3.98% to +0.58%) |

Random walks: 3 of 59 tests pass.

H-2026-017 by instrument: SPY **not supported** (B1_Thu, B5, B6); QQQ **not supported** (B1_Thu, B1_Fri); GLD **not supported**; BTC-USD **not supported**; ETH-USD **not supported**.

Reading:

1. **H-2026-017 is not supported** for any instrument under its registered criterion: some rules pass on real prices (SPY: first Thursday, fair value gap, first session; QQQ: first Thursday and Friday), but three tests also pass on random walks.
2. **The control was not drift-neutral, and the random walks showed it.** On prices that rise on average, the month's average is above its first sessions, so any rule that tends to buy early looks cheaper and any rule that waits looks dearer. The first and last sessions of the month show the same mirror pattern on real prices and on random walks with the same drift. The rules that passed all buy early in the month; the rules that wait for a fall, a prior low or a drop below the month's open paid more than a random session, and the ones that waited most paid most.
3. **What a monthly buyer can take from it:** in rising markets, waiting costs about the drift of the days waited, and no timing rule tested here recovered that cost once the drift is accounted for. The same lesson came from step 5, where buying on arrival and the lump sum beat waiting for pullbacks.
4. **Limits:** the development periods are short for crypto (63 months for Bitcoin and 25 for Ethereum); B6 chose the first session of the month for every instrument (the month's low formed most often on its first session in development), so it repeats the first-session reference.
5. **Next question, to pre-register before any figure:** the same rules against a drift-neutral control (random sessions drawn at the same positions in the month as the rule's purchases, or prices detrended within the month).

## A third look: the same rules against a drift-neutral control

Repair of the second study, fixed before any figure in specification 0030 with hypothesis H-2026-018 (commit `fe1bd20`); code and tests committed before the run; one logged run (kind `timing_matched`). The rules and their parameters are the frozen ones of the second study; only the control changes: each rule is compared with random sessions taken at the same positions in the month as its own purchases, so buying early or late earns nothing by itself. These months had already been read with the first control, so this is a re-analysis, not an independent test.

```sh
python -m tsip.capstone.timing confirm-matched   # single logged run with the drift-neutral control
python -m tsip.capstone.timing --markdown        # all timing tables, this one last
```

**Confirmation, control: matched position** (59 tests, Benjamini–Hochberg across all; passes: mean advantage at least 0.20% and q below 0.05)

| Instrument | Test | Rule | Months | Mean advantage (95%) | Share of months positive | Wealth vs random | q | Passes |
|---|---|---|---:|---|---:|---:|---:|---|
| SPY | B1_Mon | weekday Mon | 130 | +0.00% (-0.21% to +0.23%) | 42% | +0.30% | 1.000 | no |
| SPY | B1_Tue | weekday Tue | 130 | -0.03% (-0.16% to +0.10%) | 57% | +0.37% | 1.000 | no |
| SPY | B1_Wed | weekday Wed | 130 | -0.06% (-0.21% to +0.07%) | 52% | +0.33% | 1.000 | no |
| SPY | B1_Thu | weekday Thu | 130 | +0.02% (-0.15% to +0.17%) | 55% | +0.41% | 1.000 | no |
| SPY | B1_Fri | weekday Fri | 130 | +0.02% (-0.16% to +0.19%) | 44% | +0.36% | 1.000 | no |
| SPY | B2 | after fall (k 1.0, buy next) | 130 | -0.27% (-0.70% to +0.12%) | 47% | -0.38% | 1.000 | no |
| SPY | B3 | high range | 130 | +0.02% (-0.32% to +0.32%) | 48% | -0.01% | 1.000 | no |
| SPY | B4 | prior low (horizon quarter, d 0.5) | 130 | -0.07% (-0.26% to +0.11%) | 33% | -0.44% | 1.000 | no |
| SPY | B5 | fvg | 130 | +0.29% (+0.01% to +0.60%) | 54% | +0.59% | 0.841 | no |
| SPY | B6 | month low session (session 0) | 130 | +0.00% (+0.00% to +0.00%) | 0% | +0.48% | 1.000 | no |
| SPY | B7 | below month open | 130 | +0.05% (-0.25% to +0.35%) | 49% | -0.09% | 1.000 | no |
| QQQ | B1_Mon | weekday Mon | 130 | -0.01% (-0.27% to +0.26%) | 44% | +0.37% | 1.000 | no |
| QQQ | B1_Tue | weekday Tue | 130 | -0.11% (-0.27% to +0.05%) | 52% | +0.42% | 1.000 | no |
| QQQ | B1_Wed | weekday Wed | 130 | -0.10% (-0.30% to +0.09%) | 46% | +0.42% | 1.000 | no |
| QQQ | B1_Thu | weekday Thu | 130 | +0.04% (-0.18% to +0.24%) | 55% | +0.60% | 1.000 | no |
| QQQ | B1_Fri | weekday Fri | 130 | +0.13% (-0.11% to +0.34%) | 46% | +0.62% | 1.000 | no |
| QQQ | B2 | after fall (k 1.5, buy same) | 130 | -0.40% (-0.80% to -0.03%) | 38% | -0.78% | 1.000 | no |
| QQQ | B3 | high range | 130 | -0.48% (-0.95% to -0.04%) | 43% | -0.39% | 1.000 | no |
| QQQ | B4 | prior low (horizon quarter, d 0.25) | 130 | +0.03% (-0.20% to +0.28%) | 38% | -0.53% | 1.000 | no |
| QQQ | B5 | fvg | 130 | +0.12% (-0.19% to +0.43%) | 52% | +0.40% | 1.000 | no |
| QQQ | B6 | month low session (session 0) | 130 | +0.00% (+0.00% to +0.00%) | 0% | +0.57% | 1.000 | no |
| QQQ | B7 | below month open | 130 | +0.04% (-0.30% to +0.38%) | 52% | -0.06% | 1.000 | no |
| GLD | B1_Mon | weekday Mon | 130 | +0.06% (-0.11% to +0.24%) | 54% | +0.33% | 1.000 | no |
| GLD | B1_Tue | weekday Tue | 130 | -0.04% (-0.19% to +0.11%) | 49% | +0.26% | 1.000 | no |
| GLD | B1_Wed | weekday Wed | 130 | -0.01% (-0.18% to +0.15%) | 55% | +0.29% | 1.000 | no |
| GLD | B1_Thu | weekday Thu | 130 | +0.01% (-0.15% to +0.16%) | 48% | +0.26% | 1.000 | no |
| GLD | B1_Fri | weekday Fri | 130 | -0.01% (-0.16% to +0.15%) | 48% | +0.22% | 1.000 | no |
| GLD | B2 | after fall (k 1.0, buy same) | 130 | -0.10% (-0.36% to +0.12%) | 48% | +0.05% | 1.000 | no |
| GLD | B3 | high range | 130 | +0.04% (-0.29% to +0.39%) | 49% | +0.06% | 1.000 | no |
| GLD | B4 | prior low (horizon month, d 0.25) | 130 | +0.12% (-0.18% to +0.43%) | 52% | +0.19% | 1.000 | no |
| GLD | B5 | fvg | 130 | +0.07% (-0.17% to +0.30%) | 58% | +0.33% | 1.000 | no |
| GLD | B6 | month low session (session 0) | 130 | +0.00% (+0.00% to +0.00%) | 0% | +0.45% | 1.000 | no |
| GLD | B7 | below month open | 130 | -0.22% (-0.48% to +0.04%) | 42% | -0.18% | 1.000 | no |
| BTC-USD | B1_Mon | weekday Mon | 82 | -0.10% (-0.92% to +0.70%) | 50% | +0.34% | 1.000 | no |
| BTC-USD | B1_Tue | weekday Tue | 82 | -0.13% (-0.73% to +0.53%) | 50% | -0.05% | 1.000 | no |
| BTC-USD | B1_Wed | weekday Wed | 82 | -0.41% (-1.00% to +0.15%) | 44% | +0.29% | 1.000 | no |
| BTC-USD | B1_Thu | weekday Thu | 82 | -0.52% (-1.30% to +0.28%) | 50% | -0.14% | 1.000 | no |
| BTC-USD | B1_Fri | weekday Fri | 82 | +0.55% (+0.07% to +1.05%) | 59% | +0.85% | 0.767 | no |
| BTC-USD | B1_Sat | weekday Sat | 82 | +0.40% (-0.03% to +0.85%) | 59% | +0.90% | 0.865 | no |
| BTC-USD | B1_Sun | weekday Sun | 82 | +0.22% (-0.27% to +0.74%) | 52% | +1.31% | 1.000 | no |
| BTC-USD | B2 | after fall (k 1.0, buy next) | 82 | -2.31% (-3.74% to -0.91%) | 44% | -2.14% | 1.000 | no |
| BTC-USD | B3 | high range | 82 | -0.42% (-2.16% to +1.39%) | 39% | -2.57% | 1.000 | no |
| BTC-USD | B4 | prior low (horizon month, d 0.25) | 82 | -1.10% (-2.63% to +0.63%) | 46% | -3.50% | 1.000 | no |
| BTC-USD | B5 | fvg | 82 | +0.01% (-0.69% to +0.66%) | 52% | +0.38% | 1.000 | no |
| BTC-USD | B6 | month low session (session 0) | 82 | +0.00% (+0.00% to +0.00%) | 0% | +0.89% | 1.000 | no |
| BTC-USD | B7 | below month open | 82 | -0.74% (-1.89% to +0.43%) | 52% | -2.00% | 1.000 | no |
| ETH-USD | B1_Mon | weekday Mon | 82 | -0.19% (-1.18% to +0.77%) | 46% | +0.29% | 1.000 | no |
| ETH-USD | B1_Tue | weekday Tue | 82 | -0.26% (-1.17% to +0.63%) | 49% | +0.01% | 1.000 | no |
| ETH-USD | B1_Wed | weekday Wed | 82 | -0.64% (-1.57% to +0.26%) | 43% | +1.82% | 1.000 | no |
| ETH-USD | B1_Thu | weekday Thu | 82 | -0.43% (-1.45% to +0.59%) | 50% | +1.41% | 1.000 | no |
| ETH-USD | B1_Fri | weekday Fri | 82 | +0.69% (-0.17% to +1.52%) | 63% | +1.44% | 0.937 | no |
| ETH-USD | B1_Sat | weekday Sat | 82 | +0.53% (-0.39% to +1.41%) | 60% | +2.63% | 1.000 | no |
| ETH-USD | B1_Sun | weekday Sun | 82 | +0.30% (-0.40% to +0.99%) | 52% | +2.77% | 1.000 | no |
| ETH-USD | B2 | after fall (k 2.0, buy same) | 82 | -1.05% (-2.32% to +0.07%) | 44% | -6.50% | 1.000 | no |
| ETH-USD | B3 | high range | 82 | +0.32% (-1.89% to +2.94%) | 54% | -2.15% | 1.000 | no |
| ETH-USD | B4 | prior low (horizon quarter, d 0.25) | 82 | -0.43% (-1.56% to +0.72%) | 46% | -2.54% | 1.000 | no |
| ETH-USD | B5 | fvg | 82 | -0.30% (-1.91% to +1.21%) | 59% | +1.35% | 1.000 | no |
| ETH-USD | B6 | month low session (session 0) | 82 | +0.00% (+0.00% to +0.00%) | 0% | +3.23% | 1.000 | no |
| ETH-USD | B7 | below month open | 82 | -1.65% (-3.22% to -0.10%) | 55% | -6.13% | 1.000 | no |

| Instrument | Reference | Mean advantage (95%) |
|---|---|---|
| SPY | first session | +0.00% (+0.00% to +0.00%) |
| SPY | last session | -0.03% (-0.12% to +0.07%) |
| QQQ | first session | +0.00% (+0.00% to +0.00%) |
| QQQ | last session | -0.07% (-0.21% to +0.07%) |
| GLD | first session | +0.00% (+0.00% to +0.00%) |
| GLD | last session | +0.02% (-0.05% to +0.11%) |
| BTC-USD | first session | +0.00% (+0.00% to +0.00%) |
| BTC-USD | last session | +0.08% (-0.06% to +0.22%) |
| ETH-USD | first session | +0.00% (+0.00% to +0.00%) |
| ETH-USD | last session | -0.06% (-0.38% to +0.19%) |

Random walks: 1 of 59 tests pass.

H-2026-018 by instrument: SPY **not supported**; QQQ **not supported**; GLD **not supported**; BTC-USD **not supported**; ETH-USD **not supported**.

Reading:

1. **H-2026-018 is not supported.** Once the drift is neutralised, no rule buys at a significantly better price than a random session at the same point of the month, on any instrument; the advantages that looked significant in the second study were the drift.
2. **The first session scores exactly zero**, as the control requires, and the last session is close to zero: the timing within the month carries no price advantage of its own here.
3. **One test passed on random walks** (a first Tuesday on simulated QQQ). With 59 tests, a chance rejection on data without information happens about once in twenty runs; a check with a single random-walk seed cannot tell chance from a flawed control. The next version uses several seeds and compares the pass rate with the nominal rate.
4. **For a monthly buyer:** buy when the money arrives. Neither the weekday, nor a fall, nor a prior low, nor a fair value gap, nor the usual session of the monthly low gave a better price than chance in these markets, and every rule that waits pays the drift.

## Exploratory analysis and diagnostics

Descriptive and exploratory: nothing here changes a registered result. The correlations use training and validation rows only; the diagnostics use the test predictions saved by the registered run. All four model families of step 3 were regenerated on 2026-11-10 with `run_models fit` and reproduce the step 3 tables exactly.

```sh
python -m tsip.capstone.analysis --markdown
```

**Correlation with the return of the next 5 rows** (Spearman, training and validation rows, 15 strongest)

| Feature | Set | Spearman | Rows |
|---|---|---:|---:|
| `macro_ten_year_yield` | LECTURE | -0.063 | 22,522 |
| `growth_btc_usd_30d` | LECTURE | +0.062 | 12,521 |
| `macro_cpi_yoy` | LECTURE | -0.052 | 21,035 |
| `growth_wti_oil_7d` | LECTURE | -0.052 | 22,167 |
| `growth_btc_usd_90d` | LECTURE | +0.049 | 12,278 |
| `growth_wti_oil_365d` | LECTURE | -0.047 | 20,709 |
| `growth_brent_oil_365d` | LECTURE | -0.045 | 16,553 |
| `session_of_month` | TIME | +0.044 | 22,522 |
| `space_month_untested_below_age` | SPACE | +0.043 | 21,120 |
| `growth_brent_oil_7d` | LECTURE | -0.043 | 18,010 |
| `macro_tbill_3m_change_30d` | LECTURE | -0.042 | 22,399 |
| `macro_ten_year_yield_change_30d` | LECTURE | -0.041 | 22,399 |
| `week_of_month` | TIME | +0.040 | 22,522 |
| `ln_volume` | LECTURE | +0.040 | 22,522 |
| `day_of_month` | TIME | +0.039 | 22,522 |

**Correlation with the return of the next 20 rows** (Spearman, training and validation rows, 15 strongest)

| Feature | Set | Spearman | Rows |
|---|---|---:|---:|
| `growth_wti_oil_365d` | LECTURE | -0.110 | 20,709 |
| `growth_brent_oil_365d` | LECTURE | -0.109 | 16,553 |
| `macro_cpi_yoy` | LECTURE | -0.104 | 21,035 |
| `macro_tbill_3m_change_30d` | LECTURE | -0.096 | 22,399 |
| `macro_ten_year_yield` | LECTURE | -0.094 | 22,522 |
| `growth_btc_usd_30d` | LECTURE | +0.089 | 12,521 |
| `growth_btc_usd_90d` | LECTURE | +0.083 | 12,278 |
| `growth_btc_usd_7d` | LECTURE | +0.069 | 12,618 |
| `macro_ten_year_yield_change_30d` | LECTURE | -0.059 | 22,399 |
| `ma_ratio_200` | LECTURE | +0.057 | 21,527 |
| `ln_volume` | LECTURE | +0.053 | 22,522 |
| `macro_cpi` | LECTURE | +0.050 | 22,522 |
| `macro_tbill_3m` | LECTURE | -0.048 | 22,522 |
| `growth_brent_oil_30d` | LECTURE | +0.046 | 17,913 |
| `space_month_untested_below_age` | SPACE | +0.044 | 21,120 |

**Vector view, approximate return on capital** (bets of 100; total net over the capital needed)

| Period | Feature set | Bets | Hit rate | Total net | Capital needed | Return on capital |
|---|---|---:|---:|---:|---:|---:|
| validation | LECTURE | 294 | 55.1% | +241 | 3,200 | +7.5% |
| validation | LECTURE+TIME+SPACE | 1,469 | 55.5% | +769 | 3,400 | +22.6% |
| test | LECTURE | 238 | 63.0% | +262 | 3,400 | +7.7% |
| test | LECTURE+TIME+SPACE | 1,328 | 56.7% | +463 | 3,400 | +13.6% |

**Test period by instrument** (direction of the next 5 rows; precision of the 10% most confident calls, cut fixed on the whole test set; exploratory)

| Instrument | Rows | Base rate | AUC LECTURE | AUC +TIME+SPACE | Precision top decile LECTURE (rows) | Precision top decile +TIME+SPACE (rows) |
|---|---:|---:|---:|---:|---|---|
| BTC-USD | 1038 | 51.3% | 0.509 | 0.515 | 57.9% (38) | 58.2% (55) |
| ETH-USD | 1038 | 49.3% | 0.514 | 0.526 | 53.8% (52) | 48.5% (101) |
| GLD | 712 | 60.1% | 0.556 | 0.568 | 76.1% (46) | 68.9% (45) |
| QQQ | 712 | 58.6% | 0.536 | 0.515 | 63.4% (131) | 59.0% (100) |
| SPY | 712 | 60.8% | 0.554 | 0.523 | 65.8% (155) | 66.1% (121) |

**Test period by month of the year** (direction of the next 5 rows; precision of the 10% most confident calls, cut fixed on the whole test set; exploratory)

| Month of the year | Rows | Base rate | AUC LECTURE | AUC +TIME+SPACE | Precision top decile LECTURE (rows) | Precision top decile +TIME+SPACE (rows) |
|---|---:|---:|---:|---:|---|---|
| 1 | 369 | 53.1% | 0.660 | 0.546 | 85.0% (20) | 62.8% (43) |
| 2 | 344 | 58.1% | 0.643 | 0.661 | 68.2% (22) | 65.5% (29) |
| 3 | 375 | 52.0% | 0.466 | 0.427 | 44.9% (118) | 43.7% (71) |
| 4 | 372 | 62.9% | 0.592 | 0.642 | 80.7% (83) | 76.3% (93) |
| 5 | 375 | 55.5% | 0.484 | 0.510 | 74.3% (35) | 78.6% (14) |
| 6 | 360 | 49.7% | 0.727 | 0.767 | 100.0% (19) | 100.0% (9) |
| 7 | 384 | 54.2% | 0.443 | 0.469 | 46.2% (26) | 59.6% (47) |
| 8 | 378 | 55.3% | 0.553 | 0.528 | 70.0% (20) | 47.4% (19) |
| 9 | 366 | 65.6% | 0.550 | 0.538 | 78.6% (42) | 88.2% (17) |
| 10 | 390 | 42.3% | 0.479 | 0.431 | 35.7% (28) | 34.4% (64) |
| 11 | 246 | 58.5% | 0.537 | 0.542 | 37.5% (8) | 60.0% (15) |
| 12 | 253 | 56.9% | 0.525 | 0.642 | 100.0% (1) | 0.0% (1) |

**Wrong predictions** (LECTURE+TIME+SPACE): error rate 52.5%. Share of the 10% most confident errors by instrument: BTC-USD 43%, ETH-USD 38%, GLD 11%, QQQ 4%, SPY 4%; by year: 2024 30%, 2025 34%, 2026 35%.

Calibration (mean predicted probability against the base rate): BTC-USD 37.7% against 51.3%; ETH-USD 39.2% against 49.3%; GLD 40.2% against 60.1%; QQQ 44.6% against 58.6%; SPY 45.4% against 60.8%.

| Date | Instrument | Probability | Outcome (positive 5 rows) | Return of the next 5 rows |
|---|---|---:|---:|---:|
| 2025-05-08 | ETH-USD | 0.145 | 1 | +21.5% |
| 2026-08-22 | ETH-USD | 0.156 | 1 | +3.6% |
| 2026-03-01 | ETH-USD | 0.173 | 1 | +2.0% |
| 2026-03-07 | ETH-USD | 0.175 | 1 | +5.3% |
| 2026-03-07 | BTC-USD | 0.176 | 1 | +4.8% |
| 2025-05-24 | ETH-USD | 0.183 | 1 | +4.0% |
| 2025-05-11 | ETH-USD | 0.185 | 1 | +1.0% |
| 2026-03-06 | BTC-USD | 0.187 | 1 | +3.0% |
| 2026-03-06 | ETH-USD | 0.188 | 1 | +3.7% |
| 2026-03-08 | BTC-USD | 0.188 | 1 | +7.6% |

Reading:

1. **What correlates with future returns** (training and validation rows): macro levels and changes (the 10-year yield, CPI inflation and short rates, negatively), oil over a year (negatively) and Bitcoin's recent growth (positively) lead, and all are weak (absolute Spearman correlations of 0.04 to 0.11). The strongest time features (session, week and day of the month) and one space feature (the age of the nearest untested monthly low below) are of the same weak size.
2. **The model ranks a little better than chance but is badly calibrated in the test period.** Its mean probability of a positive period is 38% to 45% by instrument against observed shares of 49% to 61%, so with a 0.5 cut it is wrong more than half the time. Ranking (AUC) is the fairer reading; thresholds must be relative, as the strategies' frozen thresholds were.
3. **Where it works and where it fails:** with the course features the AUC is highest on GLD and SPY and close to 0.5 on crypto; the most confident errors are almost all crypto calls of a strong fall that rose instead (81% of the most confident errors are Bitcoin or Ether). By month of the year the results swing widely on few rows each, which is noise rather than seasonality.
4. **The vector view** earns a positive return on capital in both periods (bets on every high-probability signal), while the exact account with costs and cash at the bill rate did not beat buy and hold (step 5): many small bets with a hit rate near 55% and overlapping positions do not add up to a better portfolio.

Ideas for improvement, each to be fixed before it is run:

- **Calibration:** recalibrate probabilities on the validation period (isotonic or Platt) and set thresholds as percentiles of recent probabilities instead of absolute values.
- **Stationary inputs:** replace macro levels by changes or z-scores against a rolling window; a plausible reason for the low test probabilities is that rates in 2024–2026 sat far above most of the training period, which the model reads as bearish (untested).
- **One model per market family:** funds and crypto behave differently; a pooled model with ticker indicators lets crypto's bear years shape the fund predictions and the reverse.
- **Intraday time and space:** the daily features did not help; the levels and sessions TSIP measures act within the day and the week (hourly bars, the current week's levels).
- **Direction is the hardest target:** predict the range or the volatility of the next sessions, where time features already carry graded evidence (`docs/TIME_SPACE_MODEL.md`).

## Rubric map

Where each item of the course rubric is answered, and what is not claimed.

| Criterion | Evidence in this repository | Status |
|---|---|---|
| Problem description | "Problem" above; README release section; specification 0028 | done |
| Data sources | yfinance (5 instruments, 8 reference markets) and FRED (4 series), two modes, fingerprinted store outside Git (step 1, `tsip.capstone.data`) | done |
| Twenty or more features, documented | 122 columns in named sets with a dictionary (step 2) and a no-look-ahead test | done |
| More than one million records | Not met: daily data give 26,759 rows | not claimed |
| New data source (not yfinance or FRED) | Coinbase daily candles for Bitcoin and Ether (`tsip.capstone.extra_sources`): cross-check and three exchange-specific features (premium and volume share), exploratory | written; tables after the first download (the founder's computer or the scheduled run) |
| Transformations and exploratory analysis | Point-in-time joins with release lags (step 1); notebook section "Exploratory view" (shares of positive periods by instrument, weekday and position in the prior week) | done: correlations with the 5- and 20-row returns in "Exploratory analysis and diagnostics" |
| Models and tuning | Decision tree, random forest, logistic regression and XGBoost tuned on time-ordered folds; selection rule fixed before training (step 3) | done: all four families regenerated and shown in the notebook (reusing saved results) |
| Probability thresholds | Thresholds chosen on validation and frozen (`registry/capstone_choices_h5.json`, step 4) | done |
| Two or more strategies, vector and exact simulation | sim1 to sim5, vector view and an exact account with costs, cash at the bill rate, one-session delay (steps 4 and 5) | done; the vector view's return on capital is in "Exploratory analysis and diagnostics" |
| Benchmark with dividends | Five-instrument buy and hold and SPY with dividends (adjusted close), with block-bootstrap intervals | done |
| Stop loss and a new strategy | sim3 (2 ATR stop and a volatility filter); pullback buying with monthly deposits (sim5) | done |
| Deep analysis | Rotation and random-walk controls, validation against test, walk-forward check, reproducibility across downloads | done: AUC, precision of the most confident decile, calibration and the most confident errors by instrument and month, with improvement ideas |
| Exceptional returns | The registered strategy did not beat either benchmark on the test period (step 5) | not claimed |
| Scripts and dependencies | `pyproject.toml` extra `capstone`; one command, `tsip.capstone.run_all`, in two modes, both run (file mode here, download mode on the founder's computer, compared above) | done |
| Incremental data outside GitHub | `--mode update` downloads only from ten days before the last stored date and splices the new rows in, rescaling the stored history to the provider's latest dividend and split adjustment; the store stays outside Git with a fingerprinted manifest; results computed on older data are set aside, never mixed | done |
| Scheduled run | `.github/workflows/capstone.yml`: every Sunday and on demand, fresh download, the whole flow, the latest predictions and the paper-trading orders (dry run) in the run summary and an artifact | written; verified after its first run on GitHub |
| Modular code | `src/tsip/capstone/` modules with their tests (`tests/test_capstone_*.py`); the notebook only calls them | done |
| Broker API | `tsip.capstone.paper_order`: orders to Alpaca's paper endpoint only, with simulated money | done (dry run verified; sending needs the founder's paper keys) |
| Container | `Dockerfile`, built and run by the `container` job of `.github/workflows/capstone.yml` | written; verified after its first run on GitHub |
| Deployment | The project's public report on GitHub Pages | done |
