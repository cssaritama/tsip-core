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


def test_close_only_series_publish_cleanly():
    """Regression: a FRED close-only index produced NaN distances and stopped the report (0.2.7)."""
    import json

    from tsip.data.schema import make_bars
    from tsip.report.build import InstrumentInput, build_report

    d = random_walk_daily(n=900)
    d[["open", "high", "low"]] = np.nan
    bars = make_bars(d, instrument="NDX", source="fred", timeframe="1d", price_basis="close-only")
    bars.attrs["close_only"] = True
    report = build_report([InstrumentInput("NDX", "us_rth", daily=bars)], reps=30)
    json.dumps(report, allow_nan=False)  # must not raise
    inst = report["instruments"][0]
    assert inst["open_levels"] == {} and inst["position"] == {}


def test_reach_odds_rise_with_time_and_fall_with_distance():
    curves = revisit.reach_curves(random_walk_daily(n=1500), crypto=False)
    near = revisit.reach_odds(curves, "low", 0.5)["within"]
    far = revisit.reach_odds(curves, "low", 3.0)["within"]
    assert near["5"]["pct"] < near["20"]["pct"] < near["60"]["pct"]
    assert far["20"]["pct"] < near["20"]["pct"]
    assert near["20"]["ci_low"] <= near["20"]["pct"] <= near["20"]["ci_high"]


def test_levels_at_one_price_are_merged():
    board = revisit.open_levels(random_walk_daily(n=900), crypto=False)
    for zone in board["levels"]:
        assert zone["confluence"] == len(zone["levels"]) >= 1
    sides = [(z["side"], z["distance_pct"]) for z in board["levels"]]
    assert len(sides) == len(set(sides))  # no two zones at the same price on the same side


def test_revisit_curves_rise_and_stay_in_range():
    ev = revisit.build_events(random_walk_daily(n=1500), "week", crypto=False)
    curves = revisit.revisit_curves(ev, 20)
    high = curves["high"]
    assert high["sessions"][0] == 1 and high["sessions"][-1] == 20
    assert high["real_pct"][-1] >= high["real_pct"][0]
    assert all(0 <= v <= 100 for v in high["real_pct"] + high["control_pct"])


def test_volatility_regime_percentile():
    from tsip.studies.position import volatility_regime

    d = random_walk_daily(n=800)
    calm = volatility_regime(d)
    assert 0 <= calm["atr_percentile"] <= 100 and calm["atr_median_pct"] > 0
    wild = d.copy()
    wild.iloc[-14:, wild.columns.get_loc("high")] *= 1.05  # the last two weeks swing far more
    assert volatility_regime(wild)["atr_percentile"] > 95
