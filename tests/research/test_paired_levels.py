import pandas as pd
import pytest

from tsip.research.paired_levels import paired_level_baseline


def bars():
    dates = pd.to_datetime(
        ["2024-11-25", "2024-11-26", "2024-11-27", "2024-11-29", "2024-12-02", "2024-12-03", "2024-12-04"]
    )
    return pd.DataFrame(
        {
            "open": [100, 103, 100, 100, 100, 102, 100],
            "high": [101, 104, 101, 103, 101, 102, 104],
            "low": [99, 97, 97, 97, 99, 99, 97],
            "close": 100,
        },
        index=dates,
    )


def test_four_outcomes_opening_gap_holiday_and_cutoff():
    result = paired_level_baseline(bars(), down_pct=-2, up_pct=2, horizon=1, as_of=pd.Timestamp("2024-12-03"))
    assert result["eligible_windows"] == 5
    assert result["excluded_terminal_window"] == 1
    assert result["excluded_missing_window"] == 0
    assert result["counts"] == {"upper_first": 2, "lower_first": 1, "neither": 1, "ambiguous": 1}
    assert result["gap_beyond_level_counts"] == {"upper_first": 1, "lower_first": 0}
    assert result["ambiguity_bounds"]["upper_first"] == [0.4, 0.6]
    assert result["median_sessions_among_observed_first_touches"]["lower_first"] == 1
    assert sum(result["fractions"].values()) == pytest.approx(1)


def test_missing_session_is_not_counted_as_neither_or_bridged():
    daily = bars().drop(pd.Timestamp("2024-11-27"))
    result = paired_level_baseline(daily, down_pct=-2, up_pct=2, horizon=1, as_of=pd.Timestamp("2024-12-03"))
    assert result["excluded_missing_window"] == 1
    assert result["eligible_windows"] == 3
    assert result["counts"]["neither"] == 1
