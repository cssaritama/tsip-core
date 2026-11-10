"""Models for the course project (specification 0028, R7, R8 and the controls of its protocol).

Periods: training up to 2021-12-31, validation 2022-01-01 to 2023-12-31, test from 2024-01-01. This
module only ever reads training and validation rows: ``split`` refuses to return test rows unless
``allow_test=True``, which only ``evaluate.py`` (step 5) passes, once.

Rows whose target window reaches into the next period are purged (the last ``horizon`` rows of
each ticker before a boundary), so no training label is computed from validation prices.

Four model families (decision tree, random forest, logistic regression, XGBoost) are tuned on
time-ordered folds of the training period only, then trained on the whole training period and
scored on validation, for each of four feature sets: LECTURE, LECTURE+TIME, LECTURE+SPACE and
LECTURE+TIME+SPACE (ticker indicators always included). Two controls accompany the lift:
the TIME and SPACE columns shuffled within each ticker on the validation rows, and the whole
pipeline on random-walk prices (``random_walk_frame``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRAIN_END = pd.Timestamp("2021-12-31")
VALIDATION_END = pd.Timestamp("2023-12-31")
FEATURE_SETS = {
    "LECTURE": ("LECTURE",),
    "LECTURE+TIME": ("LECTURE", "TIME"),
    "LECTURE+SPACE": ("LECTURE", "SPACE"),
    "LECTURE+TIME+SPACE": ("LECTURE", "TIME", "SPACE"),
}
SEED = 28


# ---------------------------------------------------------------- data splits


def period_of(dates: pd.Series) -> pd.Series:
    return pd.Series(
        np.select([dates <= TRAIN_END, dates <= VALIDATION_END], ["train", "validation"], "test"), index=dates.index
    )


def split(features: pd.DataFrame, horizon: int, *, allow_test: bool = False) -> dict[str, pd.DataFrame]:
    """Rows of each period with a known target, purged at the boundaries."""
    target = f"is_positive_growth_{horizon}d"
    frame = features[features[target].notna()].copy()
    frame["period"] = period_of(frame["date"])
    keep = np.ones(len(frame), dtype=bool)
    for _, idx in frame.groupby("ticker").indices.items():
        periods = frame["period"].to_numpy()[idx]
        for name in ("train", "validation"):
            rows = idx[periods == name]
            keep[rows[-horizon:]] = False  # their labels look into the next period
    frame = frame[keep]
    out = {name: frame[frame["period"] == name] for name in ("train", "validation")}
    if allow_test:
        out["test"] = frame[frame["period"] == "test"]
    return out


def columns_for(sets: dict[str, list[str]], feature_set: str) -> list[str]:
    cols = [c for group in FEATURE_SETS[feature_set] for c in sets[group]]
    return cols + list(sets["DUMMIES"])


# ---------------------------------------------------------------- model families


def make_model(family: str, params: dict | None = None):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeClassifier

    params = dict(params or {})
    if family == "decision_tree":
        return DecisionTreeClassifier(random_state=SEED, **params)
    if family == "random_forest":
        return RandomForestClassifier(random_state=SEED, n_jobs=-1, **params)
    if family == "logistic":
        return make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            StandardScaler(),
            LogisticRegression(max_iter=2000, **params),
        )
    if family == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(random_state=SEED, n_jobs=2, eval_metric="logloss", tree_method="hist", **params)
    raise ValueError(family)


GRIDS = {
    "decision_tree": [{"max_depth": d, "min_samples_leaf": m} for d in (3, 5) for m in (200, 800)],
    "random_forest": [
        {"n_estimators": 200, "max_depth": d, "min_samples_leaf": m, "max_features": 0.3}
        for d in (4, 8)
        for m in (100, 400)
    ],
    "logistic": [{"C": c} for c in (0.01, 0.1, 1.0)],
    "xgboost": [
        {
            "n_estimators": 200,
            "max_depth": d,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.5,
            "min_child_weight": w,
        }
        for d in (2, 4)
        for w in (20, 100)
    ],
}


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else float("nan")


def tune(family: str, X: pd.DataFrame, y: np.ndarray, dates: pd.Series, folds: int = 3) -> tuple[dict, list]:
    """Pick the parameters with the best mean AUC on expanding, time-ordered folds of the training rows."""
    order = np.argsort(dates.to_numpy(), kind="stable")
    X, y = X.iloc[order], y[order]
    unique_dates = np.sort(dates.unique())
    cuts = [unique_dates[int(len(unique_dates) * k / (folds + 1))] for k in range(1, folds + 1)] + [unique_dates[-1]]
    sorted_dates = dates.to_numpy()[order]
    trials = []
    for params in GRIDS[family]:
        scores = []
        for start, end in zip(cuts[:-1], cuts[1:], strict=True):
            fit_rows = sorted_dates <= start
            score_rows = (sorted_dates > start) & (sorted_dates <= end)
            model = make_model(family, params).fit(X[fit_rows], y[fit_rows])
            scores.append(_auc(y[score_rows], model.predict_proba(X[score_rows])[:, 1]))
        trials.append({"params": params, "cv_auc": float(np.nanmean(scores))})
    best = max(trials, key=lambda t: t["cv_auc"])
    return best["params"], trials


# ---------------------------------------------------------------- evaluation on validation


def precision_top_decile(y: np.ndarray, p: np.ndarray) -> float:
    cut = np.quantile(p, 0.9)
    top = p >= cut
    return float(y[top].mean()) if top.any() else float("nan")


def block_bootstrap_dates(values: pd.DataFrame, statistic, *, block: int = 20, reps: int = 500, seed: int = SEED):
    """Circular block bootstrap over dates: resample blocks of consecutive dates, keep all tickers of a date."""
    rng = np.random.default_rng(seed)
    dates = np.sort(values["date"].unique())
    groups = {d: g for d, g in values.groupby("date")}
    n = len(dates)
    out = []
    for _ in range(reps):
        starts = rng.integers(0, n, size=int(np.ceil(n / block)))
        picked = np.concatenate([(np.arange(s, s + block) % n) for s in starts])[:n]
        sample = pd.concat([groups[dates[i]] for i in picked], ignore_index=True)
        out.append(statistic(sample))
    return np.quantile(out, [0.025, 0.975]).tolist()


@dataclass
class Fitted:
    family: str
    feature_set: str
    params: dict
    model: object
    columns: list


def fit_and_score(features, sets, family, feature_set, horizon, *, tune_folds=3) -> tuple[Fitted, pd.DataFrame, dict]:
    parts = split(features, horizon)
    cols = columns_for(sets, feature_set)
    target = f"is_positive_growth_{horizon}d"
    train, val = parts["train"], parts["validation"]
    params, trials = tune(family, train[cols], train[target].to_numpy(), train["date"], folds=tune_folds)
    model = make_model(family, params).fit(train[cols], train[target].to_numpy())
    scored = val[["date", "ticker", target, f"growth_future_{horizon}d"]].copy()
    scored["probability"] = model.predict_proba(val[cols])[:, 1]
    record = {
        "family": family,
        "feature_set": feature_set,
        "horizon": horizon,
        "params": params,
        "cv_trials": trials,
        "train_rows": len(train),
        "validation_rows": len(val),
        "validation_auc": _auc(scored[target].to_numpy(), scored["probability"].to_numpy()),
        "validation_base_rate": float(scored[target].mean()),
        "validation_precision_top_decile": precision_top_decile(
            scored[target].to_numpy(), scored["probability"].to_numpy()
        ),
        "validation_auc_by_ticker": {
            t: _auc(g[target].to_numpy(), g["probability"].to_numpy()) for t, g in scored.groupby("ticker")
        },
    }
    return Fitted(family, feature_set, params, model, cols), scored, record


def permuted_control(fitted: Fitted, features, sets, horizon, *, seed: int = SEED) -> float:
    """Validation AUC with the TIME and SPACE columns shuffled within each ticker (their link to the target broken)."""
    rng = np.random.default_rng(seed)
    val = split(features, horizon)["validation"].copy()
    shuffled = [c for c in sets["TIME"] + sets["SPACE"] if c in fitted.columns]
    for _, idx in val.groupby("ticker").indices.items():
        perm = rng.permutation(idx)
        val.iloc[idx, [val.columns.get_loc(c) for c in shuffled]] = val.iloc[perm][shuffled].to_numpy()
    target = f"is_positive_growth_{horizon}d"
    return _auc(val[target].to_numpy(), fitted.model.predict_proba(val[fitted.columns])[:, 1])


def random_walk_frame(frame: pd.DataFrame, *, seed: int = SEED) -> pd.DataFrame:
    """The unified frame with each ticker's prices replaced by a random walk of the same drift and volatility.

    Dates, volume, reference closes and macro values are kept, so only the link between price paths
    and their own time and space coordinates is removed.
    """
    rng = np.random.default_rng(seed)
    parts = []
    for _, g in frame.sort_values(["ticker", "date"]).groupby("ticker"):
        g = g.copy()
        ret = np.log(g["close"]).diff().dropna()
        sim = np.exp(np.cumsum(np.r_[0.0, rng.normal(ret.mean(), ret.std(), len(g) - 1)])) * g["close"].iloc[0]
        wiggle = np.abs(rng.normal(0, ret.std() / 2, len(g)))
        g["open"] = sim * np.exp(rng.normal(0, ret.std() / 4, len(g)))
        g["close"] = g["adj_close"] = sim
        g["high"] = np.maximum(g["open"], sim) * np.exp(wiggle)
        g["low"] = np.minimum(g["open"], sim) * np.exp(-wiggle)
        parts.append(g)
    return pd.concat(parts, ignore_index=True)
