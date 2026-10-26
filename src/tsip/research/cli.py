"""CLI: synthetic data generation (demo) and local licensed CSV analysis."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from .engine import load_ohlcv,temporal_features,first_touch_weekly_low_study,next_open_strategy
from .assets import get_instrument
from .validation import validate_anchor
from .sessions import load_intraday,session_rows,session_summary,rolling_elapsed_windows
from .cross_market import compare_etfs
from .conditional_paths import two_barrier_study
from .fred_close import parse_fred_csv,close_only_research

def generate_synthetic(path:str,n:int,seed:int=33)->None:
    if n<40: raise ValueError('n must be >=40')
    rng=np.random.default_rng(seed)
    dates=pd.bdate_range(end='2026-10-23',periods=n)
    r=rng.normal(0.00028,0.011,n)
    close=450*np.exp(np.cumsum(r))
    opening=close*np.exp(rng.normal(0,0.003,n))
    high=np.maximum(close,opening)*(1+rng.uniform(0.001,0.009,n))
    low=np.minimum(close,opening)*(1-rng.uniform(0.001,0.009,n))
    vol=rng.integers(35_000_000,90_000_000,n)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(dict(date=dates,open=opening,high=high,low=low,close=close,volume=vol)).to_csv(path,index=False)



def generate_synthetic_intraday(path:str,days:int=35,minutes:int=30,seed:int=33)->None:
    """Synthetic hourly/half-hour bars for QA, absolutely NOT real futures data."""
    if minutes not in (5,15,30,60):raise ValueError('minutes must be 5/15/30/60')
    if days<2:raise ValueError('days must be >=2')
    dates=pd.date_range('2026-09-01T00:00:00Z',periods=days*24*60//minutes,freq=f'{minutes}min')
    dates=dates[dates.dayofweek<5]
    rng=np.random.default_rng(seed)
    steps=rng.normal(0,1.7,len(dates));openp=7650+np.cumsum(steps)
    closep=openp+rng.normal(0,1,len(dates))
    hi=np.maximum(openp,closep)+rng.uniform(.5,3,len(dates))
    lo=np.minimum(openp,closep)-rng.uniform(.5,3,len(dates))
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame({'timestamp':dates.strftime('%Y-%m-%dT%H:%M:%SZ'),
                  'open':openp,'high':hi,'low':lo,'close':closep,
                  'volume':rng.integers(100,20000,len(dates))}).to_csv(dest,index=False)

def serialize(v):
    if pd.isna(v): return None
    if isinstance(v, (bool,np.bool_)): return bool(v)
    if isinstance(v, (np.integer,int)): return int(v)
    if isinstance(v, (np.floating,float)): return round(float(v),5)
    return str(v)

def snapshot(df:pd.DataFrame, f:pd.DataFrame,origin:str,symbol:str="SPY")->dict:
    latest=f.iloc[-1]
    levels={}
    for prefix in ('prev_day','monday_current_eod','monday_previous_week','prev_week','prev_month','prev_quarter','prev_halfyear','prev_year','same_quarter_y1','same_month_y1','same_halfyear_y1'):
        levels[prefix] = {k:serialize(latest.get(f'{prefix}_{k}')) for k in ('open','high','low','close')}
    weekday_names=['Monday','Tuesday','Wednesday','Thursday','Friday']
    by_weekday=[]
    for wd in range(5):
        sub=f.loc[f.weekday==wd]
        by_weekday.append({'weekday':weekday_names[wd],'n':len(sub),
                           'mean_range_pct':serialize(sub.range_pct.mean()),
                           'mean_return_pct':serialize(sub.return_1d.mean()),
                           'median_range_pct':serialize(sub.range_pct.median())})
    data={'version':'v0.1.0-demo','origin':origin,'synthetic':origin=='synthetic',
          'data_license_status':'NOT_VERIFIED' if origin!='synthetic' else 'SYNTHETIC_NO_MARKET_DATA',
          'as_of_eod_date':str(df.index[-1].date()),'n_bars':len(df),
          'instrument_label':'DEMO' if origin=='synthetic' else symbol, 'instrument':get_instrument(symbol),
          'quote_delay':'NOT_LIVE_EOD', 'vendor':'UNSPECIFIED_CSV',
          'last_close':serialize(latest.close),'last_range_pct':serialize(latest.range_pct),
          'levels':levels,'weekday_summary':by_weekday,
          'studies':[first_touch_weekly_low_study(f,n) for n in (1,3,5,10,20)],
          'prototype_backtest':next_open_strategy(df,f),
          'last_90_dates':[str(x.date()) for x in df.index[-90:]],
          'last_90_closes':[serialize(x) for x in df.close.iloc[-90:]],
          'disclaimer':'This application is a research prototype. Samples and indicators are descriptive; no guarantee of predicted price paths, broker execution or profit.'}
    return data

def main():
    p=argparse.ArgumentParser(description='TSIP research toolkit (legacy studies)')
    sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('synthetic');s.add_argument('--out',required=True);s.add_argument('--n',type=int,default=900)
    ssi=sub.add_parser('synthetic-intraday');ssi.add_argument('--out',required=True);ssi.add_argument('--days',type=int,default=35);ssi.add_argument('--bar-minutes',type=int,default=30)
    cm=sub.add_parser('compare-markets',help='Compare SPY and QQQ EOD from authorized local CSVs')
    cm.add_argument('--spy',required=True);cm.add_argument('--qqq',required=True)
    cm.add_argument('--out',required=True)
    cm.add_argument('--origin',choices=['synthetic','licensed-research','user-provided'],default='synthetic')
    a=sub.add_parser('analyze');a.add_argument('--csv',required=True);a.add_argument('--out',required=True)
    a.add_argument('--origin',choices=['synthetic','licensed-research','user-provided'],default='synthetic')
    a.add_argument('--symbol',choices=['SPX','SPY','ES','CFD_SP500','NDX','QQQ','NQ'],default='SPY')
    a.add_argument('--check-anchor',default=None,help='Optional JSON file containing externally verified dated quote reference')
    si=sub.add_parser('sessions');si.add_argument('--csv',required=True);si.add_argument('--out',required=True)
    si.add_argument('--symbol',choices=['ES','NQ'],required=True);si.add_argument('--bar-minutes',type=int,default=30)
    si.add_argument('--origin',choices=['synthetic','user-provided'],default='user-provided')
    ps=sub.add_parser('path-study',help='Descriptive frozen previous-week two-barrier study from local OHLC CSV')
    ps.add_argument('--csv',required=True);ps.add_argument('--out',required=True)
    ps.add_argument('--symbol',choices=['SPX','SPY','ES','NDX','QQQ','NQ'],default='SPY')
    ps.add_argument('--horizon',type=int,default=5)
    ps.add_argument('--selection',choices=['first_eligible_per_week','every_eligible_day'],default='first_eligible_per_week')
    ps.add_argument('--origin',choices=['synthetic','licensed-research','user-provided'],default='synthetic')
    fc=sub.add_parser('fred-close',help='Local FRED CSV close-only research; NEVER OHLC')
    fc.add_argument('--csv',required=True);fc.add_argument('--series',choices=['SP500','NASDAQ100'],required=True)
    fc.add_argument('--out',required=True)
    args=p.parse_args()
    if args.cmd=='fred-close':
        frame=parse_fred_csv(args.csv,args.series)
        summary=close_only_research(frame,args.series)
        out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf8')
        print('FRED close-only private research (rights not cleared):',out,'observations=',len(frame));return
    if args.cmd=='path-study':
        df=load_ohlcv(args.csv);ft=temporal_features(df)
        report=two_barrier_study(df,ft,args.horizon,args.selection)
        report.update({'instrument':get_instrument(args.symbol),'origin':args.origin,
            'synthetic':args.origin=='synthetic','redistribution_rights':'NOT_VERIFIED' if args.origin!='synthetic' else 'SYNTHETIC',
            'start':str(df.index[0].date()),'end':str(df.index[-1].date())})
        out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf8')
        print('Two-barrier descriptive path study:',out,'events=',report['n_eligible_observations']);return
    if args.cmd=='compare-markets':
        report=compare_etfs({'SPY':load_ohlcv(args.spy),'QQQ':load_ohlcv(args.qqq)})
        report.update({'origin':args.origin,'synthetic':args.origin=='synthetic',
          'redistribution_rights':'NOT_VERIFIED' if args.origin!='synthetic' else 'SYNTHETIC'})
        out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf8')
        print('EOD pair comparison:',out,'common_return_days=',report['n_overlapping_return_days']);return
    if args.cmd=='synthetic-intraday':
        generate_synthetic_intraday(args.out,args.days,args.bar_minutes)
        print('SYNTHETIC intraday generated:',args.out);return
    if args.cmd=='sessions':
        bars=load_intraday(args.csv)
        rows=session_rows(bars,bar_minutes=args.bar_minutes)
        summary=session_summary(rows)
        summary.update({'instrument':get_instrument(args.symbol),'origin':args.origin,
                        'synthetic':args.origin=='synthetic',
                        'source_license_status':'SYNTHETIC' if args.origin=='synthetic' else 'UNVERIFIED','data_frequency':'intraday',
                        'as_of_utc':str(bars.index[-1]),'bar_minutes':args.bar_minutes,
                        'rolling_windows_tested':[6,12,18,24,25]})
        rolling=rolling_elapsed_windows(bars)
        summary['last_window_asof_bar_close']={k:serialize(v) for k,v in rolling.iloc[-1].items()}
        out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
        print(f'{args.symbol} session research summary created:',out,'rows=',len(rows));return
    if args.cmd=='synthetic':
        generate_synthetic(args.out,args.n)
        print('SYNTHETIC generated:',args.out)
    else:
        df=load_ohlcv(args.csv)
        f=temporal_features(df)
        data=snapshot(df,f,args.origin,args.symbol)
        if args.check_anchor:
            data['anchor_reconciliation']=validate_anchor(df,args.symbol,args.check_anchor)
        dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
        print('Research snapshot created:',args.out,'origin=',args.origin,'bars=',len(df))
if __name__=='__main__': main()
