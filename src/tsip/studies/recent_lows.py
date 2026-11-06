"""Revisit of Monday's low and of the recent lows (specification 0010).

Monday's low. At the close of each day after Monday (equities: Tuesday to Thursday; crypto:
Tuesday to Saturday) on which price has not traded at or below Monday's low since Monday, the
event asks whether a later session trades at or below it before the week ends, and within 5 and
10 sessions.

The last three lows. At each week or month close, the lows of the last three complete periods
(the one just closed and the two before) are reference levels. The event asks whether price
trades at or below the nearest of them that lies below the close, and below the lowest of the
three, within each window. (Reaching any of them is the same as reaching the nearest.)

Control, as in the revisit study: from the paths of all other events, the share that travelled
at least the same distance (in units of the 60-session volatility known at the event's close),
downwards, within the same number of sessions. The graded difference is what the real level adds
beyond distance, volatility, drift and the shape of returns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.studies.common import StudyContext, consecutive_mask, period_of
from tsip.studies.revisit import _sigma, atr_pct, excursions, kaplan_meier_median

PP = 100.0
MIN_EVENTS = 60
MONDAY_WINDOWS = (5, 10)
RECENT = {"week": ((5, 10, 20), 8), "month": ((10, 20, 60), 6)}


def _down_outcomes(z: np.ndarray, down: np.ndarray, ks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Observed reach (0/1, NaN when the window is not fully observed) and the distance control,
    for windows of ``ks[i]`` sessions (one per event)."""
    n = len(z)
    obs = np.full(n, np.nan)
    base = np.full(n, np.nan)
    for k in np.unique(ks[ks > 0]):
        rows = np.flatnonzero(ks == k)
        reached_all = down[:, k - 1] if k <= down.shape[1] else np.full(n, np.nan)
        pool = np.sort(reached_all[np.isfinite(reached_all)])
        if len(pool) < 2:
            continue
        for i in rows:
            r = reached_all[i]
            if not np.isfinite(r) or not np.isfinite(z[i]):
                continue
            obs[i] = float(r >= z[i])
            count = len(pool) - np.searchsorted(pool, z[i], side="left")
            base[i] = (count - (1 if r >= z[i] else 0)) / (len(pool) - 1)
    return obs, base


def _statistic(u: dict) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        return np.nanmean(u["obs"], axis=0) - np.nanmean(u["base"], axis=0)


def _cut_gaps(up: np.ndarray, down: np.ndarray, starts: np.ndarray, gaps: np.ndarray, kmax: int) -> None:
    for i, s in enumerate(starts):
        span = gaps[s + 1 : s + kmax]
        if span.any():
            cut = int(np.argmax(span)) + 1
            up[i, cut:] = np.nan
            down[i, cut:] = np.nan


def monday_events(daily: pd.DataFrame, *, crypto: bool) -> dict | None:
    """Events at the close of each day after Monday with Monday's low still untested."""
    idx = pd.DatetimeIndex(daily.index)
    lo = daily["low"].to_numpy(float)
    close = daily["close"].to_numpy(float)
    sigma = _sigma(close)
    gaps = ~consecutive_mask(idx, crypto=crypto)
    week = idx.to_period("W-SUN")
    last_obs_day = 5 if crypto else 3
    rows = []
    for _, pos in pd.Series(np.arange(len(idx))).groupby(np.asarray(week)):
        pos = pos.to_numpy()
        if idx[pos[0]].dayofweek != 0:
            continue  # the week's first session is not a Monday (holiday, or data start)
        monday_low = lo[pos[0]]
        running = np.inf
        for j, p in enumerate(pos[1:], start=1):
            running = min(running, lo[p])
            if idx[p].dayofweek > last_obs_day:
                break
            if running <= monday_low:
                break  # tested: no more events this week
            sd = sigma[p]
            if p + 1 >= len(idx) or not np.isfinite(sd) or sd <= 0:
                continue
            remaining = len(pos) - 1 - j
            rows.append((p + 1, np.log(close[p] / monday_low) / sd, remaining, idx[p], idx[p].dayofweek))
    if len(rows) < MIN_EVENTS:
        return None
    starts = np.array([r[0] for r in rows])
    kmax = max(max(MONDAY_WINDOWS), max(r[2] for r in rows), 1)
    up, down = excursions(daily, starts, sigma, kmax)
    _cut_gaps(up, down, starts, gaps, kmax)
    return {
        "z": np.array([r[1] for r in rows]),
        "remaining": np.array([r[2] for r in rows], dtype=int),
        "date": pd.DatetimeIndex([r[3] for r in rows]),
        "weekday": np.array([r[4] for r in rows], dtype=int),
        "down": down,
    }


