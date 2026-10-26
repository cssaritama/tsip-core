"""Level memory: how often price trades through the prior period's high and low.

Base rates for days and for calendar periods (week, month, quarter, half-year and
year): the share of periods that trade above the prior high, below the prior low,
both or neither, and how often a break is still in place at the period close. For
weeks, also how often the Monday high and low are exceeded later in the week.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation, widen_proportions
from tsip.frames import HORIZON_NAMES, horizon_bars, period_bounds, period_key
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
# Bootstrap block length and "recent" window, both in periods.
HORIZON_SETTINGS = {"week": (8, 52), "month": (6, 12), "quarter": (4, 8), "half": (2, 4), "year": (2, 5)}
MIN_PERIODS = 8  # fewer complete periods: no card. Fewer than 30 are shown as insufficient.


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
    items = widen_proportions(items_from_evaluation(labels, result, scale=PP, recent=recent_values, n_per_item=n_items))
    notes = []
    if scope not in ("day", "week", "month"):
        notes.append(
            f"Long horizons have few observations: {len(index)} complete {n_label} here. "
            "Fewer than 30 are reported but not graded."
        )
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
            f"of the sample with the most recent 30%. 'Recent' covers the last {recent} {n_label}. Weeks run Monday "
            "to Sunday and half-years January–June and July–December; a period counts only once it is complete."
        ),
        control="Descriptive base rate (no null)",
        n_label=n_label,
        items=items,
        period=period_of(index),
        notes=notes,
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


def _monday_units(d: pd.DataFrame, keys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For each period key, whether the Monday high/low is exceeded later in the week (NaN if no Monday)."""
    mon_high = np.full(len(keys), np.nan)
    mon_low = np.full(len(keys), np.nan)
    position = {int(k): i for i, k in enumerate(keys)}
    for k, g in d.groupby(period_key(d.index, "week")):
        i = position.get(int(k))
        if i is None or len(g) < 2 or g.index[0].dayofweek != 0:
            continue
        rest = g.iloc[1:]
        mon_high[i] = float(rest["high"].max() > g["high"].iloc[0])
        mon_low[i] = float(rest["low"].min() < g["low"].iloc[0])
    return mon_high, mon_low


def horizon_units(ctx: StudyContext, horizon: str) -> tuple[dict, pd.DatetimeIndex] | None:
    """Indicator units for each complete period that directly follows a complete period."""
    d = ctx.daily
    bars = horizon_bars(d, horizon, crypto=ctx.is_crypto)
    if len(bars) < MIN_PERIODS + 1:
        return None
    keys = bars.index.to_numpy()
    sel = np.concatenate([[False], np.diff(keys) == 1])
    if sel.sum() < MIN_PERIODS:
        return None
    prev = bars.shift(1)
    units = _indicators(
        bars["high"].to_numpy(float)[sel],
        bars["low"].to_numpy(float)[sel],
        bars["close"].to_numpy(float)[sel],
        prev["high"].to_numpy(float)[sel],
        prev["low"].to_numpy(float)[sel],
    )
    if horizon == "week":
        mon_high, mon_low = _monday_units(d, keys)
        units["mon_high"] = mon_high[sel]
        units["mon_low"] = mon_low[sel]
    index = pd.DatetimeIndex([period_bounds(k, horizon)[0] for k in keys[sel]])
    return units, index


def horizon_levels(ctx: StudyContext, horizon: str) -> EvidenceCard | None:
    if not ctx.has_daily_ohlc:
        return None
    built = horizon_units(ctx, horizon)
    if built is None:
        return None
    units, index = built
    block, recent = HORIZON_SETTINGS[horizon]
    name = HORIZON_NAMES[horizon]
    labels = LABELS + MONDAY_LABELS if horizon == "week" else LABELS
    return _card(ctx, units, scope=name, block=block, recent=recent, index=index, n_label=f"{name}s", labels=labels)


def weekly_levels(ctx: StudyContext) -> EvidenceCard | None:
    return horizon_levels(ctx, "week")


def monthly_levels(ctx: StudyContext) -> EvidenceCard | None:
    return horizon_levels(ctx, "month")


def run(ctx: StudyContext) -> list[EvidenceCard]:
    cards = [daily_levels(ctx)] + [horizon_levels(ctx, h) for h in HORIZON_SETTINGS]
    return [c for c in cards if c is not None]
