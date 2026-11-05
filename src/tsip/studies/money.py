"""Money terms: what past periods in the same place did from the same point to the period's end.

For each period in progress (week, month, quarter) after k sessions, the analogs are past complete
periods observed after the same k sessions. From the session after k to the period's last session,
the study measures how far price travelled above and below the close of session k, and where it
ended, in multiples of the 14-session ATR known at the start of the period. Specification:
``specs/0001-money-terms.md``.

The yardstick is fixed at the start of the period on purpose: the state (prior high or low already
traded) depends on the current period's own ranges, so scaling by today's ATR would shrink the
excursions of wide periods mechanically. Under a random walk every graded difference is zero.

The control is every past period at the same point (specification 0006): the comparison a trader makes is
with what happens anyway, not with the periods in the opposite state, which would make every difference look
larger by the share of the other states in the pool.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.frames import HORIZON_NAMES, horizon_bars, period_key, period_label
from tsip.studies.common import StudyContext, period_of
from tsip.studies.level_map import current_state

PP = 100.0
HORIZONS = ("week", "month", "quarter")
BLOCK = {"week": 8, "month": 6, "quarter": 4}
ATR_WINDOW = 14
THRESHOLDS = (1.0, 2.0)
# Changes to the period's end, in ATR at the start of the period, at which the share of past periods beyond
# each is published, so that the page can apply the reader's trading cost converted with the current period's
# own yardstick (specification 0003). In ATR, past periods of high and low volatility are comparable; in
# percent, the share beyond a fixed cost would depend on how volatile the past was. Grades use none.
NET_THRESHOLDS_ATR = (
    *(round(0.025 * i, 3) for i in range(21)),  # 0 to 0.5 ATR, where trading costs fall
    *(round(0.5 + 0.05 * i, 2) for i in range(1, 11)),  # 0.55 to 1 ATR
    1.25,
    1.5,
    1.75,
    2.0,
    2.5,
    3.0,
)
ITEMS = (
    ("up_1", "Reached 1 ATR above the close before the {h} ended"),
    ("down_1", "Reached 1 ATR below the close before the {h} ended"),
    ("up_2", "Reached 2 ATR above the close before the {h} ended"),
    ("down_2", "Reached 2 ATR below the close before the {h} ended"),
    ("end_up", "Ended the {h} above the close"),
    ("end_down", "Ended the {h} below the close"),
)
EXCURSIONS = ("up_atr", "down_atr", "net_atr", "up_pct", "down_pct", "net_pct")


def atr_percent(daily: pd.DataFrame, window: int = ATR_WINDOW) -> np.ndarray:
    """14-session ATR as a percentage of each session's close, using only that session and earlier ones."""
    h, lo, c = (daily[col].astype(float) for col in ("high", "low", "close"))
    prev = c.shift(1)
    tr = pd.concat([h - lo, (h - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)
    return (tr.rolling(window, min_periods=window).mean() / c * PP).to_numpy(float)


def money_events(daily: pd.DataFrame, horizon: str, *, crypto: bool, sessions: int) -> pd.DataFrame:
    """One row per complete period that follows a complete period and lasts longer than ``sessions``."""
    bars = horizon_bars(daily, horizon, crypto=crypto)
    keys = period_key(daily.index, horizon)
    high, low, close = (daily[col].to_numpy(float) for col in ("high", "low", "close"))
    atr = atr_percent(daily)
    complete = {int(k) for k in bars.index}
    starts = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
    ends = np.r_[starts[1:], len(keys)]
    rows = []
    for start, end in zip(starts, ends, strict=True):
        key = int(keys[start])
        if key not in complete or key - 1 not in complete or start == 0:
            continue
        if end - start <= sessions:
            continue
        yardstick = atr[start - 1]
        if not np.isfinite(yardstick) or yardstick <= 0:
            continue
        prior = bars.loc[key - 1]
        stop = start + sessions  # first session after the observation point
        ref = close[stop - 1]
        up = (high[stop:end].max() / ref - 1.0) * PP
        down = (1.0 - low[stop:end].min() / ref) * PP
        net = (close[end - 1] / ref - 1.0) * PP
        rows.append(
            {
                "key": key,
                "start": daily.index[start],
                "broke_high_so_far": bool(high[start:stop].max() > float(prior["high"])),
                "broke_low_so_far": bool(low[start:stop].min() < float(prior["low"])),
                "up_pct": up,
                "down_pct": down,
                "net_pct": net,
                "up_atr": up / yardstick,
                "down_atr": down / yardstick,
                "net_atr": net / yardstick,
                "up_1": float(up / yardstick >= THRESHOLDS[0]),
                "down_1": float(down / yardstick >= THRESHOLDS[0]),
                "up_2": float(up / yardstick >= THRESHOLDS[1]),
                "down_2": float(down / yardstick >= THRESHOLDS[1]),
                "end_up": float(net > 0.0),
                "end_down": float(net < 0.0),
            }
        )
    return pd.DataFrame(rows)


def _summary(frame: pd.DataFrame) -> dict:
    out = {}
    for col in EXCURSIONS:
        values = frame[col].to_numpy(float) if len(frame) else np.array([])
        if len(values):
            q1, med, q3 = np.percentile(values, [25, 50, 75])
            out[col] = {"q1": round(float(q1), 3), "median": round(float(med), 3), "q3": round(float(q3), 3)}
    return out


def _net_thresholds(frame: pd.DataFrame) -> dict:
    """Share of periods (percent) whose change to the period's end exceeded each ATR threshold, each way."""
    net = frame["net_atr"].to_numpy(float) if len(frame) else np.array([])
    if not len(net):
        return {"above": [], "below": []}
    return {
        "above": [round(float((net > t).mean() * PP), 1) for t in NET_THRESHOLDS_ATR],
        "below": [round(float((net < -t).mean() * PP), 1) for t in NET_THRESHOLDS_ATR],
    }


def money_card(ctx: StudyContext, horizon: str) -> EvidenceCard | None:
    if not ctx.has_daily_ohlc or ctx.daily.attrs.get("close_only"):
        return None
    d = ctx.daily
    state = current_state(d, horizon, crypto=ctx.is_crypto)
    if state is None:
        return None
    events = money_events(d, horizon, crypto=ctx.is_crypto, sessions=state["sessions"])
    if len(events) == 0:
        return None
    events = events[events["key"] != state["key"]]  # the current period never enters its own analogs
    same_mask = (events["broke_high_so_far"] == state["broke_high"]) & (
        events["broke_low_so_far"] == state["broke_low"]
    )
    same, others = events[same_mask], events[~same_mask]
    name = HORIZON_NAMES[horizon]
    cols = [col for col, _ in ITEMS]
    labels = [label.format(h=name) for _, label in ITEMS]
    s = same_mask.to_numpy(float)
    units = {"s": s, **{col: events[col].to_numpy(float) for col in cols}}

    def statistic(u: dict) -> np.ndarray:
        inside, outside = u["s"] == 1.0, u["s"] == 0.0
        if not inside.any() or not outside.any():
            return np.full(len(cols), np.nan)
        return np.array([u[c][inside].mean() - u[c].mean() for c in cols], dtype=float)  # state against all periods

    items = []
    if len(same) and len(others):
        result = evaluate(units, statistic, block=BLOCK[horizon], reps=ctx.reps, seed=ctx.seed + 31)
        items = items_from_evaluation(
            labels,
            result,
            scale=PP,
            observed=np.array([same[c].mean() for c in cols]),
            baseline=np.array([events[c].mean() for c in cols]),
            n_per_item=[len(same)] * len(cols),
        )
        for item, col in zip(items, cols, strict=True):
            item.extra = {"outcome": col}
    lengths = horizon_bars(d, horizon, crypto=ctx.is_crypto)["n_sessions"]
    typical = int(np.median(lengths)) if len(lengths) else None
    unit_word = "days" if ctx.is_crypto else "sessions"
    keys = period_key(d.index, horizon)
    first = int(np.flatnonzero(keys == state["key"])[0])
    yardstick = atr_percent(d)[first - 1] if first > 0 else float("nan")
    card_state = {
        "horizon": name,
        "period": period_label(state["key"], horizon),
        "sessions_elapsed": state["sessions"],
        "typical_sessions": typical,
        "session_unit": unit_word,
        "broke_prior_high": state["broke_high"],
        "broke_prior_low": state["broke_low"],
        "atr_start_pct": round(float(yardstick), 3) if np.isfinite(yardstick) else None,
        "analogs": int(len(same)),
        "others": int(len(others)),
        "all_periods": int(len(events)),
        "as_of": str(state["as_of"].date()),
        "excursions": {"same": _summary(same), "others": _summary(others), "all": _summary(events)},
        "net_thresholds": {
            "atr": list(NET_THRESHOLDS_ATR),
            "same": _net_thresholds(same),
            "others": _net_thresholds(others),
            "all": _net_thresholds(events),
        },
    }
    situation = (
        ("above" if state["broke_high"] else "not above")
        + " the prior high and "
        + ("below" if state["broke_low"] else "not below")
        + " the prior low"
    )
    return EvidenceCard(
        id=f"{ctx.instrument.code}.money.{name}",
        instrument=ctx.instrument.code,
        family="money",
        kind="edge",
        title=f"From here to the end of the {name}",
        question=(
            f"After {state['sessions']} {unit_word} of {card_state['period']}, {situation} so far: how far did price "
            f"travel above and below the close in past {name}s at the same point, and where did they end?"
        ),
        unit="pp",
        method=(
            f"Analogs are past complete {name}s, each after a complete {name}, observed after the same "
            f"{state['sessions']} {unit_word} and in the same state. From the next session to the {name}'s last "
            f"session: highest high and lowest low against the close at the observation point, and the last close, "
            f"in multiples of the 14-session ATR at the start of the {name}. Each share is compared with all past "
            f"{name}s at the same point, whatever their state; circular block bootstrap over {name}s "
            f"({BLOCK[horizon]}-{name} blocks), most recent 30% held out. All figures are gross; the share of past "
            f"{name}s that ended beyond each of several thresholds in ATR is published so that any trading cost can "
            f"be applied."
        ),
        control=f"All past {name}s at the same point, in any state",
        contrast=f"all {name}s at the same point",
        n_label=f"{name}s",
        items=items,
        period=period_of(pd.DatetimeIndex(same["start"]) if len(same) else pd.DatetimeIndex([])),
        notes=[
            "Figures are gross: no commissions, spread, financing or taxes. On the page, a cost profile shows how often past periods ended beyond that cost."
        ],
        state=card_state,
    )


def run(ctx: StudyContext) -> list[EvidenceCard]:
    cards = [money_card(ctx, h) for h in HORIZONS]
    return [c for c in cards if c is not None]


__all__ = ["money_events", "money_card", "run", "atr_percent", "NET_THRESHOLDS_ATR"]
