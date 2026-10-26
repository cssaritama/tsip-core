"""Data quality evidence published with every report."""

from __future__ import annotations

import numpy as np
import pandas as pd


def hourly_completeness(bars: pd.DataFrame) -> dict:
    if bars is None or bars.empty:
        return {}
    expected = int((bars.index[-1] - bars.index[0]) / pd.Timedelta(hours=1)) + 1
    present = int(len(bars))
    return {
        "expected_bars": expected,
        "present_bars": present,
        "missing_bars": expected - present,
        "missing_pct": round(100 * (expected - present) / expected, 4) if expected else None,
    }


def cross_validate(primary: pd.DataFrame, secondary: pd.DataFrame) -> dict:
    """Compare two independent feeds of the same asset on shared timestamps."""
    if primary is None or secondary is None or primary.empty or secondary.empty:
        return {}
    joined = pd.concat({"a": primary["close"], "b": secondary["close"]}, axis=1, join="inner").dropna()
    if len(joined) < 100:
        return {"overlap_bars": int(len(joined))}
    ra = np.log(joined["a"]).diff()
    rb = np.log(joined["b"]).diff()
    diff_bps = (joined["b"] / joined["a"] - 1).abs() * 1e4
    return {
        "overlap_bars": int(len(joined)),
        "overlap_start": str(joined.index[0]),
        "overlap_end": str(joined.index[-1]),
        "return_correlation": round(float(ra.corr(rb)), 6),
        "median_abs_close_diff_bps": round(float(diff_bps.median()), 3),
        "share_close_diff_over_50bps_pct": round(float((diff_bps > 50).mean() * 100), 4),
    }


def session_completeness(daily: pd.DataFrame, calendar_code: str = "XNYS") -> dict:
    """Compare observed sessions with the exchange calendar when available."""
    if daily is None or daily.empty:
        return {}
    try:
        import exchange_calendars as xcals
    except ImportError:  # optional dependency
        return {"calendar": "not checked (exchange_calendars not installed)"}
    start, end = daily.index[0], daily.index[-1]
    cal = xcals.get_calendar(calendar_code, start=start - pd.Timedelta(days=7), end=end + pd.Timedelta(days=7))
    sessions = pd.DatetimeIndex(cal.sessions_in_range(start, end)).tz_localize(None)
    observed = pd.DatetimeIndex(daily.index)
    missing = sessions.difference(observed)
    extra = observed.difference(sessions)
    return {
        "calendar": calendar_code,
        "expected_sessions": int(len(sessions)),
        "observed_sessions": int(len(observed)),
        "missing_sessions": int(len(missing)),
        "non_session_rows": int(len(extra)),
    }
