import numpy as np
import pandas as pd

from tsip.instruments import get_instrument
from tsip.studies import revisit
from tsip.studies.common import StudyContext
from tsip.studies.position import position


def random_walk_daily(n=2600, seed=3, start="2016-01-04"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    r = rng.normal(0.0003, 0.011, n)
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[100.0], close[:-1]])
    wiggle = np.abs(rng.normal(0, 0.006, n))
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * (1 + wiggle),
            "low": np.minimum(open_, close) * (1 - wiggle),
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )


def test_random_walk_levels_are_not_special():
    ctx = StudyContext(get_instrument("SPY"), random_walk_daily(), "us_rth", reps=200, seed=11)
    from tsip.evidence.grading import finalize_grades

    cards = revisit.run(ctx)
    assert {c.id.split(".")[-1] for c in cards} >= {"week", "month", "quarter"}
    finalize_grades(cards)
    grades = {item.grade for c in cards for item in c.items}
    assert not grades & {"A", "B"}  # random levels must not look attractive


def test_windows_past_the_data_are_not_counted():
    daily = random_walk_daily(n=900)
    ev = revisit.build_events(daily, "week", crypto=False)
    units = revisit.outcome_arrays(ev, (5, 10, 20))
    # the last events cannot have a full 20-session window
    assert np.isnan(units["obs"][-1, 2]) and np.isnan(units["base"][-1, 2])
    assert np.isfinite(units["obs"][0]).all()


def test_kaplan_meier_keeps_open_levels():
    # running max excursion; rows 0-2 reach the level after 1, 2 and 3 sessions, rows 3-5 never do
    path = np.zeros((6, 10))
    path[0, 0:] = 2
    path[1, 1:] = 2
    path[2, 2:] = 2
    z = np.ones(6)
    assert revisit.kaplan_meier_median(path, z) == 3.0  # survival 5/6, 4/6, 3/6
    assert revisit.kaplan_meier_median(path[3:], z[3:]) is None  # never reached: no median invented


def test_position_uses_the_closed_period_on_a_weekend():
    daily = random_walk_daily(n=460, start="2025-04-07")
    friday = daily[daily.index <= "2026-10-30"]
    assert friday.index[-1].day_name() == "Friday"
    pos = position(friday, crypto=False)
    week = next(h for h in pos["horizons"] if h["horizon"] == "week")
    assert week["status"] == "closed" and week["reference"] == "week of 2026-10-26"
    last_week = friday.loc["2026-10-26":"2026-10-30"]
    close = friday["close"].iloc[-1]
    assert np.isclose(week["to_reference_high_pct"], (last_week["high"].max() / close - 1) * 100, atol=1e-3)
    wednesday = friday[friday.index <= "2026-10-28"]
    week_mid = next(h for h in position(wednesday, crypto=False)["horizons"] if h["horizon"] == "week")
    assert week_mid["status"] == "in_progress" and week_mid["reference"] == "week of 2026-10-19"
    assert "took_reference_high" in week_mid


def test_open_levels_lists_only_untraded_levels():
    daily = random_walk_daily(n=600)
    board = revisit.open_levels(daily, crypto=False)
    h, lo = daily["high"].to_numpy(), daily["low"].to_numpy()
    for row in board["levels"]:
        assert row["side"] in {"high", "low"} and row["age_sessions"] >= 0
    close = daily["close"].iloc[-1]
    for row in board["levels"]:
        level = close * (1 + row["distance_pct"] / 100)
        tail = slice(len(daily) - row["age_sessions"], None)
        if row["age_sessions"]:
            if row["side"] == "high":
                assert (h[tail] < level * (1 + 1e-4)).all()
            else:
                assert (lo[tail] > level * (1 - 1e-4)).all()
