import hashlib
import io
import zipfile

import pandas as pd
import pytest

from tsip.data.sources import SourceUnavailable, alpaca, binance_vision, coinbase, fred, stooq
from tsip.http import HTTPError


def test_coinbase_windows_cover_range_without_overlap():
    start = pd.Timestamp("2024-01-01", tz="UTC")
    end = pd.Timestamp("2024-03-01", tz="UTC")
    windows = coinbase.plan_windows(start, end, 3600)
    assert windows[0][0] == start and windows[-1][1] == end
    for (a0, a1), (b0, _) in zip(windows[:-1], windows[1:], strict=True):
        assert b0 - a1 == pd.Timedelta(hours=1)
        assert (a1 - a0) / pd.Timedelta(hours=1) + 1 <= coinbase.MAX_CANDLES


def test_coinbase_fetch_parses_newest_first_rows():
    t0 = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp())

    def getter(url):
        rows = [[t0 + 3600 * k, 99.0, 101.0, 100.0, 100.5, 3.0] for k in range(5)]
        return list(reversed(rows))

    bars = coinbase.fetch("BTC-USD", "1h", start="2024-01-01", end="2024-01-01T05:00Z", getter=getter, pause=0)
    assert list(bars.columns) == ["open", "high", "low", "close", "volume"]
    assert bars.index.is_monotonic_increasing and str(bars.index.tz) == "UTC"
    assert bars["open"].iloc[0] == 100.0 and bars["low"].iloc[0] == 99.0
    assert bars.attrs["source"] == "coinbase"


def test_coinbase_errors_become_source_unavailable():
    def getter(url):
        raise HTTPError(503, url)

    with pytest.raises(SourceUnavailable):
        coinbase.fetch(start="2024-01-01", end="2024-01-02", getter=getter, pause=0)


def _kline_row(ts, price):
    return f"{ts},{price},{price + 1},{price - 1},{price + 0.5},10,{ts + 3599999},1000,5,4,400,0"


def test_binance_parses_milliseconds_and_microseconds():
    ms = int(pd.Timestamp("2024-12-31T23:00Z").timestamp() * 1000)
    us = int(pd.Timestamp("2025-01-01T00:00Z").timestamp() * 1_000_000)
    a = binance_vision.parse_klines(_kline_row(ms, 100))
    b = binance_vision.parse_klines(_kline_row(us, 101))
    assert a.index[0] == pd.Timestamp("2024-12-31T23:00Z")
    assert b.index[0] == pd.Timestamp("2025-01-01T00:00Z")


def test_binance_header_row_is_skipped_and_checksum_verified():
    text = "open_time,open,high,low,close\n" + _kline_row(1704067200000, 100)
    assert len(binance_vision.parse_klines(text)) == 1
    payload = b"abc"
    assert binance_vision.verify_checksum(payload, hashlib.sha256(payload).hexdigest() + "  file.zip")
    assert not binance_vision.verify_checksum(payload, "0" * 64 + "  file.zip")


def test_binance_fetch_downloads_monthly_files_and_skips_missing():
    def zipped(text):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("file.csv", text)
        return buf.getvalue()

    jan = zipped(_kline_row(int(pd.Timestamp("2024-01-01").timestamp() * 1000), 100))

    def getter(url):
        if url.endswith(".CHECKSUM"):
            raise HTTPError(404, url)
        if "2024-01.zip" in url:
            return jan
        raise HTTPError(404, url)

    bars = binance_vision.fetch("BTCUSDT", "1h", start="2024-01-01", end="2024-02-15", getter=getter)
    assert len(bars) == 1 and bars.attrs["instrument"] == "BTC-USDT"


def test_alpaca_paginates_and_falls_back_to_iex(monkeypatch):
    calls = []

    def getter(url, headers):
        calls.append(url)
        if "feed=sip" in url:
            raise HTTPError(403, url, "subscription does not permit querying recent SIP data")
        if "page_token=abc" in url:
            return {
                "bars": [{"t": "2024-01-02T15:00:00Z", "o": 2, "h": 3, "l": 1, "c": 2.5, "v": 10}],
                "next_page_token": None,
            }
        return {
            "bars": [{"t": "2024-01-02T14:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}],
            "next_page_token": "abc",
        }

    bars = alpaca.fetch("SPY", "30min", start="2024-01-02", end="2024-01-03", key_id="k", secret_key="s", getter=getter)
    assert len(bars) == 2 and bars.attrs["feed"] == "iex"
    assert any("feed=iex" in c for c in calls)


def test_alpaca_requires_credentials(monkeypatch):
    for name in ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY", "APCA_API_KEY_ID", "APCA_API_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SourceUnavailable):
        alpaca.fetch("SPY", "30min", getter=lambda *a: {})


def test_fred_close_only_series_never_invents_ohlc():
    text = "observation_date,SP500\n2024-01-02,4742.83\n2024-01-03,.\n2024-01-04,4688.68\n"
    bars = fred.fetch("SP500", getter=lambda url: text.encode())
    assert len(bars) == 2 and bars.attrs["close_only"]
    assert bars[["open", "high", "low"]].isna().all().all()


def test_stooq_rejects_non_csv_payloads():
    with pytest.raises(SourceUnavailable):
        stooq.parse_csv("No data")
    frame = stooq.parse_csv("Date,Open,High,Low,Close,Volume\n2024-01-02,1,2,0.5,1.5,100\n")
    assert frame["close"].iloc[0] == 1.5


def test_binance_preserves_off_grid_bars_without_relabeling():
    on_grid = 1518166800000  # 2018-02-09 09:00:00 UTC, the hour before the outage
    off_grid = 1518168494789  # 2018-02-09 09:28:14.789 UTC, a partial bar after it
    frame = binance_vision.parse_klines(_kline_row(on_grid, 100) + "\n" + _kline_row(off_grid, 110))
    assert list(frame.index) == pd.to_datetime([on_grid, off_grid], unit="ms", utc=True).tolist()
    assert frame["volume"].sum() == 20
    assert frame["open"].tolist() == [100, 110]
