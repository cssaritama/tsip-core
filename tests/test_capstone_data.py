"""Specification 0028, R1 and R6: one frame, and nothing known before it was public."""

import numpy as np
import pandas as pd
import pytest

from tsip.capstone import data


def _prices(start="2023-12-25", days=60):
    dates = pd.date_range(start, periods=days, freq="D")
    rows = []
    for ticker in dict.fromkeys((*data.UNIVERSE, "^GSPC", "^GDAXI", "BTC-USD")):
        for i, d in enumerate(dates):
            if not ticker.endswith("-USD") and d.dayofweek >= 5:
                continue  # equities and indices skip weekends
            value = float(d.toordinal())  # the close encodes its own date
            rows.append((d, ticker, value, value + 1, value - 1, value, value, 100 + i))
    frame = pd.DataFrame(rows, columns=data.PRICE_COLUMNS)
    return frame


def _fred():
    daily = pd.DataFrame({"date": pd.date_range("2023-12-01", "2024-03-31", freq="B"), "series": "DGS10"})
    daily["value"] = [d.toordinal() for d in daily["date"]]
    monthly = pd.DataFrame({"date": pd.to_datetime(["2023-12-01", "2024-01-01", "2024-02-01"]), "series": "CPIAUCSL"})
    monthly["value"] = [1.0, 2.0, 3.0]
    return pd.concat([daily, monthly], ignore_index=True)


def test_reference_closes_come_from_earlier_dates_only():
    frame = data.unified_frame(_prices(), _fred())
    for col in ("ref_close_snp500", "ref_close_dax", "ref_close_btc_usd"):
        known = frame[col].notna()
        assert known.any()
        assert (frame.loc[known, col] < frame.loc[known, "date"].map(lambda d: d.toordinal())).all()


def test_monthly_cpi_is_used_only_after_its_release_lag():
    frame = data.unified_frame(_prices(), _fred())
    spy = frame[frame["ticker"] == "SPY"].set_index("date")["macro_cpi"]
    # January 2024 CPI (value 2.0) is public from 2024-01-31 + 20 days = 2024-02-20.
    assert spy.loc["2024-02-16"] == 1.0
    assert spy.loc["2024-02-20"] == 2.0


def test_daily_rates_are_used_from_the_next_day():
    frame = data.unified_frame(_prices(), _fred())
    spy = frame[frame["ticker"] == "SPY"].set_index("date")["macro_ten_year_yield"]
    for d, value in spy.dropna().items():
        assert value < d.toordinal()


def test_rows_do_not_change_when_later_data_is_removed():
    full = data.unified_frame(_prices(), _fred())
    cut = pd.Timestamp("2024-01-20")
    prices = _prices()
    fred = _fred()
    short = data.unified_frame(prices[prices["date"] <= cut], fred[fred["date"] <= cut])
    a = full[full["date"] <= cut].reset_index(drop=True)
    b = short.reset_index(drop=True)
    pd.testing.assert_frame_equal(a[b.columns], b, check_dtype=False)


def test_one_row_per_ticker_and_date():
    frame = data.unified_frame(_prices(), _fred())
    assert set(frame["ticker"]) == set(data.UNIVERSE)
    assert not frame.duplicated(["ticker", "date"]).any()
    assert frame.groupby("ticker")["date"].apply(lambda s: s.is_monotonic_increasing).all()


def test_store_round_trip_and_fingerprint(tmp_path):
    manifest = data.save(tmp_path, _prices(), _fred(), source="synthetic")
    prices, fred, loaded = data.load_store(tmp_path)
    assert loaded["sha256"] == manifest["sha256"]
    assert len(prices) == manifest["rows"]["prices"]
    frame, summary = data.load("file", tmp_path)
    assert summary["unified_rows"] == len(frame)
    (tmp_path / "prices.csv.gz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="fingerprint"):
        data.load_store(tmp_path)


def test_file_mode_without_stored_data_says_what_to_do(tmp_path):
    with pytest.raises(FileNotFoundError, match="--mode download"):
        data.load("file", tmp_path)


def test_missing_universe_ticker_is_an_error():
    prices = _prices()
    with pytest.raises(ValueError, match="No prices"):
        data.unified_frame(prices[prices["ticker"] != "GLD"], _fred())


def test_fred_missing_marker_is_dropped():
    fred = pd.DataFrame({"date": ["2024-01-01", "2024-01-02"], "series": "DGS10", "value": [".", "4.1"]})
    out = data.normalise_fred(fred)
    assert len(out) == 1 and np.isclose(out["value"].iloc[0], 4.1)


def test_bars_of_the_download_date_are_dropped():
    prices = _prices()
    out = data.drop_unfinished(prices, "2024-01-20T00:37:33+00:00")
    assert out["date"].max() == pd.Timestamp("2024-01-19")
    assert (out["date"] < pd.Timestamp("2024-01-20")).all()


def test_a_store_used_by_a_logged_test_read_is_never_overwritten(tmp_path):
    import json

    import pandas as pd
    import pytest

    from tsip.capstone import data

    prices = pd.DataFrame({"date": ["2024-01-02"], "ticker": ["SPY"], "close": [1.0]})
    fred = pd.DataFrame({"date": ["2024-01-02"], "series": ["DTB3"], "value": [4.0]})
    log = tmp_path / "runs.json"
    store = tmp_path / "store"
    manifest = data.save(store, prices, fred, source="t", log=log)
    data.save(store, prices, fred, source="t", log=log)  # not protected yet: overwriting is allowed
    log.write_text(json.dumps([{"kind": "registered", "data_sha256": manifest["sha256"]}]))
    with pytest.raises(SystemExit):
        data.save(store, prices, fred, source="t", log=log)
    data.save(tmp_path / "other", prices, fred, source="t", log=log)  # another folder is fine
