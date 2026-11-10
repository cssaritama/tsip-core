"""Specification 0028, R9, R10 and T5: the strategy simulations on synthetic prices."""

import numpy as np
import pandas as pd
import pytest

from tsip.capstone import simulate as S


def _frame(prices=None, rate=0.0, start="2022-01-03", days=400, tickers=("SPY", "BTC-USD")):
    rows = []
    for t in tickers:
        dates = pd.date_range(start, periods=days, freq="D")
        if t != "BTC-USD":
            dates = dates[dates.dayofweek < 5]
        close = np.full(len(dates), 100.0) if prices is None else prices(len(dates))
        rows.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": t,
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "adj_close": close,
                    "volume": 1e6,
                    "macro_tbill_3m": rate,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def _panel(frame, end="2023-12-31"):
    return S.make_panel(frame, end=end)


def test_panel_refuses_the_test_period():
    with pytest.raises(ValueError):
        S.make_panel(_frame(), end="2024-06-30")


def test_cash_earns_the_bill_rate():
    panel = _panel(_frame(rate=3.65, days=366))
    run = S.run_portfolio(panel, pd.DataFrame(0.0, index=panel.adj.index, columns=panel.tickers))
    assert run.equity.iloc[-1] == pytest.approx(1.0365, rel=1e-3)


def test_full_position_follows_the_price_less_one_cost():
    frame = _frame(prices=lambda n: 100 * np.exp(np.linspace(0, 0.2, n)), days=300)
    panel = _panel(frame)
    targets = pd.DataFrame(0.0, index=panel.adj.index, columns=panel.tickers)
    targets["SPY"] = 1.0
    run = S.run_portfolio(panel, targets)
    spy = panel.adj["SPY"]
    assert run.equity.iloc[-1] == pytest.approx(spy.iloc[-1] / spy.iloc[0] * (1 - S.COST_PER_SIDE["SPY"]), rel=1e-9)


def test_fund_weight_changes_only_on_its_trading_days():
    panel = _panel(_frame(days=30))
    targets = pd.DataFrame(0.0, index=panel.adj.index, columns=panel.tickers)
    saturday = next(d for d in panel.adj.index if d.dayofweek == 5)
    targets.loc[saturday:, "SPY"] = 0.5
    run = S.run_portfolio(panel, targets)
    assert run.exposure.loc[saturday] == 0
    monday = saturday + pd.Timedelta(days=2)
    assert run.exposure.loc[monday] == pytest.approx(0.5)


def test_delay_moves_the_entry_one_row_later():
    panel = _panel(_frame(days=30))
    targets = pd.DataFrame(0.0, index=panel.adj.index, columns=panel.tickers)
    day = panel.adj.index[10]
    targets.loc[day:, "BTC-USD"] = 1.0
    now, later = S.run_portfolio(panel, targets), S.run_portfolio(panel, targets, delay=1)
    assert now.exposure.loc[day] == 1 and later.exposure.loc[day] == 0
    assert later.exposure.iloc[11] == 1


def test_stop_loss_exits_at_the_stop_level():
    def path(n):
        p = np.full(n, 100.0)
        p[40:] = 80.0  # a gap down far beyond 2 ATR
        return p

    panel = _panel(_frame(prices=path, days=80, tickers=("BTC-USD",)))
    base = pd.DataFrame(1.0, index=panel.adj.index, columns=panel.tickers)
    vol = pd.DataFrame(0.1, index=panel.adj.index, columns=panel.tickers)
    targets, exits = S.stop_and_filter(panel, base, vol)
    stop_day = panel.adj.index[40]
    assert targets.loc[stop_day, "BTC-USD"] == 0
    assert exits.loc[stop_day, "BTC-USD"] == pytest.approx(80.0)  # gap: filled at the open, below the stop
    assert (targets.loc[stop_day:, "BTC-USD"] == 0).all()  # no re-entry until the signal switches off
    run = S.run_portfolio(panel, targets, exits=exits)
    assert run.equity.iloc[-1] < 0.81


@pytest.mark.parametrize("rule", ["lump_sum", "monthly", "cash", *S.PULLBACK_TRIGGERS])
def test_accumulation_never_spends_more_than_the_cash(rule):
    rng = np.random.default_rng(5)
    frame = _frame(prices=lambda n: 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n))), days=500, tickers=("SPY",))
    panel = _panel(frame)
    out = S.accumulate(panel, "SPY", rule, start="2022-03-01")
    assert out["deposits"] > 0
    assert 0 <= out["mean_cash_share"] <= 1
    assert (out["wealth"] > 0).all()


def test_accumulation_on_a_flat_price_returns_the_deposits_less_costs():
    panel = _panel(_frame(days=500, tickers=("SPY",)))
    cost = S.COST_PER_SIDE["SPY"]
    for rule in ("lump_sum", "monthly", "atr_1"):
        out = S.accumulate(panel, "SPY", rule)
        assert out["final_wealth"] == pytest.approx(out["deposits"] * (1 - cost))
    assert S.accumulate(panel, "SPY", "cash")["final_wealth"] == pytest.approx(
        S.accumulate(panel, "SPY", "cash")["deposits"]
    )


def test_top_k_keeps_at_most_k_positions():
    idx = pd.date_range("2022-01-03", periods=5)
    prob = pd.DataFrame({"A": [0.9, 0.6, 0.7, 0.2, 0.8], "B": [0.8, 0.9, 0.1, 0.3, 0.7], "C": 0.95}, index=idx)
    t = S.top_k_targets(prob, 0.5, 2)
    assert (t.gt(0).sum(axis=1) <= 2).all()
    assert t.loc[idx[0], "C"] == 0.5 and t.loc[idx[0], "B"] == 0


def test_xirr_of_a_known_flow():
    d = pd.Timestamp("2022-01-01")
    assert S.xirr([(d, -100.0), (d + pd.Timedelta(days=365), 110.0)]) == pytest.approx(0.1, abs=1e-3)


def test_vector_simulation_counts_costs_on_both_sides():
    preds = pd.DataFrame(
        {
            "date": pd.date_range("2022-01-03", periods=2),
            "ticker": "SPY",
            "probability": [0.9, 0.1],
            "growth_future_5d": 0.01,
        }
    )
    out = S.vector_simulation(preds, 0.5, 5)
    assert out["trades"] == 1
    assert out["total_net"] == pytest.approx(100 * (0.01 - 2 * S.COST_PER_SIDE["SPY"]))
