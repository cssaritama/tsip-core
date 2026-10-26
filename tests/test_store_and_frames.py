import numpy as np
import pandas as pd
import pytest

from tsip.data.schema import BarValidationError, make_bars, validate_bars
from tsip.data.store import dataset_path, merge_incremental, read_bars, write_bars
from tsip.frames import crypto_session_labels, daily_from_intraday_utc, path_units, rth_daily_from_intraday


def hourly(start, n, price=100.0):
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    close = price + np.arange(n, dtype=float)
    frame = pd.DataFrame(
        {"open": close - 0.5, "high": close + 1, "low": close - 1, "close": close, "volume": 1.0}, index=idx
    )
    return make_bars(frame, instrument="BTC-USD", source="test", timeframe="1h")


def test_store_roundtrip_and_incremental_merge(tmp_path):
    bars = hourly("2024-01-01", 48)
    path = dataset_path(tmp_path, "BTC-USD", "test", "1h")
    meta = write_bars(bars, path)
    assert meta["rows"] == 48 and len(meta["sha256"]) == 64
    loaded = read_bars(path)
    pd.testing.assert_frame_equal(loaded, bars, check_freq=False, check_names=False)
    update = hourly("2024-01-02T23:00", 3, price=500.0)
    merged = merge_incremental(loaded, update)
    assert len(merged) == 50
    assert merged.loc["2024-01-02T23:00Z", "close"] == 500.0  # newer observation wins


def test_validation_rejects_inconsistent_bars():
    bars = hourly("2024-01-01", 3)
    bars.iloc[1, bars.columns.get_loc("high")] = 1.0  # high below open/close
    with pytest.raises(BarValidationError):
        validate_bars(bars)
    assert validate_bars(bars, strict=False)["invalid_bars"] == 1


def test_daily_from_intraday_keeps_complete_days_only():
    bars = hourly("2024-01-01", 24 * 2 + 5)
    daily = daily_from_intraday_utc(bars, bars_per_day=24)
    assert list(daily.index.strftime("%Y-%m-%d")) == ["2024-01-01", "2024-01-02"]
    assert daily["open"].iloc[0] == bars["open"].iloc[0]
    assert daily["close"].iloc[0] == bars["close"].iloc[23]


def test_rth_daily_respects_new_york_daylight_saving():
    # 2024-03-08 (EST, UTC-5) and 2024-03-11 (EDT, UTC-4)
    frames = []
    for day, offset in (("2024-03-08", 5), ("2024-03-11", 4)):
        start = pd.Timestamp(f"{day}T09:30") + pd.Timedelta(hours=offset)
        idx = pd.date_range(start.tz_localize("UTC") - pd.Timedelta(hours=2), periods=20, freq="30min")
        frames.append(pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0}, index=idx))
    bars = make_bars(pd.concat(frames), instrument="SPY", source="test", timeframe="30min")
    daily, rth = rth_daily_from_intraday(bars)
    assert list(daily.index.strftime("%Y-%m-%d")) == ["2024-03-08", "2024-03-11"]
    assert (daily["n_bars"] == 13).all()
    assert rth.groupby("date")["slot"].first().tolist() == ["09:30", "09:30"]


def test_crypto_sessions_follow_local_time():
    winter = pd.DatetimeIndex(["2024-01-15T07:00Z", "2024-01-15T08:00Z", "2024-01-15T14:00Z", "2024-01-15T21:00Z"])
    summer = pd.DatetimeIndex(["2024-07-15T06:00Z", "2024-07-15T07:00Z", "2024-07-15T13:00Z", "2024-07-15T20:00Z"])
    assert list(crypto_session_labels(winter)) == ["asia", "london", "new_york", "late_us"]
    assert list(crypto_session_labels(summer)) == ["asia", "london", "new_york", "late_us"]


def test_path_units_reference_previous_close_within_period():
    bars = hourly("2024-01-01", 48)
    day = bars.index.tz_localize(None).normalize()
    units = path_units(bars, day, bars.index.hour, list(range(24)))
    assert units["ret"].shape == (2, 24)
    first = bars.iloc[0]
    assert units["ret"][0, 0] == pytest.approx(np.log(first["close"] / first["open"]))
    second = bars.iloc[1]
    assert units["hi"][0, 1] == pytest.approx(np.log(second["high"] / first["close"]))


def test_read_bars_tolerates_and_drops_off_grid_timestamps(tmp_path):
    bars = hourly("2018-02-09", 3)
    path = dataset_path(tmp_path, "BTC-USDT", "test", "1h")
    write_bars(bars, path)
    raw = pd.read_csv(path, compression="gzip")
    extra = raw.iloc[[0]].copy()
    extra.iloc[0, 0] = "2018-02-09 00:28:14.789000+00:00"
    pd.concat([raw, extra]).to_csv(path, index=False, compression="gzip")
    loaded = read_bars(path)
    assert len(loaded) == 3 and (loaded.index == loaded.index.floor("min")).all()
