"""Where the latest session stands against the prior week, month, quarter, half-year and year.

For each horizon the current period is the one that contains the latest daily bar,
provided it is still in progress. Its state so far is whether it has already traded
above the prior period's high and below the prior period's low after *k* sessions.

Analogs are past complete periods, each following a complete prior period, observed
after the same *k* sessions and in the same state. Their outcomes at the end of the
period give the historical rates on the card. Everything is computed from data
available at the latest bar, and the current period never enters its own analogs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation, widen_proportions
from tsip.frames import HORIZON_NAMES, has_ended, horizon_bars, period_bounds, period_key, period_label
from tsip.studies.common import StudyContext, period_of

PP = 100.0
HORIZONS = ("week", "month", "quarter", "half", "year")
BLOCK = {"week": 8, "month": 6, "quarter": 4, "half": 2, "year": 2}


def current_state(daily: pd.DataFrame, horizon: str, *, crypto: bool) -> dict | None:
    """State of the period in progress after its sessions so far, or None if none is in progress."""
    if daily is None or len(daily) == 0:
        return None
    keys = period_key(daily.index, horizon)
    current = int(keys[-1])
    last_day = pd.Timestamp(daily.index[-1])
    if has_ended(last_day, period_bounds(current, horizon)[1], crypto=crypto):
        return None
    bars = horizon_bars(daily, horizon, crypto=crypto)
    if current - 1 not in bars.index:
        return None
    prior = bars.loc[current - 1]
    rows = daily[keys == current]
    high, low, close = float(rows["high"].max()), float(rows["low"].min()), float(rows["close"].iloc[-1])
    prior_high, prior_low = float(prior["high"]), float(prior["low"])
    zone = "above" if close > prior_high else "below" if close < prior_low else "inside"
    return {
        "key": current,
        "sessions": int(len(rows)),
        "broke_high": bool(high > prior_high),
        "broke_low": bool(low < prior_low),
        "zone": zone,
        "as_of": last_day,
    }


def analog_outcomes(daily: pd.DataFrame, horizon: str, *, crypto: bool, sessions: int) -> pd.DataFrame:
    """For every complete period that follows a complete period and lasts longer than ``sessions``:
    its state after ``sessions`` sessions and its outcomes at the end of the period."""
    bars = horizon_bars(daily, horizon, crypto=crypto)
    keys = period_key(daily.index, horizon)
    high, low = daily["high"].to_numpy(float), daily["low"].to_numpy(float)
    complete = set(int(k) for k in bars.index)
    starts = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
    rows = []
    for start in starts:
        key = int(keys[start])
        if key not in complete or key - 1 not in complete:
            continue
        period, prior = bars.loc[key], bars.loc[key - 1]
        if int(period["n_sessions"]) <= sessions:
            continue
        stop = start + sessions
        ph, pl = float(prior["high"]), float(prior["low"])
        rows.append(
            {
                "key": key,
                "start": period_bounds(key, horizon)[0],
                "broke_high_so_far": bool(high[start:stop].max() > ph),
                "broke_low_so_far": bool(low[start:stop].min() < pl),
                "took_high": float(period["high"] > ph),
                "took_low": float(period["low"] < pl),
                "close_above": float(period["close"] > ph),
                "close_below": float(period["close"] < pl),
                "close_inside": float(pl <= period["close"] <= ph),
                "n_sessions": int(period["n_sessions"]),
            }
        )
    return pd.DataFrame(rows)


def _items_for(state: dict, name: str) -> list[tuple[str, str]]:
    """(column, label) pairs, decision-relevant first. Outcomes already decided are left out."""
    above_close = ("close_above", f"Closes the {name} above the prior {name}'s high")
    below_close = ("close_below", f"Closes the {name} below the prior {name}'s low")
    inside_close = ("close_inside", f"Closes the {name} inside the prior {name}'s range")
    take_high = ("took_high", f"Trades above the prior {name}'s high before the {name} ends")
    take_low = ("took_low", f"Trades below the prior {name}'s low before the {name} ends")
    if state["broke_high"] and state["broke_low"]:
        return [above_close, below_close, inside_close]
    if state["broke_high"]:
        return [above_close, take_low, below_close, inside_close]
    if state["broke_low"]:
        return [below_close, take_high, above_close, inside_close]
    return [take_high, take_low, above_close, below_close, inside_close]


def map_card(ctx: StudyContext, horizon: str) -> EvidenceCard | None:
    if not ctx.has_daily_ohlc:
        return None
    d = ctx.daily
    state = current_state(d, horizon, crypto=ctx.is_crypto)
    if state is None:
        return None
    name = HORIZON_NAMES[horizon]
    history = analog_outcomes(d, horizon, crypto=ctx.is_crypto, sessions=state["sessions"])
    lengths = horizon_bars(d, horizon, crypto=ctx.is_crypto)["n_sessions"]
    typical = int(np.median(lengths)) if len(lengths) else None
    if len(history):
        same = history[
            (history["broke_high_so_far"] == state["broke_high"]) & (history["broke_low_so_far"] == state["broke_low"])
        ]
    else:
        same = history
    pairs = _items_for(state, name)
    items = []
    index = pd.DatetimeIndex([])
    if len(same):
        units = {col: same[col].to_numpy(float) for col, _ in pairs}
        cols = [col for col, _ in pairs]

        def statistic(u: dict) -> np.ndarray:
            return np.array([u[c].mean() for c in cols], dtype=float)

        result = evaluate(units, statistic, block=BLOCK[horizon], reps=ctx.reps, seed=ctx.seed)
        items = widen_proportions(
            items_from_evaluation([label for _, label in pairs], result, scale=PP, n_per_item=[len(same)] * len(cols))
        )
        for item, col in zip(items, cols, strict=True):
            item.extra = {"outcome": col}
        index = pd.DatetimeIndex(same["start"])
    unit_word = "days" if ctx.is_crypto else "sessions"
    situation = (
        ("above" if state["broke_high"] else "not above")
        + " the prior high and "
        + ("below" if state["broke_low"] else "not below")
        + " the prior low"
    )
    card_state = {
        "horizon": name,
        "period": period_label(state["key"], horizon),
        "prior_period": period_label(state["key"] - 1, horizon),
        "sessions_elapsed": state["sessions"],
        "typical_sessions": typical,
        "session_unit": unit_word,
        "broke_prior_high": state["broke_high"],
        "broke_prior_low": state["broke_low"],
        "last_close_vs_prior_range": state["zone"],
        "as_of": str(state["as_of"].date()),
        "analogs": int(len(same)),
    }
    notes = []
    if typical:
        notes.append(f"About {max(typical - state['sessions'], 0)} of a typical {typical} {unit_word} remain.")
    return EvidenceCard(
        id=f"{ctx.instrument.code}.map.{name}",
        instrument=ctx.instrument.code,
        family="map",
        kind="base_rate",
        title=f"This {name} so far",
        question=(
            f"{card_state['period']}, after {state['sessions']} {unit_word}: what happened by the end of past {name}s "
            f"in the same position?"
        ),
        unit="%",
        method=(
            f"State after {state['sessions']} {unit_word} of {card_state['period']} versus {card_state['prior_period']}: "
            f"{situation} so far. Analogs are past complete {name}s, each after a complete {name}, observed after the "
            f"same number of {unit_word} and in the same state; the rates are their outcomes at the end of the {name}. "
            f"95% interval by circular block bootstrap over analogs ({BLOCK[horizon]}-{name} blocks); stability "
            "compares older with more recent analogs. Price levels are not published."
        ),
        control="Descriptive conditional base rate (no null)",
        n_label=f"{name}s",
        items=items,
        period=period_of(index),
        notes=notes,
        state=card_state,
    )


def run(ctx: StudyContext) -> list[EvidenceCard]:
    cards = [map_card(ctx, h) for h in HORIZONS]
    return [c for c in cards if c is not None]
