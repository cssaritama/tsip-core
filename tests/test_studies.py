import numpy as np
import pandas as pd
import pytest

from tsip.data.schema import make_bars
from tsip.instruments import get_instrument
from tsip.studies import calendar, entry_timing, first_passage, level_memory
from tsip.studies.common import StudyContext
from tsip.studies.first_passage import AMBIGUOUS, DOWN, NONE, UP
from tsip.studies.intraday import extreme_timing_units


def random_walk_daily(n=1500, seed=0, start="2018-01-01", freq="D", drift=0.0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq=freq)
    r = rng.normal(drift, 0.02, n)
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, 0.01, n)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, 0.01, n)))
    frame = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": 1.0}, index=idx)
    frame.index.name = "date"
    return make_bars(frame, instrument="BTC-USD", source="test", timeframe="1d")


def ctx_for(daily, crypto=True, reps=200):
    return StudyContext(
        instrument=get_instrument("BTC-USD" if crypto else "SPY"),
        daily=daily,
        session_model="crypto" if crypto else "us_rth",
        reps=reps,
        seed=3,
    )


def test_first_passage_outcomes_cover_gaps_ambiguity_and_none():
    o = np.array([100.0, 100.0])
    h = np.array([101.0, 103.0])
    lo = np.array([99.0, 97.0])
    out = first_passage.first_passage(
        o, h, lo, lower=np.array([98.0, 98.0, 95.0, 101.5]), upper=np.array([102.0, 100.5, 110.0, 105.0])
    )
    # band 1: both edges inside day 2 -> ambiguous; band 2: high side on day 1;
    # band 3: never reached; band 4: open below the lower edge -> resolved at the open
    assert list(out) == [AMBIGUOUS, UP, NONE, DOWN]


def test_geometry_control_explains_random_walk():
    daily = random_walk_daily(2500, seed=11)
    card = first_passage.prior_week_first_passage(ctx_for(daily))
    assert card is not None
    item = card.items[-1]
    assert item.ci_low < 0 < item.ci_high  # no information beyond geometry in a random walk
    assert abs(item.extra["naive_upper_first_pct"] - item.extra["geometry_expected_pct"]) < 8


def test_level_memory_counts_on_a_handmade_series():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    frame = pd.DataFrame(
        {
            "open": [10, 10, 12, 9],
            "high": [11, 13, 12.5, 10],
            "low": [9, 9.5, 11, 8],
            "close": [10, 12.5, 11.5, 9.5],
            "volume": 1.0,
        },
        index=idx,
    )
    units = level_memory._indicators(
        frame["high"].to_numpy()[1:],
        frame["low"].to_numpy()[1:],
        frame["close"].to_numpy()[1:],
        frame["high"].to_numpy()[:-1],
        frame["low"].to_numpy()[:-1],
    )
    assert units["took_high"].tolist() == [1, 0, 0]
    assert units["took_low"].tolist() == [0, 0, 1]
    assert units["inside"].tolist() == [0, 1, 0]
    assert units["held_high"].tolist() == [1, 0, 0]


def test_level_memory_cards_are_base_rates():
    cards = level_memory.run(ctx_for(random_walk_daily(800, seed=2)))
    assert {c.kind for c in cards} == {"base_rate"}
    day = cards[0]
    assert 35 < day.items[0].estimate < 65 and day.items[0].ci_low < day.items[0].estimate < day.items[0].ci_high


def test_weekday_effect_finds_planted_monday_effect():
    daily = random_walk_daily(2000, seed=5)
    close = daily["close"].to_numpy().copy()
    r = np.diff(np.log(close))
    r[(daily.index[1:].dayofweek == 0)] += 0.01  # +100 bps on Mondays
    close = 100 * np.exp(np.concatenate([[0], np.cumsum(r)]))
    daily = daily.assign(close=close, open=np.concatenate([[100.0], close[:-1]]))
    daily["high"] = daily[["open", "close"]].max(axis=1) * 1.001
    daily["low"] = daily[["open", "close"]].min(axis=1) * 0.999
    card = calendar.weekday_effect(ctx_for(daily))
    monday = card.items[0]
    assert monday.label == "Monday" and monday.ci_low > 50 and monday.p_value < 0.01


def test_extreme_timing_matches_random_walk_baseline():
    rng = np.random.default_rng(4)
    n, k = 600, 8
    ret = rng.normal(0, 0.01, (n, k))
    hi = np.abs(rng.normal(0, 0.005, (n, k)))
    lo = -np.abs(rng.normal(0, 0.005, (n, k)))
    groups = np.tile(np.arange(k), (n, 1))
    units = extreme_timing_units(ret, hi, lo, groups, k, n_perm=100, seed=1)
    diff = units["obs_hi"].mean(0) - units["base_hi"].mean(0)
    assert np.abs(diff).max() < 0.06
    assert units["base_hi"][:, [0, -1]].mean() > units["base_hi"][:, 3:5].mean()  # arcsine shape


def test_entry_timing_fill_rules():
    idx = pd.date_range("2020-01-01", "2023-12-31", freq="D")
    rng = np.random.default_rng(9)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))
    open_ = np.concatenate([[100.0], close[:-1]])
    frame = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * 1.002,
            "low": np.minimum(open_, close) * 0.998,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )
    months = entry_timing.build_months(frame, min_days=20)
    assert months is not None and len(months["fill"]) == 47
    filled = months["filled"] == 1
    assert (months["fill"][~filled] > 0).all()
    card = entry_timing.prior_month_low_limit(
        ctx_for(make_bars(frame, instrument="BTC-USD", source="t", timeframe="1d"))
    )
    assert card is not None and card.items[0].extra["fill_rate_pct"] == pytest.approx(filled.mean() * 100)
