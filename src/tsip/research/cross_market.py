"""Reproducible descriptive comparison for SPY and QQQ EOD.

The module intentionally does not train a predictive model or claim alpha. Returns
are PRICE ONLY and not dividend-adjusted. Each asset's daily returns are computed
before inner-joining on dates; no price interpolation or forward fill is used.
"""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any
import numpy as np
import pandas as pd
from .assets import get_instrument
from .engine import temporal_features, first_touch_weekly_low_study

ETF_CODES=frozenset(('SPY','QQQ'))


def _finite(x:float)->float|None:
    return float(round(x,8)) if pd.notna(x) and np.isfinite(x) else None


def compare_etfs(frames:Mapping[str,pd.DataFrame], horizon:int=5)->dict[str,Any]:
    """Compare two EOD ETF inputs with common trading dates and explicit origins.

    Input DataFrames: datetime index and open, high, low, close (validated externally).
    A forward return is a research outcome, not an executable signal.
    """
    if set(frames)!=ETF_CODES:
        raise ValueError('This research comparison accepts SPY and QQQ only')
    if horizon<1 or horizon>20:
        raise ValueError('horizon must be 1..20')
    daily_returns={}
    for code,df in frames.items():
        if len(df)<40 or not isinstance(df.index,pd.DatetimeIndex) or not df.index.is_unique or not df.index.is_monotonic_increasing:
            raise ValueError(f'{code}: need >=40 validated, sorted, unique daily bars')
        if not {'open','high','low','close'}.issubset(df.columns):
            raise ValueError(f'{code}: missing required OHLC columns')
        daily_returns[code]=df['close'].pct_change(fill_method=None).rename(code)
    aligned=pd.concat([daily_returns['SPY'],daily_returns['QQQ']],axis=1,join='inner').dropna()
    if len(aligned)<30:
        raise ValueError('Fewer than 30 overlapping daily return observations')
    # Price normalization uses synchronized dates. The first aligned return is not
    # considered a portfolio trade, and different price scales are never compared.
    common=aligned.index
    stats={}
    for code,df in frames.items():
        local_returns=aligned[code]
        close=df.loc[common,'close'].astype(float)
        path=100.0*(close/close.iloc[0])
        features=temporal_features(df)
        week_low=first_touch_weekly_low_study(features,horizon)
        ranges=(df.loc[common,'high']-df.loc[common,'low'])/df.loc[common,'open']
        recent=local_returns.tail(20)
        stats[code]={
            'instrument':get_instrument(code),
            'as_of_eod':str(common[-1].date()),
            'last_close':_finite(close.iloc[-1]),
            'total_price_change_in_shared_window':_finite(close.iloc[-1]/close.iloc[0]-1),
            'mean_daily_return':_finite(local_returns.mean()),
            'annualized_volatility_252d':_finite(local_returns.std(ddof=1)*np.sqrt(252)),
            'last_20d_volatility_annualized':_finite(recent.std(ddof=1)*np.sqrt(252)),
            'mean_intraday_range_pct':_finite(ranges.mean()),
            'weekly_low_event_research':week_low,
            'normalized_index_100':[_finite(v) for v in path.tail(90)],
        }
    lead=stats['QQQ']['total_price_change_in_shared_window']-stats['SPY']['total_price_change_in_shared_window']
    return {
        'schema_version':'crossmarket-v0.1',
        'label':'DESCRIPTIVE_EOD_PRICE_ONLY_NOT_PREDICTIVE',
        'returns_method':'unadjusted close-to-close; excludes dividends, fees and taxes',
        'alignment':'common return dates, computed per asset before intersection; no ffill',
        'as_of_eod':str(common[-1].date()),
        'n_overlapping_return_days':len(common),
        'n_walking_days_plotted':min(90,len(common)),
        'dates_90':[str(x.date()) for x in common[-90:]],
        'pearson_daily_returns':_finite(aligned['SPY'].corr(aligned['QQQ'])),
        'pearson_last_20d':_finite(aligned['SPY'].tail(20).corr(aligned['QQQ'].tail(20))),
        'fraction_same_direction':_finite(((aligned['SPY']>0)==(aligned['QQQ']>0)).mean()),
        'QQQ_minus_SPY_price_change_in_shared_window':_finite(lead),
        'assets':stats,
        'critical_limitations':['Prices are not dividend-adjusted; not total return',
          'Nonsynchronous ETF histories are inner-joined without interpolation',
          'Correlation does not demonstrate predictive lead/lag or tradable alpha',
          'Weekly-low events are EOD studies, not fills at intraday low',
          'No liquidity/order book inferred, data redistribution rights unresolved'],
    }
