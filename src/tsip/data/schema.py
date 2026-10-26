"""Canonical bar schema.

Intraday bars are indexed by the bar *start* time in UTC (timezone-aware).
Daily bars are indexed by the session date (timezone-naive, normalised).
Columns are ``open, high, low, close, volume``. Metadata travels in
``DataFrame.attrs``: ``instrument``, ``source``, ``timeframe``, ``price_basis``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BAR_COLUMNS = ["open", "high", "low", "close", "volume"]
PRICE_COLUMNS = ["open", "high", "low", "close"]


class BarValidationError(ValueError):
    """Raised when a bar set violates the canonical schema."""


def make_bars(
    frame: pd.DataFrame,
    *,
    instrument: str,
    source: str,
    timeframe: str,
    price_basis: str = "raw",
) -> pd.DataFrame:
    """Return a canonical copy of ``frame`` with metadata attached."""
    missing = [c for c in PRICE_COLUMNS if c not in frame.columns]
    if missing:
        raise BarValidationError(f"missing columns: {missing}")
    out = frame.copy()
    if "volume" not in out.columns:
        out["volume"] = np.nan
    out = out[BAR_COLUMNS].astype(float)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out.attrs = {
        "instrument": instrument,
        "source": source,
        "timeframe": timeframe,
        "price_basis": price_basis,
    }
    return out


def is_intraday(timeframe: str) -> bool:
    return timeframe not in {"1d", "1w", "1mo"}


def grid_frequency(timeframe: str) -> str:
    """Pandas frequency of an intraday timeframe ("1h", "30min", or Binance style "15m")."""
    if timeframe.endswith("m") and not timeframe.endswith("min"):
        return timeframe[:-1] + "min"
    return timeframe


def align_to_grid(frame: pd.DataFrame, freq: str) -> tuple[pd.DataFrame, int]:
    """Fold bars that open off the interval grid into the bar of the interval that contains them.

    Exchange outages leave partial bars that start mid-interval (Binance, February 2018).
    They are real trades, so they are merged into their interval rather than dropped:
    first open, highest high, lowest low, last close, summed volume. Returns the aligned
    frame and the number of bars that were off the grid.
    """
    if frame.empty:
        return frame, 0
    frame = frame.sort_index()
    grid = frame.index.floor(freq)
    off_grid = int((grid != frame.index).sum())
    if off_grid == 0:
        return frame, 0
    grouped = frame.groupby(grid)
    out = pd.DataFrame(
        {
            "open": grouped["open"].first(),
            "high": grouped["high"].max(),
            "low": grouped["low"].min(),
            "close": grouped["close"].last(),
            "volume": grouped["volume"].sum(min_count=1),
        }
    )
    out.index.name = frame.index.name
    out.attrs = dict(frame.attrs)
    return out, off_grid


def validate_bars(bars: pd.DataFrame, *, strict: bool = True) -> dict:
    """Check schema and OHLC consistency.

    Returns a quality summary. With ``strict=True`` any violation raises
    :class:`BarValidationError`; otherwise violations are counted only.
    """
    timeframe = bars.attrs.get("timeframe", "")
    idx = bars.index
    problems: list[str] = []
    if not isinstance(idx, pd.DatetimeIndex):
        raise BarValidationError("index must be a DatetimeIndex")
    if is_intraday(timeframe):
        if idx.tz is None or str(idx.tz) != "UTC":
            problems.append("intraday index must be timezone-aware UTC")
    else:
        if idx.tz is not None:
            problems.append("daily index must be timezone-naive session dates")
        elif len(idx) and not (idx == idx.normalize()).all():
            problems.append("daily index must be normalised dates")
    if not idx.is_unique:
        problems.append("duplicate timestamps")
    if not idx.is_monotonic_increasing:
        problems.append("index not sorted")
    if bars.attrs.get("close_only"):
        close = bars["close"].to_numpy(dtype=float)
        bad = ~(np.isfinite(close) & (close > 0))
    else:
        prices = bars[PRICE_COLUMNS].to_numpy(dtype=float)
        finite = np.isfinite(prices).all(axis=1)
        positive = (prices > 0).all(axis=1)
        o, h, l, c = (bars[col].to_numpy(dtype=float) for col in PRICE_COLUMNS)
        with np.errstate(invalid="ignore"):
            enclosure = (h >= np.maximum(o, c)) & (l <= np.minimum(o, c)) & (h >= l)
        bad = ~(finite & positive & enclosure)
    n_bad = int(bad.sum())
    if n_bad:
        problems.append(f"{n_bad} bars violate finite/positive/OHLC-enclosure rules")
    summary = {
        "rows": int(len(bars)),
        "start": str(idx[0]) if len(idx) else None,
        "end": str(idx[-1]) if len(idx) else None,
        "invalid_bars": n_bad,
        "problems": problems,
        "status": "PASS" if not problems else "FAIL",
    }
    if strict and problems:
        raise BarValidationError("; ".join(problems))
    return summary


def drop_invalid(bars: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove bars that fail the OHLC rules; return the cleaned frame and count."""
    o, h, l, c = (bars[col].to_numpy(dtype=float) for col in PRICE_COLUMNS)
    with np.errstate(invalid="ignore"):
        ok = (
            np.isfinite(bars[PRICE_COLUMNS].to_numpy(dtype=float)).all(axis=1)
            & (bars[PRICE_COLUMNS].to_numpy(dtype=float) > 0).all(axis=1)
            & (h >= np.maximum(o, c))
            & (l <= np.minimum(o, c))
        )
    cleaned = bars.loc[ok].copy()
    cleaned.attrs = dict(bars.attrs)
    return cleaned, int((~ok).sum())


def has_ohlc(bars: pd.DataFrame) -> bool:
    """True when open, high and low are genuine observations (not close-only)."""
    return not bars.attrs.get("close_only", False) and bool(bars[["open", "high", "low"]].notna().all().all())
