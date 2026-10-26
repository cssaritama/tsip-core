"""Binance public market data archive (https://data.binance.vision).

Monthly and daily ZIP files of spot klines, each published with a SHA-256
checksum file. Spot kline timestamps are in milliseconds until the end of
2024 and in microseconds from 2025-01-01; both are handled.

Note: the Binance REST API refuses requests from some jurisdictions; the
public archive is a separate service and is used here only as a
cross-validation source.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import Callable

import pandas as pd

from tsip.data.schema import make_bars
from tsip.data.sources.base import SourceUnavailable, now_utc, utc_timestamp
from tsip.http import HTTPError, get_bytes

BASE_URL = "https://data.binance.vision/data/spot"
SOURCE = "binance"
KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore",
]


def monthly_url(symbol: str, interval: str, year: int, month: int) -> str:
    return f"{BASE_URL}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{year}-{month:02d}.zip"


def daily_url(symbol: str, interval: str, day: pd.Timestamp) -> str:
    return f"{BASE_URL}/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{day:%Y-%m-%d}.zip"


def _to_utc(values: pd.Series) -> pd.DatetimeIndex:
    numbers = values.astype("int64")
    # 16-digit values are microseconds, 13-digit values are milliseconds.
    unit = "us" if numbers.iloc[0] > 10**14 else "ms"
    return pd.DatetimeIndex(pd.to_datetime(numbers, unit=unit, utc=True))


def parse_klines(text: str) -> pd.DataFrame:
    lines = [line for line in text.splitlines() if line.strip()]
    if lines and not lines[0].split(",")[0].strip().isdigit():
        lines = lines[1:]  # header row present in some files
    if not lines:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([], tz="UTC"))
    frame = pd.read_csv(io.StringIO("\n".join(lines)), header=None, names=KLINE_COLUMNS)
    frame.index = _to_utc(frame["open_time"])
    frame.index.name = "timestamp"
    frame = frame[["open", "high", "low", "close", "volume"]].astype(float).sort_index()
    # Around exchange outages (for example February 2018) the archive holds bars that open
    # off the minute grid; they are not regular bars of the interval and are left out.
    return frame[frame.index == frame.index.floor("min")]


def verify_checksum(payload: bytes, checksum_text: str) -> bool:
    expected = checksum_text.strip().split()[0].lower()
    return hashlib.sha256(payload).hexdigest() == expected


def _download(url: str, getter: Callable[[str], bytes]) -> pd.DataFrame | None:
    try:
        payload = getter(url)
    except HTTPError as exc:
        if exc.status == 404:
            return None
        raise SourceUnavailable(f"Binance archive request failed: {exc}") from exc
    try:
        checksum = getter(url + ".CHECKSUM").decode("utf-8")
        if not verify_checksum(payload, checksum):
            raise SourceUnavailable(f"checksum mismatch for {url}")
    except HTTPError:
        pass  # checksum files are occasionally missing for the latest daily file
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        name = archive.namelist()[0]
        return parse_klines(archive.read(name).decode("utf-8"))


def fetch(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    *,
    getter: Callable[[str], bytes] = get_bytes,
) -> pd.DataFrame:
    end_ts = utc_timestamp(end, now_utc())
    start_ts = utc_timestamp(start, end_ts - pd.Timedelta(days=365))
    current_month = end_ts.tz_localize(None).to_period("M")
    frames = []
    for period in pd.period_range(start_ts.tz_localize(None).to_period("M"), current_month, freq="M"):
        if period < current_month:
            frame = _download(monthly_url(symbol, interval, period.year, period.month), getter)
            if frame is not None:
                frames.append(frame)
        else:
            day = period.start_time.tz_localize("UTC")
            while day.normalize() < end_ts.normalize():
                frame = _download(daily_url(symbol, interval, day), getter)
                if frame is not None:
                    frames.append(frame)
                day += pd.Timedelta(days=1)
    if not frames:
        raise SourceUnavailable("Binance archive returned no files for the requested range")
    data = pd.concat(frames).sort_index()
    data = data[~data.index.duplicated(keep="last")]
    data = data[(data.index >= start_ts) & (data.index <= end_ts)]
    instrument = "BTC-USDT" if symbol.upper() == "BTCUSDT" else symbol.upper()
    return make_bars(data, instrument=instrument, source=SOURCE, timeframe=interval)
