import numpy as np
import pandas as pd

from tsip.research.matched_levels import matched_weekly_levels, weekly_reference_pair


def test_pair_uses_only_completed_prior_weeks_and_ignores_future_touch():
    dates = pd.bdate_range("2024-01-01", periods=64)
    frame = pd.DataFrame(dict(high=110.0, low=90.0, close=100.0), index=dates)
    frame.iloc[55:60, frame.columns.get_loc("high")] = 120
    frame.iloc[55:60, frame.columns.get_loc("low")] = 80
    frame.iloc[61:, frame.columns.get_loc("high")] = 125
    assert weekly_reference_pair(frame, 59) is None
    assert weekly_reference_pair(frame, 60) == (80, 120)
    assert weekly_reference_pair(frame, 61) is None
    frame.iloc[58, frame.columns.get_loc("high")] = np.nan
    assert weekly_reference_pair(frame, 60) is None


def test_short_history_has_no_eligible_matched_anchors():
    dates = pd.to_datetime(["2024-11-25", "2024-11-26", "2024-11-27", "2024-11-29", "2024-12-02"])
    frame = pd.DataFrame(dict(open=100.0, high=101.0, low=99.0, close=100.0), index=dates)
    summary = matched_weekly_levels(frame, as_of=dates[-1])
    assert summary["matched_anchors"] == 0
    assert summary["upper_first_difference_pp"] is None
    assert summary["upper_first_exploratory_block95_pp"] is None


def test_synthetic_holdout_matches_only_completed_control_paths():
    import exchange_calendars as xcals

    calendar = xcals.get_calendar("XNYS", start="2021-12-01", end="2025-01-10")
    dates = pd.DatetimeIndex(calendar.sessions_in_range("2022-01-03", "2024-12-31")).tz_localize(None)
    rng = np.random.default_rng(27)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, len(dates))))
    opening = close * (1 + rng.normal(0, 0.006, len(dates)))
    frame = pd.DataFrame(
        dict(
            open=opening, high=np.maximum(close, opening) * 1.003, low=np.minimum(close, opening) * 0.997, close=close
        ),
        index=dates,
    )
    result = matched_weekly_levels(frame, as_of=dates[-1])
    assert result["control_pool_last_outcome_session"] < result["holdout_first_session"]
    assert result["matched_anchors"] >= 40
    assert sum(result["actual_counts"].values()) == result["matched_anchors"]
    assert np.isclose(sum(result["control_fractions"].values()), 1.0)
    lower, upper = result["upper_first_exploratory_block95_pp"]
    assert -100 <= lower <= upper <= 100
