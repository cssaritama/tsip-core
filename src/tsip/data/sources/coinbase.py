"""Coinbase Exchange public candles (no API key required).

Endpoint: ``GET /products/{product}/candles`` returns at most 300 candles per
request as ``[time, low, high, open, close, volume]`` rows, newest first.
Hourly BTC-USD history starts in mid-2015.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pandas as pd

from tsip.data.schema import make_bars
from tsip.data.sources.base import SourceUnavailable, iso_z, now_utc, utc_timestamp
from tsip.http import HTTPError, build_url, get_json

BASE_URL = "https://api.exchange.coinbase.com"
GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}
MAX_CANDLES = 300
SOURCE = "coinbase"


def plan_windows(start: pd.Timestamp, end: pd.Timestamp, step_seconds: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Split ``[start, end]`` into request windows of at most 300 candles."""
    step = pd.Timedelta(seconds=step_seconds)
    span = step * (MAX_CANDLES - 1)
    windows = []
    cursor = start.floor(f"{step_seconds}s")
    while cursor <= end:
        window_end = min(cursor + span, end)
        windows.append((cursor, window_end))
        cursor = window_end + step
    return windows


def parse_candles(rows: list[list[Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([], tz="UTC"))
    frame = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    frame.index = pd.to_datetime(frame.pop("time").astype("int64"), unit="s", utc=True)
    frame.index.name = "timestamp"
    return frame[["open", "high", "low", "close", "volume"]].astype(float).sort_index()


def fetch(
    product: str = "BTC-USD",
    timeframe: str = "1h",
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    *,
    getter: Callable[..., Any] = get_json,
    pause: float = 0.2,
) -> pd.DataFrame:
    if timeframe not in GRANULARITY:
        raise ValueError(f"unsupported timeframe {timeframe!r}; use one of {sorted(GRANULARITY)}")
    step = GRANULARITY[timeframe]
    end_ts = utc_timestamp(end, now_utc()).floor(f"{step}s") - pd.Timedelta(seconds=step)  # last closed bar
    start_ts = utc_timestamp(start, end_ts - pd.Timedelta(days=30))
    frames = []
    for w_start, w_end in plan_windows(start_ts, end_ts, step):
        url = build_url(
            f"{BASE_URL}/products/{product}/candles",
            {"granularity": step, "start": iso_z(w_start), "end": iso_z(w_end)},
        )
        try:
            rows = getter(url)
        except HTTPError as exc:
            raise SourceUnavailable(f"Coinbase request failed: {exc}") from exc
        if isinstance(rows, dict):  # error payload
            raise SourceUnavailable(f"Coinbase error: {rows}")
        frames.append(parse_candles(rows))
        if pause:
            time.sleep(pause)
    data = pd.concat(frames) if frames else parse_candles([])
    data = data[(data.index >= start_ts) & (data.index <= end_ts)]
    if data.empty:
        raise SourceUnavailable("Coinbase returned no candles for the requested range")
    return make_bars(data, instrument=product.upper(), source=SOURCE, timeframe=timeframe)
