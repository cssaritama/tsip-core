"""Auditable, descriptive weekly-barrier research; never a trading simulator.

The exact exchange-session calendar is mandatory. The primary complete-window
cohort excludes terminal windows by date alone (including early-resolved ones);
all selected observations are also retained, with explicit right-censoring.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import math
import numpy as np
import pandas as pd

OUTCOMES = ("upper_first", "lower_first", "both_same_bar_ambiguous", "unreached", "right_censored")


def _check_prices(df: pd.DataFrame, calendar_sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if not isinstance(df.index, pd.DatetimeIndex) or df.empty:
        raise ValueError("nonempty daily DatetimeIndex required")
    if df.index.tz is not None or not df.index.equals(df.index.normalize()):
        raise ValueError("prices must use timezone-naive exchange session dates")
    if not df.index.is_unique or not df.index.is_monotonic_increasing:
        raise ValueError("prices must have unique increasing session dates")
    cols = ["open", "high", "low", "close"]
    if not set(cols).issubset(df.columns):
        raise ValueError("OHLC columns required")
    values = df[cols].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("finite positive OHLC required")
    if ((df.high < df[["open", "close"]].max(axis=1)) |
        (df.low > df[["open", "close"]].min(axis=1)) | (df.high < df.low)).any():
        raise ValueError("OHLC enclosure violation")
    sessions = pd.DatetimeIndex(calendar_sessions)
    if sessions.tz is not None:
        raise ValueError("calendar must use timezone-naive exchange session dates")
    if not sessions.is_unique or not sessions.is_monotonic_increasing or not sessions.equals(sessions.normalize()):
        raise ValueError("calendar must have unique increasing date labels")
    first_monday = df.index[0].to_period("W-SUN").start_time
    # Requiring the previous week's coverage prevents an initial partial week
    # from being silently accepted as a complete historical reference.
    if sessions.empty or sessions[0] > first_monday - pd.Timedelta(days=7) or sessions[-1] < df.index[-1]:
        raise ValueError("calendar must cover previous Monday before first data week through final data date")
    expected = sessions[(sessions >= df.index[0]) & (sessions <= df.index[-1])]
    if not expected.equals(df.index):
        missing = expected.difference(df.index).strftime("%Y-%m-%d").tolist()
        extra = df.index.difference(expected).strftime("%Y-%m-%d").tolist()
        raise ValueError(f"calendar mismatch; missing={missing[:10]}, non_sessions={extra[:10]}")
    return sessions


def previous_complete_week_features(df: pd.DataFrame, calendar_sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Use previous CALENDAR week only, with exact observed session coverage.

    A holiday-shortened week is complete if all scheduled sessions exist. The
    preceding week before the dataset starts is unavailable, never backfilled.
    """
    sessions = _check_prices(df, calendar_sessions)
    keys = df.index.to_period("W-SUN")
    calendar_groups = {key: pd.DatetimeIndex(group) for key, group in
                       pd.Series(sessions, index=sessions).groupby(sessions.to_period("W-SUN"))}
    actual_groups = {key: group for key, group in df.groupby(keys)}
    references = {}
    for key, group in actual_groups.items():
        expected = calendar_groups.get(key, pd.DatetimeIndex([]))
        if group.index.equals(expected):
            references[key] = (float(group.low.min()), float(group.high.max()))
    rows = [references.get(key - 1, (np.nan, np.nan)) for key in keys]
    return pd.DataFrame(rows, columns=["prev_week_low", "prev_week_high"], index=df.index)


def _label(df: pd.DataFrame, i: int, low: float, high: float, horizon: int) -> dict:
    available = min(horizon, len(df) - i - 1)
    complete = available == horizon
    state = "unreached" if complete else "right_censored"
    touch = None
    gap = False
    for j in range(1, available + 1):
        bar = df.iloc[i + j]
        if bar.open >= high:
            state, gap = "upper_first", True
        elif bar.open <= low:
            state, gap = "lower_first", True
        elif bar.high >= high and bar.low <= low:
            state = "both_same_bar_ambiguous"
        elif bar.high >= high:
            state = "upper_first"
        elif bar.low <= low:
            state = "lower_first"
        else:
            continue
        touch = j
        break
    return {"outcome": state, "sessions_to_first_passage": touch,
            "opening_price_already_beyond_barrier": gap, "available_future_sessions": available,
            "complete_horizon": complete,
            "horizon_end": str(df.index[i + horizon].date()) if complete else None,
            "last_observed_label_date": str(df.index[i + (touch or available)].date())}


def _placebo_position(seed: int, signal_date: str) -> float:
    # Hash by signal date: appending future records cannot move old controls.
    raw = hashlib.sha256(f"TSIP_R81:{seed}:{signal_date}".encode()).digest()
    return 0.1 + 0.8 * int.from_bytes(raw[:8], "big") / (2**64 - 1)


