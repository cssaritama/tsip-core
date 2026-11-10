"""Second data source (Coinbase daily candles): storage, fingerprint, cross-check and features."""

import urllib.parse

import numpy as np
import pandas as pd
import pytest

from tsip.capstone import extra_sources as X


def _getter(price=lambda day: 100.0 + day, volume=10.0):
    def get(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        start, end = pd.Timestamp(q["start"][0]), pd.Timestamp(q["end"][0])
        days = pd.date_range(start, end, freq="D")
        rows = []
        for d in days:
            n = (d.tz_localize(None) - pd.Timestamp("2016-01-01")).days
            p = price(n)
            rows.append([int(d.timestamp()), p * 0.99, p * 1.01, p, p, volume])
        return rows[::-1]  # newest first, as the API

    return get


def _aggregate(candles, factor=1.001, volume_usd=1e6):
    rows = candles.rename(columns={"close": "cb_close"})
    return pd.DataFrame(
        {"date": rows["date"], "ticker": rows["ticker"], "close": rows["cb_close"] * factor, "volume": volume_usd}
    )


def test_download_stores_its_own_fingerprinted_folder(tmp_path):
    manifest = X.download(tmp_path, start="2026-01-01", getter=_getter())
    assert (tmp_path / "coinbase" / "candles.csv.gz").exists() and manifest["products"] == ["BTC-USD", "ETH-USD"]
    assert not (tmp_path / "manifest.json").exists()  # the main store's manifest is untouched
    candles = X.load(tmp_path)
    assert set(candles["ticker"]) == {"BTC-USD", "ETH-USD"} and (candles.groupby("ticker").size() > 300).all()
    (tmp_path / "coinbase" / "candles.csv.gz").write_bytes(b"changed")
    with pytest.raises(ValueError):
        X.load(tmp_path)


def test_crosscheck_and_features_measure_the_gap_between_sources(tmp_path):
    X.download(tmp_path, start="2026-01-01", getter=_getter())
    candles = X.load(tmp_path)
    frame = _aggregate(candles)
    cc = X.crosscheck(frame, candles).set_index("ticker")
    assert abs(cc.loc["BTC-USD", "median_abs_close_diff_bps"] - 9.99) < 0.05
    assert cc.loc["BTC-USD", "return_correlation"] > 0.999
    feats = X.new_features(frame, candles)
    assert np.allclose(feats["cb_premium_bps"], (1 / 1.001 - 1) * 1e4)
    assert feats["cb_volume_share_change_20d"].iloc[:19].isna().all()  # needs 20 days of history


def test_features_of_a_day_do_not_change_when_later_days_are_removed(tmp_path):
    X.download(tmp_path, start="2026-01-01", getter=_getter(price=lambda d: 100 + np.sin(d) * 5, volume=3.0))
    candles = X.load(tmp_path)
    frame = _aggregate(candles)
    cut = candles["date"].sort_values().iloc[60]
    full = X.new_features(frame, candles).set_index(["date", "ticker"])
    short = X.new_features(frame[frame["date"] <= cut], candles[candles["date"] <= cut]).set_index(["date", "ticker"])
    pd.testing.assert_frame_equal(full.loc[short.index], short)
