"""Course project diagnostics: exploration excludes the test period; group metrics and errors are right."""

import numpy as np
import pandas as pd

from tsip.capstone import analysis as A


def _pred(n=400, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, n).astype(float)
    good = np.clip(0.5 + (y - 0.5) * 0.4 + rng.normal(0, 0.1, n), 0, 1)
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n).astype(str),
            "ticker": np.where(np.arange(n) % 2, "SPY", "BTC-USD"),
            "is_positive_growth_5d": y,
            "growth_future_5d": np.where(y == 1, 0.01, -0.01),
            "LECTURE": rng.random(n),
            "LECTURE+TIME+SPACE": good,
        }
    )


def test_correlations_use_training_and_validation_rows_only():
    dates = pd.date_range("2018-01-01", "2025-12-31", freq="D")
    x = np.arange(len(dates), dtype=float)
    future = np.where(dates > pd.Timestamp("2023-12-31"), -x, x)  # perfectly inverted in the test years
    feats = pd.DataFrame({"date": dates, "f": x, "growth_future_5d": future})
    table = A.correlations(feats, {"LECTURE": ["f"], "TIME": [], "SPACE": []}, 5)
    assert table.loc[0, "spearman"] > 0.99


def test_group_metrics_reward_the_informative_model():
    groups = A.by_group(_pred())
    t = groups["ticker"].set_index("ticker")
    assert (t["auc LECTURE+TIME+SPACE"] > 0.8).all() and (t["auc LECTURE"] < 0.65).all()
    assert (t["precision top decile LECTURE+TIME+SPACE"] > 0.9).all()
    assert set(groups["month_of_year"]["month_of_year"]) <= set(range(1, 13))


def test_confident_errors_are_wrong_and_sorted_by_confidence():
    pred = _pred()
    out = A.confident_errors(pred)
    worst = out["worst"]
    for w in worst:
        assert (w["LECTURE+TIME+SPACE"] >= 0.5) != (w["is_positive_growth_5d"] == 1)
    conf = [abs(w["LECTURE+TIME+SPACE"] - 0.5) for w in worst]
    assert conf == sorted(conf, reverse=True)


def test_vector_return_on_capital():
    assert A.vector_return({"total_net": 50.0, "capital_needed": 1000.0}) == 0.05
    assert A.vector_return({"trades": 0}) is None
