"""Research-only OHLCV temporal levels. Data is known at each daily bar's CLOSE.

Do not backtest a same-day open entry using this bar's H/L/C. Market calendars
and corporate actions must be supplied/validated in production.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

COLS = ("open", "high", "low", "close")

def load_ohlcv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {s.lower().strip(): s for s in df.columns}
    if "date" not in cols or any(c not in cols for c in COLS):
        raise ValueError("CSV must contain date, open, high, low, close (volume optional)")
    df = df.rename(columns={v:k for k,v in cols.items()})
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    if df["date"].isna().any() or df["date"].duplicated().any():
        raise ValueError("dates must be non-null and unique")
    df = df.sort_values("date").set_index("date")
    for c in COLS:
        df[c] = pd.to_numeric(df[c], errors="raise")
    if df[list(COLS)].isna().any().any() or (df[list(COLS)] <= 0).any().any():
        raise ValueError("OHLC must have positive non-null prices")
    if ((df.high < df.low) | (df.high < df[["open","close"]].max(axis=1)) |
        (df.low > df[["open","close"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC: high/low not enclosing open/close")
    if "volume" in df:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        if (df["volume"].dropna() < 0).any():
            raise ValueError("negative volume")
    if len(df) < 40:
        raise ValueError("At least 40 rows needed for basic studies")
    return df


def completed_period_ohlc(df: pd.DataFrame, period: str, prefix: str) -> pd.DataFrame:
    """Map prior COMPLETED weekly/monthly/quarterly/halfyear/year OHLC.
    Periods are calendar labels, shifts are over observed periods. For major
    market closures, a formal exchange-calendar reindex is required in prod.
    """
    key = df.index.to_period(period)
    agg = df.groupby(key).agg(open=("open","first"),high=("high","max"),
                               low=("low","min"),close=("close","last"))
    prev = agg.shift(1).rename(columns={c:f"{prefix}_{c}" for c in COLS})
    out = prev.reindex(key)
    out.index = df.index
    return out


def same_calendar_date_prev_year(df: pd.DataFrame) -> pd.DataFrame:
    """Do not silently map Feb 29 to Feb 28 or holidays to another day."""
    mapped = []
    for d in df.index:
        try:
            mapped.append(d.replace(year=d.year-1))
        except ValueError:
            mapped.append(pd.NaT)
    out = df.reindex(pd.DatetimeIndex(mapped))[list(COLS)].copy()
    out.index = df.index
    return out.rename(columns={c:f"same_date_y1_{c}" for c in COLS})


def temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Features known at EOD of row t. No current-week future aggregation."""
    result = df.copy()
    prev_day = df[list(COLS)].shift(1)
    result = result.join(prev_day.rename(columns={c:f"prev_day_{c}" for c in COLS}))
    for frequency, label in [("W-SUN","prev_week"),("M","prev_month"),
                             ("Q-DEC","prev_quarter"),("2Q-DEC","prev_halfyear"),
                             ("Y-DEC","prev_year")]:
        # pandas 2.2 does not support '2Q-DEC' as an anchoring halfyear period
        if label == "prev_halfyear":
            halfkeys = pd.Index([f"{d.year}-H{1 if d.month<=6 else 2}" for d in df.index])
            agg = df.groupby(halfkeys).agg(open=("open","first"),high=("high","max"),
                                           low=("low","min"),close=("close","last"))
            out = agg.shift(1).rename(columns={c:f"{label}_{c}" for c in COLS}).reindex(halfkeys)
            out.index = df.index
        else:
            out = completed_period_ohlc(df,frequency,label)
        result = result.join(out)

    # Same month and same half-year LAST YEAR: only completed historical reference.
    mkeys = df.index.to_period('M')
    m_agg = df.groupby(mkeys).agg(open=('open','first'),high=('high','max'),
                                  low=('low','min'),close=('close','last'))
    m_prior = m_agg.reindex(pd.PeriodIndex([x-12 for x in mkeys],freq='M'))
    m_prior.index=df.index
    result = result.join(m_prior.rename(columns={c:f'same_month_y1_{c}' for c in COLS}))

    hkeys = pd.Index([f'{d.year}-H{1 if d.month<=6 else 2}' for d in df.index])
    h_agg = df.groupby(hkeys).agg(open=('open','first'),high=('high','max'),
                                  low=('low','min'),close=('close','last'))
    prior_half_keys=[f'{d.year-1}-H{1 if d.month<=6 else 2}' for d in df.index]
    h_prior=h_agg.reindex(prior_half_keys); h_prior.index=df.index
    result=result.join(h_prior.rename(columns={c:f'same_halfyear_y1_{c}' for c in COLS}))

    # Historical OHLC from same fiscal/calendar quarter LAST YEAR, always already complete.
    qkeys = df.index.to_period("Q-DEC")
    q_agg = df.groupby(qkeys).agg(open=("open","first"),high=("high","max"),
                                   low=("low","min"),close=("close","last"))
    same_q_keys = pd.PeriodIndex([q-4 for q in qkeys],freq="Q-DEC")
    lastq = q_agg.reindex(same_q_keys);lastq.index=df.index
    result = result.join(lastq.rename(columns={c:f"same_quarter_y1_{c}" for c in COLS}))

    # Previous week's SAME WEEKDAY; missing trading days stay missing (not shifted to another weekday).
    for offset in [1,2,3,4]:
        lookups = df.index - pd.Timedelta(days=7*offset)
        wd = df.reindex(lookups)[list(COLS)];wd.index=df.index
        result = result.join(wd.rename(columns={c:f"same_weekday_w{offset}_{c}" for c in COLS}))
    result = result.join(same_calendar_date_prev_year(df))

    # Monday OHLC is only observed as EOD Monday; holiday Monday -> all missing.
    weekly_key = df.index.to_period('W-SUN')
    mondays = df.loc[df.index.weekday==0, list(COLS)].copy()
    mondays["_week"] = mondays.index.to_period('W-SUN')
    monday_by_week = mondays.set_index('_week')[list(COLS)]
    monday_current = monday_by_week.reindex(weekly_key)
    monday_current.index = df.index
    result = result.join(monday_current.rename(columns={c:f"monday_current_eod_{c}" for c in COLS}))
    # Previous weekly Monday, not the last observed Monday in any earlier week.
    monday_prev = monday_by_week.reindex(pd.PeriodIndex([x-1 for x in weekly_key],freq='W-SUN'))
    monday_prev.index = df.index
    result = result.join(monday_prev.rename(columns={c:f"monday_previous_week_{c}" for c in COLS}))

    # Current partial period as_of EOD t: cumulative extreme through row t, NOT full period.
    for period, tag in [('W-SUN','week'),('M','month'),('Q-DEC','quarter'),('Y-DEC','year')]:
        keys=df.index.to_period(period)
        grouped=df.groupby(keys)
        result[f'current_{tag}_high_asof_eod'] = grouped.high.cummax().to_numpy()
        result[f'current_{tag}_low_asof_eod'] = grouped.low.cummin().to_numpy()
        result[f'current_{tag}_open_asof_eod'] = grouped.open.transform('first').to_numpy()
        result[f'current_{tag}_close_asof_eod'] = df.close

    # Current semester YTD extrema known only through EOD current bar.
    half_grouped = df.groupby(hkeys)
    result['current_halfyear_high_asof_eod'] = half_grouped.high.cummax().to_numpy()
    result['current_halfyear_low_asof_eod'] = half_grouped.low.cummin().to_numpy()
    result['current_halfyear_open_asof_eod'] = half_grouped.open.transform('first').to_numpy()
    result['current_halfyear_close_asof_eod'] = df.close

    prev_close = df.close.shift(1)
    result['return_1d'] = df.close.pct_change(fill_method=None)
    for n in [3,5,10,20]:
        result[f'return_{n}d'] = df.close.pct_change(periods=n,fill_method=None)
    result['gap_pct'] = df.open / prev_close - 1
    rng = df.high-df.low
    result['clv_0_1'] = ((df.close-df.low)/rng.replace(0,np.nan)).fillna(.5)
    result['range_pct'] = rng/df.open
    result['weekday'] = df.index.weekday
    result['month'] = df.index.month
    result['quarter'] = df.index.quarter
    result['leap_year'] = df.index.is_leap_year
    result['years_since_2000'] = df.index.year-2000
    # only calendar year label, not proof of election-related prediction
    result['us_presidential_election_year'] = ((df.index.year-2000)%4 == 0)
    result['distance_prev_week_low_pct'] = df.close/result.prev_week_low - 1
    result['position_prev_week_range']=(df.close-result.prev_week_low)/(
        result.prev_week_high-result.prev_week_low).replace(0,np.nan)
    result['prev_week_low_touched'] = (df.low<=result.prev_week_low)&(df.high>=result.prev_week_low)
    result['prev_week_high_touched'] = (df.low<=result.prev_week_high)&(df.high>=result.prev_week_high)
    # distinguish a simple touch from a failed breakout/reclaim and no inference about true stops
    result['prev_week_low_sweep_reclaim'] = (df.low<result.prev_week_low)&(df.close>result.prev_week_low)
    return result


