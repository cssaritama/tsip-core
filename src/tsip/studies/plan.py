"""Trade plan from here: what a simple plan taken at the latest close returned by the period's end.

For each period in progress (week, month) after k sessions, the analogs are past complete periods observed
after the same k sessions, in the same state (prior high and low traded or not), as in the money study. From
the close of session k, six plans are followed on intraday bars to the period's last session: long and
short, each held to the period's last close, with a stop at 1 ATR and a target at 1 ATR, and with a stop at
1 ATR and a target at 2 ATR. The ATR is the 14-session ATR at the start of the period. A bar that reaches
both levels counts as the stop; a bar that opens beyond a level exits at its open. Results are in ATR and
gross. Each plan's average result in today's state is compared with its average over all past periods at
the same point. Under a random walk every difference is zero. Specification: ``specs/0005-trade-plan-from-here.md``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.frames import HORIZON_NAMES, horizon_bars, period_key, period_label
from tsip.studies.common import StudyContext, period_of
from tsip.studies.level_map import current_state
from tsip.studies.money import atr_percent

HORIZONS = ("week", "month")
BLOCK = {"week": 8, "month": 6}
STOP_ATR = 1.0
PP = 100.0
# (code, label, direction, target in ATR or None for a plan held to the period's last close)
PLANS = (
    ("long_hold", "Long, held to the {h}'s last close", 1, None),
    ("long_1_1", "Long, stop 1 ATR, target 1 ATR", 1, 1.0),
    ("long_1_2", "Long, stop 1 ATR, target 2 ATR", 1, 2.0),
    ("short_hold", "Short, held to the {h}'s last close", -1, None),
    ("short_1_1", "Short, stop 1 ATR, target 1 ATR", -1, 1.0),
    ("short_1_2", "Short, stop 1 ATR, target 2 ATR", -1, 2.0),
)


def bracket(o, h, lo, ref: float, atr_pct: float, side: int, target: float, last: float, stop: float = STOP_ATR):
    """Result in ATR and how the plan ended ("target", "stop" or "neither") on the bars after the entry.

    ``side`` is 1 for a long and -1 for a short. A bar that reaches both levels counts as the stop; a bar
    that opens beyond a level exits at its open; with no level reached the plan exits at ``last``.
    """
    o, h, lo = (np.asarray(x, float) for x in (o, h, lo))
    unit = ref * atr_pct / PP
    if side > 0:
        upper, lower = ref + target * unit, ref - stop * unit
        gap_stop, gap_target, hit_stop, hit_target = o <= lower, o >= upper, lo <= lower, h >= upper
    else:
        upper, lower = ref + stop * unit, ref - target * unit
        gap_stop, gap_target, hit_stop, hit_target = o >= upper, o <= lower, h >= upper, lo <= lower
    ends = gap_stop | gap_target | hit_stop | hit_target
    if not ends.any():
        return side * (last / ref - 1.0) * PP / atr_pct, "neither"
    i = int(np.argmax(ends))
    if gap_stop[i] or gap_target[i]:
        return side * (o[i] / ref - 1.0) * PP / atr_pct, "target" if gap_target[i] else "stop"
    if hit_stop[i]:
        return -stop, "stop"
    return target, "target"


def path_arrays(ctx: StudyContext):
    """Session date, open, high and low of every intraday bar, in time order, or None without intraday data."""
    if ctx.is_crypto:
        bars = ctx.intraday
        if bars is None or not len(bars):
            return None
        idx = pd.DatetimeIndex(bars.index)
        dates = (idx.tz_convert("UTC").tz_localize(None) if idx.tz is not None else idx).normalize()
    else:
        bars = ctx.path_bars
        if bars is None or not len(bars) or "date" not in bars:
            return None
        dates = pd.DatetimeIndex(bars["date"])
    order = np.argsort(np.asarray(bars.index.values), kind="stable")
    cols = [bars[c].to_numpy(float)[order] for c in ("open", "high", "low")]
    return (np.asarray(dates.values, dtype="datetime64[ns]")[order], *cols)


MIN_HISTORY = 250
REGIMES = (("calm", 0.0, 100 / 3), ("normal", 100 / 3, 200 / 3), ("volatile", 200 / 3, 100.0001))


def atr_percentiles(atr: np.ndarray, min_history: int = MIN_HISTORY) -> np.ndarray:
    """Percentile of each session's ATR among the ATR values of all earlier sessions (NaN without enough)."""
    import bisect

    out = np.full(len(atr), np.nan)
    seen: list[float] = []
    for i, value in enumerate(atr):
        if np.isfinite(value):
            if len(seen) >= min_history:
                out[i] = 100.0 * bisect.bisect_left(seen, value) / len(seen)
            bisect.insort(seen, float(value))
    return out


