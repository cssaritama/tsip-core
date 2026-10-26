"""Stooq daily OHLC download (index symbols such as ``^spx``).

Availability of this endpoint varies over time; failures raise
:class:`SourceUnavailable` so callers can fall back to another source.
"""

from __future__ import annotations

import io
from collections.abc import Callable

import pandas as pd

from tsip.data.schema import make_bars
from tsip.data.sources.base import SourceUnavailable
from tsip.http import HTTPError, build_url, get_bytes

BASE_URL = "https://stooq.com/q/d/l/"
SOURCE = "stooq"
INSTRUMENT_FOR_SYMBOL = {"^spx": "SPX", "^ndx": "NDX", "spy.us": "SPY", "qqq.us": "QQQ"}


def parse_csv(text: str) -> pd.DataFrame:
    if not text.lower().startswith("date,"):
        raise SourceUnavailable(f"Stooq returned no data: {text[:80]!r}")
    frame = pd.read_csv(io.StringIO(text))
    frame.columns = [c.strip().lower() for c in frame.columns]
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop("date")), name="date")
    if "volume" not in frame.columns:
        frame["volume"] = float("nan")
    return frame[["open", "high", "low", "close", "volume"]].astype(float)


def fetch(
    symbol: str = "^spx", *, start: str | None = None, getter: Callable[[str], bytes] = get_bytes
) -> pd.DataFrame:
    url = build_url(BASE_URL, {"s": symbol, "i": "d"})
    try:
        text = getter(url).decode("utf-8", "replace")
    except HTTPError as exc:
        raise SourceUnavailable(f"Stooq request failed: {exc}") from exc
    data = parse_csv(text)
    if start:
        data = data[data.index >= pd.Timestamp(start)]
    if data.empty:
        raise SourceUnavailable("Stooq returned an empty series")
    return make_bars(
        data, instrument=INSTRUMENT_FOR_SYMBOL.get(symbol.lower(), symbol.upper()), source=SOURCE, timeframe="1d"
    )