def recent_low_events(daily: pd.DataFrame, horizon: str, *, crypto: bool) -> dict | None:
    """Events at each period close with the nearest and the lowest of the last three period lows."""
    windows, _ = RECENT[horizon]
    idx = pd.DatetimeIndex(daily.index)
    lo = daily["low"].to_numpy(float)
    close = daily["close"].to_numpy(float)
    sigma = _sigma(close)
    gaps = ~consecutive_mask(idx, crypto=crypto)
    key = np.asarray(idx.to_period("W-SUN" if horizon == "week" else "M"))
    labels = pd.unique(key)
    lows, last_pos = [], []
    for lab in labels:
        pos = np.flatnonzero(key == lab)
        lows.append(lo[pos].min())
        last_pos.append(pos[-1])
    rows = []
    for i in range(3, len(labels) - 1):  # the first period may be partial; the last may be open
        p = last_pos[i]
        sd = sigma[p]
        if p + 1 >= len(idx) or gaps[p + 1] or not np.isfinite(sd) or sd <= 0:
            continue
        three = np.array(lows[i - 2 : i + 1])
        below = three[three < close[p]]
        if len(below) == 0:
            continue
        rows.append(
            (p + 1, np.log(close[p] / below.max()) / sd, np.log(close[p] / three.min()) / sd, idx[p], len(below))
        )
    if len(rows) < MIN_EVENTS // 2:
        return None
    starts = np.array([r[0] for r in rows])
    kmax = max(windows)
    up, down = excursions(daily, starts, sigma, kmax)
    _cut_gaps(up, down, starts, gaps, kmax)
    z_all = np.array([r[2] if r[4] == 3 else np.nan for r in rows])  # all three below the close
    return {
        "z_nearest": np.array([r[1] for r in rows]),
        "z_lowest": z_all,
        "date": pd.DatetimeIndex([r[3] for r in rows]),
        "down": down,
    }


def _extra(obs_col, base_col, path, z, unit_word):
    with np.errstate(invalid="ignore"):
        return {
            "observed_pct": float(np.nanmean(obs_col) * PP),
            "control_pct": float(np.nanmean(base_col) * PP),
            "median_sessions": kaplan_meier_median(path[np.isfinite(z)], z[np.isfinite(z)])
            if np.isfinite(z).any()
            else None,
            "median_distance_sigma": float(np.nanmedian(z)) if np.isfinite(z).any() else None,
            "unit_word": unit_word,
        }


def _card(ctx, *, card_id, title, question, method, n_label, labels, obs, base, extras, period, block, state):
    units = {"obs": obs, "base": base}
    result = evaluate(units, _statistic, block=block, reps=ctx.reps, seed=ctx.seed + len(card_id))
    with np.errstate(invalid="ignore"):
        observed = np.nanmean(obs, axis=0)
        baseline = np.nanmean(base, axis=0)
    counts = [int(np.isfinite(obs[:, j]).sum()) for j in range(obs.shape[1])]
    items = items_from_evaluation(labels, result, scale=PP, observed=observed, baseline=baseline, n_per_item=counts)
    for item, x in zip(items, extras, strict=True):
        item.extra = x
    return EvidenceCard(
        id=card_id,
        instrument=ctx.instrument.code,
        family="recent_lows",
        kind="edge",
        title=title,
        question=question,
        unit="pp",
        method=method,
        control="Arbitrary levels at the same volatility-scaled distance below the close, from all other events",
        n_label=n_label,
        items=items,
        period=period,
        contrast="equally distant arbitrary levels",
        notes=["A level counts as reached when a later session's low trades at or below it."],
        state=state,
    )


def _monday_today(daily: pd.DataFrame, *, crypto: bool) -> dict:
    idx = pd.DatetimeIndex(daily.index)
    week = idx.to_period("W-SUN")
    pos = np.flatnonzero(week == week[-1])
    lo = daily["low"].to_numpy(float)
    first = idx[pos[0]]
    state = {"week_start": str(first.date()), "today_weekday": int(idx[-1].dayofweek)}
    if first.dayofweek != 0:
        return {**state, "monday_low_untested": None}
    untested = bool(len(pos) > 1 and lo[pos[1:]].min() > lo[pos[0]])
    atr = atr_pct(daily)
    dist = float(np.log(daily["close"].iloc[-1] / lo[pos[0]]) * PP / atr) if atr else None
    return {**state, "monday_low_untested": untested, "distance_atr": dist if untested else None}


