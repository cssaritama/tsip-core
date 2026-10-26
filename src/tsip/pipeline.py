"""Fetch-and-cache pipeline and report inputs from the local store."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tsip.data import quality
from tsip.data.schema import drop_invalid
from tsip.data.sources import SourceUnavailable, alpaca, binance_vision, coinbase, fred, stooq
from tsip.data.store import dataset_path, merge_incremental, read_bars, read_meta, write_bars
from tsip.frames import rth_daily_from_intraday
from tsip.report.build import InstrumentInput

OVERLAP = {"1h": pd.Timedelta(hours=48), "30min": pd.Timedelta(days=3), "1d": pd.Timedelta(days=10)}

SOURCE_INFO = {
    "coinbase": {
        "name": "Coinbase Exchange public market data",
        "url": "https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles",
        "terms": "Public endpoint; statistics are derived aggregates. Raw candles are not redistributed.",
    },
    "binance": {
        "name": "Binance public data archive",
        "url": "https://github.com/binance/binance-public-data",
        "terms": "Public archive with SHA-256 checksums; used here as an independent cross-check.",
    },
    "alpaca": {
        "name": "Alpaca Market Data API",
        "url": "https://docs.alpaca.markets/docs/about-market-data-api",
        "terms": "Account-holder access; only aggregated statistics are published.",
    },
    "stooq": {
        "name": "Stooq daily index history",
        "url": "https://stooq.com/",
        "terms": "Long daily index history used for derived statistics only; levels are not redistributed.",
    },
    "fred": {
        "name": "FRED, Federal Reserve Bank of St. Louis (index close)",
        "url": "https://fred.stlouisfed.org/",
        "terms": "Close-only series; index data copyright of its provider. Aggregates only.",
    },
}


def fetch_dataset(
    data_dir: str | Path,
    *,
    source: str,
    instrument: str,
    timeframe: str,
    start: str,
    fetcher,
) -> dict:
    """Download incrementally, validate, merge with the cache and write it back."""
    path = dataset_path(Path(data_dir) / "raw", instrument, source, timeframe)
    existing = read_bars(path) if path.exists() else None
    fetch_start = pd.Timestamp(start, tz="UTC")
    if existing is not None and len(existing):
        last = pd.Timestamp(existing.index[-1])
        last = last if last.tz is not None else last.tz_localize("UTC")
        fetch_start = max(fetch_start, last - OVERLAP.get(timeframe, pd.Timedelta(days=3)))
    new = fetcher(fetch_start)
    merged = merge_incremental(existing, new)
    if merged.attrs.get("close_only"):
        cleaned, dropped = merged, 0
    else:
        cleaned, dropped = drop_invalid(merged)
    meta = write_bars(cleaned, path, extra_meta={"invalid_bars_dropped": dropped, "fetch_start": str(fetch_start)})
    return {"path": str(path), **meta}


def fetch_bitcoin(data_dir: str | Path, *, source: str = "coinbase", start: str = "2016-01-01") -> dict:
    if source == "coinbase":
        return fetch_dataset(
            data_dir,
            source="coinbase",
            instrument="BTC-USD",
            timeframe="1h",
            start=start,
            fetcher=lambda s: coinbase.fetch("BTC-USD", "1h", start=s),
        )
    if source == "binance":
        return fetch_dataset(
            data_dir,
            source="binance",
            instrument="BTC-USDT",
            timeframe="1h",
            start=start,
            fetcher=lambda s: binance_vision.fetch("BTCUSDT", "1h", start=s),
        )
    raise ValueError(f"unknown Bitcoin source {source!r}")


# Exchange-traded families: ETF (intraday, Alpaca), index (long daily history, Stooq) and index close (FRED).
EQUITY_FAMILIES = {
    "sp500": {"etf": "SPY", "index": "SPX", "stooq": "^spx", "fred": "SP500", "name": "S&P 500"},
    "nasdaq100": {"etf": "QQQ", "index": "NDX", "stooq": "^ndx", "fred": "NASDAQ100", "name": "Nasdaq-100"},
}


def fetch_equity(data_dir: str | Path, family: str, *, source: str = "alpaca", start: str = "2016-01-01") -> dict:
    spec = EQUITY_FAMILIES[family]
    if source == "alpaca":
        etf = spec["etf"]
        return fetch_dataset(
            data_dir,
            source="alpaca",
            instrument=etf,
            timeframe="30min",
            start=start,
            fetcher=lambda s: alpaca.fetch(etf, "30min", start=s, adjustment="all"),
        )
    if source == "stooq":
        # The endpoint returns the whole history; it is re-read in full so revisions are picked up.
        return fetch_dataset(
            data_dir,
            source="stooq",
            instrument=spec["index"],
            timeframe="1d",
            start=start,
            fetcher=lambda s: stooq.fetch(spec["stooq"], start=start),
        )
    if source == "fred":
        return fetch_dataset(
            data_dir,
            source="fred",
            instrument=spec["index"],
            timeframe="1d",
            start=start,
            fetcher=lambda s: fred.fetch(spec["fred"], start=str(s.date())),
        )
    raise ValueError(f"unknown {spec['name']} source {source!r}")


def fetch_sp500(data_dir: str | Path, *, source: str = "alpaca", start: str = "2016-01-01") -> dict:
    return fetch_equity(data_dir, "sp500", source=source, start=start)


def fetch_nasdaq100(data_dir: str | Path, *, source: str = "alpaca", start: str = "2016-01-01") -> dict:
    return fetch_equity(data_dir, "nasdaq100", source=source, start=start)


def _provenance(path: Path) -> dict:
    meta = read_meta(path)
    source = meta.get("source", path.parent.name)
    keep = (
        "source",
        "instrument",
        "timeframe",
        "price_basis",
        "feed",
        "rows",
        "start",
        "end",
        "sha256",
        "written_at_utc",
        "invalid_bars_dropped",
    )
    return {**{k: meta[k] for k in keep if k in meta}, **SOURCE_INFO.get(source, {})}


def load_inputs(data_dir: str | Path) -> list[InstrumentInput]:
    raw = Path(data_dir) / "raw"
    inputs: list[InstrumentInput] = []

    # Bitcoin: Coinbase BTC-USD is primary; Binance BTC-USDT is an independent cross-check.
    cb = dataset_path(raw, "BTC-USD", "coinbase", "1h")
    bn = dataset_path(raw, "BTC-USDT", "binance", "1h")
    if cb.exists():
        bars = read_bars(cb)
        q = {"completeness": quality.hourly_completeness(bars)}
        sources = [_provenance(cb)]
        if bn.exists():
            secondary = read_bars(bn)
            q["cross_check_vs_binance_btcusdt"] = quality.cross_validate(bars, secondary)
            sources.append(_provenance(bn))
        inputs.append(InstrumentInput("BTC-USD", "crypto", intraday=bars, sources=sources, quality=q))
    elif bn.exists():
        bars = read_bars(bn)
        inputs.append(
            InstrumentInput(
                "BTC-USDT",
                "crypto",
                intraday=bars,
                sources=[_provenance(bn)],
                quality={"completeness": quality.hourly_completeness(bars)},
            )
        )
    else:
        inputs.append(InstrumentInput("BTC-USD", "crypto"))

    for spec in EQUITY_FAMILIES.values():
        inputs.extend(_equity_inputs(raw, spec))
    return inputs


def _equity_inputs(raw: Path, spec: dict) -> list[InstrumentInput]:
    """ETF intraday bars (sessions) and the index's long daily history (levels), never mixed."""
    found: list[InstrumentInput] = []
    al = dataset_path(raw, spec["etf"], "alpaca", "30min")
    if al.exists():
        bars = read_bars(al)
        daily, _ = rth_daily_from_intraday(bars)
        found.append(
            InstrumentInput(
                spec["etf"],
                "us_rth",
                intraday=bars,
                sources=[_provenance(al)],
                quality={"sessions": quality.session_completeness(daily)},
            )
        )
    st = dataset_path(raw, spec["index"], "stooq", "1d")
    fr = dataset_path(raw, spec["index"], "fred", "1d")
    if st.exists():
        daily = read_bars(st)
        info = quality.ohlc_reliability(daily)
        start = info.get("range_reliable_from")
        notes = [
            "Long daily index history for prior-period levels and calendar questions; sessions and intraday "
            f"questions use {spec['etf']}."
        ]
        if start is None:
            notes.append("No span of this history carries a genuine daily range; level studies are skipped.")
            daily = daily.iloc[0:0]
        elif start != str(pd.Timestamp(daily.index[0]).date()):
            notes.append(f"Days before {start} repeat the close as high and low and are left out.")
            daily = daily[daily.index >= pd.Timestamp(start)]
        open_from = info.get("open_reliable_from")
        if open_from and start and open_from > start:
            notes.append(f"Opens are genuine from {open_from}; gap and open-based studies start there.")
        found.append(
            InstrumentInput(
                spec["index"],
                "us_rth",
                daily=daily,
                sources=[_provenance(st)],
                quality={"sessions": quality.session_completeness(daily), "history": info},
                notes=notes,
                open_from=open_from,
            )
        )
    elif fr.exists():
        found.append(
            InstrumentInput(
                spec["index"],
                "us_rth",
                daily=read_bars(fr),
                sources=[_provenance(fr)],
                notes=["Close-only series: range, level and path studies need open, high and low."],
            )
        )
    if not found:
        found.append(InstrumentInput(spec["etf"], "us_rth"))
    return found


__all__ = ["SourceUnavailable", "fetch_bitcoin", "fetch_equity", "fetch_nasdaq100", "fetch_sp500", "load_inputs"]
