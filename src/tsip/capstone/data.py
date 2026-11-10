"""Unified daily data for the course project (specification 0028, R1 and R6).

Two modes: ``download`` reads the course's sources (yfinance prices, FRED macro series) and stores
them; ``file`` reads the stored copy, so the workflow can be repeated without a network. Data files
are never committed: the store defaults to ``~/tsip_capstone_data`` (override with
``TSIP_CAPSTONE_DATA``).

Every value attached to a row must have been public at that row's close:

* reference markets close at different times (Frankfurt before New York, crypto at midnight UTC),
  so a row of date t only sees reference closes of dates strictly before t;
* macro series are dated by the period they describe, not by their release, so each series is
  shifted by a conservative release lag before it is joined (``MACRO_SERIES``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

UNIVERSE = ("SPY", "QQQ", "GLD", "BTC-USD", "ETH-USD")

# Reference markets used for the course's growth features; column suffix in the unified frame.
REFERENCES = {
    "^GSPC": "snp500",
    "^NDX": "ndx",
    "^GDAXI": "dax",
    "GC=F": "gold",
    "CL=F": "wti_oil",
    "BZ=F": "brent_oil",
    "BTC-USD": "btc_usd",
    "^VIX": "vix",
}


@dataclass(frozen=True)
class MacroSeries:
    name: str
    frequency: str  # "daily" or "monthly"
    release_lag_days: int  # calendar days after the observation date (daily) or after the period's end (monthly)


# Conservative release lags. Daily rates are used from the next calendar day; the effective federal
# funds monthly average from the 3rd day after the month ends; CPI from the 20th day after it ends
# (it is usually released in the second or third week of the next month).
MACRO_SERIES = {
    "DGS10": MacroSeries("ten_year_yield", "daily", 1),
    "DTB3": MacroSeries("tbill_3m", "daily", 1),
    "FEDFUNDS": MacroSeries("fed_funds", "monthly", 3),
    "CPIAUCSL": MacroSeries("cpi", "monthly", 20),
}

PRICE_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


def default_store() -> Path:
    return Path(os.environ.get("TSIP_CAPSTONE_DATA", Path.home() / "tsip_capstone_data"))


# ---------------------------------------------------------------- downloads (network)


def download_prices(tickers: list[str], start: str) -> pd.DataFrame:
    """Daily OHLCV from yfinance, unadjusted prices plus the adjusted close, in long format."""
    import yfinance as yf  # optional dependency: pip install -e ".[capstone]"

    frames = []
    for ticker in tickers:
        raw = yf.download(ticker, start=start, auto_adjust=False, progress=False, actions=False)
        if raw.empty:
            raise RuntimeError(f"No data returned for {ticker}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        frame = raw.rename(columns=str.lower).rename(columns={"adj close": "adj_close"}).reset_index()
        frame = frame.rename(columns={"Date": "date", "index": "date"})
        frame["ticker"] = ticker
        frames.append(frame[PRICE_COLUMNS])
    return normalise_prices(pd.concat(frames, ignore_index=True))


def download_fred(series_ids: list[str]) -> pd.DataFrame:
    """FRED series from the public CSV endpoint (no key), in long format."""
    frames = []
    for sid in series_ids:
        raw = pd.read_csv(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
        raw.columns = ["date", "value"]
        raw["series"] = sid
        frames.append(raw)
    return normalise_fred(pd.concat(frames, ignore_index=True))


# ---------------------------------------------------------------- normalisation


def normalise_prices(prices: pd.DataFrame) -> pd.DataFrame:
    out = prices[PRICE_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None).dt.normalize()
    for col in PRICE_COLUMNS[2:]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out.drop_duplicates(["ticker", "date"], keep="last")
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def normalise_fred(fred: pd.DataFrame) -> pd.DataFrame:
    out = fred[["date", "series", "value"]].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["value"] = pd.to_numeric(out["value"], errors="coerce")  # FRED writes "." for missing days
    out = out.dropna(subset=["value"]).drop_duplicates(["series", "date"], keep="last")
    return out.sort_values(["series", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------- point-in-time joins


def macro_available(fred: pd.DataFrame) -> pd.DataFrame:
    """Wide frame of macro values indexed by the first date each value was public."""
    columns = []
    for sid, spec in MACRO_SERIES.items():
        rows = fred[fred["series"] == sid]
        if rows.empty:
            continue
        observed = rows.set_index("date")["value"]
        if spec.frequency == "monthly":
            period_end = observed.index + pd.offsets.MonthEnd(0)
            available = period_end + pd.Timedelta(days=spec.release_lag_days)
        else:
            available = observed.index + pd.Timedelta(days=spec.release_lag_days)
        series = pd.Series(observed.to_numpy(), index=available, name=f"macro_{spec.name}")
        columns.append(series[~series.index.duplicated(keep="last")])
    if not columns:
        return pd.DataFrame()
    return pd.concat(columns, axis=1).sort_index().ffill()


def _asof(dates: pd.Series, values: pd.DataFrame, *, strictly_before: bool) -> pd.DataFrame:
    """Values known at each date; with strictly_before, only values dated earlier than it."""
    left = pd.DataFrame({"date": dates.to_numpy()}).reset_index()
    if strictly_before:
        left["key"] = left["date"] - pd.Timedelta(days=1)
    else:
        left["key"] = left["date"]
    left = left.sort_values("key")
    right = values.sort_index().rename_axis("key").reset_index()
    merged = pd.merge_asof(left, right, on="key", direction="backward")
    return merged.sort_values("index").drop(columns=["index", "date", "key"]).reset_index(drop=True)


def unified_frame(prices: pd.DataFrame, fred: pd.DataFrame, universe: tuple[str, ...] = UNIVERSE) -> pd.DataFrame:
    """One row per (ticker, date) of the universe, with reference closes and macro values known at that close."""
    prices = normalise_prices(prices)
    rows = prices[prices["ticker"].isin(universe)].reset_index(drop=True)
    missing = sorted(set(universe) - set(rows["ticker"]))
    if missing:
        raise ValueError(f"No prices for {missing}")
    refs = prices[prices["ticker"].isin(REFERENCES)].pivot(index="date", columns="ticker", values="close")
    refs = refs.rename(columns={k: f"ref_close_{v}" for k, v in REFERENCES.items()})
    parts = [rows]
    if not refs.empty:
        parts.append(_asof(rows["date"], refs.ffill(), strictly_before=True))
    macro = macro_available(normalise_fred(fred)) if not fred.empty else pd.DataFrame()
    if not macro.empty:
        parts.append(_asof(rows["date"], macro, strictly_before=False))
    out = pd.concat(parts, axis=1)
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------- store


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


RUN_LOG = Path(__file__).resolve().parents[3] / "registry" / "capstone_test_runs.json"


def protected_fingerprints(log: Path = RUN_LOG) -> list[dict]:
    """Data fingerprints of logged test-period reads: the stores they used must stay reproducible."""
    if not log.exists():
        return []
    return [r["data_sha256"] for r in json.loads(log.read_text()) if r.get("data_sha256")]


def save(store: Path, prices: pd.DataFrame, fred: pd.DataFrame, *, source: str, log: Path = RUN_LOG) -> dict:
    manifest_path = store / "manifest.json"
    if manifest_path.exists():
        current = json.loads(manifest_path.read_text()).get("sha256")
        if current and current in protected_fingerprints(log):
            raise SystemExit(
                f"Refused: {store} holds the data of a logged test-period read (registry/capstone_test_runs.json); "
                "overwriting it would make that read impossible to reproduce. Download into another folder: --store <new folder>."
            )
    store.mkdir(parents=True, exist_ok=True)
    files = {"prices": store / "prices.csv.gz", "fred": store / "fred.csv.gz"}
    prices.to_csv(files["prices"], index=False)
    fred.to_csv(files["fred"], index=False)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "rows": {"prices": len(prices), "fred": len(fred)},
        "tickers": sorted(prices["ticker"].unique().tolist()),
        "fred_series": sorted(fred["series"].unique().tolist()),
        "sha256": {name: _sha256(path) for name, path in files.items()},
    }
    (store / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def load_store(store: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    manifest_path = store / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No stored data in {store}: run with --mode download first")
    manifest = json.loads(manifest_path.read_text())
    for name in ("prices", "fred"):
        path = store / f"{name}.csv.gz"
        if _sha256(path) != manifest["sha256"][name]:
            raise ValueError(f"{path} does not match its manifest fingerprint")
    prices = drop_unfinished(normalise_prices(pd.read_csv(store / "prices.csv.gz")), manifest["created_utc"])
    fred = normalise_fred(pd.read_csv(store / "fred.csv.gz"))
    return prices, fred, manifest


def drop_unfinished(prices: pd.DataFrame, downloaded_utc: str) -> pd.DataFrame:
    """Drop bars dated on or after the download's UTC date: they can still be open.

    A crypto day ends at midnight UTC and a US session at 21:00 UTC at the latest, so every bar dated
    before the download's UTC date is complete; a bar of that date may be a few minutes old.
    """
    cutoff = pd.Timestamp(downloaded_utc).tz_convert("UTC").tz_localize(None).normalize()
    return prices[prices["date"] < cutoff].reset_index(drop=True)


OVERLAP_DAYS = 10


def splice(old: pd.DataFrame, new: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Stored prices plus a recent download, per ticker, with the stored history rescaled to the new adjustment.

    The provider back-adjusts the whole history when a dividend or split occurs, so the stored rows
    are multiplied by the median ratio of new to old values on the overlapping dates (adjusted close
    for ``adj_close``; close for the other price columns), then the new rows replace the overlap.
    """
    parts, ratios = [], {}
    for ticker in sorted(set(old["ticker"]) | set(new["ticker"])):
        o = old[old["ticker"] == ticker].set_index("date")
        n = new[new["ticker"] == ticker].set_index("date")
        if n.empty:
            parts.append(o.reset_index())
            continue
        overlap = o.index.intersection(n.index)
        if len(overlap) == 0 and not o.empty:
            raise ValueError(f"{ticker}: the update does not overlap the stored data; download the full history")
        o = o.copy()
        if len(overlap):
            r_adj = float((n.loc[overlap, "adj_close"] / o.loc[overlap, "adj_close"]).median())
            r_px = float((n.loc[overlap, "close"] / o.loc[overlap, "close"]).median())
            o["adj_close"] *= r_adj
            for col in ("open", "high", "low", "close"):
                o[col] *= r_px
            ratios[ticker] = {"adj_close": r_adj, "close": r_px, "overlap": len(overlap)}
        merged = pd.concat([o[~o.index.isin(n.index)], n]).sort_index()
        parts.append(merged.reset_index())
    out = pd.concat(parts, ignore_index=True)[PRICE_COLUMNS]
    return normalise_prices(out), ratios


