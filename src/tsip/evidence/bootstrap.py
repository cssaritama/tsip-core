"""Circular block bootstrap over time-ordered units.

Market observations are serially dependent, so resampling individual days
understates uncertainty. Units (days, weeks, events, months) are resampled
in contiguous circular blocks that preserve short-range dependence.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np

from tsip.evidence.inference import bootstrap_p_value, percentile_interval

Units = Mapping[str, np.ndarray]
Statistic = Callable[[Units], np.ndarray]


def circular_block_indices(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    block = max(1, min(block, n))
    n_blocks = -(-n // block)
    starts = rng.integers(0, n, size=n_blocks)
    idx = (starts[:, None] + np.arange(block)[None, :]) % n
    return idx.ravel()[:n]


def take(units: Units, idx: np.ndarray) -> dict[str, np.ndarray]:
    return {key: np.asarray(value)[idx] for key, value in units.items()}


def replicates(units: Units, statistic: Statistic, *, block: int, reps: int, seed: int) -> np.ndarray:
    n = len(next(iter(units.values())))
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        out.append(np.atleast_1d(statistic(take(units, circular_block_indices(n, block, rng)))))
    return np.vstack(out)


def evaluate(
    units: Units,
    statistic: Statistic,
    *,
    block: int,
    reps: int = 1000,
    seed: int = 0,
    null: float | np.ndarray = 0.0,
    holdout_fraction: float = 0.3,
) -> dict[str, np.ndarray | int]:
    """Estimate, 95% interval, p-value and discovery/holdout split for each item.

    ``statistic`` maps a dict of unit arrays to a vector of item estimates.
    Units must be ordered in time; the holdout is the most recent
    ``holdout_fraction`` of units.
    """
    n = len(next(iter(units.values())))
    estimate = np.atleast_1d(statistic(units)).astype(float)
    reps_full = replicates(units, statistic, block=block, reps=reps, seed=seed)
    ci_low, ci_high = percentile_interval(reps_full)
    p_value = bootstrap_p_value(estimate, reps_full, null)
    cut = int(round(n * (1 - holdout_fraction)))
    disc = {k: np.asarray(v)[:cut] for k, v in units.items()}
    hold = {k: np.asarray(v)[cut:] for k, v in units.items()}
    discovery = np.atleast_1d(statistic(disc)).astype(float) if cut > 0 else np.full_like(estimate, np.nan)
    holdout = np.atleast_1d(statistic(hold)).astype(float) if n - cut > 0 else np.full_like(estimate, np.nan)
    if n - cut >= 2 * block:
        reps_hold = replicates(hold, statistic, block=block, reps=max(200, reps // 2), seed=seed + 1)
        holdout_p = bootstrap_p_value(holdout, reps_hold, null)
        hold_low, hold_high = percentile_interval(reps_hold)
    else:
        holdout_p = np.full_like(estimate, np.nan)
        hold_low = hold_high = np.full_like(estimate, np.nan)
    return {
        "n": n,
        "n_discovery": cut,
        "n_holdout": n - cut,
        "estimate": estimate,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "p_value": p_value,
        "discovery": discovery,
        "holdout": holdout,
        "holdout_low": hold_low,
        "holdout_high": hold_high,
        "holdout_p": holdout_p,
    }