def regime_of(percentile: float) -> str | None:
    if not np.isfinite(percentile):
        return None
    return next(name for name, lo, hi in REGIMES if lo <= percentile < hi)


def plan_events(daily: pd.DataFrame, path, horizon: str, *, crypto: bool, sessions: int) -> pd.DataFrame:
    """One row per complete past period, after a complete period, lasting longer than ``sessions``, whose
    every remaining session has intraday bars: its state after ``sessions`` sessions and each plan's result."""
    bars = horizon_bars(daily, horizon, crypto=crypto)
    keys = period_key(daily.index, horizon)
    high, low, close = (daily[col].to_numpy(float) for col in ("high", "low", "close"))
    atr = atr_percent(daily)
    ranks = atr_percentiles(atr)
    days = np.asarray(pd.DatetimeIndex(daily.index).values, dtype="datetime64[ns]")
    pdates, po, ph, pl = path
    complete = {int(k) for k in bars.index}
    starts = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
    ends = np.r_[starts[1:], len(keys)]
    rows = []
    for start, end in zip(starts, ends, strict=True):
        key = int(keys[start])
        if key not in complete or key - 1 not in complete or start == 0 or end - start <= sessions:
            continue
        yardstick = atr[start - 1]
        if not np.isfinite(yardstick) or yardstick <= 0:
            continue
        entry = start + sessions  # first session after the observation point
        remaining = days[entry:end]
        a = int(np.searchsorted(pdates, remaining[0], side="left"))
        b = int(np.searchsorted(pdates, remaining[-1], side="right"))
        if b <= a or not np.isin(remaining, pdates[a:b]).all():
            continue  # a session without intraday bars: the order of stop and target is unknown
        prior = bars.loc[key - 1]
        ref, last = close[entry - 1], close[end - 1]
        row = {
            "key": key,
            "start": daily.index[start],
            "atr_percentile": float(ranks[start - 1]),
            "broke_high_so_far": bool(high[start:entry].max() > float(prior["high"])),
            "broke_low_so_far": bool(low[start:entry].min() < float(prior["low"])),
        }
        for code, _, side, target in PLANS:
            if target is None:
                result, how = side * (last / ref - 1.0) * PP / yardstick, "neither"
            else:
                result, how = bracket(po[a:b], ph[a:b], pl[a:b], ref, yardstick, side, target, last)
            row[code], row[f"{code}__how"] = float(result), how
        rows.append(row)
    return pd.DataFrame(rows)


def _summary(frame: pd.DataFrame, code: str) -> dict:
    values = frame[code].to_numpy(float)
    how = frame[f"{code}__how"].to_numpy()
    q1, med, q3 = np.percentile(values, [25, 50, 75])
    share = lambda mask: round(float(np.mean(mask)) * PP, 1)  # noqa: E731
    return {
        "target_first": share(how == "target"),
        "stop_first": share(how == "stop"),
        "neither": share(how == "neither"),
        "win": share(values > 0),
        "q1": round(float(q1), 3),
        "median": round(float(med), 3),
        "q3": round(float(q3), 3),
    }


