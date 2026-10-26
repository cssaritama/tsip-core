"""Derived frames: sessions, daily/weekly/monthly bars and intraday matrices.

All aggregation is explicit about completeness: an incomplete day, week or
month is dropped rather than treated as complete.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

OHLCV_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}

# Crypto trades around the clock. Days are split into four exclusive,
# hour-aligned windows defined in local time, so daylight saving time is
# handled per date. The 09:00 New York hour contains the 09:30 cash open.
CRYPTO_SESSIONS = ("asia", "london", "new_york", "late_us")
CRYPTO_SESSION_LABELS = {
    "asia": "Asia (00:00 UTC – London 08:00)",
    "london": "London (08:00 London – 09:00 New York)",
    "new_york": "New York (09:00 – 16:00 New York)",
    "late_us": "Late US (16:00 New York – 24:00 UTC)",
}

US_RTH_OPEN = time(9, 30)
US_RTH_CLOSE = time(16, 0)


def daily_from_intraday_utc(bars: pd.DataFrame, bars_per_day: int) -> pd.DataFrame:
    """Aggregate UTC intraday bars into complete UTC calendar days."""
    if bars.empty:
        return _empty_daily()
    day = bars.index.tz_convert("UTC").tz_localize(None).normalize()
    grouped = bars.groupby(day)
    daily = grouped.agg(OHLCV_AGG)
    daily["n_bars"] = grouped.size()
    daily = daily[daily["n_bars"] == bars_per_day].drop(columns="n_bars")
    daily.index = pd.DatetimeIndex(daily.index, name="date")
    daily.attrs = {**bars.attrs, "timeframe": "1d", "derived_from": bars.attrs.get("timeframe")}
    return daily


def rth_daily_from_intraday(
    bars: pd.DataFrame,
    *,
    tz: str = "America/New_York",
    open_time: time = US_RTH_OPEN,
    close_time: time = US_RTH_CLOSE,
    min_bars: int = 7,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Regular-trading-hours daily bars from intraday bars.

    Returns ``(daily, rth_bars)`` where ``rth_bars`` carries a ``date`` and a
    ``slot`` column (local bar start, ``HH:MM``). Days with fewer than
    ``min_bars`` bars are dropped; ``daily['full_day']`` marks complete days.
    """
    local = bars.index.tz_convert(tz)
    clock = local.time
    mask = (clock >= open_time) & (clock < close_time)
    rth = bars.loc[mask].copy()
    local_rth = local[mask]
    rth["date"] = pd.DatetimeIndex(local_rth.tz_localize(None)).normalize()
    rth["slot"] = local_rth.strftime("%H:%M")
    grouped = rth.groupby("date")
    daily = grouped.agg(OHLCV_AGG)
    daily["n_bars"] = grouped.size()
    expected = int(rth.groupby("date").size().max()) if len(rth) else 0
    daily = daily[daily["n_bars"] >= min_bars]
    daily["full_day"] = daily["n_bars"] == expected
    daily.index = pd.DatetimeIndex(daily.index, name="date")
    daily.attrs = {**bars.attrs, "timeframe": "1d", "session": "rth", "derived_from": bars.attrs.get("timeframe")}
    rth = rth[rth["date"].isin(daily.index)]
    return daily, rth


def period_bars(daily: pd.DataFrame, freq: str, *, min_days: int) -> pd.DataFrame:
    """Weekly (``"W"``, Monday–Sunday) or monthly (``"M"``) bars from daily bars."""
    if daily.empty:
        return _empty_daily()
    rule = "W-SUN" if freq == "W" else "M"
    periods = daily.index.to_period(rule)
    grouped = daily.groupby(periods)
    out = grouped.agg(OHLCV_AGG)
    out["n_days"] = grouped.size()
    out["first_day"] = grouped.apply(lambda g: g.index[0])
    out["last_day"] = grouped.apply(lambda g: g.index[-1])
    out = out[out["n_days"] >= min_days]
    out.index.name = "period"
    return out


