import numpy as np
import pandas as pd

from tsip.cli import MARKETS
from tsip.data.schema import make_bars
from tsip.data.store import dataset_path, write_bars
from tsip.pipeline import EQUITY_FAMILIES, load_inputs


def rth_30min(symbol, start="2025-06-02", end="2025-10-24", seed=0):
    rng = np.random.default_rng(seed)
    stamps = [
        pd.date_range(d + pd.Timedelta(hours=9, minutes=30), periods=13, freq="30min", tz="America/New_York")
        for d in pd.bdate_range(start, end)
    ]
    idx = pd.DatetimeIndex(np.concatenate([s.tz_convert("UTC").tz_localize(None).to_numpy() for s in stamps]))
    idx = idx.tz_localize("UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    frame = pd.DataFrame(
        {"open": close, "high": close * 1.001, "low": close * 0.999, "close": close, "volume": 1.0}, index=idx
    )
    return make_bars(frame, instrument=symbol, source="alpaca", timeframe="30min", price_basis="adjusted:all")


def index_daily(symbol, start, end="2025-10-24", flat_until=None, source="stooq"):
    idx = pd.DatetimeIndex(pd.bdate_range(start, end), name="date")
    close = np.linspace(100, 200, len(idx))
    frame = pd.DataFrame(
        {"open": close * 0.999, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": np.nan}, index=idx
    )
    if flat_until:
        flat = idx < flat_until
        frame.loc[flat, ["open", "high", "low"]] = np.repeat(frame.loc[flat, ["close"]].to_numpy(), 3, axis=1)
    return make_bars(frame, instrument=symbol, source=source, timeframe="1d")


def test_each_family_keeps_etf_and_index_separate(tmp_path):
    raw = tmp_path / "raw"
    write_bars(rth_30min("SPY"), dataset_path(raw, "SPY", "alpaca", "30min"))
    write_bars(index_daily("SPX", "1960-01-04", flat_until="1962-01-01"), dataset_path(raw, "SPX", "stooq", "1d"))
    write_bars(index_daily("NDX", "1990-01-02"), dataset_path(raw, "NDX", "stooq", "1d"))
    inputs = {i.code: i for i in load_inputs(tmp_path)}
    assert list(inputs) == ["BTC-USD", "SPY", "SPX", "NDX"]  # QQQ intraday absent: its index still reported
    spx = inputs["SPX"]
    assert spx.daily.index[0] == pd.Timestamp("1962-01-01")  # days without a range are left out
    assert spx.quality["history"]["range_reliable_from"] == "1962-01-01"
    assert any("SPY" in note for note in spx.notes) and spx.intraday is None
    assert inputs["SPY"].intraday is not None and inputs["SPY"].daily is None
    assert inputs["BTC-USD"].intraday is None  # placeholder: no Bitcoin data stored


def test_close_only_fallback_and_placeholders(tmp_path):
    raw = tmp_path / "raw"
    fred = index_daily("SPX", "2016-01-04", source="fred")
    fred[["open", "high", "low"]] = np.nan
    fred.attrs["close_only"] = True
    write_bars(fred, dataset_path(raw, "SPX", "fred", "1d"))
    inputs = {i.code: i for i in load_inputs(tmp_path)}
    assert "SPX" in inputs and any("Close-only" in n for n in inputs["SPX"].notes)
    assert "QQQ" in inputs and inputs["QQQ"].daily is None and inputs["QQQ"].intraday is None


def test_market_names_and_aliases():
    assert MARKETS["spx"] == MARKETS["sp500"] == "sp500"
    assert MARKETS["ndx"] == MARKETS["nasdaq100"] == "nasdaq100"
    assert set(EQUITY_FAMILIES) == {"sp500", "nasdaq100"}
