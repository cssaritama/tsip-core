import numpy as np
import pandas as pd
import pytest

from tsip.data.schema import make_bars
from tsip.evidence.grading import finalize_grades
from tsip.frames import daily_from_intraday_utc
from tsip.report.build import InstrumentInput, prepare_context
from tsip.studies import plan
from tsip.studies.plan import bracket, plan_events


def test_bracket_counts_a_bar_reaching_both_levels_as_the_stop():
    # entry 100, 1 ATR = 2% = 2.0: long stop 98, target 102 (1:1); the bar spans both
    assert bracket([100.0], [103.0], [97.0], 100.0, 2.0, 1, 1.0, 100.0) == (-1.0, "stop")
    assert bracket([100.0], [103.0], [97.0], 100.0, 2.0, -1, 1.0, 100.0) == (-1.0, "stop")


def test_bracket_gaps_fill_at_the_open_and_order_is_respected():
    assert bracket([95.0], [96.0], [94.0], 100.0, 2.0, 1, 1.0, 95.0) == (pytest.approx(-2.5), "stop")
    assert bracket([105.0], [106.0], [104.0], 100.0, 2.0, 1, 1.0, 105.0) == (pytest.approx(2.5), "target")
    assert bracket([105.0], [106.0], [104.0], 100.0, 2.0, -1, 1.0, 105.0) == (pytest.approx(-2.5), "stop")
    # target on the first bar, stop on the second: the target came first
    assert bracket([100.0, 101.0], [102.5, 101.0], [99.5, 97.0], 100.0, 2.0, 1, 1.0, 97.0) == (1.0, "target")
    # short: stop above at 102, target below at 96 (1:2); the low reaches the target
    assert bracket([100.0], [101.0], [95.5], 100.0, 2.0, -1, 2.0, 99.0) == (2.0, "target")
    # nothing reached: exit at the last close, in ATR
    assert bracket([100.0], [101.0], [99.0], 100.0, 2.0, 1, 2.0, 101.0) == (pytest.approx(0.5), "neither")
    assert bracket([100.0], [101.0], [99.0], 100.0, 2.0, -1, 2.0, 101.0) == (pytest.approx(-0.5), "neither")


def _flat_hours(weeks=10):
    idx = pd.date_range("2026-01-05", periods=weeks * 7 * 24, freq="1h", tz="UTC")  # starts on a Monday
    frame = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1.0}, index=idx)
    return frame


def test_plan_events_use_only_bars_after_the_observation_point():
    hours = _flat_hours()
    week6 = pd.Timestamp("2026-02-09", tz="UTC")  # Monday of the sixth week
    hours.loc[week6 + pd.Timedelta(days=1, hours=10), "low"] = 90.0  # Tuesday, the observation day (k = 2)
    hours.loc[week6 + pd.Timedelta(days=3, hours=5), "high"] = 101.6  # Thursday, after the observation point
    daily = daily_from_intraday_utc(hours, bars_per_day=24)
    idx = pd.DatetimeIndex(hours.index)
    path = (
        np.asarray(idx.tz_localize(None).normalize().values, dtype="datetime64[ns]"),
        hours["open"].to_numpy(float),
        hours["high"].to_numpy(float),
        hours["low"].to_numpy(float),
    )
    events = plan_events(daily, path, "week", crypto=True, sessions=2)
    row = events[events["start"] == pd.Timestamp("2026-02-09")].iloc[0]
    assert row["broke_low_so_far"] and not row["broke_high_so_far"]
    # yardstick: ATR of 1% at the prior week's last day, so 1 ATR = 1.0 from the entry at 100
    assert row["long_1_1"] == 1.0 and row["long_1_1__how"] == "target"  # Tuesday's dip is not on the path
    assert row["long_1_2"] == pytest.approx(0.0) and row["long_1_2__how"] == "neither"
    assert row["short_1_1"] == -1.0 and row["short_1_1__how"] == "stop"
    assert row["long_hold"] == pytest.approx(-row["short_hold"])


def _crypto_walk(seed=21, hours=24 * 365 * 3):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end="2026-11-04 23:00", periods=hours, freq="1h", tz="UTC")
    r = rng.normal(0.0, 0.006, len(idx))
    close = 20000 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[20000.0], close[:-1]])
    wick = np.abs(rng.normal(0, 0.003, len(idx)))
    frame = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * (1 + wick),
            "low": np.minimum(open_, close) * (1 - wick),
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )
    return make_bars(frame, instrument="BTC-USD", source="coinbase", timeframe="1h")


def _rth_walk(seed=22, days=252 * 6):
    rng = np.random.default_rng(seed)
    stamps = []
    for d in pd.bdate_range(end="2026-11-04", periods=days):
        t0 = pd.Timestamp(f"{d.date()} 09:30", tz="America/New_York")
        stamps += [t0 + pd.Timedelta(minutes=30 * k) for k in range(13)]
    idx = pd.DatetimeIndex(stamps).tz_convert("UTC")
    r = rng.normal(0.0, 0.0025, len(idx))
    close = 400 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[400.0], close[:-1]])
    wick = np.abs(rng.normal(0, 0.0012, len(idx)))
    frame = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * (1 + wick),
            "low": np.minimum(open_, close) * (1 - wick),
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )
    return make_bars(frame, instrument="SPY", source="alpaca", timeframe="30min")


@pytest.fixture(scope="module")
def walk_cards():
    contexts = [
        prepare_context(InstrumentInput("BTC-USD", "crypto", intraday=_crypto_walk()), reps=200, seed=7),
        prepare_context(InstrumentInput("SPY", "us_rth", intraday=_rth_walk()), reps=200, seed=7),
    ]
    cards = [card for ctx in contexts for card in plan.run(ctx)]
    finalize_grades(cards)
    return cards


def test_plan_random_walk_has_no_edge(walk_cards):
    assert {c.id for c in walk_cards} == {"BTC-USD.plan.week", "BTC-USD.plan.month", "SPY.plan.week", "SPY.plan.month"}
    grades = [it.grade for c in walk_cards for it in c.items]
    assert not any(g in {"A", "B"} for g in grades), grades


def test_plan_card_compares_with_all_periods(walk_cards):
    card = next(c for c in walk_cards if c.id == "SPY.plan.week")
    st = card.state
    assert st["all_periods"] > st["analogs"] > 30 and st["atr_start_pct"] > 0 and card.unit == "ATR"
    assert [it.extra["plan"] for it in card.items] == [code for code, *_ in plan.PLANS]
    for it in card.items:
        assert it.estimate == pytest.approx(it.observed - it.baseline, abs=1e-9)
        for group in ("same", "all"):
            s = it.extra[group]
            assert s["target_first"] + s["stop_first"] + s["neither"] == pytest.approx(100.0, abs=0.15)
            assert s["q1"] <= s["median"] <= s["q3"]
    hold = {it.extra["plan"]: it for it in card.items}
    assert hold["long_hold"].observed == pytest.approx(-hold["short_hold"].observed)
    assert hold["long_hold"].extra["same"]["neither"] == 100.0


def test_plan_needs_intraday_paths():
    hours = _crypto_walk(hours=24 * 400)
    daily = daily_from_intraday_utc(hours, bars_per_day=24)
    ctx = prepare_context(InstrumentInput("BTC-USD", "crypto", daily=daily), reps=50, seed=1)
    assert plan.run(ctx) == []
