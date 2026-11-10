# Course project: do time and space improve the prediction of future returns?

Working document of the final project of the Stock Markets Analytics course (specification [0028](../specs/0028-time-space-features-for-return-prediction.md), hypothesis H-2026-016). It is completed step by step; sections not yet built say so. Every figure here names the command that produced it (ADR 0071 of the project's decision record).

## Problem

TSIP describes where price stands in time (calendar coordinates) and in space (against the highs and lows of prior days, weeks, months and quarters). The project tests whether that information improves the out-of-sample prediction of the direction of the next 5 and 20 sessions for SPY, QQQ, GLD, Bitcoin and Ethereum, beyond the course's standard features, and whether a strategy built on the predictions beats buy and hold after costs. The hypothesis and its pass criterion were registered before any model was trained.

## How to run

```sh
pip install -e ".[dev,calendar,capstone]"
python -m tsip.capstone.data --mode download   # fresh data from yfinance and FRED, stored outside Git
python -m tsip.capstone.data --mode file       # repeat from the stored copy, no network
```

Data are stored in `~/tsip_capstone_data` (override with `TSIP_CAPSTONE_DATA`) with a manifest that fingerprints each file; nothing is committed to Git.

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

## Models (step 3) · Simulation (step 4) · Evaluation (step 5)

To be built, in this order, under specification 0028; the test period from 2024-01-01 is read once, at step 5.
