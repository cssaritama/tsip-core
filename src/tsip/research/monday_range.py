"""Private descriptive research from complete hourly crypto weeks."""

from __future__ import annotations

import numpy as np
import pandas as pd


def monday_range_summary(bars: pd.DataFrame, *, as_of: pd.Timestamp) -> dict:
    """Count weekly extremes from Monday to Sunday UTC, using bar-start times."""
    if bars.empty or bars.index.tz is None or as_of.tz is None:
        raise ValueError("Nonempty hourly bars and an explicit timezone-aware cutoff are required")

    index = bars.index.tz_convert("UTC")
    if index.has_duplicates or not index.equals(index.floor("h")):
        raise ValueError("Expected unique UTC-aligned hourly bar starts")
    prices = bars[["high", "low"]].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any() or (prices[:, 0] < prices[:, 1]).any():
        raise ValueError("Invalid hourly highs or lows")

    bars = bars.set_axis(index).sort_index()
    as_of = as_of.tz_convert("UTC")
    first_monday = index.min().normalize() - pd.Timedelta(days=index.min().dayofweek)
    counts = {key: 0 for key in ("both", "high_only", "low_only", "neither", "high_tied", "low_tied")}
    complete_weeks = incomplete_weeks = 0
    for start in pd.date_range(first_monday, as_of - pd.Timedelta(days=7), freq="7D"):
        hours = pd.date_range(start, periods=168, freq="h")
        if not hours.isin(index).all():
            incomplete_weeks += 1
            continue
        week = bars.loc[hours]
        monday, rest = week.iloc[:24], week.iloc[24:]
        high, later_high = monday.high.max(), rest.high.max()
        low, later_low = monday.low.min(), rest.low.min()
        keeps_high, keeps_low = high > later_high, low < later_low
        category = {
            (True, True): "both",
            (True, False): "high_only",
            (False, True): "low_only",
            (False, False): "neither",
        }[keeps_high, keeps_low]
        counts[category] += 1
        counts["high_tied"] += int(high == later_high)
        counts["low_tied"] += int(low == later_low)
        complete_weeks += 1

    return {
        "as_of_utc": as_of.isoformat(),
        "complete_weeks": complete_weeks,
        "incomplete_weeks": incomplete_weeks,
        "counts": counts,
        "frequencies_pct": {
            key: round(100 * value / complete_weeks, 2) if complete_weeks else None
            for key, value in counts.items()
        },
    }
