"""Historical paired-level geometry baseline using complete equity session windows."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.studies.first_passage import AMBIGUOUS, DOWN, NONE, UP, first_passage

OUTCOMES = {"upper_first": UP, "lower_first": DOWN, "neither": NONE, "ambiguous": AMBIGUOUS}


def paired_level_baseline(
    daily: pd.DataFrame, *, down_pct: float, up_pct: float, horizon: int, as_of: pd.Timestamp
) -> dict:
    """Apply the same two signed close-relative distances at each eligible historical close."""
    import exchange_calendars as xcals

    if not np.isfinite([down_pct, up_pct]).all() or not -100 < down_pct < 0 < up_pct:
        raise ValueError("Distances must be finite, with -100 < down_pct < 0 < up_pct")
    if not 1 <= horizon <= 20:
        raise ValueError("Horizon must be 1..20 sessions")
    index = pd.DatetimeIndex(daily.index)
    if (
        index.tz is not None
        or not index.is_unique
        or not index.is_monotonic_increasing
        or not index.equals(index.normalize())
    ):
        raise ValueError("Expected ordered, unique, timezone-naive session dates")
    if as_of.tz is not None or pd.isna(as_of) or as_of != as_of.normalize():
        raise ValueError("Cutoff must be a completed session date without a time zone")
    daily = daily.loc[:as_of]
    if daily.empty:
        raise ValueError("No observations on or before the cutoff")
    start = daily.index[0]
    calendar = xcals.get_calendar("XNYS", start=start - pd.Timedelta(days=7), end=as_of + pd.Timedelta(days=7))
    if not calendar.is_session(as_of):
        raise ValueError("Cutoff must be an exchange session")
    sessions = pd.DatetimeIndex(calendar.sessions_in_range(start, as_of)).tz_localize(None)
    if not daily.index.isin(sessions).all():
        raise ValueError("Input includes dates outside the exchange calendar")
    values = daily[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("OHLC must be finite and positive")
    opens, highs, lows, closes = values.T
    if (highs < np.maximum(opens, closes)).any() or (lows > np.minimum(opens, closes)).any():
        raise ValueError("High and low must enclose open and close")

    counts = dict.fromkeys(OUTCOMES, 0)
    gaps = {"upper_first": 0, "lower_first": 0}
    delays: dict[str, list[int]] = {"upper_first": [], "lower_first": []}
    missing_window = terminal = 0
    positions = daily.index.get_indexer(sessions)
    for i, anchor in enumerate(positions):
        if anchor < 0:
            continue
        future = positions[i + 1 : i + 1 + horizon]
        if len(future) != horizon:
            terminal += 1
            continue
        if (future < 0).any():
            missing_window += 1
            continue
        close = closes[anchor]
        lower, upper = close * np.array([1 + down_pct / 100, 1 + up_pct / 100])
        code = first_passage(opens[future], highs[future], lows[future], np.array([lower]), np.array([upper]))[0]
        outcome = next(name for name, value in OUTCOMES.items() if code == value)
        counts[outcome] += 1
        if outcome in delays:
            reached = (highs[future] >= upper) | (lows[future] <= lower)
            first = int(np.argmax(reached))
            delays[outcome].append(first + 1)
            opening = opens[future[first]]
            gaps[outcome] += int(opening > upper if code == UP else opening < lower)

    n = sum(counts.values())

    def fraction(count: int) -> float | None:
        return count / n if n else None

    return {
        "study": "paired_level_geometry_baseline",
        "as_of_session": as_of.date().isoformat(),
        "first_observed_session": start.date().isoformat(),
        "down_pct": down_pct,
        "up_pct": up_pct,
        "horizon_sessions": horizon,
        "eligible_windows": n,
        "excluded_missing_window": missing_window,
        "excluded_terminal_window": terminal,
        "counts": counts,
        "fractions": {name: fraction(count) for name, count in counts.items()},
        "gap_beyond_level_counts": gaps,
        "median_sessions_among_observed_first_touches": {
            name: float(np.median(items)) if items else None for name, items in delays.items()
        },
        "ambiguity_bounds": {
            name: [fraction(counts[name]), fraction(counts[name] + counts["ambiguous"])] for name in delays
        },
        "interpretation": "Descriptive fixed-distance history; overlapping windows; no prediction or fill model.",
    }