def first_touch_weekly_low_study(features: pd.DataFrame, horizon: int=5) -> dict:
    """EOD event at t and close-to-close forward label t+h. RESEARCH, not execution.
    Events reduced to first per calendar week to limit overlapping observations.
    """
    if horizon < 1: raise ValueError('horizon must be positive')
    p = features.index.to_period('W-SUN')
    touch = features.prev_week_low_touched.fillna(False)
    prior_touch_count = touch.astype(int).groupby(p).cumsum().groupby(p).shift(1).fillna(0)
    first = touch & (prior_touch_count == 0)
    ret = features.close.shift(-horizon)/features.close-1
    sample = ret[first].dropna()
    baseline = ret.dropna()
    return {'event':'first_touch_prev_week_low','horizon_sessions':horizon,
            'n_events':int(len(sample)),'n_baseline':int(len(baseline)),
            'mean_forward_return':float(sample.mean()) if len(sample) else None,
            'positive_fraction':float((sample>0).mean()) if len(sample) else None,
            'baseline_mean_forward_return':float(baseline.mean()) if len(baseline) else None,
            'baseline_positive_fraction':float((baseline>0).mean()) if len(baseline) else None,
            'limitations':'EOD condition known at t close; does not imply trading at intraday low; overlapping horizon events remain possible across weeks; price-only, not total return, no statistical significance inferred.'}