def _counts(events: list[dict], label: str = "event") -> dict:
    c = Counter(item[label]["outcome"] for item in events)
    n = len(events)
    resolved = c["upper_first"] + c["lower_first"]
    return {"n": n, "counts": {state: c[state] for state in OUTCOMES},
            "upper_first_fraction_all_selected": c["upper_first"] / n if n else None,
            "upper_first_fraction_unambiguous_resolved": c["upper_first"] / resolved if resolved else None,
            "unreached_or_ambiguous_or_right_censored_fraction":
                (n - resolved) / n if n else None}


def _blocked_intervals(events: list[dict], reps: int, block_weeks: int, seed: int) -> dict:
    """Paired circular moving-block percentile intervals over calendar weeks.

    Empty weeks are retained. This addresses local serial dependence, not
    structural breaks or unmeasured confounding. No independence p-value.
    """
    if not events:
        return {"status": "insufficient_sample", "n_week_blocks": 0}
    event_weeks = pd.PeriodIndex([e["signal_date"] for e in events], freq="W-SUN")
    weeks = pd.period_range(event_weeks.min(), event_weeks.max(), freq="W-SUN")
    n = len(weeks)
    if len(events) < 8 or n < 2 * block_weeks:
        return {"status": "insufficient_sample", "n_week_blocks": n,
                "minimum_weeks_required": 2 * block_weeks, "minimum_events_required": 8}
    # columns: n, upper, resolved, placebo upper
    rows = np.zeros((n, 4), dtype=float)
    loc = {w: k for k, w in enumerate(weeks)}
    for e, w in zip(events, event_weeks):
        actual = e["event"]["outcome"]
        rows[loc[w]] += [1, actual == "upper_first", actual in ("upper_first", "lower_first"),
                         e["placebo"]["outcome"] == "upper_first"]
    rng = np.random.default_rng(seed)
    estimates = []
    conditional = []
    for _ in range(reps):
        starts = rng.integers(0, n, size=math.ceil(n / block_weeks))
        positions = ((starts[:, None] + np.arange(block_weeks)[None, :]) % n).ravel()[:n]
        total, upper, resolved, placebo_upper = rows[positions].sum(axis=0)
        if total:
            estimates.append((upper / total, (upper - placebo_upper) / total))
        if resolved:
            conditional.append(upper / resolved)
    values = np.asarray(estimates)
    return {"status": "descriptive_dependency_aware_interval", "method": "circular_moving_calendar_week_blocks",
            "repetitions": reps, "seed": seed, "block_weeks": block_weeks, "n_week_blocks": n,
            "upper_first_fraction_all_complete_ci95": np.quantile(values[:, 0], [.025, .975]).tolist() if len(values) else None,
            "paired_actual_minus_placebo_upper_fraction_ci95": np.quantile(values[:, 1], [.025, .975]).tolist() if len(values) else None,
            "upper_first_fraction_resolved_ci95": np.quantile(conditional, [.025, .975]).tolist() if conditional else None,
            "valid_unconditional_replicates": len(values), "valid_conditional_replicates": len(conditional),
            "caution": "Percentile intervals are exploratory, sensitive to block length and regime shifts; no multiplicity correction or causal/forecast claim."}


def _summary(events: list[dict], reps: int, block_weeks: int, seed: int) -> dict:
    complete = [e for e in events if e["event"]["complete_horizon"]]
    return {"all_selected_including_terminal": _counts(events),
            "primary_complete_horizon": _counts(complete),
            "placebo_same_complete_horizon_cohort": _counts(complete, "placebo"),
            "excluded_from_primary_by_date_only": len(events) - len(complete),
            "intervals_primary": _blocked_intervals(complete, reps, block_weeks, seed)}


