"""Prior-week range: which side breaks first, against a geometry-matched control.

Event: the first daily close of a week that lies strictly inside the prior
complete week's range [low, high]. Levels are frozen at that close; the path
starts at the next session's open.

Outcome within *h* sessions: ``upper`` (high side reached first), ``lower``,
``ambiguous`` (both reached inside one daily bar from an inside open; the
order is unknown without intraday data) or ``none``. An open beyond a level
resolves the order at the open (a gap, not a fill at the level).

Naive statistics overstate how informative the levels are, because an event
whose close sits near the top of the range is mechanically more likely to
reach the top first. For every event the control places
bands of the same width around the same close, at relative positions drawn
symmetrically around the event's own position, and follows the same future
path. The difference isolates what the actual prior-week levels add beyond
geometry.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.frames import period_bars
from tsip.studies.common import StudyContext, consecutive_mask, period_of

PP = 100.0
N_CONTROLS = 20
MATCH_WINDOW = 0.10  # controls sit within ±10% of the range width of the event's position
UP, DOWN, AMBIGUOUS, NONE = 1, -1, 2, 0


def first_passage(o: np.ndarray, h: np.ndarray, lo: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """Outcome for each band (rows of ``lower``/``upper``) along one future path.

    ``o, h, lo`` are 1-D arrays over future sessions; ``lower``/``upper`` are
    1-D arrays of band edges. Returns an array of outcome codes.
    """
    lower = lower[:, None]
    upper = upper[:, None]
    gap_up = o[None, :] >= upper
    gap_down = o[None, :] <= lower
    touch_up = h[None, :] >= upper
    touch_down = lo[None, :] <= lower
    any_event = gap_up | gap_down | touch_up | touch_down
    has = any_event.any(axis=1)
    first = any_event.argmax(axis=1)
    rows = np.arange(len(first))
    gu, gd = gap_up[rows, first], gap_down[rows, first]
    tu, td = touch_up[rows, first], touch_down[rows, first]
    out = np.full(len(first), NONE)
    out[has & gu] = UP
    out[has & ~gu & gd] = DOWN
    inside_open = has & ~gu & ~gd
    out[inside_open & tu & td] = AMBIGUOUS
    out[inside_open & tu & ~td] = UP
    out[inside_open & ~tu & td] = DOWN
    return out


def build_events(daily: pd.DataFrame, *, crypto: bool, horizon: int, seed: int) -> dict[str, np.ndarray] | None:
    min_days = 7 if crypto else 4
    weeks = period_bars(daily, "W", min_days=min_days)
    if len(weeks) < 30:
        return None
    week_of_day = daily.index.to_period("W-SUN")
    consecutive = consecutive_mask(daily.index, crypto=crypto)
    o, h, lo, c = (daily[col].to_numpy(float) for col in ("open", "high", "low", "close"))
    n_days = len(daily)
    rng = np.random.default_rng(seed)
    records = []
    week_index = {p: i for i, p in enumerate(weeks.index)}
    day_positions = pd.Series(np.arange(n_days), index=daily.index).groupby(week_of_day)
    for week, positions in day_positions:
        i = week_index.get(week)
        if i is None or i == 0 or (weeks.index[i] - weeks.index[i - 1]).n != 1:
            continue
        low_ref, high_ref = weeks["low"].iloc[i - 1], weeks["high"].iloc[i - 1]
        inside = [p for p in positions.to_numpy() if low_ref < c[p] < high_ref]
        if not inside:
            continue
        t = inside[0]
        future = np.arange(t + 1, t + 1 + horizon)
        if future[-1] >= n_days or not consecutive[future].all():
            continue  # incomplete horizon or a data gap: excluded, never filled
        width = high_ref - low_ref
        position = (c[t] - low_ref) / width
        half = min(MATCH_WINDOW, position, 1.0 - position)
        q = position + half * rng.uniform(-1.0, 1.0, N_CONTROLS)  # symmetric around the event's position
        ctrl_low = c[t] - q * width
        ctrl_high = ctrl_low + width
        actual = first_passage(o[future], h[future], lo[future], np.array([low_ref]), np.array([high_ref]))[0]
        control = first_passage(o[future], h[future], lo[future], ctrl_low, ctrl_high)
        records.append((daily.index[t], position, actual, q, control))
    if len(records) < 30:
        return None
    return {
        "date": np.array([r[0] for r in records], dtype="datetime64[ns]"),
        "pos": np.array([r[1] for r in records]),
        "actual": np.array([r[2] for r in records]),
        "ctrl_pos": np.vstack([r[3] for r in records]),
        "ctrl": np.vstack([r[4] for r in records]),
    }


def geometry_expected(ctrl_up: np.ndarray) -> np.ndarray:
    """Upper-first probability expected from geometry alone, per event.

    Each event has its own controls, placed symmetrically around its relative
    position (the window narrows near the edges so it stays symmetric). To
    first order the controls therefore share the event's geometry exactly.
    """
    return ctrl_up.mean(axis=1)


def _statistic(u: dict) -> np.ndarray:
    actual_up = (u["actual"] == UP).astype(float)
    ctrl_up = (u["ctrl"] == UP).astype(float)
    return np.array([actual_up.mean() - geometry_expected(ctrl_up).mean()])


def prior_week_first_passage(ctx: StudyContext) -> EvidenceCard | None:
    if not ctx.has_daily_ohlc or len(ctx.daily) < 400:
        return None
    items = []
    horizons = (5, 10)
    built_any = None
    for idx, horizon in enumerate(horizons):
        events = build_events(ctx.daily, crypto=ctx.is_crypto, horizon=horizon, seed=ctx.seed + horizon)
        if events is None:
            continue
        built_any = events
        result = evaluate(events, _statistic, block=8, reps=ctx.reps, seed=ctx.seed + idx)
        actual_up = (events["actual"] == UP).astype(float)
        ctrl_up = (events["ctrl"] == UP).astype(float)
        expected = geometry_expected(ctrl_up)
        item = items_from_evaluation(
            [f"{horizon} sessions"],
            result,
            scale=PP,
            observed=np.array([actual_up.mean()]),
            baseline=np.array([expected.mean()]),
        )[0]
        item.extra = {
            "naive_upper_first_pct": float(actual_up.mean() * PP),
            "geometry_expected_pct": float(expected.mean() * PP),
            "lower_first_pct": float((events["actual"] == DOWN).mean() * PP),
            "ambiguous_pct": float((events["actual"] == AMBIGUOUS).mean() * PP),
            "unresolved_pct": float((events["actual"] == NONE).mean() * PP),
            "mean_close_position_pct": float(events["pos"].mean() * PP),
        }
        items.append(item)
    if not items:
        return None
    return EvidenceCard(
        id=f"{ctx.instrument.code}.paths.prior_week",
        instrument=ctx.instrument.code,
        family="paths",
        kind="edge",
        title="Prior-week range: which side breaks first",
        question="When price closes back inside last week's range, is the high side reached first more often than geometry alone explains?",
        unit="pp",
        method=(
            f"Upper-first rate of actual events minus that of {N_CONTROLS} control bands per event with the same width, "
            "placed symmetrically within ±10% of the range around the event's own relative position; events resampled "
            "in 8-week blocks."
        ),
        control="Geometry-matched control bands on the same future path",
        n_label="weeks",
        items=items,
        period=period_of(pd.DatetimeIndex(built_any["date"])),
        notes=[
            "The naive rate is shown for comparison; it mixes the information in the levels with the mechanical effect of where the close sits.",
            "Ambiguous outcomes need intraday data to resolve and are not counted as upper-first.",
        ],
    )


def run(ctx: StudyContext) -> list[EvidenceCard]:
    card = prior_week_first_passage(ctx)
    return [card] if card else []
