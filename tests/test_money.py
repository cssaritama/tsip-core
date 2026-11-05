import json

import numpy as np
import pandas as pd
import pytest

from tsip.report import InstrumentInput, build_report
from tsip.studies.money import NET_THRESHOLDS_ATR, _net_thresholds, money_events


def _flat_week_days(weeks=8):
    idx = pd.bdate_range("2026-01-05", periods=weeks * 5)
    frame = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0}, index=idx)
    return frame


def test_money_events_use_only_the_forward_window():
    d = _flat_week_days()
    week = d.index[25:30]  # sixth week, Monday to Friday
    d.loc[week[1], "high"] = 110.0  # observation session (k = 2): must not count as a forward excursion
    d.loc[week[3], "high"] = 104.0  # after the observation point: counts
    events = money_events(d, "week", crypto=False, sessions=2)
    row = events[events["start"] == week[0]].iloc[0]
    assert row["broke_high_so_far"] and not row["broke_low_so_far"]
    assert row["up_pct"] == pytest.approx(4.0)  # 104 against the close of session 2, not 110
    assert row["up_atr"] == pytest.approx(2.0)  # yardstick: ATR of 2% at the prior week's last session
    assert row["down_atr"] == pytest.approx(0.5)
    assert row["up_1"] == 1.0 and row["up_2"] == 1.0 and row["down_1"] == 0.0
    assert row["end_up"] == 0.0 and row["end_down"] == 0.0  # flat close: neither above nor below
    # the spike widens the ATR only from the next week on
    later = events[events["start"] == d.index[30]].iloc[0]
    assert later["up_atr"] < 0.5


def _random_walk(days, *, crypto, seed, vol):
    rng = np.random.default_rng(seed)
    if crypto:
        idx = pd.date_range("2016-01-01", periods=days, freq="D")
    else:
        idx = pd.bdate_range(end="2026-11-04", periods=days)
    r = rng.normal(0.0, vol, days)
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[100.0], close[:-1]])
    wick = np.abs(rng.normal(0, vol / 2, days))
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
    frame.index.name = "timestamp"
    return frame


@pytest.fixture(scope="module")
def rw_report():
    spy = _random_walk(2600, crypto=False, seed=11, vol=0.011)
    btc = _random_walk(3600, crypto=True, seed=12, vol=0.035)
    inputs = [InstrumentInput("SPY", "us_rth", daily=spy), InstrumentInput("BTC-USD", "crypto", daily=btc)]
    return build_report(inputs, reps=200)


def _money_cards(report):
    return [
        c for i in report["instruments"] for s in i.get("sections", []) for c in s["cards"] if c["family"] == "money"
    ]


def test_money_random_walk_has_no_edge(rw_report):
    cards = _money_cards(rw_report)
    assert cards, "money cards are produced for periods in progress"
    grades = [it["grade"] for c in cards for it in c["items"]]
    assert not any(g in {"A", "B"} for g in grades), grades


def test_money_card_for_the_current_period(rw_report):
    card = next(c for c in _money_cards(rw_report) if c["id"] == "SPY.money.week")
    assert [it["extra"]["outcome"] for it in card["items"]] == [
        "up_1",
        "down_1",
        "up_2",
        "down_2",
        "end_up",
        "end_down",
    ]
    for it in card["items"]:
        assert 0 <= it["observed"] <= 100 and 0 <= it["baseline"] <= 100
    st = card["state"]
    assert "cost_pct" not in st and not any("cost" in it["label"] for it in card["items"])  # grades carry no cost
    assert st["atr_start_pct"] > 0 and st["analogs"] > 30 and st["others"] > 30
    nt = st["net_thresholds"]
    assert nt["atr"] == list(NET_THRESHOLDS_ATR) and nt["atr"][0] == 0.0 and nt["atr"] == sorted(nt["atr"])
    for group in ("same", "others", "all"):
        for side in ("above", "below"):
            values = nt[group][side]
            assert len(values) == len(nt["atr"]) and values == sorted(values, reverse=True)
    by_outcome = {it["extra"]["outcome"]: it for it in card["items"]}
    assert nt["same"]["above"][0] == pytest.approx(by_outcome["end_up"]["observed"], abs=0.05)
    # the comparison is all periods at the same point (specification 0006), not the other states
    n_same, n_others, n_all = st["analogs"], st["others"], st["all_periods"]
    assert n_all == n_same + n_others and card["contrast"].startswith("all ")
    assert nt["all"]["below"][0] == pytest.approx(by_outcome["end_down"]["baseline"], abs=0.05)
    pooled = (n_same * nt["same"]["above"][0] + n_others * nt["others"]["above"][0]) / n_all
    assert by_outcome["end_up"]["baseline"] == pytest.approx(pooled, abs=0.1)
    for it in card["items"]:
        assert it["estimate"] == pytest.approx(it["observed"] - it["baseline"], abs=0.01)
    for group in ("same", "others", "all"):
        med = st["excursions"][group]["up_atr"]
        assert med["q1"] <= med["median"] <= med["q3"]
    json.dumps(rw_report, allow_nan=False)


def test_net_thresholds_are_in_atr_of_each_period():
    # Two past weeks both ended 1% higher: one in a calm market (ATR 2%, so 0.5 ATR) and one in a volatile
    # market (ATR 5%, so 0.2 ATR). Against a cost worth 0.3 ATR today, only the calm week cleared it.
    frame = pd.DataFrame({"net_pct": [1.0, 1.0, -0.6], "net_atr": [0.5, 0.2, -0.3]})
    nt = _net_thresholds(frame)
    at = NET_THRESHOLDS_ATR.index
    assert nt["above"][at(0.0)] == pytest.approx(66.7)  # 0 ATR: ended above
    assert nt["above"][at(0.3)] == pytest.approx(33.3)
    assert nt["below"][at(0.25)] == pytest.approx(33.3)
    assert nt["below"][at(0.3)] == 0.0  # a change of exactly -0.3 ATR is not beyond 0.3 ATR
    assert len(NET_THRESHOLDS_ATR) == len(set(NET_THRESHOLDS_ATR)) and max(NET_THRESHOLDS_ATR) == 3.0


def test_money_skips_close_only_series():
    d = _random_walk(2600, crypto=False, seed=3, vol=0.011)
    d[["open", "high", "low"]] = float("nan")
    d.attrs["close_only"] = True
    report = build_report([InstrumentInput("SPX", "us_rth", daily=d)], reps=50)
    assert _money_cards(report) == []
    json.dumps(report, allow_nan=False)
