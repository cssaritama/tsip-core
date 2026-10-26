import numpy as np
import pandas as pd
import pytest
from tsip.research.sessions import load_intraday, rolling_elapsed_windows, session_rows, session_summary,Session
from tsip.research.assets import get_instrument

def make_bars(periods=400, freq='30min'):
    dates=pd.date_range('2026-10-19T00:30:00Z',periods=periods,freq=freq)
    op=7500+np.linspace(0,10,periods)
    return pd.DataFrame(dict(open=op,high=op+2,low=op-2,close=op+1,volume=100),index=dates)

def test_spx_spy_distinct_units():
    assert get_instrument('SPX')['units']=='index points'
    assert get_instrument('SPY')['units']=='USD per ETF share'
    assert get_instrument('ES')['kind']=='future'

def test_naive_timestamp_rejected(tmp_path):
    f=tmp_path/'a.csv';make_bars().reset_index().rename(columns={'index':'timestamp'}).assign(timestamp='2026-10-19T09:30:00').to_csv(f,index=False)
    with pytest.raises(ValueError,match='timezone'):load_intraday(f)

def test_rolling_utc_hour_25_not_day():
    df=make_bars()
    out=rolling_elapsed_windows(df)
    assert out.iloc[0]['w6h_count_bars']==1
    assert out.iloc[-1]['w25h_count_bars']==50
    assert out.iloc[-1]['w24h_count_bars']==48
    assert out.iloc[-1]['w25h_open_asof_close']!=out.iloc[-1]['w24h_open_asof_close']

def test_session_attribution_dst_iana():
    # 08:30 in London is 07:30 UTC in UK summer, 08:30 UTC in UK winter
    df=make_bars(1)
    points=pd.to_datetime(['2026-10-23T07:30:00Z','2026-10-26T08:30:00Z'],utc=True)
    b=pd.DataFrame({'open':[100,100],'high':[101,101],'low':[99,99],'close':[100,100]},index=points)
    r=session_rows(b,[Session('London','Europe/London','08:00','16:30')],bar_minutes=30)
    assert len(r)==2
    assert r.session.eq('London').all()
    assert r.quality_status.eq('partial').all()

def test_session_incomplete_not_in_summary():
    b=make_bars(30)
    rows=session_rows(b,bar_minutes=30)
    s=session_summary(rows)
    assert s['coverage']['n_total'] >= s['coverage']['n_complete']
    assert s['coverage']['n_partial']>0
    assert all(x['n']>=1 for x in s['by_session'])

def test_overlapping_windows_not_mutually_exclusive():
    # 02:00 UTC falls in Japan and Singapore windows on same day
    t=pd.to_datetime(['2026-10-20T02:00:00Z'],utc=True)
    b=pd.DataFrame({'open':[100], 'high':[101], 'low':[99], 'close':[100]},index=t)
    rows=session_rows(b,bar_minutes=30)
    assert set(rows.session)=={'Tokyo','Singapore'}

def test_truncated_future_does_not_modify_past_windows():
    b=make_bars()
    a=rolling_elapsed_windows(b.iloc[:150]);c=rolling_elapsed_windows(b)
    pd.testing.assert_frame_equal(a,c.loc[a.index])
