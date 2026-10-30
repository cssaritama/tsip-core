"""Where the last close stands against each horizon's reference range, as distances.

For a period in progress the reference is the prior complete period; once a period has ended
(for example on a Friday evening or a weekend for the week), the reference is the period that
just closed, so the next period's starting position is always shown. Distances are derived
figures (percent of the last close and multiples of the average true range); price levels are
not published.
"""

from __future__ import annotations

import pandas as pd

from tsip.frames import HORIZON_NAMES, has_ended, horizon_bars, period_bounds, period_key, period_label
from tsip.studies.revisit import atr_pct

PP = 100.0
HORIZONS = ("week", "month", "quarter", "half", "year")


def horizon_position(daily: pd.DataFrame, horizon: str, *, crypto: bool, atr: float | None) -> dict | None:
    keys = period_key(daily.index, horizon)
    current = int(keys[-1])
    last_day = pd.Timestamp(daily.index[-1])
    ended = has_ended(last_day, period_bounds(current, horizon)[1], crypto=crypto)
    bars = horizon_bars(daily, horizon, crypto=crypto)
    reference_key = current if ended else current - 1
    if reference_key not in bars.index:
        return None
    ref = bars.loc[reference_key]
    close = float(daily["close"].iloc[-1])
    high, low = float(ref["high"]), float(ref["low"])
    out = {
        "horizon": HORIZON_NAMES[horizon],
        "status": "closed" if ended else "in_progress",
        "period": period_label(current + 1 if ended else current, horizon),
        "reference": period_label(reference_key, horizon),
        "to_reference_high_pct": round((high / close - 1.0) * PP, 3),
        "to_reference_low_pct": round((low / close - 1.0) * PP, 3),
        "range_position_pct": round((close - low) / (high - low) * PP, 1) if high > low else None,
        "range_width_pct": round((high / low - 1.0) * PP, 3) if low > 0 else None,
    }
    if atr:
        out["to_reference_high_atr"] = round(out["to_reference_high_pct"] / atr, 2)
        out["to_reference_low_atr"] = round(out["to_reference_low_pct"] / atr, 2)
    if not ended:
        rows = daily[keys == current]
        out["took_reference_high"] = bool(float(rows["high"].max()) > high)
        out["took_reference_low"] = bool(float(rows["low"].min()) < low)
    return out


def position(daily: pd.DataFrame | None, *, crypto: bool) -> dict:
    if daily is None or len(daily) < 30 or not {"high", "low", "close"} <= set(daily.columns):
        return {}
    if daily[["high", "low"]].isna().all().any():
        return {}
    atr = atr_pct(daily)
    rows = [horizon_position(daily, h, crypto=crypto, atr=atr) for h in HORIZONS]
    return {
        "as_of": str(pd.Timestamp(daily.index[-1]).date()),
        "atr_pct": None if atr is None else round(atr, 3),
        "atr_sessions": 14,
        "horizons": [r for r in rows if r is not None],
    }


__all__ = ["position"]
