import numpy as np
import pandas as pd

from tsip.data.schema import make_bars
from tsip.evidence.grading import finalize_grades
from tsip.report.build import InstrumentInput, prepare_context
from tsip.studies import recent_lows as rl


def _daily(close, low=None, high=None, start="2016-01-04", code="SPY"):
    idx = pd.bdate_range(start=start, periods=len(close))
    close = np.asarray(close, float)
    open_ = np.concatenate([[close[0]], close[:-1]])
    low = np.minimum(open_, close) * 0.998 if low is None else low
    high = np.maximum(open_, close) * 1.002 if high is None else high
    frame = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": 1.0}, index=idx)
    return make_bars(frame, instrument=code, source="alpaca", timeframe="1d")


def _ctx(daily, code="SPY"):
    return prepare_context(InstrumentInput(code, "us_rth", daily=daily), reps=200, seed=5)


def test_monday_events_start_on_tuesday_and_stop_once_tested():
    # a week whose Wednesday trades below Monday's low
    d = _walk(2, n=600)
    lows = d["low"].to_numpy().copy()
    week = pd.bdate_range("2017-06-05", periods=5)  # Monday 5 June 2017
    pos = [d.index.get_loc(t) for t in week]
    wk_min = lows[pos].min()
    lows[pos[0]] = wk_min * 0.99  # Monday's low, below the rest of Monday to Tuesday
    lows[pos[2]] = wk_min * 0.985  # Wednesday trades below it
    d["low"] = lows
    ev = rl.monday_events(d, crypto=False)
    days = ev["date"][(ev["date"] >= week[0]) & (ev["date"] <= week[-1])]
    assert list(days) == [week[1]]  # only Tuesday: Wednesday's own low tests the level
    i = int(np.flatnonzero(ev["date"] == week[1])[0])
    assert ev["remaining"][i] == 3 and ev["weekday"][i] == 1
    assert ev["z"][i] > 0


def test_windows_only_count_when_fully_observed():
    z = np.array([1.0, 1.0, 1.0])
    down = np.array([[0.5, 1.2, 1.3], [0.2, 0.4, 0.6], [0.1, np.nan, np.nan]])
    obs, base = rl._down_outcomes(z, down, np.array([2, 2, 2]))
    assert obs[0] == 1.0 and obs[1] == 0.0 and np.isnan(obs[2])
    assert base[0] == 0.0 and base[1] == 1.0  # the other observed path


def _walk(seed, n=2_727, start="2016-01-04", code="SPY", drift=0.0003):
    rng = np.random.default_rng(seed)
    close = 300 * np.exp(np.cumsum(rng.normal(drift, 0.011, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    wick = np.abs(rng.normal(0, 0.004, n))
    return _daily(
        close,
        low=np.minimum(open_, close) * (1 - wick),
        high=np.maximum(open_, close) * (1 + wick),
        start=start,
        code=code,
    )


def test_random_walk_has_no_edge():
    cards = rl.run(_ctx(_walk(17)))
    finalize_grades(cards)
    assert {c.id for c in cards} == {"SPY.recent_lows.monday", "SPY.recent_lows.week", "SPY.recent_lows.month"}
    items = [it for c in cards for it in c.items]
    assert len(items) == 15
    assert not any(it.grade in {"A", "B"} for it in items), [(it.label, it.grade) for it in items]
    monday = next(c for c in cards if c.id.endswith("monday"))
    assert monday.items[0].n > 200 and set(monday.state["by_weekday"]) == {1, 2, 3}
    assert all(0 <= it.extra["observed_pct"] <= 100 for it in monday.items)


def test_planted_return_to_monday_low_is_found():
    # Monday sets a low a random distance below; Friday's low comes back to it exactly
    rng = np.random.default_rng(3)
    d = _walk(8, drift=0.0006)
    idx = d.index
    low = d["low"].to_numpy().copy()
    close = d["close"].to_numpy()
    for wk in pd.unique(idx.to_period("W-SUN")):
        pos = np.flatnonzero(idx.to_period("W-SUN") == wk)
        if len(pos) != 5 or idx[pos[0]].dayofweek != 0:
            continue
        level = close[pos[0]] * (1 - rng.uniform(0.01, 0.05))
        low[pos[0]] = level
        low[pos[1:4]] = np.maximum(low[pos[1:4]], level * 1.001)
        low[pos[4]] = min(low[pos[4]], level)
    d["low"] = np.minimum(low, d[["open", "close"]].min(axis=1).to_numpy())
    cards = [rl.monday_card(_ctx(d))]
    finalize_grades(cards)
    first = cards[0].items[0]
    assert first.observed > 95
    assert first.estimate > 20 and first.grade == "A"


def test_today_state():
    card = rl.monday_card(_ctx(_walk(21)))
    st = card.state
    assert pd.Timestamp(st["week_start"]).dayofweek == 0 or st["monday_low_untested"] is None
    assert st["monday_low_untested"] in (True, False, None)
    if st["monday_low_untested"]:
        assert st["distance_atr"] > 0