def update(store: Path, *, overlap_days: int = OVERLAP_DAYS) -> dict:
    """Incremental load: download prices only from shortly before the last stored date and splice them in."""
    old_prices, _, manifest = load_store(store)
    if manifest["sha256"] in protected_fingerprints():
        raise SystemExit(
            f"Refused: {store} holds the data of a logged test-period read; update a copy in another folder instead."
        )
    old_prices = normalise_prices(pd.read_csv(store / "prices.csv.gz"))  # keep the stored rows as stored
    start = (old_prices["date"].max() - pd.Timedelta(days=overlap_days)).date().isoformat()
    tickers = list(dict.fromkeys([*UNIVERSE, *REFERENCES]))
    new_prices = download_prices(tickers, start)
    prices, ratios = splice(old_prices, new_prices)
    fred = download_fred(list(MACRO_SERIES))  # four small series, fetched whole
    out = save(store, prices, fred, source="yfinance and FRED public CSV (incremental update)")
    out["update"] = {"from": start, "new_rows": int(len(prices) - len(old_prices)), "rescaling": ratios}
    (store / "manifest.json").write_text(json.dumps(out, indent=2))
    return out


def load(mode: str = "file", store: Path | None = None, start: str = "2000-01-01") -> tuple[pd.DataFrame, dict]:
    """Unified frame in ``file`` mode (stored copy) or ``download`` mode (fresh data, then stored)."""
    store = store or default_store()
    if mode == "update":
        update(store)
    elif mode == "download":
        tickers = list(dict.fromkeys([*UNIVERSE, *REFERENCES]))
        prices = download_prices(tickers, start)
        fred = download_fred(list(MACRO_SERIES))
        save(store, prices, fred, source="yfinance and FRED public CSV")
    elif mode != "file":
        raise ValueError("mode must be 'file', 'download' or 'update'")
    prices, fred, manifest = load_store(store)
    frame = unified_frame(prices, fred)
    summary = {
        "store": str(store),
        "created_utc": manifest["created_utc"],
        "source_rows": manifest["rows"],
        "unified_rows": len(frame),
        "unified_columns": frame.shape[1],
        "first_date": frame["date"].min().date().isoformat(),
        "last_date": frame["date"].max().date().isoformat(),
        "rows_by_ticker": frame.groupby("ticker").size().to_dict(),
    }
    return frame, summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Course project data: download or read the stored copy.")
    parser.add_argument("--mode", choices=["file", "download", "update"], default="file")
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--start", default="2000-01-01")
    args = parser.parse_args(argv)
    _, summary = load(args.mode, args.store, args.start)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
