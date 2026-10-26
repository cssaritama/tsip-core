"""Point-in-time TWO BARRIER descriptive path research.

Signal observed at close t, prior week OHLC reference frozen at t.
Outcomes assessed only on complete subsequent daily bars t+1...t+h.
Same-bar touches are labelled AMBIGUOUS, not assigned a winner.
Missing future bars at the end of the sample are excluded from eligible cohort.
This module is NOT a strategy, entry price or probabilistic forecast.
"""
from __future__ import annotations
from collections import Counter
import math
import numpy as np
import pandas as pd

STATES = ('upper_first','lower_first','both_same_bar_ambiguous','unreached')


def _signal_rows(df: pd.DataFrame, feat: pd.DataFrame, selection: str) -> list[int]:
    """Choose historically observable in-band EOD observations."""
    if selection not in ('every_eligible_day','first_eligible_per_week'):
        raise ValueError('Unsupported cohort selection')
    lower=feat['prev_week_low']; upper=feat['prev_week_high']
    inside = (df['close'] > lower)&(df['close'] < upper)&(upper>lower)&lower.notna()&upper.notna()
    candidates=np.flatnonzero(inside.to_numpy()).tolist()
    if selection=='every_eligible_day': return candidates
    result=[];seen=set()
    for i in candidates:
        week=df.index[i].to_period('W-SUN')
        if week not in seen:
            result.append(i);seen.add(week)
    return result


def two_barrier_study(df:pd.DataFrame,feat:pd.DataFrame,horizon:int=5,
                      selection:str='first_eligible_per_week')->dict:
    """For in-band EOD close, which *frozen* previous-week barrier visits first?

    An event at t is not traded at t low/high. For resolved events the empirical
    upper_first rate is conditional on a resolved (non-ambiguous) outcome; censoring
    rate MUST accompany it. Possible overlapping forward paths are not independent.
    """
    if horizon<1 or horizon>100: raise ValueError('horizon must be 1..100')
    if not df.index.equals(feat.index):raise ValueError('features and prices misaligned')
    if not df.index.is_monotonic_increasing or not df.index.is_unique:
        raise ValueError('index must be unique increasing')
    if not {'open','high','low','close'}.issubset(df.columns):
        raise ValueError('OHLC columns missing')
    if not {'prev_week_high','prev_week_low'}.issubset(feat.columns):
        raise ValueError('previous-week barrier columns missing')
    idxs=_signal_rows(df,feat,selection)
    counts=Counter(); eligible=0; excluded_insufficient_future=0
    examples=[]
    for i in idxs:
        if i+horizon>=len(df):
            excluded_insufficient_future+=1;continue
        eligible+=1
        hi=float(feat['prev_week_high'].iloc[i]);lo=float(feat['prev_week_low'].iloc[i])
        state='unreached';bars_to_first=None
        for j in range(1,horizon+1):
            bar=df.iloc[i+j]
            # The open is the first observed price of the daily session. If it
            # already crosses a barrier its ordering is known even when the
            # other barrier is reached later. This is threshold passage, NOT
            # evidence of an executable fill at the skipped barrier price.
            if bar['open'] >= hi:
                state='upper_first';bars_to_first=j;break
            if bar['open'] <= lo:
                state='lower_first';bars_to_first=j;break
            upper=bar['high']>=hi;lower=bar['low']<=lo
            if upper or lower:
                state=('both_same_bar_ambiguous' if upper and lower else
                       'upper_first' if upper else 'lower_first')
                bars_to_first=j
                break
        counts[state]+=1
        if len(examples)<5:
            examples.append({'signal_date':str(df.index[i].date()),'prior_week_high':hi,
                             'prior_week_low':lo,'state':state,'sessions_to_touch':bars_to_first})
    resolved=counts['upper_first']+counts['lower_first']
    upper_rate=counts['upper_first']/resolved if resolved else None
    # Indicative Wilson interval ONLY; events need dependence-aware/blocked bootstrap for inferential claims.
    if resolved:
        z=1.96;p=upper_rate;n=resolved
        den=1+z*z/n
        center=(p+z*z/(2*n))/den
        half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
        ci=[round(max(0,center-half),4),round(min(1,center+half),4)]
    else:ci=None
    return {'study':'prior_week_first_passage_eod','horizon_future_sessions':horizon,
            'cohort_selection':selection,'n_eligible_observations':eligible,
            'excluded_insufficient_future':excluded_insufficient_future,
            'counts':{k:counts[k] for k in STATES},
            'upper_first_fraction_among_unambiguous_resolved':upper_rate,
            'illustrative_wilson95_conditional_not_dependency_adjusted':ci,
            'unresolved_or_ambiguous_fraction':((counts['unreached']+counts['both_same_bar_ambiguous'])/eligible if eligible else None),
            'sample_examples':examples,
            'unit':'price-only index/ETF OHLC; EOD signal',
            'warnings':['Not a forecast nor a trading signal. No transaction cost or execution model.',
                        'Same daily bar hitting both barriers remains ambiguous unless its open already crosses one barrier; a gap is not an executable fill at the level.',
                        'Legacy input features/calendar are caller-supplied. Use research_paths.run_path_research for strict calendar completeness and terminal-censor reporting.',
                        'Upper-first rate is conditional on resolved observations; censored/ambiguous are shown separately.',
                        'Events may be serially dependent; CI only indicative. No out-of-sample edge demonstrated.',
                        'Prior week barrier levels must be frozen as of EOD signal; no future information.']}
