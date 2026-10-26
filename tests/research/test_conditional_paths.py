import pandas as pd
import numpy as np
import pytest
from tsip.research.conditional_paths import two_barrier_study
from tsip.research.cli import generate_synthetic
from tsip.research.engine import load_ohlcv,temporal_features

def _fabricated(hi_list,lo_list,week_high=110,week_low=90):
    dates=pd.bdate_range('2026-01-05',periods=len(hi_list))
    df=pd.DataFrame({'open':[100]*len(dates),'high':hi_list,'low':lo_list,'close':[100]*len(dates)},index=dates)
    ft=pd.DataFrame({'prev_week_high':[week_high]*len(dates),'prev_week_low':[week_low]*len(dates)},index=dates)
    return df,ft

def test_upper_hit_after_signal_close_only():
    df,ft=_fabricated([100,113,100,100],[99,99,99,99])
    obj=two_barrier_study(df,ft,1,'every_eligible_day')
    assert obj['counts']['upper_first']==1
    assert obj['n_eligible_observations']==3
    assert obj['excluded_insufficient_future']==1

def test_both_barriers_same_bar_not_decidable():
    df,ft=_fabricated([100,112,100,100],[99,88,99,99])
    obj=two_barrier_study(df,ft,1,'every_eligible_day')
    assert obj['counts']['both_same_bar_ambiguous']==1
    assert obj['counts']['upper_first']==0

def test_censoring_instead_of_false_binary():
    df,ft=_fabricated([101,102,103,102],[98,97,99,98])
    obj=two_barrier_study(df,ft,2,'every_eligible_day')
    assert obj['counts']['unreached']==2
    assert obj['upper_first_fraction_among_unambiguous_resolved'] is None

def test_weekly_one_event_sampling(tmp_path):
    dest=tmp_path/'sample.csv';generate_synthetic(str(dest),120)
    df=load_ohlcv(dest);feat=temporal_features(df)
    single=two_barrier_study(df,feat,3,'first_eligible_per_week')
    every=two_barrier_study(df,feat,3,'every_eligible_day')
    assert single['n_eligible_observations']<=every['n_eligible_observations']

def test_future_prices_cannot_change_earlier_study_status_when_not_reached():
    df,ft=_fabricated([101,102,103,104,106,109],[99,98,99,97,97,97])
    short=two_barrier_study(df,ft,2,'every_eligible_day')
    assert short['counts']['upper_first']==0
    with pytest.raises(ValueError):two_barrier_study(df,ft,0)

def test_feature_alignment_check():
    df,ft=_fabricated([100]*4,[99]*4)
    with pytest.raises(ValueError):two_barrier_study(df,ft.iloc[1:])

def test_opening_gap_orders_dual_touch_bar_without_assuming_barrier_fill():
    df,ft=_fabricated([100,115,100],[99,85,99])
    df.loc[df.index[1], 'open']=112
    obj=two_barrier_study(df,ft,1,'every_eligible_day')
    assert obj['counts']['upper_first']==1
    assert obj['counts']['both_same_bar_ambiguous']==0