def _graded_items(ctx: StudyContext, events: pd.DataFrame, same_mask: pd.Series, horizon: str, seed: int) -> list:
    same = events[same_mask]
    name = HORIZON_NAMES[horizon]
    cols = [code for code, *_ in PLANS]
    labels = [label.format(h=name) for _, label, _, _ in PLANS]
    units = {"s": same_mask.to_numpy(float), **{c: events[c].to_numpy(float) for c in cols}}

    def statistic(u: dict) -> np.ndarray:
        inside = u["s"] == 1.0
        if not inside.any() or inside.all():
            return np.full(len(cols), np.nan)
        return np.array([u[c][inside].mean() - u[c].mean() for c in cols], dtype=float)  # state against all

    if not 0 < len(same) < len(events):
        return []
    result = evaluate(units, statistic, block=BLOCK[horizon], reps=ctx.reps, seed=ctx.seed + seed)
    items = items_from_evaluation(
        labels,
        result,
        scale=1.0,
        observed=np.array([same[c].mean() for c in cols]),
        baseline=np.array([events[c].mean() for c in cols]),
        n_per_item=[len(same)] * len(cols),
    )
    for item, code in zip(items, cols, strict=True):
        item.extra = {"plan": code, "same": _summary(same, code), "all": _summary(events, code)}
    return items


def plan_card(ctx: StudyContext, horizon: str) -> EvidenceCard | None:
    if not ctx.has_daily_ohlc or ctx.daily.attrs.get("close_only"):
        return None
    path = path_arrays(ctx)
    if path is None:
        return None
    d = ctx.daily
    state = current_state(d, horizon, crypto=ctx.is_crypto)
    if state is None:
        return None
    events = plan_events(d, path, horizon, crypto=ctx.is_crypto, sessions=state["sessions"])
    if len(events) == 0:
        return None
    events = events[events["key"] != state["key"]]  # the current period never enters its own analogs
    same_mask = (events["broke_high_so_far"] == state["broke_high"]) & (
        events["broke_low_so_far"] == state["broke_low"]
    )
    same = events[same_mask]
    name = HORIZON_NAMES[horizon]
    items = _graded_items(ctx, events, same_mask, horizon, 37)
    keys = period_key(d.index, horizon)
    first = int(np.flatnonzero(keys == state["key"])[0])
    yardstick = atr_percent(d)[first - 1] if first > 0 else float("nan")
    lengths = horizon_bars(d, horizon, crypto=ctx.is_crypto)["n_sessions"]
    unit_word = "days" if ctx.is_crypto else "sessions"
    card_state = {
        "horizon": name,
        "period": period_label(state["key"], horizon),
        "sessions_elapsed": state["sessions"],
        "typical_sessions": int(np.median(lengths)) if len(lengths) else None,
        "session_unit": unit_word,
        "broke_prior_high": state["broke_high"],
        "broke_prior_low": state["broke_low"],
        "atr_start_pct": round(float(yardstick), 3) if np.isfinite(yardstick) else None,
        "stop_atr": STOP_ATR,
        "analogs": int(len(same)),
        "all_periods": int(len(events)),
        "path_from": str(pd.Timestamp(path[0][0]).date()),
        "as_of": str(state["as_of"].date()),
    }
    situation = (
        ("above" if state["broke_high"] else "not above")
        + " the prior high and "
        + ("below" if state["broke_low"] else "not below")
        + " the prior low"
    )
    bar_word = "hourly" if ctx.is_crypto else "30-minute"
    return EvidenceCard(
        id=f"{ctx.instrument.code}.plan.{name}",
        instrument=ctx.instrument.code,
        family="plan",
        kind="edge",
        title=f"A simple plan from here to the end of the {name}",
        question=(
            f"After {state['sessions']} {unit_word} of {card_state['period']}, {situation} so far: what did a long "
            f"or a short taken at the close return by the end of the {name}, held or with a 1 ATR stop, in past "
            f"{name}s at the same point?"
        ),
        unit="ATR",
        method=(
            f"Analogs are past complete {name}s, each after a complete {name}, observed after the same "
            f"{state['sessions']} {unit_word} and in the same state. From the close at the observation point, each "
            f"plan is followed on {bar_word} bars to the {name}'s last session: a bar that reaches both the stop and "
            f"the target counts as the stop, and a bar that opens beyond a level exits at its open. Results are in "
            f"multiples of the 14-session ATR at the start of the {name}, gross. Each plan's average result is "
            f"compared with its average over all past {name}s at the same point; circular block bootstrap over "
            f"{name}s ({BLOCK[horizon]}-{name} blocks), most recent 30% held out."
        ),
        control=f"All past {name}s at the same point, in any state",
        contrast=f"all {name}s at the same point",
        n_label=f"{name}s",
        items=items,
        period=period_of(pd.DatetimeIndex(same["start"]) if len(same) else pd.DatetimeIndex([])),
        notes=[
            "Results are gross: no commissions, spread, financing, borrowing or taxes. On the page, the reader's "
            "round-trip cost is converted into ATR of the period and subtracted.",
            "Counting a bar that reaches both levels as the stop biases every plan against itself, equally in "
            "today's state and in all periods.",
        ],
        state=card_state,
    )


