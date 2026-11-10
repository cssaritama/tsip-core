"""Specification 0028, R7, R8 and T2 to T4: splits, controls and model plumbing on synthetic data."""

import numpy as np
import pandas as pd
import pytest

from tsip.capstone import features as F
from tsip.capstone import models as M


def _frame(seed=3, start="2016-01-04", days=3300, tickers=("SPY", "QQQ")):
    rng = np.random.default_rng(seed)
    rows = []
    for t in tickers:
        dates = pd.bdate_range(start, periods=days * 5 // 7)
        close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(dates))))
        wig = np.abs(rng.normal(0, 0.004, len(dates)))
        rows.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": t,
                    "open": close,
                    "high": close * np.exp(wig),
                    "low": close * np.exp(-wig),
                    "close": close,
                    "adj_close": close,
                    "volume": 1e6,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


@pytest.fixture(scope="module")
def built():
    return F.build_features(_frame())


def test_split_never_returns_test_rows_unless_asked(built):
    feats, _ = built
    parts = M.split(feats, 5)
    assert set(parts) == {"train", "validation"}
    assert parts["validation"]["date"].max() <= M.VALIDATION_END
    assert "test" in M.split(feats, 5, allow_test=True)


def test_boundary_rows_whose_labels_reach_the_next_period_are_purged(built):
    feats, _ = built
    parts = M.split(feats, 5)
    for _, g in parts["train"].groupby("ticker"):
        last = g["date"].max()
        later = feats[
            (feats["ticker"] == g["ticker"].iloc[0]) & (feats["date"] > last) & (feats["date"] <= M.TRAIN_END)
        ]
        assert len(later) == 5  # exactly the purged rows


def test_feature_sets_always_include_ticker_indicators(built):
    _, sets = built
    for name in M.FEATURE_SETS:
        cols = M.columns_for(sets, name)
        assert set(sets["DUMMIES"]) <= set(cols)
        assert not set(sets["TO_PREDICT"]) & set(cols)


def test_random_walk_frame_keeps_dates_and_changes_prices():
    frame = _frame(days=400)
    rw = M.random_walk_frame(frame)
    assert (rw["date"].to_numpy() == frame.sort_values(["ticker", "date"])["date"].to_numpy()).all()
    assert not np.allclose(rw["close"].to_numpy(), frame.sort_values(["ticker", "date"])["close"].to_numpy())
    assert (rw["high"] >= rw[["open", "close"]].max(axis=1)).all() and (
        rw["low"] <= rw[["open", "close"]].min(axis=1)
    ).all()


def test_random_walk_gives_no_time_space_lift():
    """On random walks the time-space lift averages out to zero.

    A single validation sample of this size is noisy (AUC spread about 0.04 across seeds, checked on
    2026-11-10), so the test averages three independent walks.
    """
    lifts, bases = [], []
    for seed in (1, 2, 4):
        feats, sets = F.build_features(_frame(seed=seed))
        full = M.fit_and_score(feats, sets, "logistic", "LECTURE+TIME+SPACE", 5, tune_folds=2)[2]
        base = M.fit_and_score(feats, sets, "logistic", "LECTURE", 5, tune_folds=2)[2]
        lifts.append(full["validation_auc"] - base["validation_auc"])
        bases.append(base["validation_auc"])
    assert abs(np.mean(lifts)) < 0.03
    assert abs(np.mean(bases) - 0.5) < 0.05


def test_planted_space_effect_is_found():
    """Prices drift up for five days after closing below the prior week's low.

    The pipeline must find it (AUC well above 0.5) and SPACE must add to the course features. The
    course features see part of it too, because a close below last week's low follows recent losses,
    so the required lift is positive rather than large.
    """
    rng = np.random.default_rng(11)
    dates = pd.bdate_range("2016-01-04", periods=2400)
    close = np.empty(len(dates))
    close[0] = 100.0
    week = dates.to_period("W-SUN").asi8
    boost = np.zeros(len(dates))
    prior_low = np.nan
    cur_low = np.inf
    for i in range(1, len(dates)):
        if week[i] != week[i - 1]:
            prior_low, cur_low = cur_low, np.inf
        close[i] = close[i - 1] * np.exp(rng.normal(0, 0.01) + boost[i])
        cur_low = min(cur_low, close[i])
        if not np.isnan(prior_low) and close[i] < prior_low:
            boost[i + 1 : i + 6] += 0.006
    frame = pd.DataFrame(
        {
            "date": dates,
            "ticker": "SPY",
            "open": close,
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
            "adj_close": close,
            "volume": 1e6,
        }
    )
    feats, sets = F.build_features(frame)
    _, _, full = M.fit_and_score(feats, sets, "xgboost", "LECTURE+SPACE", 5, tune_folds=2)
    _, _, base = M.fit_and_score(feats, sets, "xgboost", "LECTURE", 5, tune_folds=2)
    assert full["validation_auc"] > 0.6
    assert full["validation_auc"] > base["validation_auc"]
