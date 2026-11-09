"""Private holdout comparison of real weekly levels and volatility-matched geometry."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import replicates
from tsip.research.paired_levels import OUTCOMES, session_bars
from tsip.studies.first_passage import UP, first_passage
from tsip.studies.revisit import OPEN_LEVEL_PERIODS, VOL_WINDOW

HORIZON = 5
CONTROL_LIMIT = 20
MIN_CONTROLS = 5
VOL_TOLERANCE = 0.20
BLOCK_SESSIONS = 20
MIN_INTERVAL_ANCHORS = 40


def weekly_reference_pair(bars: pd.DataFrame, anchor: int) -> tuple[float, float] | None:
    """Read only through the anchor; caller supplies calendar-complete session rows."""
    observed = bars.iloc[: anchor + 1]
    weeks = observed.index.to_period("W-SUN")
    prior = weeks.unique()[:-1][-OPEN_LEVEL_PERIODS["week"] :]
    if len(prior) != OPEN_LEVEL_PERIODS["week"]:
        return None
    window = observed.loc[weeks >= prior[0], ["high", "low"]]
    if window.isna().any().any():
        return None
    close = float(observed["close"].iloc[-1])
    highs = window["high"].to_numpy()
    lows = window["low"].to_numpy()
    window_weeks = window.index.to_period("W-SUN")
    above, below = [], []
    for week in prior:
        rows = np.flatnonzero(window_weeks == week)
        high, low = highs[rows].max(), lows[rows].min()
        later = rows[-1] + 1
        if high > close and not (highs[later:] >= high).any():
            above.append(float(high))
        if low < close and not (lows[later:] <= low).any():
            below.append(float(low))
    return (max(below), min(above)) if above and below else None


def matched_weekly_levels(daily: pd.DataFrame, *, as_of: pd.Timestamp) -> dict:
    sessions, daily = session_bars(daily, as_of)
    bars = daily.reindex(sessions)
    opens, highs, lows, closes = bars[["open", "high", "low", "close"]].to_numpy().T
    vol = np.log(bars["close"]).diff().rolling(VOL_WINDOW).std().to_numpy()
    split = int(len(bars) * 0.70)
    valid_anchor = np.isfinite(vol) & (vol > 0)
    # Require all future rows before a path enters either pool.
    complete = np.isfinite(closes)
    anchors = [i for i in range(len(bars) - HORIZON) if valid_anchor[i] and complete[i + 1 : i + HORIZON + 1].all()]
    controls = np.array([i for i in anchors if i + HORIZON < split], dtype=int)
    holdout = [i for i in anchors if i >= split]

    def score(i: int, lower: float, upper: float) -> int:
        window = slice(i + 1, i + HORIZON + 1)
        return int(first_passage(opens[window], highs[window], lows[window], np.array([lower]), np.array([upper]))[0])

    actual_counts = dict.fromkeys(OUTCOMES, 0)
    control_totals = dict.fromkeys(OUTCOMES, 0.0)
    deltas = np.full(len(bars) - split, np.nan)
    no_pair = no_match = 0
    match_counts = []
    for i in holdout:
        pair = weekly_reference_pair(bars, i)
        if pair is None:
            no_pair += 1
            continue
        distance = np.abs(vol[controls] / vol[i] - 1)
        nearest = controls[np.argsort(distance, kind="stable")]
        matched = nearest[np.abs(vol[nearest] / vol[i] - 1) <= VOL_TOLERANCE][:CONTROL_LIMIT]
        if len(matched) < MIN_CONTROLS:
            no_match += 1
            continue
        log_distances = np.log(np.asarray(pair) / closes[i])
        actual = score(i, *pair)
        comparison = np.array([score(j, *(closes[j] * np.exp(log_distances * vol[j] / vol[i]))) for j in matched])
        match_counts.append(len(matched))
        for name, code in OUTCOMES.items():
            actual_counts[name] += int(actual == code)
            control_totals[name] += float((comparison == code).mean())
        deltas[i - split] = 100 * (int(actual == UP) - (comparison == UP).mean())

    n = len(match_counts)
    estimate = float(np.nanmean(deltas)) if n else None
    interval = None
    if n >= MIN_INTERVAL_ANCHORS and len(deltas) >= 2 * BLOCK_SESSIONS:

        def mean_delta(units: dict) -> np.ndarray:
            usable = units["delta"][np.isfinite(units["delta"])]
            return np.array([usable.mean() if len(usable) else np.nan])

        draws = replicates({"delta": deltas}, mean_delta, block=BLOCK_SESSIONS, reps=1000, seed=27).ravel()
        interval = np.quantile(draws[np.isfinite(draws)], [0.025, 0.975]).tolist()

    return {
        "study": "matched_weekly_levels_private",
        "as_of_session": as_of.date().isoformat(),
        "holdout_first_session": sessions[split].date().isoformat(),
        "horizon_sessions": HORIZON,
        "control_pool_windows": len(controls),
        "control_pool_last_outcome_session": (
            sessions[controls[-1] + HORIZON].date().isoformat() if len(controls) else None
        ),
        "holdout_sessions": len(deltas),
        "holdout_complete_windows_with_volatility": len(holdout),
        "excluded_no_pair_or_history_gap": no_pair,
        "excluded_insufficient_controls": no_match,
        "matched_anchors": n,
        "median_controls_per_anchor": float(np.median(match_counts)) if n else None,
        "actual_counts": actual_counts,
        "actual_fractions": {name: count / n if n else None for name, count in actual_counts.items()},
        "control_fractions": {name: total / n if n else None for name, total in control_totals.items()},
        "upper_first_difference_pp": estimate,
        "upper_first_exploratory_block95_pp": interval,
        "interpretation": "Holdout comparison conditional on a fixed historical control pool; no execution or grading model.",
    }
