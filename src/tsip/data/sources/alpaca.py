"""Alpaca Market Data API v2 (US equities and ETFs).

A free Alpaca account gives historical bars from 2016 onwards. Consolidated
(SIP) history is available on the free plan except for the most recent
15 minutes, so requests end 20 minutes before now. If the account cannot
query SIP data the connector falls back to the IEX feed and records it.

Credentials are read from ``ALPACA_API_KEY_ID`` / ``ALPACA_API_SECRET_KEY``
(or the ``APCA_*`` equivalents). They are never written to disk.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import pandas as pd

from tsip.data.schema import make_bars
from tsip.data.sources.base import SourceUnavailable, iso_z, now_utc, utc_timestamp
from tsip.http import HTTPError, build_url, get_json

BASE_URL = "https://data.alpaca.markets/v2/stocks"
TIMEFRAMES = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "30min": "30Min", "1h": "1Hour", "1d": "1Day"}
SOURCE = "alpaca"


def credentials(key_id: str | None = None, secret_key: str | None = None) -> tuple[str, str]:
    key = key_id or os.environ.get("ALPACA_API_KEY_ID") or os.environ.get("APCA_API_KEY_ID")
    secret = secret_key or os.environ.get("ALPACA_API_SECRET_KEY") or os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise SourceUnavailable("Alpaca credentials not configured (ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY)")
    return key, secret


def parse_bars(bars: list[dict[str, Any]]) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([], tz="UTC"))
    frame = pd.DataFrame(bars)
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame["t"], utc=True), name="timestamp")
    frame = frame.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return frame[["open", "high", "low", "close", "volume"]].astype(float).sort_index()


def _pages(url_base: str, params: dict[str, Any], headers: dict[str, str], getter: Callable[..., Any]) -> list[dict]:
    collected: list[dict] = []
    token = None
    while True:
        payload = getter(build_url(url_base, {**params, "page_token": token}), headers)
        collected.extend(payload.get("bars") or [])
        token = payload.get("next_page_token")
        if not token:
            return collected


def fetch(
    symbol: str = "SPY",
    timeframe: str = "30min",
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    *,
    adjustment: str = "raw",
    feed: str = "sip",
    key_id: str | None = None,
    secret_key: str | None = None,
    getter: Callable[..., Any] = get_json,
) -> pd.DataFrame:
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"unsupported timeframe {timeframe!r}; use one of {sorted(TIMEFRAMES)}")
    key, secret = credentials(key_id, secret_key)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    end_ts = utc_timestamp(end, now_utc() - pd.Timedelta(minutes=20))
    start_ts = utc_timestamp(start, pd.Timestamp("2016-01-01", tz="UTC"))
    params = {
        "timeframe": TIMEFRAMES[timeframe],
        "start": iso_z(start_ts),
        "end": iso_z(end_ts),
        "limit": 10000,
        "adjustment": adjustment,
        "feed": feed,
        "sort": "asc",
    }
    url = f"{BASE_URL}/{symbol.upper()}/bars"
    used_feed = feed
    try:
        rows = _pages(url, params, headers, getter)
    except HTTPError as exc:
        if exc.status == 403 and feed == "sip":
            used_feed = "iex"
            try:
                rows = _pages(url, {**params, "feed": "iex"}, headers, getter)
            except HTTPError as exc2:
                raise SourceUnavailable(f"Alpaca request failed: {exc2}") from exc2
        else:
            raise SourceUnavailable(f"Alpaca request failed: {exc}") from exc
    data = parse_bars(rows)
    if data.empty:
        raise SourceUnavailable(f"Alpaca returned no bars for {symbol}")
    basis = "raw" if adjustment == "raw" else f"adjusted:{adjustment}"
    if timeframe == "1d":
        data.index = data.index.tz_convert("America/New_York").tz_localize(None).normalize()
        data.index.name = "date"
    bars = make_bars(data, instrument=symbol.upper(), source=SOURCE, timeframe=timeframe, price_basis=basis)
    bars.attrs["feed"] = used_feed
    return bars
