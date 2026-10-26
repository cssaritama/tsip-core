import numpy as np
import pandas as pd
import pytest
from tsip.research.cli import generate_synthetic
from tsip.research.engine import load_ohlcv
from tsip.research.cross_market import compare_etfs
from tsip.research.assets import get_instrument


def fixture_pairs(tmp_path):
    spy=tmp_path/'spy.csv';qqq=tmp_path/'qqq.csv'
    generate_synthetic(str(spy),300,seed=33)
    generate_synthetic(str(qqq),300,seed=34)
    return {'SPY':load_ohlcv(spy),'QQQ':load_ohlcv(qqq)}


def test_assets_are_not_interchangeable():
    assert get_instrument('NDX')['kind']=='index'
    assert get_instrument('QQQ')['units']=='USD per ETF share'
    assert get_instrument('NQ')['kind']=='future'
    assert get_instrument('SPY')['units']!=get_instrument('SPX')['units']


def test_pair_report_is_honestly_labeled(tmp_path):
    rep=compare_etfs(fixture_pairs(tmp_path))
    assert rep['n_overlapping_return_days']==299
    assert rep['label']=='DESCRIPTIVE_EOD_PRICE_ONLY_NOT_PREDICTIVE'
    assert rep['assets']['SPY']['normalized_index_100'][0] > 0
    assert rep['assets']['QQQ']['instrument']['code']=='QQQ'
    assert len(rep['dates_90'])==90
    assert -1 <= rep['pearson_daily_returns'] <= 1


def test_no_forward_fill_when_dates_mismatch(tmp_path):
    frames=fixture_pairs(tmp_path)
    removed=frames['QQQ'].index[100]
    frames['QQQ']=frames['QQQ'].drop(index=removed)
    rep=compare_etfs(frames)
    assert rep['n_overlapping_return_days']==298
    assert str(removed.date()) not in rep['dates_90']


def test_pair_report_prefix_invariance(tmp_path):
    frames=fixture_pairs(tmp_path)
    a=compare_etfs({k:v.iloc[:180] for k,v in frames.items()})
    b=compare_etfs(frames)
    # Values at a historical as-of must not change when later data is added.
    c=compare_etfs({k:v.loc[:pd.Timestamp(a['as_of_eod'])] for k,v in frames.items()})
    assert a==c
    assert b['as_of_eod']!=a['as_of_eod']


def test_reject_wrong_assets(tmp_path):
    frames=fixture_pairs(tmp_path)
    with pytest.raises(ValueError):compare_etfs({'SPY':frames['SPY'],'SPX':frames['QQQ']})


def test_reject_insufficient_overlap(tmp_path):
    frames=fixture_pairs(tmp_path)
    shifted=frames['QQQ'].copy();shifted.index=shifted.index+pd.DateOffset(years=30)
    with pytest.raises(ValueError,match='overlapping'):compare_etfs({'SPY':frames['SPY'],'QQQ':shifted})


def test_price_only_not_total_return(tmp_path):
    rep=compare_etfs(fixture_pairs(tmp_path))
    assert 'excludes dividends' in rep['returns_method']
    assert rep['assets']['SPY']['weekly_low_event_research']['horizon_sessions']==5