def run_path_research(df: pd.DataFrame, calendar_sessions: pd.DatetimeIndex,
                      horizons: tuple[int, ...] = (1, 5, 10, 20), cutoff: str = "2024-01-01",
                      bootstrap_reps: int = 1000, block_weeks: int = 8, seed: int = 810,
                      selection: str = "first_eligible_per_week") -> dict:
    """Return JSON-safe event records, matched controls and purged temporal summaries.

    All OHLC must share one price basis. A continuous split-adjusted price series
    is appropriate for price-coordinate research; dividend-adjusted OHLC changes
    barrier meaning. This function cannot certify vendor adjustment semantics.
    """
    if not horizons or any(not isinstance(h, int) or isinstance(h, bool) or not 1 <= h <= 100 for h in horizons):
        raise ValueError("horizons must contain integers 1..100")
    if len(set(horizons)) != len(horizons):
        raise ValueError("duplicate horizons")
    if not isinstance(bootstrap_reps, int) or bootstrap_reps < 100:
        raise ValueError("bootstrap_reps must be integer >=100")
    if not isinstance(block_weeks, int) or block_weeks < 1:
        raise ValueError("block_weeks must be integer >=1")
    if selection not in ("first_eligible_per_week", "every_eligible_day"):
        raise ValueError("unsupported selection")
    split_date = pd.Timestamp(cutoff)
    if pd.isna(split_date) or split_date.tz is not None or split_date != split_date.normalize():
        raise ValueError("cutoff must be an exchange-session date label")
    feat = previous_complete_week_features(df, calendar_sessions)
    valid = (df.close > feat.prev_week_low) & (df.close < feat.prev_week_high)
    candidates = np.flatnonzero(valid.to_numpy()).tolist()
    selected = []
    seen = set()
    for i in candidates:
        week = df.index[i].to_period("W-SUN")
        if selection == "every_eligible_day" or week not in seen:
            selected.append(i)
            seen.add(week)
    trailing_mean = df.close.rolling(200, min_periods=200).mean()
    output = {}
    for horizon in horizons:
        events = []
        excluded_nonpositive_placebo = 0
        for i in selected:
            low, high = map(float, feat.iloc[i][["prev_week_low", "prev_week_high"]])
            day = str(df.index[i].date())
            position = _placebo_position(seed, day)
            width = high - low
            placebo_low = float(df.close.iloc[i]) - position * width
            placebo_high = placebo_low + width
            if placebo_low <= 0:
                excluded_nonpositive_placebo += 1
                continue
            actual = _label(df, i, low, high, horizon)
            placebo = _label(df, i, placebo_low, placebo_high, horizon)
            before = df.index[i] < split_date
            partition = ("discovery" if before and actual["horizon_end"] is not None and
                         pd.Timestamp(actual["horizon_end"]) < split_date else
                         "purged_boundary" if before else "later_descriptive_holdout")
            regime = ("insufficient_200_session_history" if pd.isna(trailing_mean.iloc[i]) else
                      "above_sma200_at_signal_close" if df.close.iloc[i] >= trailing_mean.iloc[i] else
                      "below_sma200_at_signal_close")
            events.append({"signal_date": day, "prior_calendar_week": str(df.index[i].to_period("W-SUN") - 1),
                           "prior_week_low": low, "prior_week_high": high,
                           "signal_close": float(df.close.iloc[i]), "regime_at_signal_close": regime,
                           "placebo_low": placebo_low, "placebo_high": placebo_high,
                           "partition": partition, "event": actual, "placebo": placebo})
        partition_stats = {part: _summary([e for e in events if e["partition"] == part],
                           bootstrap_reps, block_weeks, seed + horizon + n)
                           for n, part in enumerate(("discovery", "later_descriptive_holdout", "purged_boundary"))}
        output[str(horizon)] = {"horizon_sessions": horizon,
                               "summary": _summary(events, bootstrap_reps, block_weeks, seed + horizon),
                               "partitions": partition_stats,
                               "regime_primary_counts": {regime: _counts([e for e in events if e["regime_at_signal_close"] == regime and e["event"]["complete_horizon"]])
                                    for regime in ("insufficient_200_session_history", "above_sma200_at_signal_close", "below_sma200_at_signal_close")},
                               "excluded_nonpositive_placebo": excluded_nonpositive_placebo,
                               "events": events}
    return {"schema_version": "tsip.path-research.v8.1", "study": "previous_complete_week_first_passage",
            "data_start": str(df.index[0].date()), "data_end": str(df.index[-1].date()), "n_price_sessions": len(df),
            "selection": selection, "n_inside_range_candidates": len(candidates), "n_selected_signal_dates": len(selected),
            "cutoff": str(split_date.date()), "horizons": output,
            "control": {"type": "matched_signal_dates_same_width_random_position", "seed": seed,
                        "position_uniform_range": [.1, .9], "n_placebos_per_event": 1,
                        "meaning": "Same dates, width and horizon; random in-band close position. This tests sensitivity to actual level placement, not a causal null and not a trading strategy."},
            "warnings": ["Descriptive historical research only; not a forecast, calibrated probability, strategy or evidence of profitable trading.",
                         "A gap beyond a barrier establishes observed ordering at session open, not a trade at the skipped price.",
                         "Same-session dual touches with an inside-range open remain ambiguous.",
                         "Incomplete terminal windows are retained, but excluded from primary comparison by date regardless of their outcome.",
                         "The later partition is descriptive: split chosen in this release, not proof of a previously untouched out-of-sample test.",
                         "Discovery labels whose full horizon reaches the cutoff are purged; all features and placebo levels use only signal-time data.",
                         "Bootstrap addresses local dependence only; horizons and regime slices are exploratory and uncorrected for multiple comparisons.",
                         "SMA200 regimes use signal-close information; warmup observations stay explicitly labelled.",
                         "Caller must verify corporate actions, price basis, source provenance and usage rights separately."]}
