"""When in the month and in the quarter the period's low and high form (specification 0008).

For every complete month and quarter, the session of the lowest and of the highest close is
placed in a window (month: first week, middle, last week; quarter: first, second, third month).
The control keeps each period's own daily returns and length and shuffles only their order, so it
carries the market's drift, volatility and fat tails: a difference from it means that *when* in
the period the moves happen matters, not merely that the market tends to rise (which on its own
places lows early and highs late). A driftless random walk (the arcsine law) is a second
reference, shown in the card state.

Closing prices are graded in every market so that one definition holds everywhere, including
close-only index histories; where daily highs and lows exist, the day of the intraday low and
high is shown beside it as context, not graded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.studies.common import StudyContext, period_of

PP = 100.0
N_SHUFFLES = 10_000
MONTH_LABELS = ["First week", "Middle", "Last week"]
QUARTER_LABELS = ["1st month", "2nd month", "3rd month"]
MIN_PERIODS = {"month": 36, "quarter": 20}
BLOCK = {"month": 6, "quarter": 4}


def _first_extreme(path: np.ndarray, side: str) -> np.ndarray:
    """Index of the first lowest (or highest) value along the last axis; ties take the first."""
    return path.argmin(axis=-1) if side == "low" else path.argmax(axis=-1)


def window_groups(scope: str, dates: pd.DatetimeIndex, *, crypto: bool) -> np.ndarray:
    """Window of each session of one period, by position."""
    n = len(dates)
    if scope == "month":
        edge = 7 if crypto else 5
        g = np.ones(n, dtype=int)
        g[: min(edge, n)] = 0
        g[max(n - edge, min(edge, n)) :] = 2
        return g
    first_month = dates[0].month
    return ((dates.month - first_month) % 12).to_numpy(dtype=int).clip(0, 2)


def complete_periods(close: pd.Series, scope: str, *, crypto: bool) -> list[tuple[pd.Timestamp, pd.Series]]:
    """Complete months or quarters (the first and the last one in the data are dropped), each with
    the close before it, so that the first session's return is defined."""
    freq = "M" if scope == "month" else "Q"
    key = close.index.to_period(freq)
    labels = key.unique()
    out = []
    for i in range(1, len(labels) - 1):
        seg = close[key == labels[i]]
        prev = close[key == labels[i - 1]]
        if len(prev) == 0 or len(seg) < 2:
            continue
        if crypto:
            days = (labels[i].end_time.normalize() - labels[i].start_time.normalize()).days + 1
            if len(seg) != days:
                continue
        elif len(seg) < (15 if scope == "month" else 55):
            continue
        out.append((labels[i].start_time, pd.concat([prev.iloc[-1:], seg])))
    return out


def extreme_units(
    periods: list[tuple[pd.Timestamp, pd.Series]],
    scope: str,
    *,
    crypto: bool,
    n_shuffles: int = N_SHUFFLES,
    seed: int = 0,
) -> dict[str, np.ndarray]:
    """Observed window of each period's low and high and the share of shuffles placing it in each
    window (the control), plus a driftless random-walk reference."""
    rng = np.random.default_rng(seed)
    n = len(periods)
    out = {f"{k}_{s}": np.zeros((n, 3)) for k in ("obs", "base", "rw") for s in ("low", "high")}
    position = {s: np.zeros(n) for s in ("low", "high")}
    for i, (_, seg) in enumerate(periods):
        values = np.log(seg.to_numpy(float))
        ret = np.diff(values)
        k = len(ret)
        groups = window_groups(scope, pd.DatetimeIndex(seg.index[1:]), crypto=crypto)
        path = np.cumsum(ret)
        order = np.argsort(rng.random((n_shuffles, k)), axis=1)
        shuffled = np.cumsum(ret[order], axis=1)
        walk = np.cumsum(rng.standard_normal((n_shuffles, k)), axis=1)
        for side in ("low", "high"):
            j = int(_first_extreme(path, side))
            out[f"obs_{side}"][i, groups[j]] = 1.0
            position[side][i] = j / max(k - 1, 1)
            out[f"base_{side}"][i] = np.bincount(groups[_first_extreme(shuffled, side)], minlength=3)[:3] / n_shuffles
            out[f"rw_{side}"][i] = np.bincount(groups[_first_extreme(walk, side)], minlength=3)[:3] / n_shuffles
    out["position_low"], out["position_high"] = position["low"], position["high"]
    return out


def _difference(u: dict) -> np.ndarray:
    return u["obs"].mean(axis=0) - u["base"].mean(axis=0)


