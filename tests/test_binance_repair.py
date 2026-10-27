import hashlib
import io
import zipfile

import pandas as pd
import pytest

from tsip.data.schema import make_bars
from tsip.data.sources.base import SourceUnavailable
from tsip.data.sources.binance_repair import REPAIR_KEY, repair_february_2018
from tsip.data.store import merge_incremental, read_bars, write_bars


def fixture_data():
    idx = pd.to_datetime(["2018-02-01", "2018-02-09T09:28:14.789", "2018-02-15"], utc=True, format="mixed")
    bars = make_bars(
        pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.0, "volume": 100.0}, index=idx),
        instrument="BTC-USDT",
        source="binance",
        timeframe="1h",
    )
    payloads = {}
    for i, day in enumerate(pd.date_range("2018-02-09", periods=3, tz="UTC")):
        stamp = day.value // 1_000_000
        rows = f"{i * 2},10,2,{i * 2},{i * 2},{stamp},true,true\n{i * 2 + 1},12,3,{i * 2 + 1},{i * 2 + 1},{stamp + 1000},false,true\n"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("trades.csv", rows)
        payloads[f"BTCUSDT-aggTrades-{day:%Y-%m-%d}.zip"] = buffer.getvalue()

    def getter(url):
        name = url.rsplit("/", 1)[1]
        if name.endswith(".CHECKSUM"):
            return hashlib.sha256(payloads[name[:-9]]).hexdigest().encode()
        return payloads[name]

    return bars, getter


def test_repair_preserves_originals_reconstructs_and_is_idempotent(tmp_path):
    bars, getter = fixture_data()
    original = bars.copy(deep=True)
    fixed = repair_february_2018(bars, tmp_path / "evidence", getter=getter)
    pd.testing.assert_frame_equal(bars, original)
    assert len(fixed) == 5
    assert fixed.loc[pd.Timestamp("2018-02-09", tz="UTC")].tolist() == [10.0, 12.0, 10.0, 12.0, 5.0]
    assert fixed.iloc[0].tolist() == bars.iloc[0].tolist()
    assert len(list((tmp_path / "evidence").glob("*.zip"))) == 3
    assert len(list((tmp_path / "evidence").glob("*original-cached-bars.csv"))) == 1
    assert fixed.attrs[REPAIR_KEY]["aggregate_trades"] == 6
    again = repair_february_2018(fixed, tmp_path, getter=lambda _: pytest.fail("must not redownload"))
    pd.testing.assert_frame_equal(again, fixed)
    path = tmp_path / "bars.csv.gz"
    write_bars(fixed, path)
    loaded = read_bars(path)
    new = bars.iloc[[-1]].copy()
    merged = merge_incremental(loaded, new)
    assert merged.attrs[REPAIR_KEY] == fixed.attrs[REPAIR_KEY]


def test_repair_recovers_filtered_cache_without_off_grid_rows(tmp_path):
    bars, getter = fixture_data()
    bars = bars.iloc[[0, 2]].copy()
    fixed = repair_february_2018(bars, tmp_path, getter=getter)
    assert len(fixed) == 5
    assert fixed.attrs[REPAIR_KEY]["source_cached_rows"] == 0


def test_repair_bad_checksum_keeps_input_unmodified(tmp_path):
    bars, getter = fixture_data()
    original = bars.copy(deep=True)

    def broken(url):
        return b"0" * 64 if url.endswith(".CHECKSUM") else getter(url)

    with pytest.raises(SourceUnavailable, match="checksum mismatch"):
        repair_february_2018(bars, tmp_path, getter=broken)
    pd.testing.assert_frame_equal(bars, original)


def test_repair_duplicate_trade_ids_fail_closed(tmp_path):
    bars, getter = fixture_data()

    def duplicate(url):
        payload = getter(url)
        if url.endswith(".CHECKSUM"):
            return hashlib.sha256(duplicate(url[:-9])).hexdigest().encode()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            text = archive.read(archive.namelist()[0]).decode()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("trades.csv", text + text.splitlines()[0] + "\n")
        return buffer.getvalue()

    with pytest.raises(SourceUnavailable, match="aggregate trade identities"):
        repair_february_2018(bars, tmp_path, getter=duplicate)


def test_vendor_revision_invalidates_cached_repair_marker(tmp_path):
    bars, getter = fixture_data()
    fixed = repair_february_2018(bars, tmp_path, getter=getter)
    revised = bars.iloc[[1]].copy()
    merged = merge_incremental(fixed, revised)
    assert REPAIR_KEY not in merged.attrs
    repaired_again = repair_february_2018(merged, tmp_path, getter=getter)
    pd.testing.assert_frame_equal(repaired_again, fixed)
