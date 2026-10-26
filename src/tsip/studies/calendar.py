"""Calendar studies: day of week, month of year, turn of the month, weekends."""

from __future__ import annotations

import numpy as np

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.studies.common import MONTHS, WEEKDAYS, StudyContext, daily_log_returns, period_of

BPS = 1e4


def _group_difference(groups: list[int]):
    def statistic(u: dict) -> np.ndarray:
        r, g = u["r"], u["g"]
        out = []
        for value in groups:
            inside, outside = r[g == value], r[g != value]
            out.append(inside.mean() - outside.mean() if len(inside) and len(outside) else np.nan)
        return np.array(out)

    return statistic


def weekday_effect(ctx: StudyContext) -> EvidenceCard | None:
    if ctx.daily is None or len(ctx.daily) < 120:
        return None
    r = daily_log_returns(ctx.daily, crypto=ctx.is_crypto)
    days = list(range(7 if ctx.is_crypto else 5))
    g = r.index.dayofweek.to_numpy()
    units = {"r": r.to_numpy(), "g": g}
    result = evaluate(units, _group_difference(days), block=20, reps=ctx.reps, seed=ctx.seed)
    observed = np.array([r[g == d].mean() for d in days])
    items = items_from_evaluation(
        [WEEKDAYS[d] for d in days],
        result,
        scale=BPS,
        observed=observed,
        n_per_item=[int((g == d).sum()) for d in days],
    )
    return EvidenceCard(
        id=f"{ctx.instrument.code}.calendar.weekday",
        contrast="the other days",
        instrument=ctx.instrument.code,
        family="calendar",
        kind="edge",
        title="Day-of-week returns",
        question="Does any weekday return more or less than the other days?",
        unit="bps",
        method="Close-to-close log return of each day minus the mean of all other days; circular block bootstrap (20-day blocks).",
        control="Mean return of all other days",
        n_label="days",
        items=items,
        period=period_of(r.index),
    )


def month_effect(ctx: StudyContext) -> EvidenceCard | None:
    if ctx.daily is None or len(ctx.daily) < 400:
        return None
    month_close = ctx.daily["close"].groupby(ctx.daily.index.to_period("M")).last()
    r = np.log(month_close / month_close.shift(1)).dropna()
    months = list(range(1, 13))
    g = r.index.month.to_numpy()
    units = {"r": r.to_numpy(), "g": g}
    result = evaluate(units, _group_difference(months), block=3, reps=ctx.reps, seed=ctx.seed)
    observed = np.array([r[g == m].mean() if (g == m).any() else np.nan for m in months])
    items = items_from_evaluation(
        MONTHS, result, scale=BPS, observed=observed, n_per_item=[int((g == m).sum()) for m in months]
    )
    return EvidenceCard(
        id=f"{ctx.instrument.code}.calendar.month",
        contrast="the other months",
        instrument=ctx.instrument.code,
        family="calendar",
        kind="edge",
        title="Month-of-year returns",
        question="Is any calendar month systematically better or worse than the others?",
        unit="bps",
        method="Monthly log return minus the mean of all other months; block bootstrap (3-month blocks).",
        control="Mean return of all other months",
        n_label="months",
        items=items,
        period=period_of(r.index.to_timestamp()),
        notes=[
            "Each month contributes one observation per year; a decade gives about ten per month, which is rarely enough to grade."
        ],
    )


def turn_of_month_effect(ctx: StudyContext) -> EvidenceCard | None:
    if ctx.is_crypto or ctx.daily is None or len(ctx.daily) < 250:
        return None
    r = daily_log_returns(ctx.daily, crypto=False)
    month = r.index.to_period("M")
    pos_from_start = r.groupby(month).cumcount().to_numpy()
    pos_from_end = r[::-1].groupby(month[::-1]).cumcount()[::-1].to_numpy()
    tom = (pos_from_start < 3) | (pos_from_end == 0)
    units = {"r": r.to_numpy(), "g": tom.astype(int)}
    result = evaluate(units, _group_difference([1]), block=20, reps=ctx.reps, seed=ctx.seed)
    items = items_from_evaluation(
        ["Turn of month (last day + first 3 days)"],
        result,
        scale=BPS,
        observed=np.array([r[tom].mean()]),
        n_per_item=[int(tom.sum())],
    )
    return EvidenceCard(
        id=f"{ctx.instrument.code}.calendar.turn_of_month",
        contrast="other trading days",
        instrument=ctx.instrument.code,
        family="calendar",
        kind="edge",
        title="Turn-of-the-month effect",
        question="Do the last trading day and first three trading days of a month outperform the rest?",
        unit="bps",
        method="Mean daily log return inside the window minus outside it; block bootstrap (20-day blocks).",
        control="Mean return of all other trading days",
        n_label="days",
        items=items,
        period=period_of(r.index),
    )


def weekend_effect(ctx: StudyContext) -> EvidenceCard | None:
    if not ctx.is_crypto or ctx.daily is None or len(ctx.daily) < 120:
        return None
    r = daily_log_returns(ctx.daily, crypto=True)
    weekend = (r.index.dayofweek >= 5).astype(int)
    units = {"r": r.to_numpy(), "g": weekend}
    result = evaluate(units, _group_difference([1]), block=20, reps=ctx.reps, seed=ctx.seed)
    items = items_from_evaluation(
        ["Saturday and Sunday"],
        result,
        scale=BPS,
        observed=np.array([r[weekend == 1].mean()]),
        n_per_item=[int(weekend.sum())],
    )
    return EvidenceCard(
        id=f"{ctx.instrument.code}.calendar.weekend",
        contrast="weekdays",
        instrument=ctx.instrument.code,
        family="calendar",
        kind="edge",
        title="Weekend returns",
        question="Does Bitcoin behave differently on weekends, when traditional markets are closed?",
        unit="bps",
        method="Mean daily log return on Saturdays and Sundays minus weekdays; block bootstrap (20-day blocks).",
        control="Mean weekday return",
        n_label="days",
        items=items,
        period=period_of(r.index),
    )


def run(ctx: StudyContext) -> list[EvidenceCard]:
    cards = [weekday_effect(ctx), weekend_effect(ctx), turn_of_month_effect(ctx), month_effect(ctx)]
    return [c for c in cards if c is not None]