def _intraday_context(ctx: StudyContext, periods, scope: str) -> dict | None:
    """Share of periods whose intraday low (high) falls in each window; context only."""
    if not ctx.has_daily_ohlc:
        return None
    d = ctx.daily
    shares = {"low": np.zeros(3), "high": np.zeros(3)}
    used = 0
    for _, seg in periods:
        days = d.loc[seg.index[1:]]
        if len(days) != len(seg) - 1:
            continue
        groups = window_groups(scope, pd.DatetimeIndex(days.index), crypto=ctx.is_crypto)
        shares["low"][groups[int(days["low"].to_numpy(float).argmin())]] += 1
        shares["high"][groups[int(days["high"].to_numpy(float).argmax())]] += 1
        used += 1
    if used == 0:
        return None
    return {"periods": used, "low_pct": list(shares["low"] / used * PP), "high_pct": list(shares["high"] / used * PP)}


def _current(close: pd.Series, scope: str, periods) -> dict:
    """The period in progress: sessions so far, where its low and high stand, and how often past
    periods had already set them by the same point (observed only; context)."""
    freq = "M" if scope == "month" else "Q"
    key = close.index.to_period(freq)
    seg = close[key == key[-1]]
    k = len(seg)
    typical = int(np.median([len(s) - 1 for _, s in periods])) if periods else None
    already = {}
    for side in ("low", "high"):
        hits = []
        for _, s in periods:
            v = s.to_numpy(float)[1:]
            if len(v) <= k:
                continue
            j = int(v.argmin() if side == "low" else v.argmax())
            hits.append(j < k)
        already[side] = float(np.mean(hits) * PP) if hits else None
    low_day = int(seg.to_numpy(float).argmin()) + 1 if k else None
    high_day = int(seg.to_numpy(float).argmax()) + 1 if k else None
    return {
        "period_start": str(seg.index[0].date()) if k else None,
        "sessions_elapsed": k,
        "typical_sessions": typical,
        "low_so_far_session": low_day,
        "high_so_far_session": high_day,
        "low_set_by_now_pct": already["low"],
        "high_set_by_now_pct": already["high"],
    }


def extremes_cards(ctx: StudyContext, scope: str) -> list[EvidenceCard]:
    if ctx.daily is None or len(ctx.daily) == 0:
        return []
    close = ctx.daily["close"].astype(float).dropna()
    periods = complete_periods(close, scope, crypto=ctx.is_crypto)
    if len(periods) < MIN_PERIODS[scope]:
        return []
    units = extreme_units(periods, scope, crypto=ctx.is_crypto, n_shuffles=N_SHUFFLES, seed=ctx.seed)
    labels = MONTH_LABELS if scope == "month" else QUARTER_LABELS
    starts = pd.DatetimeIndex([p for p, _ in periods])
    context = _intraday_context(ctx, periods, scope)
    current = _current(close, scope, periods)
    unit_label = "months" if scope == "month" else "quarters"
    cards = []
    for side in ("low", "high"):
        u = {"obs": units[f"obs_{side}"], "base": units[f"base_{side}"]}
        result = evaluate(u, _difference, block=BLOCK[scope], reps=ctx.reps, seed=ctx.seed)
        items = items_from_evaluation(
            labels, result, scale=PP, observed=u["obs"].mean(axis=0), baseline=u["base"].mean(axis=0)
        )
        for i, item in enumerate(items):
            item.extra = {"random_walk": float(units[f"rw_{side}"].mean(axis=0)[i] * PP)}
            if context:
                item.extra["intraday"] = float(context[f"{side}_pct"][i])
        cards.append(
            EvidenceCard(
                id=f"{ctx.instrument.code}.extremes.{scope}_{side}",
                contrast="the same days in random order",
                instrument=ctx.instrument.code,
                family="extremes",
                kind="edge",
                title=f"When the {scope}'s {side} forms",
                question=(
                    f"In which part of the {scope} does the lowest close form, compared with the same days in random order?"
                    if side == "low"
                    else f"In which part of the {scope} does the highest close form, compared with the same days in random order?"
                ),
                unit="pp",
                method=(
                    f"Share of {unit_label} whose {'lowest' if side == 'low' else 'highest'} close falls in each window minus the "
                    f"share when the {scope}'s own daily returns are shuffled ({N_SHUFFLES:,} shuffles per {scope}); "
                    f"{BLOCK[scope]}-{scope} blocks, most recent 30% held out."
                ),
                control="The period's own daily returns in random order (keeps drift, volatility and fat tails)",
                n_label=unit_label,
                items=items,
                period=period_of(starts),
                notes=[
                    "Closing prices; ties take the first session. Windows: first and last "
                    + ("7 days" if ctx.is_crypto else "5 sessions")
                    + " of the month, or the three months of the quarter."
                    if scope == "month"
                    else "Closing prices; ties take the first session. Windows: the three calendar months of the quarter."
                ],
                state={
                    "scope": scope,
                    "periods": len(periods),
                    "intraday_context": context,
                    "mean_position": float(units[f"position_{side}"].mean()),
                    **current,
                },
            )
        )
    return cards


def run(ctx: StudyContext) -> list[EvidenceCard]:
    return [card for scope in ("month", "quarter") for card in extremes_cards(ctx, scope)]