def next_open_strategy(df: pd.DataFrame, features: pd.DataFrame, cost_bps:float=2.0) -> dict:
    """Simplified price-only next-open to next-open test, cash vs one-day long.
    Signal from t EOD, position at t+1 OPEN, exit at t+2 OPEN. Two-sided bps on changes.
    NOT adjusted dividends, finance/tax or realistic spread; do NOT market as performance.
    """
    signal=features.prev_week_low_sweep_reclaim.fillna(False).astype(int)
    exposure=signal.shift(1,fill_value=0)
    returns=(df.open.shift(-1)/df.open-1).iloc[:-1]
    expo=exposure.iloc[:-1]
    turnover=expo.diff().abs().fillna(expo.iloc[0])
    net=expo*returns-turnover*(cost_bps/10000)
    # include the final exit cost when position stays open at last observation
    terminal_fee=float(expo.iloc[-1])*(cost_bps/10000)
    equity=(1+net).cumprod().iloc[-1]*(1-terminal_fee)
    benchmark=(df.open.iloc[-1]/df.open.iloc[0])*(1-cost_bps/10000)
    return {'strategy':'next_open_one_day_after_sweep','n_entries':int((expo.diff().fillna(expo.iloc[0])>0).sum()),
            'gross_style':'price_only', 'ending_equity_multiple_net_costs':round(float(equity),6),
            'buy_hold_price_only_multiple_approx':round(float(benchmark),6),
            'cost_bps_one_way':float(cost_bps),'warning':'Experimental only. NO dividends, risk free rate, full benchmark total return, real-market execution or statistical validation.'}
