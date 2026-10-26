import numpy as np
import pandas as pd
import pytest

from tsip.data.quality import ohlc_reliability
from tsip.data.schema import make_bars
from tsip.evidence.card import EvidenceItem, widen_proportions
from tsip.evidence.grading import finalize_grades
from tsip.evidence.inference import wilson_interval
from tsip.frames import (
    has_ended,
    horizon_bars,
    period_bounds,
    period_key,
    period_label,
    starts_on_time,
)
from tsip.instruments import get_instrument
from tsip.report import assert_publishable
from tsip.studies import level_map, level_memory
from tsip.studies.common import StudyContext


def business_daily(start, end, seed=0, drift=0.0003):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, end)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, len(idx))))
    open_ = np.concatenate([[100.0], close[:-1]]) * np.exp(rng.normal(0, 0.002, len(idx)))
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, 0.004, len(idx))))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, 0.004, len(idx))))
    frame = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1.0},
        index=pd.DatetimeIndex(idx, name="date"),
    )
    return make_bars(frame, instrument="SPX", source="test", timeframe="1d")


def ctx(daily, reps=150):
    return StudyContext(instrument=get_instrument("SPX"), daily=daily, session_model="us_rth", reps=reps, seed=5)


@pytest.mark.parametrize("horizon", ["week", "month", "quarter", "half", "year"])
def test_period_keys_step_by_one_across_year_ends(horizon):
    days = pd.date_range("2023-11-15", "2026-02-15", freq="D")
    keys = period_key(days, horizon)
    steps = np.unique(np.diff(keys))
    assert set(steps) <= {0, 1}
    for key in np.unique(keys):
        start, end = period_bounds(key, horizon)
        inside = days[keys == key]
        assert inside.min() >= start and inside.max() <= end


def test_half_year_and_quarter_bounds_and_labels():
    key_h2 = int(period_key(pd.DatetimeIndex(["2026-10-23"]), "half")[0])
    assert period_label(key_h2, "half") == "H2 2026"
    assert period_bounds(key_h2, "half") == (pd.Timestamp("2026-07-01"), pd.Timestamp("2026-12-31"))
    key_q = int(period_key(pd.DatetimeIndex(["2026-02-28"]), "quarter")[0])
    assert period_label(key_q, "quarter") == "Q1 2026"
    assert period_bounds(key_q, "quarter")[1] == pd.Timestamp("2026-03-31")
    key_w = int(period_key(pd.DatetimeIndex(["2026-10-23"]), "week")[0])  # a Friday
    assert period_bounds(key_w, "week") == (pd.Timestamp("2026-10-19"), pd.Timestamp("2026-10-25"))


def test_period_edges_for_exchange_and_crypto_calendars():
    # equities: data ending Friday completes a week whose calendar end is Sunday
    assert has_ended(pd.Timestamp("2026-10-23"), pd.Timestamp("2026-10-25"), crypto=False)
    assert not has_ended(pd.Timestamp("2026-10-22"), pd.Timestamp("2026-10-25"), crypto=False)
    # crypto trades every day
    assert not has_ended(pd.Timestamp("2026-10-24"), pd.Timestamp("2026-10-25"), crypto=True)
    # a holiday on the first weekday is tolerated, a later start is not
    assert starts_on_time(pd.Timestamp("2016-01-04"), pd.Timestamp("2016-01-01"), crypto=False)
    assert not starts_on_time(pd.Timestamp("2016-01-06"), pd.Timestamp("2016-01-01"), crypto=False)


def test_horizon_bars_drop_partial_first_and_unfinished_last_periods():
    daily = business_daily("2020-03-11", "2026-10-21")
    quarters = horizon_bars(daily, "quarter", crypto=False)
    first_start = period_bounds(quarters.index[0], "quarter")[0]
    last_end = period_bounds(quarters.index[-1], "quarter")[1]
    assert first_start == pd.Timestamp("2020-04-01")  # Q1 2020 started before the data
    assert last_end == pd.Timestamp("2026-09-30")  # Q4 2026 is in progress
    assert (quarters["n_sessions"] >= 55).all()


def test_level_memory_reports_every_horizon_on_a_long_history():
    daily = business_daily("1985-01-01", "2026-10-23", seed=3)
    found = level_memory.run(ctx(daily))
    finalize_grades(found)
    cards = {c.id.split(".")[-1]: c for c in found}
    assert {"day", "week", "month", "quarter", "half-year", "year"} <= set(cards)
    year = cards["year"]
    assert year.items[0].n >= 39 and year.grade != "N/A"
    assert all(i.ci_low <= i.estimate <= i.ci_high for i in year.items if i.estimate is not None)


def test_wilson_floor_keeps_zero_counts_honest():
    low, high = wilson_interval(0.0, 38)
    assert low == 0.0 and 0.08 < high < 0.10
    item = EvidenceItem("x", estimate=0.0, ci_low=0.0, ci_high=0.0, n=38, discovery=0.0, holdout=0.0)
    widen_proportions([item])
    assert item.ci_high > 8.0


def test_map_reads_the_current_state_without_looking_ahead():
    daily = business_daily("1990-01-01", "2026-10-23", seed=8)
    keys = period_key(daily.index, "quarter")
    current = keys == keys[-1]
    prior_high = daily.loc[keys == keys[-1] - 1, "high"].max()
    daily.loc[daily.index[current][3], "high"] = prior_high * 1.01  # break the prior high on day 4
    c = ctx(daily)
    state = level_map.current_state(daily, "quarter", crypto=False)
    assert state["broke_high"] and state["sessions"] == int(current.sum())
    card = level_map.map_card(c, "quarter")
    assert card.state["broke_prior_high"] and card.state["period"] == "Q4 2026"
    assert card.items[0].extra["outcome"] == "close_above"  # already broke the high: does it hold?
    assert all(i.n == card.state["analogs"] for i in card.items)
    history = level_map.analog_outcomes(daily, "quarter", crypto=False, sessions=state["sessions"])
    assert keys[-1] not in set(history["key"])  # the period in progress is never its own analog
    # data after the latest bar cannot exist, and the analogs do not change if it is removed
    trimmed = level_map.analog_outcomes(daily.iloc[:-1], "quarter", crypto=False, sessions=state["sessions"])
    pd.testing.assert_frame_equal(history, trimmed)
    assert_publishable(card.to_dict())


def test_map_skips_periods_that_have_ended():
    daily = business_daily("2000-01-03", "2026-10-23")  # a Friday: the week has ended
    assert level_map.current_state(daily, "week", crypto=False) is None
    assert level_map.current_state(daily, "month", crypto=False) is not None


def test_ohlc_reliability_finds_genuine_ranges_and_opens():
    daily = business_daily("1950-01-02", "1999-12-31", seed=2)
    no_range = daily.index < "1962-01-01"
    daily.loc[no_range, ["open", "high", "low"]] = np.repeat(daily.loc[no_range, ["close"]].to_numpy(), 3, axis=1)
    repeat = (daily.index >= "1962-01-01") & (daily.index < "1982-05-01")
    daily.loc[repeat, "open"] = daily["close"].shift(1)[repeat]
    daily.loc[repeat, "high"] = daily.loc[repeat, ["open", "high"]].max(axis=1)
    daily.loc[repeat, "low"] = daily.loc[repeat, ["open", "low"]].min(axis=1)
    info = ohlc_reliability(daily)
    assert info["range_reliable_from"] == "1962-01-01"
    assert info["open_reliable_from"] == "1982-05-03"
