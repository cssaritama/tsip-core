"""FRED daily close series (e.g. ``SP500``), no API key required.

FRED publishes the S&P 500 index close only; open, high and low are not
available and are never reconstructed. The series carries the index
provider's copyright: use it for research and publish aggregates only.
"""

from __future__ import annotations

import io
from collections.abc import Callable

import numpy as np
import pandas as pd

from tsip.data.schema import make_bars
from tsip.data.sources.base import SourceUnavailable
from tsip.http import HTTPError, build_url, get_bytes

BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
SOURCE = "fred"
INSTRUMENT_FOR_SERIES = {"SP500": "SPX", "NASDAQ100": "NDX"}


def parse_csv(text: str, series: str) -> pd.DataFrame:
    frame = pd.read_csv(io.StringIO(text))
    date_col = next(c for c in frame.columns if c.lower() in {"date", "observation_date"})
    value_col = series if series in frame.columns else frame.columns[-1]
    values = pd.to_numeric(frame[value_col].replace(".", np.nan), errors="coerce")
    out = pd.DataFrame(
        {"open": np.nan, "high": np.nan, "low": np.nan, "close": values.to_numpy(), "volume": np.nan},
        index=pd.DatetimeIndex(pd.to_datetime(frame[date_col]), name="date"),
    )
    return out.dropna(subset=["close"])


def fetch(
    series: str = "SP500", *, start: str | None = None, getter: Callable[[str], bytes] = get_bytes
) -> pd.DataFrame:
    url = build_url(BASE_URL, {"id": series, "cosd": start})
    try:
        text = getter(url).decode("utf-8")
    except HTTPError as exc:
        raise SourceUnavailable(f"FRED request failed: {exc}") from exc
    data = parse_csv(text, series)
    if data.empty:
        raise SourceUnavailable(f"FRED returned no observations for {series}")
    bars = make_bars(
        data,
        instrument=INSTRUMENT_FOR_SERIES.get(series, series),
        source=SOURCE,
        timeframe="1d",
        price_basis="close-only",
    )
    bars.attrs["close_only"] = True
    return bars
