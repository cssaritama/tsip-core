import pandas as pd
import pytest

from tsip.research.monday_range import monday_range_summary


def test_only_complete_utc_weeks_count_and_ties_are_separate():
    hours = pd.date_range("2026-10-26", periods=3 * 168, freq="h", tz="UTC")
    bars = pd.DataFrame({"high": 100, "low": 90}, index=hours)
    bars.loc[hours[0], ["high", "low"]] = [101, 89]
    bars.loc[hours[2 * 168], "high"] = 101
    bars = bars.drop(hours[168 + 30])

    report = monday_range_summary(bars, as_of=pd.Timestamp("2026-11-16T00:00Z"))
    assert report["complete_weeks"] == 2
    assert report["incomplete_weeks"] == 1
    assert report["counts"] == {
        "both": 1, "high_only": 1, "low_only": 0, "neither": 0, "high_tied": 0, "low_tied": 1
    }
    assert report["frequencies_pct"]["both"] == 50.0

    cutoff = monday_range_summary(bars, as_of=pd.Timestamp("2026-11-15T23:00Z"))
    assert cutoff["complete_weeks"] == 1


def test_rejects_duplicate_or_misaligned_bar_starts():
    start = pd.Timestamp("2026-11-02T00:00Z")
    for other in (start, start + pd.Timedelta(minutes=30)):
        bars = pd.DataFrame({"high": 100, "low": 90}, index=[start, other])
        with pytest.raises(ValueError, match="UTC-aligned"):
            monday_range_summary(bars, as_of=start)