def regime_card(ctx: StudyContext, horizon: str) -> EvidenceCard | None:
    """The six plans in past periods that started in today's volatility regime (specification 0007)."""
    if not ctx.has_daily_ohlc or ctx.daily.attrs.get("close_only"):
        return None
    path = path_arrays(ctx)
    if path is None:
        return None
    d = ctx.daily
    state = current_state(d, horizon, crypto=ctx.is_crypto)
    if state is None:
        return None
    atr = atr_percent(d)
    keys = period_key(d.index, horizon)
    first = int(np.flatnonzero(keys == state["key"])[0])
    if first == 0:
        return None
    today_pct = atr_percentiles(atr)[first - 1]
    regime = regime_of(today_pct)
    if regime is None:
        return None
    events = plan_events(d, path, horizon, crypto=ctx.is_crypto, sessions=state["sessions"])
    if len(events) == 0:
        return None
    events = events[(events["key"] != state["key"]) & np.isfinite(events["atr_percentile"])]
    same_mask = events["atr_percentile"].map(regime_of) == regime
    items = _graded_items(ctx, events, same_mask, horizon, 41)
    name = HORIZON_NAMES[horizon]
    unit_word = "days" if ctx.is_crypto else "sessions"
    bar_word = "hourly" if ctx.is_crypto else "30-minute"
    card_state = {
        "horizon": name,
        "period": period_label(state["key"], horizon),
        "sessions_elapsed": state["sessions"],
        "session_unit": unit_word,
        "regime": regime,
        "atr_start_pct": round(float(atr[first - 1]), 3),
        "atr_start_percentile": round(float(today_pct), 1),
        "analogs": int(same_mask.sum()),
        "all_periods": int(len(events)),
        "path_from": str(pd.Timestamp(path[0][0]).date()),
        "as_of": str(state["as_of"].date()),
    }
    return EvidenceCard(
        id=f"{ctx.instrument.code}.plan_regime.{name}",
        instrument=ctx.instrument.code,
        family="plan_regime",
        kind="edge",
        title=f"A simple plan from here to the end of the {name}, by volatility regime",
        question=(
            f"{card_state['period'].capitalize()} started {regime} (ATR at the {today_pct:.0f}th percentile of all "
            f"earlier {unit_word}): after {state['sessions']} {unit_word}, what did a long or a short taken at the "
            f"close return by the end of the {name} in past {name}s that started {regime}?"
        ),
        unit="ATR",
        method=(
            f"Each past {name} is classed by the percentile of its starting ATR (the last session of the prior "
            f"{name}) among all earlier {unit_word}: calm below the 33rd, volatile from the 67th, normal between; at "
            f"least {MIN_HISTORY} earlier {unit_word} are required. The six plans of the trade plan study are "
            f"followed on {bar_word} bars from the close after the same {state['sessions']} {unit_word}; each plan's "
            f"average result in today's regime is compared with all {name}s at the same point; circular block "
            f"bootstrap over {name}s ({BLOCK[horizon]}-{name} blocks), most recent 30% held out."
        ),
        control=f"All past {name}s at the same point, in any regime",
        contrast=f"all {name}s at the same point",
        n_label=f"{name}s",
        items=items,
        period=period_of(pd.DatetimeIndex(events.loc[same_mask, "start"]) if same_mask.any() else pd.DatetimeIndex([])),
        notes=["Results are gross. The regime uses only volatility known before the period started."],
        state=card_state,
    )


def run(ctx: StudyContext) -> list[EvidenceCard]:
    cards = [plan_card(ctx, h) for h in HORIZONS] + [regime_card(ctx, h) for h in HORIZONS]
    return [c for c in cards if c is not None and c.items]


__all__ = [
    "bracket",
    "plan_events",
    "plan_card",
    "regime_card",
    "atr_percentiles",
    "regime_of",
    "path_arrays",
    "run",
    "PLANS",
]
