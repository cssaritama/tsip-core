"""Close-only S&P 500 observations from Federal Reserve Economic Data (FRED).

FRED SP500 is published with 10 years of daily CLOSE observations and copyright
restrictions. This adapter deliberately does NOT synthesize O/H/L from close.
Do not republish FRED/SP500 CSV or derived index-level time series without rights.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np


def parse_fred_csv(path: str|Path, expected_series: str='SP500')->pd.DataFrame:
    if expected_series not in ('SP500','NASDAQ100'):
        raise ValueError('Only audited series identifiers allowed')
    data=pd.read_csv(path)
    dates_col='observation_date' if 'observation_date' in data else 'DATE' if 'DATE' in data else None
    if dates_col is None or expected_series not in data:
        raise ValueError(f'FRED CSV needs observation_date or DATE and {expected_series}')
    data=data.rename(columns={dates_col:'date',expected_series:'close'})
    data['date']=pd.to_datetime(data['date'],errors='raise')
    data['close']=pd.to_numeric(data['close'].replace('.',pd.NA),errors='coerce')
    if data.date.isna().any() or data.date.duplicated().any():
        raise ValueError('invalid FRED dates')
    data=data.dropna(subset=['close']).set_index('date').sort_index()
    if (data.close<=0).any() or not np.isfinite(data.close).all():
        raise ValueError('invalid close price')
    if len(data)<40: raise ValueError('insufficient close-only history')
    return data[['close']]


def close_only_research(df:pd.DataFrame,series:str='SP500')->dict:
    if 'close' not in df or len(df)<40:raise ValueError('need close-only history >=40')
    returns=df.close.pct_change(fill_method=None)
    dow=[]
    for i in range(5):
        s=returns[df.index.dayofweek==i].dropna()
        dow.append({'weekday':i,'n':len(s),'mean_close_return':float(s.mean()) if len(s) else None,
                    'positive_fraction':float((s>0).mean()) if len(s) else None})
    by_month=[]
    for month in range(1,13):
        s=returns[df.index.month==month].dropna()
        by_month.append({'month':month,'n':len(s),'mean_daily_return':float(s.mean()) if len(s) else None})
    return {'series':series,'frequency':'daily_close_only','start':str(df.index[0].date()),
            'end':str(df.index[-1].date()),'n_observations':len(df),'last_close':float(df.close.iloc[-1]),
            'first_close':float(df.close.iloc[0]),'close_price_change_fraction':float(df.close.iloc[-1]/df.close.iloc[0]-1),
            'weekday_returns':dow,'month_daily_returns':by_month,
            'data_usage':'LOCAL_RESEARCH_ONLY_COPYRIGHT_RESTRICTIONS_CHECK_BEFORE_REUSE',
            'license_review':'REQUIRED_BEFORE_PUBLIC_REDISPLAY_OR_REDISTRIBUTION',
            'limitations':['CLOSE ONLY: cannot calculate OHLC levels, sweeps or intraday sessions.',
                           'S&P 500 price index omits dividends; not a total-return benchmark.',
                           'Daily seasonality untested for significance and multiple comparisons.',
                           'FRED history depth is restricted by licensing.']}
