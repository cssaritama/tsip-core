"""Intraday SESSION research for ES, separate from SPY daily data.

Sessions are ANALYTICAL CLOCK WINDOWS, not proof of exchange-order-flow or
unique buckets: Tokyo/Singapore/London/NY can overlap. Assign a timestamp
representing END of a fully closed intraday bar. Never use this-bar OHLC
at bar OPEN in a trading decision.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd

COLS=['open','high','low','close']
@dataclass(frozen=True)
class Session:
    name:str
    timezone:str
    start:str
    end:str

DEFAULT_SESSIONS=(
    Session('Tokyo','Asia/Tokyo','09:00','15:00'),
    Session('Singapore','Asia/Singapore','09:00','17:00'),
    Session('London','Europe/London','08:00','16:30'),
    Session('New York','America/New_York','09:30','16:00'),
)

def load_intraday(path:str|Path)->pd.DataFrame:
    frame=pd.read_csv(path)
    names={c.lower().strip():c for c in frame.columns}
    if not all(c in names for c in ['timestamp',*COLS]):
        raise ValueError('Intraday CSV requires timestamp,open,high,low,close (optional volume); ISO timezone offset or Z')
    frame=frame.rename(columns={v:k for k,v in names.items()})
    # Reject timezone-naive timestamps; parser would otherwise incorrectly assume UTC.
    if not frame.timestamp.astype(str).str.contains(r'(?:[Zz]|[+-]\d\d:\d\d)$',regex=True).all():
        raise ValueError('Every timestamp must carry explicit UTC Z or timezone offset')
    frame['timestamp']=pd.to_datetime(frame.timestamp,utc=True,errors='raise')
    if frame.timestamp.isna().any() or frame.timestamp.duplicated().any():
        raise ValueError('timestamp must be non-null, unique, timezone-aware')
    frame=frame.sort_values('timestamp').set_index('timestamp')
    for c in COLS:
        frame[c]=pd.to_numeric(frame[c],errors='raise')
    if frame[COLS].isna().any().any() or (frame[COLS]<=0).any().any():
        raise ValueError('missing, zero or negative prices')
    if ((frame.high < frame.low) | (frame.high < frame[['open','close']].max(axis=1)) |
        (frame.low > frame[['open','close']].min(axis=1))).any():
        raise ValueError('Invalid OHLC: high/low must enclose open/close')
    if 'volume' in frame:
        frame['volume']=pd.to_numeric(frame.volume,errors='raise')
        if (frame.volume.dropna()<0).any(): raise ValueError('negative volume')
    return frame

def _minutes(hhmm:str)->int:
    h,m=map(int,hhmm.split(':'))
    if h not in range(24) or m not in range(60): raise ValueError('Invalid HH:MM')
    return h*60+m

def rolling_elapsed_windows(bars:pd.DataFrame, hours=(6,12,18,24,25))->pd.DataFrame:
    """Actual ELAPSED UTC hour windows; gaps remain gaps, no fabricated prices.
    All features at t are known once bar t CLOSED; no prediction guarantee.
    """
    if bars.index.tz is None: raise ValueError('UTC-aware timestamp index required')
    bars=bars.sort_index()
    out=pd.DataFrame(index=bars.index)
    for hour in hours:
        if hour<=0: raise ValueError('hours must be positive')
        boundary=bars.index.asi8-int(pd.Timedelta(hours=hour).value)
        # time interval (t-hour,t] with last bar close included
        start=np.searchsorted(bars.index.asi8,boundary,side='right')
        out[f'w{hour}h_open_asof_close']=bars.open.to_numpy()[start]
        out[f'w{hour}h_high_asof_close']=bars.high.rolling(f'{hour}h',min_periods=1).max().to_numpy()
        out[f'w{hour}h_low_asof_close']=bars.low.rolling(f'{hour}h',min_periods=1).min().to_numpy()
        out[f'w{hour}h_close_asof_close']=bars.close.to_numpy()
        out[f'w{hour}h_count_bars']=(np.arange(len(bars))-start+1)
    return out

def session_rows(bars:pd.DataFrame, sessions=DEFAULT_SESSIONS, bar_minutes:int=30)->pd.DataFrame:
    """Aggregates independent named windows. An exchange calendar is needed in production.
    `bar_minutes` is the expected input cadence; missing/partial sessions flagged.
    The minute bars are *end-stamped*. Time range uses (start, end] for inclusion.
    """
    if bar_minutes<=0: raise ValueError('bar_minutes must be positive')
    if bars.index.tz is None: raise ValueError('timezone-aware timestamp index required')
    frames=[]
    for ses in sessions:
        local=bars.index.tz_convert(ses.timezone)
        mins=np.asarray(local.hour*60+local.minute,dtype=np.int64)
        begin,end=_minutes(ses.start),_minutes(ses.end)
        overnight=end<=begin
        # candle end timestamp in (session start, session end]
        if not overnight:
            mask=(mins>begin)&(mins<=end)
            expected=(end-begin)/bar_minutes
        else:
            mask=(mins>begin)|(mins<=end)
            expected=(24*60-begin+end)/bar_minutes
        if not mask.any():continue
        selection=bars.loc[mask,COLS+(['volume'] if 'volume' in bars else [])].copy()
        # strip the clock, preserve *local calendar date*, not UTC calendar date
        dates=pd.to_datetime(local[mask].date)
        if overnight:
            early=mins[mask]<=end
            dates=dates-pd.to_timedelta(early.astype(int),unit='D')
        selection['local_date']=dates
        grouped=selection.groupby('local_date',sort=True)
        aggregates=grouped.agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),n_bars=('close','size'))
        if 'volume' in selection:aggregates['volume']=grouped.volume.sum(min_count=1)
        aggregates['session']=ses.name
        aggregates['timezone']=ses.timezone
        aggregates['start_local']=ses.start
        aggregates['end_local']=ses.end
        aggregates['expected_bars']=expected
        aggregates['coverage_ratio']=(aggregates.n_bars/expected).clip(upper=1)
        aggregates['quality_status']=np.where(aggregates.coverage_ratio>=0.95,'complete','partial')
        aggregates['range_points']=aggregates.high-aggregates.low
        aggregates['range_pct']=aggregates.range_points/aggregates.open
        aggregates['net_points']=aggregates.close-aggregates.open
        aggregates['return_pct']=aggregates.close/aggregates.open-1
        aggregates['up_close']=aggregates.close>aggregates.open
        aggregates['clv_0_1']=(aggregates.close-aggregates.low)/aggregates.range_points.replace(0,np.nan)
        aggregates['weekday']=aggregates.index.weekday
        aggregates['week_start']=aggregates.index.to_period('W-SUN').start_time.astype(str)
        aggregates['month']=aggregates.index.to_period('M').astype(str)
        aggregates.index.name='local_date'
        frames.append(aggregates.reset_index())
    if not frames:return pd.DataFrame(columns=['session','local_date','n_bars'])
    out=pd.concat(frames,ignore_index=True).sort_values(['session','local_date']).reset_index(drop=True)
    out['previous_same_session_range_pct']=out.groupby('session').range_pct.shift(1)
    out['previous_same_session_return_pct']=out.groupby('session').return_pct.shift(1)
    return out

def session_summary(rows:pd.DataFrame)->dict:
    """Aggregate only complete sessions. Suppress false certainty for insufficient n."""
    if rows.empty:return {'coverage':{'n_total':0,'n_complete':0},'by_session':[],'by_session_weekday':[],'by_session_month':[],'by_session_week':[]}
    df=rows.loc[rows.quality_status=='complete'].copy()
    def stats(group):
        if group.empty:return []
        series=group.groupby(grouping,dropna=False,sort=True).agg(
            n=('return_pct','size'),mean_range_pct=('range_pct','mean'),
            median_range_pct=('range_pct','median'),
            mean_return_pct=('return_pct','mean'),
            up_close_fraction=('up_close','mean'),
            mean_range_points=('range_points','mean')).reset_index()
        for col in ['mean_range_pct','median_range_pct','mean_return_pct','up_close_fraction','mean_range_points']:
            series[col]=series[col].round(8)
        return series.to_dict(orient='records')
    result={'coverage':{'n_total':int(len(rows)),'n_complete':int(len(df)),
                        'n_partial':int(len(rows)-len(df))}}
    for label, grouping in [('by_session',['session']),('by_session_weekday',['session','weekday']),
                            ('by_session_month',['session','month']),('by_session_week',['session','week_start'])]:
        result[label]=stats(df)
    result['limitations']=['Clock windows may overlap. Never sum values over named sessions as if disjoint.',
                            'Session open/close are FIRST/LAST observed bar, not certified exchange auction prices.',
                            'Completed bars only; DST via IANA zones; actual exchange holidays/rolls require external calendar.',
                            'Range measures maximum excursion, not directional trading profit.']
    return result
