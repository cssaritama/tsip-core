"""Entry timing for long-term buyers: does a level-based limit order beat plain DCA?

Baseline: buy a fixed amount at the open of the first session of every month.
Rule: at the start of the month place a limit order at the prior month's
low. It fills at the limit on the first session that trades through it (at
the open if the session opens below the limit). If it never fills, buy at
the month's last close. The rule uses only information available before the
order is placed; there is no look-ahead.

Measured per purchase: price improvement versus the baseline (positive means
cheaper). Over the whole sample: extra shares accumulated with the same
monthly budget. Costs are identical for both (one purchase per month) and
excluded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.studies.common import StudyContext, period_of

PCT = 100.0


def build_months(daily: pd.DataFrame, *, min_days: int) -> dict[str, np.ndarray] | None:
    month = daily.index.to_period("M")
    groups = list(daily.groupby(month))
    rows = []
    for (prev_m, prev_g), (m, g) in zip(groups[:-1], groups[1:], strict=True):
        if (m - prev_m).n != 1 or len(prev_g) < min_days or len(g) < min_days:
            continue
        baseline = float(g["open"].iloc[0])
        limit = float(prev_g["low"].min())
        hit = np.flatnonzero(g["low"].to_numpy() <= limit)
        if hit.size:
            j = hit[0]
            fill = min(float(g["open"].iloc[j]), limit)
            filled = 1.0
        else:
            fill = float(g["close"].iloc[-1])
            filled = 0.0
        random_day = float(g["open"].mean())  # expected price of buying at a random session's open
        rows.append((m.start_time, baseline, fill, filled, random_day))
    if len(rows) < 36:
        return None
    return {
        "date": np.array([r[0] for r in rows], dtype="datetime64[ns]"),
        "baseline": np.array([r[1] for r in rows]),
        "fill": np.array([r[2] for r in rows]),
        "filled": np.array([r[3] for r in rows]),
        "random": np.array([r[4] for r in rows]),
    }


def _statistic(u: dict) -> np.ndarray:
    improvement = np.log(u["baseline"] / u["fill"])
    extra_shares = (1.0 / u["fill"]).sum() / (1.0 / u["baseline"]).sum() - 1.0
    return np.array([improvement.mean(), extra_shares])


def prior_month_low_limit(ctx: StudyContext) -> EvidenceCard | None:
    daily = ctx.daily_with_open
    if not ctx.has_daily_ohlc or daily is None or len(daily) < 750:
        return None
    months = build_months(daily, min_days=20 if ctx.is_crypto else 12)
    if months is None:
        return None
    result = evaluate(months, _statistic, block=6, reps=ctx.reps, seed=ctx.seed)
    items = items_from_evaluation(
        ["Average price improvement per purchase", "Extra units accumulated vs. plain DCA"], result, scale=PCT
    )
    fill_rate = float(months["filled"].mean() * PCT)
    random_improvement = float(np.log(months["baseline"] / months["random"]).mean() * PCT)
    for item in items:
        item.extra = {"fill_rate_pct": fill_rate, "random_day_improvement_pct": random_improvement}
    return EvidenceCard(
        id=f"{ctx.instrument.code}.entries.prior_month_low",
        instrument=ctx.instrument.code,
        family="entries",
        kind="edge",
        title="Smarter DCA: prior-month-low limit order",
        question="For a monthly buyer, does a limit order at last month's low beat buying on the first day of the month?",
        unit="%",
        method="Per-month price improvement (log) versus first-session open; months resampled in 6-month blocks.",
        control="Plain dollar-cost averaging at the first session open",
        n_label="months",
        items=items,
        period=period_of(pd.DatetimeIndex(months["date"])),
        notes=[
            "Unfilled months buy at the month's last close, which costs money in rising markets; the fill rate is reported.",
            "A random-session purchase is shown for context: in a rising market, waiting is usually worse than buying early.",
        ],
    )


def run(ctx: StudyContext) -> list[EvidenceCard]:
    card = prior_month_low_limit(ctx)
    return [card] if card else []
