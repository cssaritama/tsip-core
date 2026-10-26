"""Intraday and session studies.

* Hour-of-day (crypto) and half-hour slot (US cash session) returns.
* Session returns for crypto (Asia, London, New York, late US).
* Overnight versus intraday returns for US equities.
* Where the daily (and weekly) high and low form, compared with a
  random-walk baseline obtained by permuting each period's bars.

The permutation baseline matters: in a random walk the extremes of a period
are far more likely near its start and end (the arcsine law), so a raw
"the high of day usually forms in the first or last hour" says little by
itself. Each bar keeps its own return and intrabar range; only its position
in the period is shuffled.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.frames import CRYPTO_SESSION_LABELS, CRYPTO_SESSIONS, crypto_session_labels, path_units
from tsip.studies.common import WEEKDAYS, StudyContext, consecutive_mask, period_of

BPS = 1e4
PP = 100.0
N_PERMUTATIONS = 200
RTH_SLOTS = [f"{h:02d}:{m:02d}" for h in range(9, 16) for m in (0, 30)][1:]  # 09:30 … 15:30
RTH_GROUPS = {
    "Opening hour (09:30–10:30)": ["09:30", "10:00"],
    "Midday (10:30–15:00)": [s for s in RTH_SLOTS if "10:30" <= s < "15:00"],
    "Closing hour (15:00–16:00)": ["15:00", "15:30"],
}


# --------------------------------------------------------------------------- helpers
def _extreme_slots(ret: np.ndarray, hi: np.ndarray, lo: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    zeros = np.zeros(ret.shape[:-1] + (1,))
    level = np.concatenate([zeros, np.cumsum(ret, axis=-1)[..., :-1]], axis=-1)
    return (level + hi).argmax(axis=-1), (level + lo).argmin(axis=-1)


def extreme_timing_units(
    ret: np.ndarray,
    hi: np.ndarray,
    lo: np.ndarray,
    slot_groups: np.ndarray,
    n_groups: int,
    *,
    n_perm: int = N_PERMUTATIONS,
    seed: int = 0,
    chunk: int = 250,
) -> dict[str, np.ndarray]:
    """Observed group of each period's high/low and its permutation baseline."""
    n, k = ret.shape
    rng = np.random.default_rng(seed)
    obs_hi_slot, obs_lo_slot = _extreme_slots(ret, hi, lo)
    rows = np.arange(n)
    obs_hi = np.eye(n_groups)[slot_groups[rows, obs_hi_slot]]
    obs_lo = np.eye(n_groups)[slot_groups[rows, obs_lo_slot]]
    base_hi = np.zeros((n, n_groups))
    base_lo = np.zeros((n, n_groups))
    for start in range(0, n, chunk):
        sl = slice(start, min(n, start + chunk))
        m = sl.stop - sl.start
        perm = np.argsort(rng.random((m, n_perm, k)), axis=2)
        r = np.take_along_axis(ret[sl][:, None, :], perm, axis=2)
        h = np.take_along_axis(hi[sl][:, None, :], perm, axis=2)
        lw = np.take_along_axis(lo[sl][:, None, :], perm, axis=2)
        hs, ls = _extreme_slots(r, h, lw)
        groups = slot_groups[sl]
        g_hi = np.take_along_axis(groups, hs, axis=1)
        g_lo = np.take_along_axis(groups, ls, axis=1)
        for g in range(n_groups):
            base_hi[sl, g] = (g_hi == g).mean(axis=1)
            base_lo[sl, g] = (g_lo == g).mean(axis=1)
    return {"obs_hi": obs_hi, "base_hi": base_hi, "obs_lo": obs_lo, "base_lo": base_lo}


def _share_difference(obs_key: str, base_key: str):
    def statistic(u: dict) -> np.ndarray:
        return u[obs_key].mean(axis=0) - u[base_key].mean(axis=0)

    return statistic


def _relative_slot_mean(u: dict) -> np.ndarray:
    ret = u["ret"]
    return ret.mean(axis=0) - ret.mean()


def _crypto_day_units(ctx: StudyContext):
    bars = ctx.intraday
    if bars is None or len(bars) < 24 * 120:
        return None
    day = bars.index.tz_convert("UTC").tz_localize(None).normalize()
    hour = bars.index.hour
    units = path_units(bars, day, hour, list(range(24)))
    if len(units["periods"]) < 120:
        return None
    stamps = pd.DatetimeIndex(units["periods"]).tz_localize("UTC").values[:, None] + np.arange(24) * np.timedelta64(
        1, "h"
    )
    labels = crypto_session_labels(pd.DatetimeIndex(stamps.ravel()).tz_localize("UTC")).reshape(-1, 24)
    code = {name: i for i, name in enumerate(CRYPTO_SESSIONS)}
    units["session"] = np.vectorize(code.get)(labels).astype(int)
    return units


