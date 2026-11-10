"""Specification 0028, R2 to R6: feature sets, no look-ahead, and the space features on known paths."""

import numpy as np
import pandas as pd

from tsip.capstone import features as F


def _frame(days=420, seed=7, tickers=("SPY", "BTC-USD")):
    rng = np.random.default_rng(seed)
    rows = []
    for t in tickers:
        dates = pd.date_range("2022-01-03", periods=days, freq="D")
        if not t.endswith("-USD"):
            dates = dates[dates.dayofweek < 5]
        close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(dates))))
        high = close * (1 + rng.uniform(0, 0.01, len(dates)))
        low = close * (1 - rng.uniform(0, 0.01, len(dates)))
        for d, c, h, lo in zip(dates, close, high, low, strict=True):
            rows.append(
                {
                    "date": d,
                    "ticker": t,
                    "open": c,
                    "high": h,
                    "low": lo,
                    "close": c,
                    "adj_close": c,
                    "volume": 1e6,
                    "ref_close_snp500": c * 1.1,
                    "macro_ten_year_yield": 4.0,
                    "macro_cpi": 300.0,
                }
            )
    return pd.DataFrame(rows)


def test_named_sets_cover_every_feature_column():
    feats, sets = F.build_features(_frame())
    named = [c for cols in sets.values() for c in cols]
    assert set(named) | {"date", "ticker"} == set(feats.columns)
    assert len(sets["LECTURE"]) + len(sets["TIME"]) + len(sets["SPACE"]) >= 20
    assert {"growth_future_5d", "is_positive_growth_5d"} <= set(sets["TO_PREDICT"])


def test_no_feature_changes_when_later_rows_are_removed():
    frame = _frame()
    full, sets = F.build_features(frame)
    cut = pd.Timestamp("2022-09-15")
    short, _ = F.build_features(frame[frame["date"] <= cut])
    cols = [c for s, cs in sets.items() if s != "TO_PREDICT" for c in cs]
    a = full[full["date"] <= cut].reset_index(drop=True)[cols]
    b = short.reset_index(drop=True)[cols]
    pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_targets_look_exactly_h_rows_ahead_and_end_empty():
    frame = _frame(tickers=("SPY",))
    feats, _ = F.build_features(frame)
    price = frame["adj_close"].to_numpy()
    assert np.isclose(feats["growth_future_5d"].iloc[10], price[15] / price[10] - 1)
    assert feats["growth_future_5d"].iloc[-5:].isna().all()
    assert feats["is_positive_growth_20d"].iloc[-20:].isna().all()


def test_prior_week_levels_and_tested_flags_on_a_known_path():
    dates = pd.date_range("2024-01-01", periods=15, freq="B")  # Monday 1 Jan to Friday 19 Jan
    high = np.r_[[10.0] * 5, [20, 21, 22, 23, 24], [11, 12, 30, 12, 12]]
    low = high - 1
    frame = pd.DataFrame(
        {
            "date": dates,
            "ticker": "SPY",
            "open": high,
            "high": high,
            "low": low,
            "close": high - 0.5,
            "adj_close": high - 0.5,
            "volume": 1.0,
        }
    )
    feats, _ = F.build_features(frame)
    third_week = feats.iloc[10:]
    # the first week is complete here but treated as possibly partial; the third week sees week two (high 24, low 19)
    assert np.allclose(third_week["space_week_high_dist_atr"].notna(), third_week["atr_pct_14"].notna())
    tested = third_week["space_week_high_tested"].to_numpy()
    assert list(tested) == [0, 0, 1, 1, 1]  # 30 on Wednesday trades through 24 and stays tested
    assert feats["space_week_high_tested"].iloc[5:10].isna().all()  # week two has no complete prior week


def test_untested_level_disappears_once_traded():
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    high = np.full(30, 10.0)
    high[5:10] = 15.0  # week two makes a high of 15
    high[10:20] = 12.0  # weeks three and four stay below it
    high[22] = 16.0  # week five trades through it on Wednesday
    low = high - 1
    frame = pd.DataFrame(
        {
            "date": dates,
            "ticker": "SPY",
            "open": high,
            "high": high,
            "low": low,
            "close": high - 0.5,
            "adj_close": high - 0.5,
            "volume": 1.0,
        }
    )
    feats, _ = F.build_features(frame)
    pct = feats["space_week_untested_above_pct"]
    assert np.isclose(pct.iloc[12], 100 * (15 / 11.5 - 1))
    assert np.isnan(pct.iloc[23]) or pct.iloc[23] > 100 * (15 / 15.5 - 1)  # 15 is no longer untested
    assert feats["space_week_untested_above_age"].iloc[12] == 3
