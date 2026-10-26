from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


class SourceUnavailable(RuntimeError):
    """The source could not be reached or returned no usable data."""


def utc_timestamp(value: str | datetime | pd.Timestamp | None, default: pd.Timestamp | None = None) -> pd.Timestamp:
    if value is None:
        if default is None:
            raise ValueError("a timestamp is required")
        return default
    ts = pd.Timestamp(value)
    if ts.tz is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def now_utc() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(timezone.utc))


def iso_z(ts: pd.Timestamp) -> str:
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
