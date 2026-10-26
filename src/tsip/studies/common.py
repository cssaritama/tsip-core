from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from tsip.data.schema import has_ohlc
from tsip.instruments import Instrument

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass
class StudyContext:
    """Inputs shared by all studies for one instrument."""

    instrument: Instrument
    daily: pd.DataFrame | None
    session_model: str  # "crypto" (24/7) or "us_rth" (US cash session)
    intraday: pd.DataFrame | None = None  # crypto: UTC hourly bars
    rth_bars: pd.DataFrame | None = None  # us_rth: RTH bars with date/slot columns
    reps: int = 1000
    seed: int = 20261026
    sources: dict = field(default_factory=dict)

    @property
    def is_crypto(self) -> bool:
        return self.session_model == "crypto"

    @property
    def has_daily_ohlc(self) -> bool:
        return self.daily is not None and len(self.daily) > 0 and has_ohlc(self.daily)

    @property
    def trading_days_per_year(self) -> int:
        return 365 if self.is_crypto else 252


def consecutive_mask(index: pd.DatetimeIndex, *, crypto: bool) -> np.ndarray:
    """True where a row directly follows the previous row (no missing day)."""
    gaps = np.diff(index.values).astype("timedelta64[D]").astype(int)
    if crypto:
        ok = gaps == 1
    else:  # equities: any gap up to 4 calendar days (weekend + holiday)
        ok = gaps <= 4
    return np.concatenate([[False], ok])


def daily_log_returns(daily: pd.DataFrame, *, crypto: bool) -> pd.Series:
    close = daily["close"].astype(float)
    ret = np.log(close / close.shift(1))
    ret[~consecutive_mask(daily.index, crypto=crypto)] = np.nan
    return ret.dropna()


def period_of(index: pd.DatetimeIndex) -> dict:
    if len(index) == 0:
        return {"start": None, "end": None}
    return {"start": str(pd.Timestamp(index[0]).date()), "end": str(pd.Timestamp(index[-1]).date())}


def nanmean(values: np.ndarray, axis: int | None = None) -> np.ndarray | float:
    with np.errstate(invalid="ignore"):
        if np.size(values) == 0:
            return np.nan
        return np.nanmean(values, axis=axis) if np.isfinite(values).any() else np.nan


def safe_ratio(num: float, den: float) -> float:
    return float(num) / float(den) if den else np.nan
