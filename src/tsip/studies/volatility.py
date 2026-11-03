"""Volatility clock: when price moves most (time axis).

Direction is hard to predict; the size of moves is not. Volatility follows the clock: within the day
(the opening and closing of a session move more than its middle), across the week (a Monday close-to-close
return spans a weekend), and across the year. These studies measure how much price moves at each time
coordinate against the average one, so a trader can size stops and positions and choose when to act.

Measures
    Intraday slots (UTC hours for crypto, cash-session half-hours for US ETFs): the range of each bar,
    ``log(high / low)``, a direct measure of how far price travels inside the slot.
    Days: the absolute close-to-close log return. It is available for close-only series too, so long
    index histories (NDX from 1986) contribute. Where daily highs and lows exist, the average true range
    is reported alongside as the typical daily range.

Statistic
    Relative difference of each group's mean from the mean over all groups (or all days), in percent:
    +25% means price moves a quarter more than at an average coordinate. Days are resampled in circular
    blocks (20 sessions) to respect volatility clustering; intraday units are days resampled in 10-day
    blocks. Under constant volatility every estimate is zero (random-walk test).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.studies.common import MONTHS, WEEKDAYS, StudyContext, daily_log_returns, period_of
from tsip.studies.intraday import RTH_SLOTS, _crypto_day_units, _rth_day_units

PP = 100.0
WEEK_OF_MONTH = ["Days 1–7", "Days 8–14", "Days 15–21", "Days 22–28", "Days 29–31"]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]


def _relative_group_mean(groups: list[int]):
    def statistic(u: dict) -> np.ndarray:
        v, g = u["v"], u["g"]
        overall = v.mean()
        return np.array([v[g == k].mean() / overall - 1.0 if (g == k).any() else np.nan for k in groups])

    return statistic


def _relative_slot_range(u: dict) -> np.ndarray:
    r = u["range"]
    return r.mean(axis=0) / r.mean() - 1.0


def _true_range_pct(daily: pd.DataFrame) -> pd.Series | None:
    if daily.attrs.get("close_only") or daily[["high", "low"]].isna().any().any():
        return None
    prev = daily["close"].shift(1)
    tr = pd.concat([daily["high"] - daily["low"], (daily["high"] - prev).abs(), (daily["low"] - prev).abs()], axis=1)
    return (tr.max(axis=1) / prev * PP).dropna()


def _daily_card(
    ctx: StudyContext, *, key: str, title: str, question: str, labels: list[str], grouper, notes
) -> EvidenceCard | None:
    if ctx.daily is None or len(ctx.daily) < 250:
        return None
    r = daily_log_returns(ctx.daily, crypto=ctx.is_crypto)
    v = r.abs()
    g = grouper(r.index)
    present = [k for k in range(len(labels)) if (g == k).sum() >= 20]
    if len(present) < 2:
        return None
    units = {"v": v.to_numpy(), "g": g}
    result = evaluate(units, _relative_group_mean(present), block=20, reps=ctx.reps, seed=ctx.seed + len(key))
    typical = np.array([v.to_numpy()[g == k].mean() for k in present])
    items = items_from_evaluation(
        [labels[k] for k in present],
        result,
        scale=PP,
        observed=typical,  # mean absolute daily move, as a fraction (scaled to percent)
        baseline=np.full(len(present), v.mean()),
        n_per_item=[int((g == k).sum()) for k in present],
    )
    tr = _true_range_pct(ctx.daily)
    for k, item in zip(present, items, strict=True):
        item.extra = {
            "typical_move_pct": float(v.to_numpy()[g == k].mean() * PP),
            "average_move_pct": float(v.mean() * PP),
        }
        if tr is not None:
            gtr = grouper(tr.index)
            if (gtr == k).any():
                item.extra["typical_range_pct"] = float(tr.to_numpy()[gtr == k].mean())
    unit_word = "days" if ctx.is_crypto else "sessions"
    return EvidenceCard(
        id=f"{ctx.instrument.code}.volatility.{key}",
        instrument=ctx.instrument.code,
        family="volatility",
        kind="edge",
        title=title,
        question=question,
        unit="%",
        method=(
            "Mean absolute close-to-close log return of each group relative to the mean over all "
            f"{unit_word} (+25% = moves a quarter more than an average {unit_word[:-1]}); circular block bootstrap "
            "with 20-session blocks to respect volatility clustering. The typical move and, where highs and lows "
            "exist, the average true range of each group are listed in the numbers table."
        ),
        control=f"The average {unit_word[:-1]}",
        n_label=unit_word,
        items=items,
        period=period_of(r.index),
        contrast=f"the average {unit_word[:-1]}",
        notes=notes,
    )


def weekday_volatility(ctx: StudyContext) -> EvidenceCard | None:
    days = 7 if ctx.is_crypto else 5
    notes = (
        []
        if ctx.is_crypto
        else ["A Monday close-to-close move spans the weekend, so part of its size is weekend news."]
    )
    return _daily_card(
        ctx,
        key="weekday",
        title="Which weekday moves most",
        question="How much more or less does price move on each weekday than on an average day?",
        labels=WEEKDAYS[:days],
        grouper=lambda idx: idx.dayofweek.to_numpy(),
        notes=notes,
    )


def week_of_month_volatility(ctx: StudyContext) -> EvidenceCard | None:
    return _daily_card(
        ctx,
        key="week_of_month",
        title="Which week of the month moves most",
        question="How much more or less does price move in each week of the month than on an average day?",
        labels=WEEK_OF_MONTH,
        grouper=lambda idx: np.minimum((idx.day.to_numpy() - 1) // 7, 4),
        notes=["Weeks are calendar-day blocks of the month (1–7, 8–14, …), so they align with monthly events."],
    )


def month_volatility(ctx: StudyContext) -> EvidenceCard | None:
    return _daily_card(
        ctx,
        key="month",
        title="Which month moves most",
        question="How much more or less does price move in each calendar month than on an average day?",
        labels=MONTHS,
        grouper=lambda idx: idx.month.to_numpy() - 1,
        notes=[
            "Crises cluster in a few months (for example October 2008, March 2020); the recent-sample check shows "
            "whether a month is volatile every year or only in a few of them."
        ],
    )


def quarter_volatility(ctx: StudyContext) -> EvidenceCard | None:
    return _daily_card(
        ctx,
        key="quarter",
        title="Which quarter moves most",
        question="How much more or less does price move in each quarter of the year than on an average day?",
        labels=QUARTERS,
        grouper=lambda idx: (idx.month.to_numpy() - 1) // 3,
        notes=[],
    )


def intraday_volatility(ctx: StudyContext) -> EvidenceCard | None:
    if ctx.is_crypto:
        units = _crypto_day_units(ctx)
        labels = [f"{h:02d}:00 UTC" for h in range(24)]
        name, key = "hour", "hour"
    else:
        units = _rth_day_units(ctx)
        labels = [f"{s} ET" for s in RTH_SLOTS]
        name, key = "half-hour", "halfhour"
    if units is None:
        return None
    rng = units["hi"] - units["lo"]  # log(high / low) of each bar
    if not np.isfinite(rng).all():
        rng = np.where(np.isfinite(rng), rng, np.nanmean(rng))
    result = evaluate({"range": rng}, _relative_slot_range, block=10, reps=ctx.reps, seed=ctx.seed + 7)
    typical = rng.mean(axis=0)
    items = items_from_evaluation(labels, result, scale=PP, observed=typical, baseline=np.full(len(labels), rng.mean()))
    for j, item in enumerate(items):
        item.extra = {"typical_range_pct": float(typical[j] * PP), "average_range_pct": float(rng.mean() * PP)}
    return EvidenceCard(
        id=f"{ctx.instrument.code}.volatility.{key}",
        instrument=ctx.instrument.code,
        family="volatility",
        kind="edge",
        title=f"Which {name} moves most",
        question=f"How much more or less does price travel in each {name} than in an average {name}?",
        unit="%",
        method=(
            f"Mean high-to-low range of each {name} bar, log(high / low), relative to the mean over all {name}s; "
            "days resampled in 10-day blocks."
        ),
        control=f"The average {name}",
        n_label="days",
        items=items,
        period=period_of(pd.DatetimeIndex(units["periods"])),
        contrast=f"the average {name}",
        notes=["Useful for timing entries and exits and for sizing stops; it says nothing about direction."],
    )


def run(ctx: StudyContext) -> list[EvidenceCard]:
    cards = [
        intraday_volatility(ctx),
        weekday_volatility(ctx),
        week_of_month_volatility(ctx),
        month_volatility(ctx),
        quarter_volatility(ctx),
    ]
    return [c for c in cards if c is not None]
