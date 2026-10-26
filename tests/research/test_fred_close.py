import pandas as pd
import pytest
from tsip.research.fred_close import parse_fred_csv,close_only_research

def test_fred_csv_close_only_and_missing_holidays(tmp_path):
    d=pd.bdate_range('2025-01-02',periods=60)
    p=tmp_path/'fred.csv'
    pd.DataFrame({'observation_date':d.strftime('%Y-%m-%d'),'SP500':[str(5000+i) if i%7 else '.' for i in range(60)]}).to_csv(p,index=False)
    df=parse_fred_csv(p,'SP500')
    result=close_only_research(df,'SP500')
    assert 'high' not in df
    assert result['n_observations']<60
    assert result['license_review'].startswith('REQUIRED')

def test_fred_wrong_series_errors(tmp_path):
    p=tmp_path/'wrong.csv';p.write_text('DATE,SP500\n2024-01-01,5000\n')
    with pytest.raises(ValueError):parse_fred_csv(p,'NASDAQ100')
    with pytest.raises(ValueError):parse_fred_csv(p,'INVALID')
