"""Feature sets for the course project (specification 0028, R2 to R6).

``build_features`` turns the unified frame of ``tsip.capstone.data`` into one row per ticker and date
with four named sets:

* ``TO_PREDICT``: growth over the next 5 and 20 rows and its sign (the only columns that look ahead);
* ``LECTURE``: the course's features: growth of the instrument and of reference markets over 1 to
  365 days, macro levels and changes, momentum and volatility indicators, volume;
* ``TIME``: calendar coordinates (weekday, week and session of the month and quarter, days left);
* ``SPACE``: the close against prior periods' highs and lows (day, week, month, quarter), whether
  those levels have been traded since, and the nearest levels still untested from the last twelve
  weeks and months, in ATR and percent;
* ``DUMMIES``: ticker indicators.

Every feature on a row uses only that row and earlier rows of the same ticker (tested by deleting
later rows). Growth windows are calendar days, so equities (sessions) and crypto (every day) share one
definition. Levels use unadjusted prices; distances are also given in ATR, which is unit-free.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONS = (5, 20)
GROWTH_DAYS = (1, 3, 7, 30, 90, 365)
REFERENCE_GROWTH_DAYS = (1, 7, 30, 90, 365)
ATR_WINDOW = 14
LOOKBACK_PERIODS = 12
PERIODS = {"week": "W-SUN", "month": "M", "quarter": "Q"}


# ---------------------------------------------------------------- helpers


def _growth_by_days(series: pd.Series, days: int) -> pd.Series:
    """Value over the last value known ``days`` calendar days earlier, minus one."""
    clean = series.dropna()
    if clean.empty:
        return pd.Series(np.nan, index=series.index)
    past = clean.reindex(series.index - pd.Timedelta(days=days), method="ffill").to_numpy()
    return pd.Series(series.to_numpy() / past - 1, index=series.index)


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    change = close.diff()
    gain = change.clip(lower=0).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    loss = (-change.clip(upper=0)).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    return 100 - 100 / (1 + gain / loss)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = ATR_WINDOW) -> pd.Series:
    prev = close.shift(1)
    true_range = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean()


def _session_index(keys: np.ndarray) -> np.ndarray:
    """1 for the first row of each period, 2 for the second, and so on."""
    out = np.ones(len(keys), dtype=int)
    for i in range(1, len(keys)):
        out[i] = out[i - 1] + 1 if keys[i] == keys[i - 1] else 1
    return out


# ---------------------------------------------------------------- one ticker


def _targets(g: pd.DataFrame) -> dict:
    price = g["adj_close"].where(g["adj_close"].notna(), g["close"])
    cols = {}
    for h in HORIZONS:
        future = price.shift(-h) / price - 1
        cols[f"growth_future_{h}d"] = future
        cols[f"is_positive_growth_{h}d"] = (future > 0).astype(float).where(future.notna())
    return cols


def _lecture(g: pd.DataFrame) -> dict:
    price = g["adj_close"].where(g["adj_close"].notna(), g["close"]).set_axis(g["date"])
    cols = {f"growth_{d}d": _growth_by_days(price, d).to_numpy() for d in GROWTH_DAYS}
    for col in [c for c in g.columns if c.startswith("ref_close_")]:
        ref = g[col].set_axis(g["date"])
        name = col.removeprefix("ref_close_")
        for d in REFERENCE_GROWTH_DAYS:
            cols[f"growth_{name}_{d}d"] = _growth_by_days(ref, d).to_numpy()
    for col in [c for c in g.columns if c.startswith("macro_")]:
        level = g[col].set_axis(g["date"])
        cols[col] = level.to_numpy()
        if col == "macro_cpi":
            cols["macro_cpi_yoy"] = _growth_by_days(level, 365).to_numpy()
        else:
            cols[f"{col}_change_30d"] = (
                level - level.reindex(level.index - pd.Timedelta(days=30), method="ffill").to_numpy()
            ).to_numpy()
    close = price.reset_index(drop=True)
    log_ret = np.log(close).diff()
    cols["rsi_14"] = _rsi(close).to_numpy()
    cols["volatility_20"] = (log_ret.rolling(20, min_periods=20).std() * np.sqrt(252)).to_numpy()
    cols["ma_ratio_50"] = (close / close.rolling(50, min_periods=50).mean() - 1).to_numpy()
    cols["ma_ratio_200"] = (close / close.rolling(200, min_periods=200).mean() - 1).to_numpy()
    volume = g["volume"].reset_index(drop=True).astype(float)
    cols["ln_volume"] = np.log(volume.where(volume > 0)).to_numpy()
    cols["volume_ratio_20"] = (volume / volume.rolling(20, min_periods=20).mean()).to_numpy()
    return cols


def _time(g: pd.DataFrame) -> dict:
    d = pd.DatetimeIndex(g["date"])
    week = d.to_period("W-SUN").asi8
    month = d.to_period("M").asi8
    quarter = d.to_period("Q").asi8
    month_end = d + pd.offsets.MonthEnd(0)
    quarter_end = d + pd.offsets.QuarterEnd(0)
    return {
        "weekday": d.dayofweek.to_numpy(),
        "day_of_month": d.day.to_numpy(),
        "week_of_month": ((d.day - 1) // 7 + 1).to_numpy(),
        "month": d.month.to_numpy(),
        "quarter": d.quarter.to_numpy(),
        "session_of_week": _session_index(week),
        "session_of_month": _session_index(month),
        "session_of_quarter": _session_index(quarter),
        "days_to_month_end": (month_end - d).days.to_numpy(),
        "days_to_quarter_end": (quarter_end - d).days.to_numpy(),
        "is_last_week_of_month": np.asarray((month_end - d).days < 7, dtype=int),
    }


def _period_levels(high: np.ndarray, low: np.ndarray, keys: np.ndarray) -> tuple[np.ndarray, ...]:
    """For each row: prior complete period's high and low, and the current period's high and low so far."""
    n = len(keys)
    prior_high = np.full(n, np.nan)
    prior_low = np.full(n, np.nan)
    run_high = np.full(n, np.nan)
    run_low = np.full(n, np.nan)
    last_high = last_low = np.nan
    cur_high, cur_low = -np.inf, np.inf
    for i in range(n):
        if i > 0 and keys[i] != keys[i - 1]:
            last_high, last_low = cur_high, cur_low
            cur_high, cur_low = -np.inf, np.inf
        cur_high = max(cur_high, high[i])
        cur_low = min(cur_low, low[i])
        prior_high[i], prior_low[i] = last_high, last_low
        run_high[i], run_low[i] = cur_high, cur_low
    # the first period in the data may be partial, so rows of the second period have no complete prior period
    if (keys != keys[0]).any():
        second = keys == keys[np.argmax(keys != keys[0])]
        prior_high[second] = np.nan
        prior_low[second] = np.nan
    return prior_high, prior_low, run_high, run_low


def _untested(high: np.ndarray, low: np.ndarray, keys: np.ndarray) -> tuple[list, list]:
    """Highs and lows of complete periods with the row where each period ended."""
    ends = np.flatnonzero(np.r_[keys[1:] != keys[:-1], False])  # last row of each complete period
    starts = np.r_[0, ends[:-1] + 1] if len(ends) else ends
    highs = [(e, high[s : e + 1].max()) for s, e in zip(starts, ends, strict=True)]
    lows = [(e, low[s : e + 1].min()) for s, e in zip(starts, ends, strict=True)]
    return highs[1:], lows[1:]  # drop the first period: it may be partial


def _untested_features(high, low, close, atr, keys, name: str) -> dict:
    n = len(close)
    above = np.full(n, np.inf)
    below = np.full(n, -np.inf)
    age_above = np.full(n, np.nan)
    age_below = np.full(n, np.nan)
    count = np.zeros(n)
    period_no = np.cumsum(np.r_[0, keys[1:] != keys[:-1]])
    highs, lows = _untested(high, low, keys)
    for levels, side in ((highs, "high"), (lows, "low")):
        for end, level in levels:
            after = high[end + 1 :] >= level if side == "high" else low[end + 1 :] <= level
            touch = end + 1 + (int(np.argmax(after)) if after.any() else len(after))
            last_live = np.searchsorted(period_no, period_no[end] + LOOKBACK_PERIODS + 1)  # within 12 periods
            stop = min(touch, last_live, n)
            rows = np.arange(end + 1, stop)
            if not len(rows):
                continue
            near = np.abs(level - close[rows]) <= atr[rows]
            count[rows] += near
            if side == "high":
                better = level < above[rows]
                above[rows[better]] = level
                age_above[rows[better]] = rows[better] - end
            else:
                better = level > below[rows]
                below[rows[better]] = level
                age_below[rows[better]] = rows[better] - end
    above[np.isinf(above)] = np.nan
    below[np.isinf(below)] = np.nan
    return {
        f"space_{name}_untested_above_atr": (above - close) / atr,
        f"space_{name}_untested_below_atr": (close - below) / atr,
        f"space_{name}_untested_above_pct": 100 * (above / close - 1),
        f"space_{name}_untested_below_pct": 100 * (below / close - 1),
        f"space_{name}_untested_above_age": age_above,
        f"space_{name}_untested_below_age": age_below,
        f"space_{name}_untested_within_1atr": count,
    }


def _space(g: pd.DataFrame) -> dict:
    high, low, close = (g[c].to_numpy(dtype=float) for c in ("high", "low", "close"))
    atr = _atr(g["high"], g["low"], g["close"]).to_numpy()
    cols = {"atr_pct_14": 100 * atr / close}
    prev_high, prev_low = np.r_[np.nan, high[:-1]], np.r_[np.nan, low[:-1]]
    cols["space_day_high_dist_atr"] = (prev_high - close) / atr
    cols["space_day_low_dist_atr"] = (close - prev_low) / atr
    cols["space_day_position"] = (close - prev_low) / (prev_high - prev_low)
    d = pd.DatetimeIndex(g["date"])
    for name, freq in PERIODS.items():
        keys = d.to_period(freq).asi8
        p_high, p_low, r_high, r_low = _period_levels(high, low, keys)
        cols[f"space_{name}_high_dist_atr"] = (p_high - close) / atr
        cols[f"space_{name}_low_dist_atr"] = (close - p_low) / atr
        cols[f"space_{name}_high_dist_pct"] = 100 * (p_high / close - 1)
        cols[f"space_{name}_low_dist_pct"] = 100 * (p_low / close - 1)
        cols[f"space_{name}_position"] = (close - p_low) / (p_high - p_low)
        cols[f"space_{name}_high_tested"] = np.where(np.isnan(p_high), np.nan, (r_high >= p_high).astype(float))
        cols[f"space_{name}_low_tested"] = np.where(np.isnan(p_low), np.nan, (r_low <= p_low).astype(float))
        if name in ("week", "month"):
            cols.update(_untested_features(high, low, close, atr, keys, name))
    cols["space_untested_within_1atr"] = (
        cols["space_week_untested_within_1atr"] + cols["space_month_untested_within_1atr"]
    )
    return cols


# ---------------------------------------------------------------- public


def build_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Feature frame and the named feature sets (specification 0028, R1 to R5)."""
    parts = []
    sets: dict[str, list[str]] = {}
    for _ticker, g in frame.sort_values(["ticker", "date"]).groupby("ticker", sort=True):
        g = g.reset_index(drop=True)
        blocks = {"TO_PREDICT": _targets(g), "LECTURE": _lecture(g), "TIME": _time(g), "SPACE": _space(g)}
        columns = {col: np.asarray(values, dtype=float) for cols in blocks.values() for col, values in cols.items()}
        for set_name, cols in blocks.items():
            sets.setdefault(set_name, list(cols))
        parts.append(pd.concat([g[["date", "ticker"]], pd.DataFrame(columns)], axis=1))
    features = pd.concat(parts, ignore_index=True)
    dummies = pd.get_dummies(features["ticker"], prefix="ticker", dtype=float)
    features = pd.concat([features, dummies], axis=1)
    sets["DUMMIES"] = list(dummies.columns)
    features = features.replace([np.inf, -np.inf], np.nan)
    return features, sets