def monday_card(ctx: StudyContext) -> EvidenceCard | None:
    d = ctx.daily
    if not ctx.has_daily_ohlc or d is None or len(d) < 400:
        return None
    ev = monday_events(d, crypto=ctx.is_crypto)
    if ev is None:
        return None
    unit_word = "days" if ctx.is_crypto else "sessions"
    ks = [ev["remaining"]] + [np.full(len(ev["z"]), k) for k in MONDAY_WINDOWS]
    cols = [_down_outcomes(ev["z"], ev["down"], k) for k in ks]
    obs = np.column_stack([c[0] for c in cols])
    base = np.column_stack([c[1] for c in cols])
    labels = ["Before the week ends"] + [f"Within {k} {unit_word}" for k in MONDAY_WINDOWS]
    extras = [_extra(obs[:, j], base[:, j], ev["down"], ev["z"], unit_word) for j in range(obs.shape[1])]
    per_week = 5 if ctx.is_crypto else 3
    by_day = {}
    for wd in np.unique(ev["weekday"]):
        m = ev["weekday"] == wd
        with np.errstate(invalid="ignore"):
            by_day[int(wd)] = {
                "events": int(m.sum()),
                "observed_pct": float(np.nanmean(obs[m, 0]) * PP),
                "control_pct": float(np.nanmean(base[m, 0]) * PP),
            }
    return _card(
        ctx,
        card_id=f"{ctx.instrument.code}.recent_lows.monday",
        title="Back to Monday's low",
        question=(
            "When Monday's low is still untested at the close of a later day of the week, how often does price come "
            "back to it, compared with equally distant arbitrary levels?"
        ),
        method=(
            "Events: the close of each day after Monday (equities Tuesday to Thursday; crypto Tuesday to Saturday) with "
            "Monday's low not yet traded again. Share of events in which a later session traded at or below Monday's "
            "low within each window, minus the share of all other events' paths that travelled at least the same "
            "distance downwards (60-session volatility units) within the same number of sessions. Events resampled in "
            f"blocks of {8 * per_week} (about eight weeks)."
        ),
        n_label="days with Monday's low untested",
        labels=labels,
        obs=obs,
        base=base,
        extras=extras,
        period=period_of(ev["date"]),
        block=8 * per_week,
        state={**_monday_today(d, crypto=ctx.is_crypto), "by_weekday": by_day},
    )


def recent_card(ctx: StudyContext, horizon: str) -> EvidenceCard | None:
    d = ctx.daily
    if not ctx.has_daily_ohlc or d is None or len(d) < 400:
        return None
    ev = recent_low_events(d, horizon, crypto=ctx.is_crypto)
    if ev is None:
        return None
    windows, block = RECENT[horizon]
    unit_word = "days" if ctx.is_crypto else "sessions"
    obs_cols, base_cols, extras, labels = [], [], [], []
    for which, z in (("nearest", ev["z_nearest"]), ("lowest", ev["z_lowest"])):
        for k in windows:
            o, b = _down_outcomes(z, ev["down"], np.full(len(z), k))
            obs_cols.append(o)
            base_cols.append(b)
            extras.append(_extra(o, b, ev["down"], z, unit_word))
            labels.append(
                f"Nearest of the three within {k} {unit_word}"
                if which == "nearest"
                else f"Lowest of the three within {k} {unit_word}"
            )
    name = horizon
    return _card(
        ctx,
        card_id=f"{ctx.instrument.code}.recent_lows.{horizon}",
        title=f"Back to the last three {name}ly lows",
        question=(
            f"After a {name} closes, how often does price come back to the nearest, and to the lowest, of the last three "
            f"{name}s' lows, compared with equally distant arbitrary levels?"
        ),
        method=(
            f"Events: each {name} close. Levels: the lows of that {name} and of the two before; 'nearest' is the highest "
            "of them below the close, 'lowest' the lowest of the three, used when all three are below the close. Share "
            "of events reached within each window minus the share of all other events' paths that travelled at least "
            f"the same distance downwards (60-session volatility units). Events resampled in {block}-{name} blocks."
        ),
        n_label=f"{name}s",
        labels=labels,
        obs=np.column_stack(obs_cols),
        base=np.column_stack(base_cols),
        extras=extras,
        period=period_of(ev["date"]),
        block=block,
        state={"horizon": horizon},
    )


def run(ctx: StudyContext) -> list[EvidenceCard]:
    cards = [monday_card(ctx)] + [recent_card(ctx, h) for h in RECENT]
    return [c for c in cards if c is not None]
