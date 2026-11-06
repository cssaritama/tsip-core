import numpy as np
import pandas as pd
import pytest

from tsip.data.schema import make_bars
from tsip.evidence.grading import finalize_grades
from tsip.report.build import InstrumentInput, prepare_context
from tsip.studies import period_extremes as pe


def _close_only(close: np.ndarray, start="1986-01-02", code="NDX") -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=len(close))
    frame = pd.DataFrame({"open": np.nan, "high": np.nan, "low": np.nan, "close": close, "volume": np.nan}, index=idx)
    bars = make_bars(frame, instrument=code, source="fred", timeframe="1d", price_basis="close-only")
    bars.attrs["close_only"] = True
    return bars


def _ctx(close, code="NDX", reps=200):
    return prepare_context(InstrumentInput(code, "us_rth", daily=_close_only(close, code=code)), reps=reps, seed=3)


@pytest.fixture(autouse=True)
def fewer_shuffles(monkeypatch):
    monkeypatch.setattr(pe, "N_SHUFFLES", 400)


def test_ties_take_the_first_session():
    path = np.array([0.0, -1.0, 0.5, -1.0, 2.0, 2.0])
    assert pe._first_extreme(path, "low") == 1
    assert pe._first_extreme(path, "high") == 4


def test_windows_by_position():
    days = pd.bdate_range("2026-03-02", "2026-03-31")  # 22 sessions
    g = pe.window_groups("month", days, crypto=False)
    assert list(g[:5]) == [0] * 5 and list(g[-5:]) == [2] * 5 and set(g[5:-5]) == {1}
    q = pd.bdate_range("2026-01-02", "2026-03-31")
    gq = pe.window_groups("quarter", q, crypto=False)
    assert gq[0] == 0 and gq[-1] == 2 and set(gq) == {0, 1, 2}
    assert (gq[q.month == 2] == 1).all()


def test_control_keeps_each_period_returns_and_only_changes_their_order():
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 600)))
    series = _close_only(close)["close"]
    periods = pe.complete_periods(series, "month", crypto=False)
    assert periods and all(len(s) - 1 >= 15 for _, s in periods)
    # the first and the last month in the data are never used
    months = {p.to_period("M") for p, _ in periods}
    assert series.index[0].to_period("M") not in months and series.index[-1].to_period("M") not in months
    units = pe.extreme_units(periods, "month", crypto=False, n_shuffles=300, seed=2)
    for key in ("obs_low", "base_low", "rw_low", "obs_high", "base_high"):
        assert np.allclose(units[key].sum(axis=1), 1.0)
    # a period whose returns are all equal and positive: every order gives the same path,
    # so the shuffled control puts the low on the first session exactly as observed
    flat = [
        (
            pd.Timestamp("2026-03-02"),
            pd.Series(np.exp(np.arange(23) * 0.01), index=pd.bdate_range("2026-02-27", periods=23)),
        )
    ]
    u = pe.extreme_units(flat, "month", crypto=False, n_shuffles=50, seed=0)
    assert np.allclose(u["base_low"], u["obs_low"]) and u["obs_low"][0, 0] == 1.0


def test_random_walk_shows_no_timing_effect():
    rng = np.random.default_rng(11)
    close = 1000 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, 10_300)))  # NDX length, with drift
    cards = pe.run(_ctx(close))
    finalize_grades(cards)
    assert {c.id for c in cards} == {
        "NDX.extremes.month_low",
        "NDX.extremes.month_high",
        "NDX.extremes.quarter_low",
        "NDX.extremes.quarter_high",
    }
    grades = [it.grade for c in cards for it in c.items]
    assert len(grades) == 12 and not any(g in {"A", "B"} for g in grades), grades
    month = next(c for c in cards if c.id.endswith("month_low"))
    assert month.state["periods"] > 450 and month.unit == "pp"
    assert all("random_walk" in it.extra for it in month.items)
    # with drift, the control itself places lows early more often than late
    assert month.items[0].baseline > month.items[2].baseline


def test_lows_on_the_first_session_are_found():
    # every month: a large fall on its first session, small gains afterwards
    idx = pd.bdate_range("1986-01-02", periods=10_300)
    first = ~pd.Series(idx.to_period("M")).duplicated().to_numpy()
    rng = np.random.default_rng(5)
    ret = np.where(first, -0.05, 0.003 + rng.normal(0, 0.001, len(idx)))
    cards = pe.run(_ctx(100 * np.exp(np.cumsum(ret))))
    finalize_grades(cards)
    low = next(c for c in cards if c.id == "NDX.extremes.month_low")
    assert low.items[0].observed == pytest.approx(100.0)
    assert low.items[0].estimate > 50 and low.items[0].grade == "A"


def test_short_histories_cannot_reach_grade_a():
    rng = np.random.default_rng(9)
    idx = pd.bdate_range("2016-01-04", periods=2_727)
    first = ~pd.Series(idx.to_period("M")).duplicated().to_numpy()
    ret = np.where(first, -0.05, 0.003 + rng.normal(0, 0.001, len(idx)))
    cards = pe.run(_ctx(400 * np.exp(np.cumsum(ret)), code="SPX"))
    finalize_grades(cards)
    low = next(c for c in cards if c.id == "SPX.extremes.month_low")
    assert low.state["periods"] < 200 and low.items[0].grade != "A" and low.items[0].grade == "B"


def test_current_period_state():
    rng = np.random.default_rng(4)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 1_500)))
    cards = pe.run(_ctx(close, code="SPX"))
    st = next(c for c in cards if c.id.endswith("month_low")).state
    assert 1 <= st["sessions_elapsed"] <= 23 and st["typical_sessions"] in range(19, 24)
    assert 1 <= st["low_so_far_session"] <= st["sessions_elapsed"]
    assert 0 <= st["low_set_by_now_pct"] <= 100
