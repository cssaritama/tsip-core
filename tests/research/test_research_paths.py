import json
import numpy as np
import pandas as pd
import pytest

from tsip.research.research_paths import previous_complete_week_features, run_path_research, _label


def fixture(periods=45, start='2023-01-02'):
    dates=pd.bdate_range(start, periods=periods)
    calendar=pd.bdate_range(dates[0]-pd.Timedelta(days=28), dates[-1]+pd.Timedelta(days=7))
    frame=pd.DataFrame({'open':100., 'high':110., 'low':90., 'close':100.}, index=dates)
    return frame,calendar


def test_calendar_rejects_missing_sessions_and_extra_weekends():
    df,calendar=fixture()
    with pytest.raises(ValueError,match='calendar mismatch'):
        run_path_research(df.drop(df.index[8]),calendar,bootstrap_reps=100)
    with pytest.raises(ValueError,match='calendar mismatch'):
        run_path_research(pd.concat([df,pd.DataFrame({'open':[100.],'high':[110.],'low':[90.],'close':[100.]},index=pd.to_datetime(['2023-01-07']))]).sort_index(),calendar,bootstrap_reps=100)


def test_initial_partial_week_excluded_but_holiday_week_is_complete():
    df,calendar=fixture(start='2023-01-04')
    features=previous_complete_week_features(df,calendar)
    assert features.loc['2023-01-09':'2023-01-13'].prev_week_high.isna().all()
    assert features.loc['2023-01-16','prev_week_high']==110
    df,calendar=fixture()
    holiday=pd.Timestamp('2023-01-02')
    df=df.drop(holiday);calendar=calendar.drop(holiday)
    features=previous_complete_week_features(df,calendar)
    assert features.loc['2023-01-09','prev_week_high']==110


def test_future_changes_cannot_move_reference_or_control():
    df,calendar=fixture()
    one=run_path_research(df,calendar,horizons=(1,),bootstrap_reps=100)
    modified=df.copy()
    modified.loc['2023-01-24':,'high']=400.
    two=run_path_research(modified,calendar,horizons=(1,),bootstrap_reps=100)
    event1=one['horizons']['1']['events'][0]
    event2=two['horizons']['1']['events'][0]
    assert event1==event2


def test_truncation_reports_right_censored_and_early_resolved_separately():
    df,calendar=fixture(periods=12)
    # Jan 16 has a selected signal with only one subsequent session available.
    obj=run_path_research(df,calendar,horizons=(5,),bootstrap_reps=100)
    last=obj['horizons']['5']['events'][-1]
    assert last['event']['complete_horizon'] is False
    # Default next day spans both barriers: observed ambiguous despite truncation.
    assert last['event']['outcome']=='both_same_bar_ambiguous'
    df.iloc[-1]=[100,105,95,100]
    obj=run_path_research(df,calendar,horizons=(5,),bootstrap_reps=100)
    assert obj['horizons']['5']['events'][-1]['event']['outcome']=='right_censored'
    primary=obj['horizons']['5']['summary']
    assert primary['excluded_from_primary_by_date_only']==1
    assert primary['primary_complete_horizon']['n']==1


def test_gap_order_and_intrabar_ambiguity_are_distinct():
    df,calendar=fixture(periods=10)
    df.iloc[1]=[112,115,85,100]
    upper=_label(df,0,90,110,1)
    assert upper['outcome']=='upper_first'
    assert upper['opening_price_already_beyond_barrier'] is True
    df.iloc[1]=[88,115,85,100]
    assert _label(df,0,90,110,1)['outcome']=='lower_first'
    df.iloc[1]=[100,115,85,100]
    assert _label(df,0,90,110,1)['outcome']=='both_same_bar_ambiguous'


def test_split_purges_full_horizons_crossing_boundary():
    df,calendar=fixture()
    obj=run_path_research(df,calendar,horizons=(5,),cutoff='2023-01-16',bootstrap_reps=100)
    events=obj['horizons']['5']['events']
    assert events[0]['signal_date']=='2023-01-09'
    assert events[0]['partition']=='purged_boundary'
    assert events[1]['partition']=='later_descriptive_holdout'


def test_block_bootstrap_reproducible_and_serializable():
    df,calendar=fixture(periods=230)
    rng=np.random.default_rng(5)
    movement=np.cumsum(rng.normal(0,.7,len(df)))
    df['close']=100+movement;df['open']=df.close
    df['high']=df.close+1;df['low']=df.close-1
    one=run_path_research(df,calendar,horizons=(1,5),block_weeks=4,bootstrap_reps=100)
    two=run_path_research(df,calendar,horizons=(1,5),block_weeks=4,bootstrap_reps=100)
    assert one==two
    assert one['horizons']['5']['summary']['intervals_primary']['status']=='descriptive_dependency_aware_interval'
    json.dumps(one,allow_nan=False)


def test_requires_real_calendar_span_and_finite_enclosed_prices():
    df,calendar=fixture()
    with pytest.raises(ValueError,match='calendar must cover'):
        run_path_research(df,df.index,bootstrap_reps=100)
    df.loc[df.index[3],'close']=float('inf')
    with pytest.raises(ValueError,match='finite positive'):
        run_path_research(df,calendar,bootstrap_reps=100)


def test_complete_nohit_is_not_terminal_censoring():
    df,calendar=fixture()
    df[['high','low']]=[105,95]
    result=_label(df,0,90,110,5)
    assert result['outcome']=='unreached'
    assert result['complete_horizon'] is True
    assert _label(df,len(df)-1,90,110,5)['outcome']=='right_censored'
