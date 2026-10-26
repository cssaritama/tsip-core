"""Import locally stored vendor files into canonical bars.

Supported layouts:

* ``canonical`` – header with ``date`` or ``timestamp`` plus OHLCV columns.
  Intraday timestamps without an offset are interpreted in ``local_tz``.
* ``kibot`` – no header, ``MM/DD/YYYY,open,high,low,close,volume`` daily rows.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tsip.data.schema import make_bars


def load(
    path: str | Path,
    *,
    instrument: str,
    timeframe: str,
    layout: str = "canonical",
    local_tz: str = "America/New_York",
    source: str = "local",
    price_basis: str = "raw",
) -> pd.DataFrame:
    path = Path(path)
    if layout == "kibot":
        frame = pd.read_csv(path, header=None, names=["date", "open", "high", "low", "close", "volume"])
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop("date"), format="%m/%d/%Y"), name="date")
    elif layout == "canonical":
        frame = pd.read_csv(path)
        frame.columns = [c.strip().lower() for c in frame.columns]
        if "timestamp" in frame.columns:
            stamps = pd.to_datetime(frame.pop("timestamp"))
            if stamps.dt.tz is None:
                stamps = stamps.dt.tz_localize(local_tz, ambiguous="infer", nonexistent="shift_forward")
            frame.index = pd.DatetimeIndex(stamps.dt.tz_convert("UTC"), name="timestamp")
        else:
            frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop("date")).dt.normalize(), name="date")
    else:
        raise ValueError(f"unknown layout {layout!r}")
    return make_bars(frame, instrument=instrument, source=source, timeframe=timeframe, price_basis=price_basis)