# Calendar horizons for prior-period levels. Weeks run Monday to Sunday, half-years are
# January–June and July–December.
HORIZONS = ("week", "month", "quarter", "half", "year")
HORIZON_NAMES = {"week": "week", "month": "month", "quarter": "quarter", "half": "half-year", "year": "year"}
# A period counts as complete only with at least this many sessions (trading days for
# exchange-traded instruments, calendar days for crypto).
MIN_SESSIONS = {
    "equity": {"week": 4, "month": 15, "quarter": 55, "half": 110, "year": 220},
    "crypto": {"week": 7, "month": 28, "quarter": 89, "half": 180, "year": 360},
}
_EPOCH_MONDAY = np.datetime64("1970-01-05", "D")


def period_key(index: pd.DatetimeIndex, horizon: str) -> np.ndarray:
    """Integer key of the calendar period of each date; consecutive periods differ by one."""
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    if horizon == "week":
        days = (idx.values.astype("datetime64[D]") - _EPOCH_MONDAY).astype(np.int64)
        return days // 7
    years = idx.year.to_numpy().astype(np.int64)
    months = idx.month.to_numpy().astype(np.int64)
    if horizon == "month":
        return years * 12 + (months - 1)
    if horizon == "quarter":
        return years * 4 + (months - 1) // 3
    if horizon == "half":
        return years * 2 + (months - 1) // 6
    if horizon == "year":
        return years
    raise ValueError(f"unknown horizon {horizon!r}; use one of {HORIZONS}")


