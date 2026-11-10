"""A second data source for the course project: Coinbase daily candles for Bitcoin and Ether.

Coinbase's public market data (no key) gives one exchange's own prices and volume, which yfinance's
aggregate does not. Two features come from it, each known at that day's close: the Coinbase close's
premium over the aggregate close (basis points) and Coinbase's share of the aggregate dollar volume
(with its change over 20 days). The two sources are also cross-checked against each other.

The candles are stored in ``<store>/coinbase/`` with their own fingerprinted manifest, so the
fingerprint of the main store (and the logged test read that used it) is untouched. These features
are exploratory: they are not used by the registered models.

    python -m tsip.capstone.extra_sources download   # needs access to api.exchange.coinbase.com
    python -m tsip.capstone.extra_sources --markdown
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from tsip.capstone import data, features
from tsip.capstone import models as M

PRODUCTS = ("BTC-USD", "ETH-USD")
START = "2016-01-01"


def folder(store: Path) -> Path:
    return store / "coinbase"


def download(store: Path, *, start: str = START, getter=None) -> dict:
    from tsip.data.sources import coinbase

    parts = []
    for product in PRODUCTS:
        kwargs = {"getter": getter} if getter is not None else {}
        bars = coinbase.fetch(product, "1d", start=start, **kwargs)
        frame = bars.reset_index().rename(columns={"timestamp": "date"})
        frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None).dt.normalize()
        frame["ticker"] = product
        parts.append(frame[["date", "ticker", "open", "high", "low", "close", "volume"]])
    candles = pd.concat(parts, ignore_index=True)
    out = folder(store)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "candles.csv.gz"
    candles.to_csv(path, index=False)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Coinbase Exchange public market data, daily candles",
        "rows": len(candles),
        "products": list(PRODUCTS),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def load(store: Path) -> pd.DataFrame | None:
    out = folder(store)
    if not (out / "manifest.json").exists():
        return None
    manifest = json.loads((out / "manifest.json").read_text())
    path = out / "candles.csv.gz"
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError(f"{path} does not match its manifest fingerprint")
    candles = pd.read_csv(path, parse_dates=["date"])
    created = pd.Timestamp(manifest["created_utc"]).tz_convert("UTC").tz_localize(None).normalize()
    return candles[candles["date"] < created]  # the download day's candle may still be open


def joined(frame: pd.DataFrame, candles: pd.DataFrame) -> pd.DataFrame:
    """Aggregate (yfinance) and Coinbase rows of the same day, crypto only."""
    agg = frame[frame["ticker"].isin(PRODUCTS)][["date", "ticker", "close", "volume"]]
    cb = candles.rename(columns={"close": "cb_close", "volume": "cb_volume"})[
        ["date", "ticker", "cb_close", "cb_volume"]
    ]
    return agg.merge(cb, on=["date", "ticker"], how="inner").sort_values(["ticker", "date"]).reset_index(drop=True)


def new_features(frame: pd.DataFrame, candles: pd.DataFrame) -> pd.DataFrame:
    """Coinbase features per crypto row, each known at that day's close."""
    j = joined(frame, candles)
    j["cb_premium_bps"] = (j["cb_close"] / j["close"] - 1) * 1e4
    share = (j["cb_volume"] * j["cb_close"]) / j["volume"].replace(0, np.nan)
    j["cb_volume_share"] = share
    j["cb_volume_share_change_20d"] = share / share.groupby(j["ticker"]).transform(lambda s: s.rolling(20).mean()) - 1
    return j[["date", "ticker", "cb_premium_bps", "cb_volume_share", "cb_volume_share_change_20d"]]


def crosscheck(frame: pd.DataFrame, candles: pd.DataFrame) -> pd.DataFrame:
    j = joined(frame, candles)
    rows = []
    for ticker, g in j.groupby("ticker"):
        diff = (g["cb_close"] / g["close"] - 1).abs() * 1e4
        rows.append(
            {
                "ticker": ticker,
                "days": len(g),
                "first": str(g["date"].min().date()),
                "last": str(g["date"].max().date()),
                "return_correlation": float(g["close"].pct_change().corr(g["cb_close"].pct_change())),
                "median_abs_close_diff_bps": float(diff.median()),
                "share_over_50bps": float((diff > 50).mean()),
                "median_volume_share": float(((g["cb_volume"] * g["cb_close"]) / g["volume"]).median()),
            }
        )
    return pd.DataFrame(rows)


def correlations_with_target(frame: pd.DataFrame, candles: pd.DataFrame) -> pd.DataFrame:
    """Spearman correlation of the Coinbase features with the next 5 and 20 rows' return (training and validation rows)."""
    feats, _ = features.build_features(frame)
    extra = new_features(frame, candles)
    rows = feats.merge(extra, on=["date", "ticker"], how="inner")
    rows = rows[rows["date"] <= M.VALIDATION_END]
    out = []
    for col in ("cb_premium_bps", "cb_volume_share", "cb_volume_share_change_20d"):
        for h in (5, 20):
            ok = rows[col].notna() & rows[f"growth_future_{h}d"].notna()
            rho = rows.loc[ok, col].rank().corr(rows.loc[ok, f"growth_future_{h}d"].rank())
            out.append({"feature": col, "horizon": h, "spearman": float(rho), "rows": int(ok.sum())})
    return pd.DataFrame(out)


def markdown(store: Path) -> str:
    candles = load(store)
    if candles is None:
        return "Coinbase candles not downloaded yet: `python -m tsip.capstone.extra_sources download`."
    frame, _ = data.load("file", store)
    cc = crosscheck(frame, candles)
    lines = [
        "**Coinbase against the aggregate (yfinance), daily closes**",
        "",
        "| Instrument | Days | From | To | Return correlation | Median close difference | Days over 50 bp | Median Coinbase share of volume |",
        "|---|---:|---|---|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {r.ticker} | {r.days:,} | {r.first} | {r.last} | {r.return_correlation:.4f} | {r.median_abs_close_diff_bps:.1f} bp "
        f"| {r.share_over_50bps * 100:.1f}% | {r.median_volume_share * 100:.1f}% |"
        for r in cc.itertuples()
    ]
    corr = correlations_with_target(frame, candles)
    lines += [
        "",
        "**Coinbase features against the target** (Spearman, training and validation rows, crypto only; exploratory)",
        "",
        "| Feature | Horizon | Spearman | Rows |",
        "|---|---:|---:|---:|",
    ]
    lines += [f"| `{r.feature}` | {r.horizon} | {r.spearman:+.3f} | {r.rows:,} |" for r in corr.itertuples()]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", nargs="?", choices=["download"])
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)
    store = args.store or data.default_store()
    if args.action == "download":
        print(json.dumps(download(store), indent=2))
    if args.markdown or not args.action:
        print(markdown(store))


if __name__ == "__main__":
    main()
