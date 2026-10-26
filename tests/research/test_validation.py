import pandas as pd
from tsip.research.validation import validate_anchor
from pathlib import Path

ANCHOR=Path(__file__).parents[2]/'examples/reference_anchors_2026_10_23.json'

def test_verified_spx_point_price():
    df=pd.DataFrame({'close':[7623.68]},index=pd.to_datetime(['2026-10-23']))
    result=validate_anchor(df,'SPX',ANCHOR)
    assert result['status']=='MATCH' and result['units']=='index points'

def test_etf_price_and_index_price_are_not_interchangeable():
    df=pd.DataFrame({'close':[7623.68]},index=pd.to_datetime(['2026-10-23']))
    result=validate_anchor(df,'SPY',ANCHOR)
    assert result['status']=='MISMATCH'

def test_absent_date_cannot_fabricate_price():
    df=pd.DataFrame({'close':[7500]},index=pd.to_datetime(['2026-10-22']))
    assert validate_anchor(df,'SPX',ANCHOR)['status']=='DATE_NOT_IN_DATA'
