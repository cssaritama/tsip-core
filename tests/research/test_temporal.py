import pandas as pd
import numpy as np
import pytest
from tsip.research.cli import generate_synthetic,snapshot
from tsip.research.engine import load_ohlcv,temporal_features,first_touch_weekly_low_study,next_open_strategy

def test_ohlc_validation(tmp_path):
    f=tmp_path/'prices.csv';generate_synthetic(str(f),120)
    df=load_ohlcv(f)
    assert len(df)==120
    bad=df.reset_index();bad.loc[0,'high']=0
    bad.to_csv(f,index=False)
    with pytest.raises(ValueError): load_ohlcv(f)

def test_previous_week_no_future(tmp_path):
    f=tmp_path/'data.csv';generate_synthetic(str(f),300)
    df=load_ohlcv(f); out=temporal_features(df)
    for day in [df.index[80],df.index[165],df.index[280]]:
        week=day.to_period('W-SUN')
        prior=df.loc[df.index.to_period('W-SUN')==week-1]
        actual=out.loc[day,'prev_week_high']
        if len(prior): assert actual==prior.high.max()
        else: assert pd.isna(actual)

def test_prefix_invariance_future_append(tmp_path):
    f=tmp_path/'f.csv';generate_synthetic(str(f),220)
    df=load_ohlcv(f)
    now=temporal_features(df.iloc[:160])
    later=temporal_features(df)
    for col in ['prev_week_low','prev_month_high','prev_quarter_high','prev_halfyear_close','prev_year_close',
                'same_quarter_y1_low','monday_current_eod_low','current_week_high_asof_eod']:
        a=now[col]; b=later.loc[now.index,col]
        pd.testing.assert_series_equal(a,b)

def test_monday_holiday_missing(tmp_path):
    f=tmp_path/'f.csv';generate_synthetic(str(f),300)
    df=load_ohlcv(f)
    target=df.index[(df.index.weekday==0)][10]
    cut=df.drop(index=target)
    x=temporal_features(cut)
    t=target.to_period('W-SUN')
    for d in cut.index[cut.index.to_period('W-SUN')==t]:
        assert pd.isna(x.loc[d,'monday_current_eod_low'])

def test_same_weekday_uses_exact_calendar_date(tmp_path):
    f=tmp_path/'f.csv';generate_synthetic(str(f),300)
    df=load_ohlcv(f); ft=temporal_features(df)
    date=df.index[-1]
    seven=date-pd.Timedelta(days=7)
    assert ft.loc[date,'same_weekday_w1_close'] == df.loc[seven,'close']

def test_event_study_no_future_at_end(tmp_path):
    f=tmp_path/'f.csv';generate_synthetic(str(f),150)
    df=load_ohlcv(f); features=temporal_features(df)
    result=first_touch_weekly_low_study(features,5)
    assert result['n_baseline']==145
    assert 0 <= result['n_events'] <= 145
    assert 'EOD condition' in result['limitations']

def test_backtest_signal_follows_event(tmp_path):
    f=tmp_path/'f.csv';generate_synthetic(str(f),150)
    df=load_ohlcv(f);ft=temporal_features(df)
    obj=next_open_strategy(df,ft)
    assert obj['cost_bps_one_way']==2
    assert obj['ending_equity_multiple_net_costs']>0
    assert obj['gross_style']=='price_only'

def test_snapshot_synthetic_label(tmp_path):
    f=tmp_path/'f.csv';generate_synthetic(str(f),110)
    df=load_ohlcv(f);ft=temporal_features(df)
    snap=snapshot(df,ft,'synthetic')
    assert snap['synthetic'] is True
    assert snap['origin']=='synthetic'
    assert snap['n_bars']==110
