import numpy as np
import pandas as pd

from tsip.evidence.grading import finalize_grades
from tsip.instruments import get_instrument
from tsip.studies import volatility
from tsip.studies.common import StudyContext


def daily(n=2600, seed=1, monday_scale=1.0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2014-01-02", periods=n)
    vol = np.where(idx.dayofweek == 0, 0.01 * monday_scale, 0.01)
    r = rng.normal(0, 1, n) * vol
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[100.0], close[:-1]])
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * 1.002,
            "low": np.minimum(open_, close) * 0.998,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )


def _cards(frame, seed=5):
    ctx = StudyContext(get_instrument("SPY"), frame, "us_rth", reps=200, seed=seed)
    cards = volatility.run(ctx)
    finalize_grades(cards)
    return cards


def test_constant_volatility_gives_no_strong_grade():
    for seed in (1, 2, 3):
        grades = {i.grade for c in _cards(daily(seed=seed)) for i in c.items}
        assert not grades & {"A", "B"}


def test_a_volatile_weekday_is_found():
    cards = _cards(daily(monday_scale=2.0))
    weekday = next(c for c in cards if c.id.endswith("volatility.weekday"))
    monday = weekday.items[0]
    assert monday.label == "Monday" and monday.estimate > 40 and monday.grade in {"A", "B"}
    assert monday.extra["typical_move_pct"] > monday.extra["average_move_pct"]
    assert "typical_range_pct" in monday.extra  # OHLC available


def test_close_only_series_still_measures_moves():
    frame = daily()
    frame[["open", "high", "low"]] = np.nan
    frame.attrs["close_only"] = True
    cards = _cards(frame)
    assert cards and all("typical_range_pct" not in i.extra for c in cards for i in c.items)