def _rth_day_units(ctx: StudyContext):
    rth = ctx.rth_bars
    if rth is None or len(rth) == 0:
        return None
    units = path_units(rth, rth["date"], rth["slot"], RTH_SLOTS)
    if len(units["periods"]) < 60:
        return None
    return units


# --------------------------------------------------------------------------- studies
def hour_of_day_effect(ctx: StudyContext) -> EvidenceCard | None:
    if not ctx.is_crypto:
        return None
    units = _crypto_day_units(ctx)
    if units is None:
        return None
    result = evaluate({"ret": units["ret"]}, _relative_slot_mean, block=10, reps=ctx.reps, seed=ctx.seed)
    labels = [f"{h:02d}:00 UTC" for h in range(24)]
    items = items_from_evaluation(labels, result, scale=BPS, observed=units["ret"].mean(axis=0))
    return EvidenceCard(
        id=f"{ctx.instrument.code}.intraday.hour",
        contrast="the average hour",
        instrument=ctx.instrument.code,
        family="intraday",
        kind="edge",
        title="Hour-of-day returns",
        question="Are some hours of the day systematically stronger or weaker?",
        unit="bps",
        method="Mean log return of each UTC hour minus the mean of all hours; days resampled in 10-day blocks.",
        control="Average hourly return",
        n_label="days",
        items=items,
        period=period_of(pd.DatetimeIndex(units["periods"])),
    )


def rth_slot_effect(ctx: StudyContext) -> EvidenceCard | None:
    if ctx.is_crypto:
        return None
    units = _rth_day_units(ctx)
    if units is None:
        return None
    result = evaluate({"ret": units["ret"]}, _relative_slot_mean, block=10, reps=ctx.reps, seed=ctx.seed)
    items = items_from_evaluation([f"{s} ET" for s in RTH_SLOTS], result, scale=BPS, observed=units["ret"].mean(axis=0))
    return EvidenceCard(
        id=f"{ctx.instrument.code}.intraday.halfhour",
        contrast="the average half-hour",
        instrument=ctx.instrument.code,
        family="intraday",
        kind="edge",
        title="Half-hour returns in the cash session",
        question="Are some half-hours of the US cash session systematically stronger or weaker?",
        unit="bps",
        method="Mean log return of each 30-minute bar (first bar from the 09:30 open) minus the mean of all bars; days in 10-day blocks.",
        control="Average half-hour return",
        n_label="days",
        items=items,
        period=period_of(pd.DatetimeIndex(units["periods"])),
    )


def session_return_effect(ctx: StudyContext) -> EvidenceCard | None:
    if not ctx.is_crypto:
        return None
    units = _crypto_day_units(ctx)
    if units is None:
        return None
    ret, session = units["ret"], units["session"]
    daily = ret.sum(axis=1)
    excess = np.zeros((len(ret), len(CRYPTO_SESSIONS)))
    raw = np.zeros_like(excess)
    for g in range(len(CRYPTO_SESSIONS)):
        mask = session == g
        raw[:, g] = np.where(mask, ret, 0.0).sum(axis=1)
        excess[:, g] = raw[:, g] - mask.sum(axis=1) / 24 * daily
    result = evaluate({"x": excess}, lambda u: u["x"].mean(axis=0), block=10, reps=ctx.reps, seed=ctx.seed)
    items = items_from_evaluation(
        [CRYPTO_SESSION_LABELS[s] for s in CRYPTO_SESSIONS], result, scale=BPS, observed=raw.mean(axis=0)
    )
    return EvidenceCard(
        id=f"{ctx.instrument.code}.intraday.sessions",
        contrast="its share of the clock",
        instrument=ctx.instrument.code,
        family="sessions",
        kind="edge",
        title="Session returns",
        question="Does any trading session capture more of the daily move than its share of the clock?",
        unit="bps",
        method="Session log return minus (session hours / 24) × day's return; daylight saving handled per date; 10-day blocks.",
        control="Time-proportional share of the daily return",
        n_label="days",
        items=items,
        period=period_of(pd.DatetimeIndex(units["periods"])),
    )


