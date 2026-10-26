"""Inference helpers: percentile intervals, bootstrap p-values and FDR control."""

from __future__ import annotations

import warnings

import numpy as np


def percentile_interval(replicates: np.ndarray, level: float = 0.95) -> tuple[np.ndarray, np.ndarray]:
    alpha = (1 - level) / 2
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # items undefined in every replicate stay NaN
        low = np.nanquantile(replicates, alpha, axis=0)
        high = np.nanquantile(replicates, 1 - alpha, axis=0)
    return low, high


def bootstrap_p_value(estimate: np.ndarray, replicates: np.ndarray, null: float | np.ndarray = 0.0) -> np.ndarray:
    """Two-sided p-value by the shift method.

    The bootstrap distribution is centred on zero and compared with the
    observed distance from the null: ``p = (1 + #{|θ*-mean(θ*)| >= |θ-θ0|}) / (B + 1)``.
    """
    estimate = np.atleast_1d(estimate).astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # items undefined in every replicate stay NaN
        centred = replicates - np.nanmean(replicates, axis=0)
    distance = np.abs(estimate - null)
    exceed = (np.abs(centred) >= distance[None, :]).sum(axis=0)
    valid = np.isfinite(replicates).sum(axis=0)
    p = (1 + exceed) / (1 + valid)
    p[~np.isfinite(estimate)] = np.nan
    return p


def wilson_interval(p: float, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score interval for a proportion ``p`` observed in ``n`` independent trials."""
    if n <= 0 or not np.isfinite(p):
        return float("nan"), float("nan")
    p = min(max(float(p), 0.0), 1.0)
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return float(max(0.0, centre - half)), float(min(1.0, centre + half))


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    """Benjamini–Hochberg adjusted p-values (q-values); NaNs are ignored."""
    p = np.asarray(p_values, dtype=float)
    q = np.full_like(p, np.nan)
    mask = np.isfinite(p)
    m = int(mask.sum())
    if m == 0:
        return q
    order = np.argsort(p[mask])
    ranked = p[mask][order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted = np.empty(m)
    adjusted[order] = np.minimum(ranked, 1.0)
    q[mask] = adjusted
    return q
