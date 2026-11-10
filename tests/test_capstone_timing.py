"""Specification 0029, T1 to T3 and T5: buy timing with a fixed monthly budget."""

import json

import numpy as np
import pandas as pd
import pytest

from tsip.capstone import evaluate as E
from tsip.capstone import timing as T


def _frame(close, ticker="SPY", start="2014-01-01", wiggle=0.004):
    dates = pd.bdate_range(start, periods=len(close))
    close = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {
            "date": dates,
            "ticker": ticker,
            "open": close,
            "high": close * (1 + wiggle),
            "low": close * (1 - wiggle),
            "close": close,
            "adj_close": close,
        }
    )


def _walk(n=900, seed=4):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))


ALL = [(f, r, p) for f, r, p in T.variants("SPY", month_low_session=3)] + T.REFERENCES


def test_every_rule_buys_once_in_every_complete_month():
    g = T.sessions(_frame(_walk()), "SPY")
    months = T.complete_months(g)
    for _, rule, params in ALL:
        picks = T.decide(g, rule, params, months)
        assert list(picks.index) == months
        assert all(g["month"].iloc[i] == m for m, i in picks.items()), rule


def test_flat_price_gives_no_advantage_to_any_rule():
    g = T.sessions(_frame(np.full(600, 100.0)), "SPY")
    months = T.complete_months(g)
    for _, rule, params in ALL:
        assert np.allclose(T.advantages(g, T.decide(g, rule, params, months)), 0), rule


def test_a_dip_on_the_first_monday_is_found():
    frame = _frame(np.full(900, 100.0))
    first_monday = (
        frame.assign(m=frame["date"].dt.to_period("M")).query("date.dt.dayofweek == 0").groupby("m").head(1).index
    )
    for col in ("open", "high", "low", "close", "adj_close"):
        frame.loc[first_monday, col] *= 0.97
    g = T.sessions(frame, "SPY")
    months = T.complete_months(g)
    by_day = {d: T.advantages(g, T.decide(g, "weekday", {"day": d}, months)).mean() for d in range(5)}
    assert max(by_day, key=by_day.get) == 0 and by_day[0] > 0.01


def test_decisions_do_not_change_when_later_sessions_are_deleted():
    frame = _frame(_walk(1200, seed=9))
    cut = frame["date"].iloc[800]
    full = T.sessions(frame, "SPY")
    short = T.sessions(frame[frame["date"] <= cut], "SPY")
    months = [m for m in T.complete_months(short)]
    for _, rule, params in ALL:
        a = full["date"].to_numpy()[T.decide(full, rule, params, months).to_numpy()]
        b = short["date"].to_numpy()[T.decide(short, rule, params, months).to_numpy()]
        assert (a == b).all(), rule


def test_benjamini_hochberg_matches_a_known_case():
    q = T.bh(np.array([0.01, 0.04, 0.03, 0.2]))
    assert np.allclose(q, [0.04, 0.0533333, 0.0533333, 0.2], atol=1e-6)


def test_bootstrap_detects_a_clear_positive_mean_and_not_a_zero_one():
    rng = np.random.default_rng(1)
    mean, ci, p = T.bootstrap_mean(rng.normal(0.01, 0.01, 120), reps=500)
    assert ci[0] > 0 and p < 0.01
    mean, ci, p = T.bootstrap_mean(rng.normal(0.0, 0.01, 120), reps=500)
    assert ci[0] < 0 < ci[1] and p > 0.05


def test_confirmation_runs_once_and_is_logged(tmp_path, monkeypatch):
    from test_capstone_evaluate import _store

    store = tmp_path / "store"
    _store(store, start="2014-01-01", end="2021-12-31")
    monkeypatch.setattr(E, "RUN_LOG", tmp_path / "runs.json")
    monkeypatch.setattr(T, "CHOICES", tmp_path / "choices.json")
    monkeypatch.setattr(T, "REPS", 100)
    monkeypatch.setattr(T, "DEV_END", {k: "2017-12-31" for k in T.DEV_END})
    monkeypatch.setattr(E, "git_state", lambda repo=None: ("abc", False))
    T.main(["develop", "--store", str(store)])
    assert json.loads((tmp_path / "choices.json").read_text())["SPY"]["chosen"]
    T.main(["confirm", "--store", str(store)])
    out = json.loads((store / "results" / "timing_confirmation.json").read_text())
    assert out["real"]["n_tests"] == 3 * 11 + 2 * 13
    assert json.loads((tmp_path / "runs.json").read_text())[0]["kind"] == "timing_confirmation"
    with pytest.raises(SystemExit):
        T.main(["confirm", "--store", str(store)])