def period_bounds(key: int, horizon: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """First and last calendar day of a period key."""
    key = int(key)
    if horizon == "week":
        start = pd.Timestamp(_EPOCH_MONDAY + np.timedelta64(key * 7, "D"))
        return start, start + pd.Timedelta(days=6)
    if horizon == "month":
        start = pd.Timestamp(year=key // 12, month=key % 12 + 1, day=1)
        return start, start + pd.offsets.MonthEnd(0)
    if horizon == "quarter":
        start = pd.Timestamp(year=key // 4, month=(key % 4) * 3 + 1, day=1)
        return start, start + pd.offsets.QuarterEnd(0)
    if horizon == "half":
        start = pd.Timestamp(year=key // 2, month=(key % 2) * 6 + 1, day=1)
        return start, (start + pd.DateOffset(months=6)) - pd.Timedelta(days=1)
    if horizon == "year":
        start = pd.Timestamp(year=key, month=1, day=1)
        return start, pd.Timestamp(year=key, month=12, day=31)
    raise ValueError(f"unknown horizon {horizon!r}; use one of {HORIZONS}")


def period_label(key: int, horizon: str) -> str:
    start, _ = period_bounds(key, horizon)
    if horizon == "week":
        return f"week of {start.date()}"
    if horizon == "month":
        return start.strftime("%b %Y")
    if horizon == "quarter":
        return f"Q{int(key) % 4 + 1} {start.year}"
    if horizon == "half":
        return f"H{int(key) % 2 + 1} {start.year}"
    return str(start.year)


def starts_on_time(first_day: pd.Timestamp, period_start: pd.Timestamp, *, crypto: bool) -> bool:
    """True if data for a period begins at the period start (one weekday of slack for a holiday)."""
    if crypto:
        return first_day <= period_start
    return int(np.busday_count(period_start.date(), first_day.date())) <= 1


def has_ended(last_day: pd.Timestamp, period_end: pd.Timestamp, *, crypto: bool) -> bool:
    """True if no session of the period can follow ``last_day`` (only weekend days remain)."""
    if crypto:
        return last_day >= period_end
    after = (last_day + pd.Timedelta(days=1)).date()
    return int(np.busday_count(after, (period_end + pd.Timedelta(days=1)).date())) == 0


def horizon_bars(daily: pd.DataFrame, horizon: str, *, crypto: bool, min_sessions: int | None = None) -> pd.DataFrame:
    """Complete calendar-period bars (week to year) from daily bars.

    The index is the integer period key (see :func:`period_key`). Interior periods need
    at least ``min_sessions`` sessions. The first period also needs data from its start and
    the last one must have ended, so a period still in progress is never treated as complete.
    """
    columns = ["open", "high", "low", "close", "volume", "n_sessions", "first_day", "last_day"]
    if daily.empty:
        return pd.DataFrame(columns=columns, index=pd.Index([], name="period", dtype=np.int64))
    if min_sessions is None:
        min_sessions = MIN_SESSIONS["crypto" if crypto else "equity"][horizon]
    keys = period_key(daily.index, horizon)
    grouped = daily[["open", "high", "low", "close", "volume"]].groupby(keys)
    out = grouped.agg(OHLCV_AGG)
    days = pd.Series(daily.index, index=daily.index).groupby(keys)
    out["n_sessions"] = grouped.size()
    out["first_day"] = days.first()
    out["last_day"] = days.last()
    keep = (out["n_sessions"] >= min_sessions).to_numpy()
    first_start = period_bounds(out.index[0], horizon)[0]
    keep[0] = keep[0] and starts_on_time(pd.Timestamp(out["first_day"].iloc[0]), first_start, crypto=crypto)
    last_end = period_bounds(out.index[-1], horizon)[1]
    keep[-1] = keep[-1] and has_ended(pd.Timestamp(out["last_day"].iloc[-1]), last_end, crypto=crypto)
    out = out[keep]
    out.index.name = "period"
    return out


def crypto_session_labels(index_utc: pd.DatetimeIndex) -> np.ndarray:
    """Label each UTC bar start with its exclusive crypto session."""
    london, new_york = ZoneInfo("Europe/London"), ZoneInfo("America/New_York")
    utc_dates = index_utc.tz_convert("UTC").tz_localize(None).normalize()
    labels = np.empty(len(index_utc), dtype=object)
    starts = index_utc.tz_convert("UTC")
    boundaries: dict[pd.Timestamp, tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]] = {}
    for d in pd.unique(utc_dates):
        d = pd.Timestamp(d)
        lo = pd.Timestamp(datetime(d.year, d.month, d.day, 8, 0, tzinfo=london)).tz_convert("UTC")
        nyo = pd.Timestamp(datetime(d.year, d.month, d.day, 9, 0, tzinfo=new_york)).tz_convert("UTC")
        nyc = pd.Timestamp(datetime(d.year, d.month, d.day, 16, 0, tzinfo=new_york)).tz_convert("UTC")
        boundaries[d] = (lo, nyo, nyc)
    for i, (ts, d) in enumerate(zip(starts, utc_dates, strict=True)):
        lo, nyo, nyc = boundaries[pd.Timestamp(d)]
        if ts < lo:
            labels[i] = "asia"
        elif ts < nyo:
            labels[i] = "london"
        elif ts < nyc:
            labels[i] = "new_york"
        else:
            labels[i] = "late_us"
    return labels


def path_units(
    bars: pd.DataFrame,
    period: pd.Series | np.ndarray,
    slot: pd.Series | np.ndarray,
    slots: list,
) -> dict[str, np.ndarray]:
    """Per-period matrices describing each bar relative to the path so far.

    For period *p* and slot *k*: ``ret`` is the log change from the reference
    to the bar close, ``hi``/``lo`` the log excursion from the reference to
    the bar high/low. The reference is the previous bar's close within the
    period, or the bar's own open for the first bar. Only periods with every
    slot present are kept. Returns ``periods`` (labels) and the matrices.
    """
    frame = pd.DataFrame(
        {
            "period": np.asarray(period),
            "slot": np.asarray(slot),
            "open": bars["open"].to_numpy(float),
            "high": bars["high"].to_numpy(float),
            "low": bars["low"].to_numpy(float),
            "close": bars["close"].to_numpy(float),
        }
    )
    frame = frame[frame["slot"].isin(slots)]
    counts = frame.groupby("period")["slot"].nunique()
    complete = counts[counts == len(slots)].index
    frame = frame[frame["period"].isin(complete)]
    order = {s: i for i, s in enumerate(slots)}
    frame = frame.assign(k=frame["slot"].map(order)).sort_values(["period", "k"])
    n, k = len(complete), len(slots)
    o = frame["open"].to_numpy().reshape(n, k)
    h = frame["high"].to_numpy().reshape(n, k)
    lo = frame["low"].to_numpy().reshape(n, k)
    c = frame["close"].to_numpy().reshape(n, k)
    ref = np.concatenate([o[:, :1], c[:, :-1]], axis=1)
    return {
        "periods": np.asarray(sorted(complete)),
        "ret": np.log(c / ref),
        "hi": np.log(h / ref),
        "lo": np.log(lo / ref),
    }


def _empty_daily() -> pd.DataFrame:
    return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([], name="date"))