def overnight_intraday(ctx: StudyContext) -> EvidenceCard | None:
    if ctx.is_crypto or not ctx.has_daily_ohlc or len(ctx.daily) < 250:
        return None
    d = ctx.daily
    ok = consecutive_mask(d.index, crypto=False)
    overnight = np.log(d["open"] / d["close"].shift(1)).to_numpy()[ok]
    intraday = np.log(d["close"] / d["open"]).to_numpy()[ok]
    units = {"on": overnight, "in": intraday}

    def statistic(u: dict) -> np.ndarray:
        return np.array([u["on"].mean(), u["in"].mean(), u["on"].mean() - u["in"].mean()])

    result = evaluate(units, statistic, block=20, reps=ctx.reps, seed=ctx.seed)
    items = items_from_evaluation(
        ["Overnight (prior close → open)", "Intraday (open → close)", "Overnight minus intraday"], result, scale=BPS
    )
    years = len(overnight) / 252
    for item, leg in zip(items[:2], (overnight, intraday), strict=True):
        item.extra = {
            "cumulative_return_pct": float(np.expm1(leg.sum()) * 100),
            "annualised_return_pct": float(np.expm1(leg.sum() / years) * 100),
        }
    return EvidenceCard(
        id=f"{ctx.instrument.code}.intraday.overnight",
        contrast="zero",
        instrument=ctx.instrument.code,
        family="intraday",
        kind="edge",
        title="Overnight versus intraday returns",
        question="Is the return earned while the market is closed different from the return earned while it is open?",
        unit="bps",
        method="Mean daily log return of each leg (null: zero) and their difference; 20-day blocks.",
        control="Zero (and each other)",
        n_label="days",
        items=items,
        period=period_of(d.index[ok]),
        notes=["Cumulative figures ignore costs and taxes; holding only one leg requires two trades per day."],
    )


def _extreme_cards(
    ctx,
    units,
    groups: np.ndarray,
    labels: list[str],
    *,
    scope: str,
    family: str,
    block: int,
    period_index: pd.DatetimeIndex,
    unit_label: str,
) -> list[EvidenceCard]:
    timing = extreme_timing_units(units["ret"], units["hi"], units["lo"], groups, len(labels), seed=ctx.seed)
    cards = []
    for side, key in (("high", "hi"), ("low", "lo")):
        u = {"obs": timing[f"obs_{key}"], "base": timing[f"base_{key}"]}
        result = evaluate(u, _share_difference("obs", "base"), block=block, reps=ctx.reps, seed=ctx.seed)
        items = items_from_evaluation(
            labels, result, scale=PP, observed=u["obs"].mean(axis=0), baseline=u["base"].mean(axis=0)
        )
        cards.append(
            EvidenceCard(
                id=f"{ctx.instrument.code}.{family}.{scope}_{side}",
                contrast="a random walk",
                instrument=ctx.instrument.code,
                family=family,
                kind="edge",
                title=f"Where the {scope} {side} forms",
                question=f"In which part of the {scope} does the {scope} {side} form, compared with a random walk?",
                unit="pp",
                method=(
                    f"Share of {unit_label} whose {side} forms in each window minus the share expected when the "
                    f"{unit_label[:-1]}'s bars are randomly reordered ({N_PERMUTATIONS} permutations); {block}-unit blocks."
                ),
                control="Random-walk baseline (bars permuted within each period)",
                n_label=unit_label,
                items=items,
                period=period_of(period_index),
            )
        )
    return cards


def daily_extremes(ctx: StudyContext) -> list[EvidenceCard]:
    if ctx.is_crypto:
        units = _crypto_day_units(ctx)
        if units is None:
            return []
        labels = [CRYPTO_SESSION_LABELS[s] for s in CRYPTO_SESSIONS]
        groups = units["session"]
    else:
        units = _rth_day_units(ctx)
        if units is None:
            return []
        labels = list(RTH_GROUPS)
        slot_group = np.array([next(i for i, s in enumerate(RTH_GROUPS.values()) if slot in s) for slot in RTH_SLOTS])
        groups = np.tile(slot_group, (len(units["periods"]), 1))
    return _extreme_cards(
        ctx,
        units,
        groups,
        labels,
        scope="day",
        family="sessions",
        block=10,
        period_index=pd.DatetimeIndex(units["periods"]),
        unit_label="days",
    )


def weekly_extremes(ctx: StudyContext) -> list[EvidenceCard]:
    if not ctx.has_daily_ohlc:
        return []
    d = ctx.daily
    n_days = 7 if ctx.is_crypto else 5
    week = d.index.to_period("W-SUN")
    units = path_units(d, week, d.index.dayofweek, list(range(n_days)))
    if len(units["periods"]) < 52:
        return []
    groups = np.tile(np.arange(n_days), (len(units["periods"]), 1))
    period_index = pd.DatetimeIndex([p.start_time for p in units["periods"]])
    return _extreme_cards(
        ctx,
        units,
        groups,
        WEEKDAYS[:n_days],
        scope="week",
        family="weekly",
        block=8,
        period_index=period_index,
        unit_label="weeks",
    )


def run(ctx: StudyContext) -> list[EvidenceCard]:
    cards: list[EvidenceCard] = []
    for study in (hour_of_day_effect, rth_slot_effect, session_return_effect, overnight_intraday):
        card = study(ctx)
        if card is not None:
            cards.append(card)
    cards.extend(daily_extremes(ctx))
    cards.extend(weekly_extremes(ctx))
    return cards
