"""Time to revisit a level: how long price takes to come back to a closed period's high or low.

Event: a calendar period (week, month, quarter, year) closes. Its high and low become reference
levels, frozen at the period's last close. The clock starts at the next session. A level is
revisited when a later session trades at or beyond it (high >= level high, low <= level low).

Distance is measured in units of volatility, ``z = |log(level / close)| / sigma``, where sigma
is the standard deviation of daily log returns over the 60 sessions up to the close (no data
after the event is used).

Control. A far level takes longer to reach for purely mechanical reasons, and drift and fat
tails change how often any level is reached. For each event the control asks how often price,
starting from *any other* period close in the same history, reached a level at the same
volatility-scaled distance on the same side within the same number of sessions. The difference
(observed minus control, in percentage points) is what the actual levels add beyond distance,
volatility, drift and the shape of returns. A positive difference means real levels are
revisited sooner than equally distant arbitrary levels.

Censoring. Rates within *k* sessions only use events with *k* sessions of data after them. The
median time to revisit uses a Kaplan–Meier estimate in which levels not yet revisited are
censored, not dropped, so slow revisits are not hidden.

Open levels. The board lists closed periods whose high or low has not been traded since, with
their age and distance from the last close in percent and in ATR units. Price levels themselves
are not published.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsip.evidence.bootstrap import evaluate
from tsip.evidence.card import EvidenceCard, items_from_evaluation
from tsip.frames import HORIZON_NAMES, horizon_bars, period_label
from tsip.studies.common import StudyContext, consecutive_mask, period_of

PP = 100.0
VOL_WINDOW = 60
ATR_WINDOW = 14
MIN_EVENTS = 30
HORIZONS = {  # windows in sessions (calendar days for crypto) and bootstrap block in events
    "week": ((5, 10, 20), 8),
    "month": ((10, 20, 60), 6),
    "quarter": ((20, 60, 120), 4),
    "year": ((60, 120, 250), 2),
}
OPEN_LEVEL_PERIODS = {"week": 12, "month": 12, "quarter": 8, "year": 5}


def _sigma(close: np.ndarray) -> np.ndarray:
    """Trailing standard deviation of daily log returns, known at each close."""
    r = np.diff(np.log(close), prepend=np.nan)
    return pd.Series(r).rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std().to_numpy()


def atr_pct(daily: pd.DataFrame, window: int = ATR_WINDOW) -> float | None:
    """Average true range of the last ``window`` sessions, as a percentage of the last close."""
    if len(daily) < window + 1:
        return None
    h, lo, c = (daily[col].to_numpy(float) for col in ("high", "low", "close"))
    prev = np.concatenate([[np.nan], c[:-1]])
    tr = np.nanmax(np.vstack([h - lo, np.abs(h - prev), np.abs(lo - prev)]), axis=0)
    value = np.nanmean(tr[-window:]) / c[-1] * PP
    return float(value) if np.isfinite(value) else None


def excursions(daily: pd.DataFrame, starts: np.ndarray, sigma: np.ndarray, kmax: int) -> tuple[np.ndarray, np.ndarray]:
    """Running maximum excursion above and below each start's reference close, in sigma units.

    ``starts`` are positions of the first session after a period close; the reference close is
    the session before. Row i, column j: largest move reached within the first j+1 sessions.
    NaN where the window runs past the data or crosses a gap.
    """
    h, lo, c = (daily[col].to_numpy(float) for col in ("high", "low", "close"))
    n = len(daily)
    up = np.full((len(starts), kmax), np.nan)
    down = np.full((len(starts), kmax), np.nan)
    for i, s in enumerate(starts):
        ref = c[s - 1]
        sd = sigma[s - 1]
        if not np.isfinite(sd) or sd <= 0:
            continue
        end = min(n, s + kmax)
        if end <= s:
            continue
        hi = np.log(h[s:end] / ref) / sd
        dn = np.log(ref / lo[s:end]) / sd
        up[i, : end - s] = np.maximum.accumulate(hi)
        down[i, : end - s] = np.maximum.accumulate(dn)
    return up, down


def build_events(daily: pd.DataFrame, horizon: str, *, crypto: bool) -> dict | None:
    windows, _ = HORIZONS[horizon]
    kmax = max(windows)
    bars = horizon_bars(daily, horizon, crypto=crypto)
    if len(bars) < MIN_EVENTS + 1:
        return None
    position = pd.Series(np.arange(len(daily)), index=daily.index)
    close = daily["close"].to_numpy(float)
    sigma = _sigma(close)
    gaps = ~consecutive_mask(daily.index, crypto=crypto)
    starts, z_up, z_down, dates = [], [], [], []
    for _, row in bars.iterrows():
        last = int(position[pd.Timestamp(row["last_day"])])
        s = last + 1
        if s >= len(daily) or gaps[s]:
            continue  # nothing after the period yet, or a data gap right after it
        sd = sigma[last]
        if not np.isfinite(sd) or sd <= 0:
            continue
        ref = close[last]
        starts.append(s)
        z_up.append(max(0.0, np.log(row["high"] / ref) / sd))
        z_down.append(max(0.0, np.log(ref / row["low"]) / sd))
        dates.append(daily.index[s])
    if len(starts) < MIN_EVENTS:
        return None
    starts = np.array(starts)
    up, down = excursions(daily, starts, sigma, kmax)
    # a window that crosses a data gap is not observed
    for i, s in enumerate(starts):
        span = gaps[s + 1 : s + kmax]
        if span.any():
            cut = int(np.argmax(span)) + 1
            up[i, cut:] = np.nan
            down[i, cut:] = np.nan
    return {
        "date": np.array(dates, dtype="datetime64[ns]"),
        "z_up": np.array(z_up),
        "z_down": np.array(z_down),
        "up": up,
        "down": down,
    }


def outcome_arrays(ev: dict, windows: tuple[int, ...]) -> dict[str, np.ndarray]:
    """Per event and window: observed revisit (0/1, NaN if unobserved) and the control probability."""
    n = len(ev["z_up"])
    cols = len(windows) * 2
    obs = np.full((n, cols), np.nan)
    base = np.full((n, cols), np.nan)
    for side, (z, path) in enumerate(((ev["z_up"], ev["up"]), (ev["z_down"], ev["down"]))):
        for j, k in enumerate(windows):
            col = side * len(windows) + j
            reached = path[:, k - 1]  # max excursion within k sessions, NaN if not fully observed
            observed = np.isfinite(reached)
            obs[observed, col] = (reached[observed] >= z[observed]).astype(float)
            pool = reached[observed]
            if len(pool) < 2:
                continue
            sorted_pool = np.sort(pool)
            for i in np.flatnonzero(observed):
                # share of other events' paths that travelled at least this event's distance
                count = len(sorted_pool) - np.searchsorted(sorted_pool, z[i], side="left")
                own = 1 if reached[i] >= z[i] else 0
                base[i, col] = (count - own) / (len(sorted_pool) - 1)
    return {"obs": obs, "base": base}


def _statistic(u: dict) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        return np.nanmean(u["obs"], axis=0) - np.nanmean(u["base"], axis=0)


def kaplan_meier_median(path: np.ndarray, z: np.ndarray) -> float | None:
    """Median sessions to revisit with levels not yet revisited treated as censored."""
    times, events = [], []
    for row, dist in zip(path, z, strict=True):
        observed = np.isfinite(row)
        if not observed.any():
            continue
        hit = np.flatnonzero(observed & (row >= dist))
        if len(hit):
            times.append(int(hit[0]) + 1)
            events.append(1)
        else:
            times.append(int(observed.sum()))
            events.append(0)
    if not times:
        return None
    t = np.array(times)
    e = np.array(events)
    survival = 1.0
    for time in np.unique(t[e == 1]):
        at_risk = (t >= time).sum()
        survival *= 1 - ((t == time) & (e == 1)).sum() / at_risk
        if survival <= 0.5:
            return float(time)
    return None  # median not reached within the observed window


def revisit_card(ctx: StudyContext, horizon: str) -> EvidenceCard | None:
    d = ctx.daily
    if not ctx.has_daily_ohlc or d is None or len(d) < 400:
        return None
    ev = build_events(d, horizon, crypto=ctx.is_crypto)
    if ev is None:
        return None
    windows, block = HORIZONS[horizon]
    units = outcome_arrays(ev, windows)
    result = evaluate(units, _statistic, block=block, reps=ctx.reps, seed=ctx.seed + len(horizon))
    unit_word = "days" if ctx.is_crypto else "sessions"
    labels = [f"High revisited within {k} {unit_word}" for k in windows] + [
        f"Low revisited within {k} {unit_word}" for k in windows
    ]
    with np.errstate(invalid="ignore"):
        observed = np.nanmean(units["obs"], axis=0)
        baseline = np.nanmean(units["base"], axis=0)
    counts = [int(np.isfinite(units["obs"][:, j]).sum()) for j in range(units["obs"].shape[1])]
    items = items_from_evaluation(labels, result, scale=PP, observed=observed, baseline=baseline, n_per_item=counts)
    med_up = kaplan_meier_median(ev["up"], ev["z_up"])
    med_down = kaplan_meier_median(ev["down"], ev["z_down"])
    for j, item in enumerate(items):
        side_up = j < len(windows)
        item.extra = {
            "observed_pct": float(observed[j] * PP),
            "control_pct": float(baseline[j] * PP),
            "median_sessions": med_up if side_up else med_down,
            "median_distance_sigma": float(np.median(ev["z_up"] if side_up else ev["z_down"])),
            "unit_word": unit_word,
        }
    name = HORIZON_NAMES[horizon]
    return EvidenceCard(
        id=f"{ctx.instrument.code}.revisits.{horizon}",
        instrument=ctx.instrument.code,
        family="revisits",
        kind="edge",
        title=f"Time to revisit the prior {name}'s high and low",
        question=(
            f"After a {name} closes, how soon does price trade back at its high or its low, and sooner than "
            "equally distant arbitrary levels?"
        ),
        unit="pp",
        method=(
            f"Share of closed {name}s whose high (low) was traded again within each window, minus the share of "
            "paths from all other period closes that travelled at least the same distance, measured in units of "
            f"the {VOL_WINDOW}-session volatility known at the close, on the same side and within the same window. "
            f"Only fully observed windows count; events resampled in {block}-{name} blocks. Median times use a "
            "Kaplan–Meier estimate with levels not yet revisited censored."
        ),
        control="Arbitrary levels at the same volatility-scaled distance, from all other period closes",
        n_label=f"{name}s",
        items=items,
        period=period_of(pd.DatetimeIndex(ev["date"])),
        contrast="equally distant arbitrary levels",
        notes=[
            "Observed and control rates are listed in the numbers table; the effect is their difference.",
            "A level counts as revisited when a later session trades at or beyond it; daily bars cannot say at what "
            "time of day.",
        ],
    )


def open_levels(daily: pd.DataFrame, *, crypto: bool) -> dict:
    """Closed periods whose high or low has not been traded since, with age and distance."""
    if daily is None or len(daily) < ATR_WINDOW + 2:
        return {}
    close = float(daily["close"].iloc[-1])
    atr = atr_pct(daily)
    position = pd.Series(np.arange(len(daily)), index=daily.index)
    h = daily["high"].to_numpy(float)
    lo = daily["low"].to_numpy(float)
    n = len(daily)
    board = []
    for horizon, keep in OPEN_LEVEL_PERIODS.items():
        bars = horizon_bars(daily, horizon, crypto=crypto)
        for key, row in bars.tail(keep).iterrows():
            last = int(position[pd.Timestamp(row["last_day"])])
            after_h = h[last + 1 :]
            after_l = lo[last + 1 :]
            for side, level, untouched in (
                ("high", row["high"], not (after_h >= row["high"]).any()),
                ("low", row["low"], not (after_l <= row["low"]).any()),
            ):
                if not untouched:
                    continue
                dist = (level / close - 1.0) * PP
                board.append(
                    {
                        "horizon": HORIZON_NAMES[horizon],
                        "period": period_label(int(key), horizon),
                        "side": side,
                        "age_sessions": int(n - 1 - last),
                        "distance_pct": round(float(dist), 3),
                        "distance_atr": None if not atr else round(float(dist / atr), 2),
                    }
                )
    board.sort(key=lambda r: abs(r["distance_pct"]))
    return {"as_of": str(pd.Timestamp(daily.index[-1]).date()), "atr_pct": atr, "levels": board}


def run(ctx: StudyContext) -> list[EvidenceCard]:
    cards = [revisit_card(ctx, horizon) for horizon in HORIZONS]
    return [c for c in cards if c is not None]
