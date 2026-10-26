"""Point-in-time quote comparison against cited (dated) closing observations.
NOT an official index data feed. Raw OHLC only; never adjusted close without conversion.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd


def validate_anchor(df:pd.DataFrame,symbol:str,anchor_file:str|Path,tolerance:float=0.05)->dict:
    if tolerance<0:raise ValueError('tolerance must be >=0')
    obj=json.loads(Path(anchor_file).read_text(encoding='utf8'))
    record=next((x for x in obj['references'] if x['symbol']==symbol),None)
    if record is None:raise ValueError(f'No comparison anchor for {symbol}')
    day=pd.Timestamp(obj['as_of_date'])
    if day not in df.index:return {'symbol':symbol,'status':'DATE_NOT_IN_DATA','date':str(day.date())}
    actual=float(df.loc[day,'close']);expected=float(record['close'])
    within=abs(actual-expected)<=tolerance
    return {'symbol':symbol,'status':'MATCH' if within else 'MISMATCH',
            'date':str(day.date()),'source_url':record['url'],'source_vendor':record['vendor'],
            'observed_close':actual,'reference_close':expected,'abs_difference':abs(actual-expected),
            'units':record['units'],'note':'Comparison of raw same-session close; not total return or licence verification.'}
