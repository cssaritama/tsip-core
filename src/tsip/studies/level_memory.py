"""Level memory: how often price trades through the prior period's high and low.

Base rates for days, weeks and months: the share of periods that trade
above the prior high, below the prior low, both or neither, and how often a
break is still in place at the period close. For weeks, also how often the
Monday high and low are exceeded later in the week.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.frames import period_bars
from tsip.studies.common import StudyContext, consecutive_mask, period_of

PP = 100.0
LABELS = [
    "Trades above the prior high",
    "Trades below the prior low",
    "Trades through both",
    "Stays inside the prior range",
    "Close holds above the prior high (when broken)",
    "Close holds below the prior low (when broken)",
]
MONDAY_LABELS = ["Monday high exceeded later in the week", "Monday low undercut later in the week"]


def _indicators(high, low, close, prev_high, prev_low) -> dict[str, np.ndarray]:
    took_high = high > prev_high
    took_low = low < prev_low
    return {
        "took_high": took_high.astype(float),
        "took_low": took_low.astype(float),
        "both": (took_high & took_low).astype(float),
        "inside": (~took_high & ~took_low).astype(float),
        "held_high": (took_high & (close > prev_high)).astype(float),
        "held_low": (took_low & (close < prev_low)).astype(float),
    }


def _statistic(u: dict) -> np.ndarray:
    th, tl = u["took_high"], u["took_low"]
    out = [
        th.mean(),
        tl.mean(),
        u["both"].mean(),
        u["inside"].mean(),
        u["held_high"].sum() / th.sum() if th.sum() else np.nan,
        u["held_low"].sum() / tl.sum() if tl.sum() else np.nan,
    ]
    if "mon_high" in u:
        with np.errstate(invalid="ignore"):
            out += [np.nanmean(u["mon_high"]), np.nanmean(u["mon_low"])]
    return np.array(out, dtype=float)


def _card(
    ctx, units, *, scope: str, block: int, recent: int, index: pd.DatetimeIndex, n_label: str, labels: list[str]
) -> EvidenceCard:
    result = evaluate(units, _statistic, block=block, reps=ctx.reps, seed=ctx.seed)
    tail = {k: v[-recent:] for k, v in units.items()}
    recent_values = _statistic(tail)
    n_items = [len(index)] * 4 + [int(units["took_high"].sum()), int(units["took_low"].sum())]
    if "mon_high" in units:
        n_items += [int(np.isfinite(units["mon_high"]).sum()), int(np.isfinite(units["mon_low"]).sum())]
    items = items_from_evaluation(labels, result, scale=PP, recent=recent_values, n_per_item=n_items)
    return EvidenceCard(
        id=f"{ctx.instrument.code}.levels.{scope}",
        instrument=ctx.instrument.code,
        family="levels",
        kind="base_rate",
        title=f"Prior {scope} high and low",
        question=f"How often does the {scope} trade through the prior {scope}'s high or low, and does the break hold?",
        unit="%",
        method=(
            f"Share of complete {n_label} with each outcome; conditional rates use only {n_label} that broke the level. "
            f"95% interval by circular block bootstrap ({block}-{n_label[:-1]} blocks); stability compares the first 70% "
            f"of the sample with the most recent 30%. 'Recent' covers the last {recent} {n_label}."
        ),
        control="Descriptive base rate (no null)",
        n_label=n_label,
        items=items,
        period=period_of(index),
    )


def daily_levels(ctx: StudyContext) -> EvidenceCard | None:
    if not ctx.has_daily_ohlc or len(ctx.daily) < 120:
        return None
    d = ctx.daily
    ok = consecutive_mask(d.index, crypto=ctx.is_crypto)
    prev = d.shift(1)
    sel = ok & prev["high"].notna().to_numpy()
    units = _indicators(
        d["high"].to_numpy()[sel],
        d["low"].to_numpy()[sel],
        d["close"].to_numpy()[sel],
        prev["high"].to_numpy()[sel],
        prev["low"].to_numpy()[sel],
    )
    return _card(
        ctx,
        units,
        scope="day",
        block=20,
        recent=365 if ctx.is_crypto else 252,
        index=d.index[sel],
        n_label="days",
        labels=LABELS,
    )


def _period_units(ctx: StudyContext, freq: str) -> tuple[dict, pd.DatetimeIndex] | None:
    d = ctx.daily
    min_days = (7 if freq == "W" else 28) if ctx.is_crypto else (4 if freq == "W" else 15)
    bars = period_bars(d, freq, min_days=min_days)
    if len(bars) < 24:
        return None
    periods = bars.index
    step_ok = np.concatenate(
        [[False], np.asarray([(b - a).n == 1 for a, b in zip(periods[:-1], periods[1:], strict=True)])]
    )
    prev = bars.shift(1)
    sel = step_ok
    units = _indicators(
        bars["high"].to_numpy()[sel],
        bars["low"].to_numpy()[sel],
        bars["close"].to_numpy()[sel],
        prev["high"].to_numpy()[sel],
        prev["low"].to_numpy()[sel],
    )
    if freq == "W":
        week = d.index.to_period("W-SUN")
        mon_high = np.full(len(bars), np.nan)
        mon_low = np.full(len(bars), np.nan)
        position = {p: i for i, p in enumerate(periods)}
        for p, g in d.groupby(week):
            i = position.get(p)
            if i is None or len(g) < 2 or g.index[0].dayofweek != 0:
                continue
            rest = g.iloc[1:]
            mon_high[i] = float(rest["high"].max() > g["high"].iloc[0])
            mon_low[i] = float(rest["low"].min() < g["low"].iloc[0])
        units["mon_high"] = mon_high[sel]
        units["mon_low"] = mon_low[sel]
    index = pd.DatetimeIndex([p.start_time for p in periods[sel]])
    return units, index


def weekly_levels(ctx: StudyContext) -> EvidenceCard | None:
    if not ctx.has_daily_ohlc:
        return None
    built = _period_units(ctx, "W")
    if built is None:
        return None
    units, index = built
    return _card(
        ctx, units, scope="week", block=8, recent=52, index=index, n_label="weeks", labels=LABELS + MONDAY_LABELS
    )


def monthly_levels(ctx: StudyContext) -> EvidenceCard | None:
    if not ctx.has_daily_ohlc:
        return None
    built = _period_units(ctx, "M")
    if built is None:
        return None
    units, index = built
    return _card(ctx, units, scope="month", block=6, recent=12, index=index, n_label="months", labels=LABELS)


def run(ctx: StudyContext) -> list[EvidenceCard]:
    cards = [daily_levels(ctx), weekly_levels(ctx), monthly_levels(ctx)]
    return [c for c in cards if c is not None]
