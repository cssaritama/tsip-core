"""Reconstruct the verified February 2018 interval defect from official trades.

Original cached observations and checksum-verified trade archives are retained
outside version control. The repair is explicit, bounded and idempotent.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

from tsip.data.sources.base import SourceUnavailable
from tsip.http import get_bytes

REPAIR_KEY = "binance_feb2018_repair"
REPAIR_VERSION = "aggtrades-utc-v1"
START = pd.Timestamp("2018-02-09", tz="UTC")
END = pd.Timestamp("2018-02-12", tz="UTC")
COLUMNS = ["id", "price", "quantity", "first_id", "last_id", "time", "maker", "best"]


def repair_february_2018(bars: pd.DataFrame, evidence_dir: str | Path, *, getter=get_bytes) -> pd.DataFrame:
    """Replace complete affected UTC dates only after verifying all trade archives.

    An incomplete requested history is left intact. No zero-trade hour is
    invented. Continuity of IDs establishes internal archive coverage, not
    an independent guarantee that the exchange recorded every real trade.
    """
    if bars.empty or bars.attrs.get(REPAIR_KEY, {}).get("version") == REPAIR_VERSION:
        return bars
    if bars.index.min() > START or bars.index.max() < END:
        return bars
    root = Path(evidence_dir)
    root.mkdir(parents=True, exist_ok=True)
    parts, sources = [], []
    for day in pd.date_range(START, END, inclusive="left", freq="D"):
        name = f"BTCUSDT-aggTrades-{day:%Y-%m-%d}.zip"
        url = f"https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/{name}"
        payload = getter(url)
        checksum = getter(url + ".CHECKSUM").decode().split()[0].lower()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != checksum:
            raise SourceUnavailable(f"Trade archive checksum mismatch: {name}")
        (root / f"{digest}-{name}").write_bytes(payload)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if len(archive.namelist()) != 1:
                raise SourceUnavailable(f"Unexpected trade archive members: {name}")
            text = archive.read(archive.namelist()[0]).decode()
        if not text.split(",", 1)[0].strip().isdigit():
            text = text.split("\n", 1)[1]
        frame = pd.read_csv(io.StringIO(text), header=None, names=COLUMNS)
        if frame.empty or frame[COLUMNS[:6]].isna().any().any():
            raise SourceUnavailable(f"Incomplete trade archive: {name}")
        for column in ("id", "first_id", "last_id", "time"):
            values = pd.to_numeric(frame[column], errors="raise")
            if (values % 1 != 0).any():
                raise SourceUnavailable(f"Noninteger trade identity/time: {name}")
            frame[column] = values.astype("int64")
        for column in ("price", "quantity"):
            frame[column] = pd.to_numeric(frame[column], errors="raise")
            if not frame[column].between(0, float("inf"), inclusive="neither").all():
                raise SourceUnavailable(f"Invalid trade {column}: {name}")
        timestamp = pd.to_datetime(frame["time"], unit="ms", utc=True)
        if not ((timestamp >= day) & (timestamp < day + pd.Timedelta(days=1))).all():
            raise SourceUnavailable(f"Trades outside declared UTC day: {name}")
        sources.append({"url": url, "sha256": digest, "rows": len(frame)})
        parts.append(frame)
    trades = pd.concat(parts, ignore_index=True).sort_values("id")
    if not (trades["id"].diff().dropna() == 1).all():
        raise SourceUnavailable("Duplicate or missing aggregate trade identities")
    if (trades["first_id"] > trades["last_id"]).any() or not (
        trades["first_id"].iloc[1:].to_numpy() == trades["last_id"].iloc[:-1].to_numpy() + 1
    ).all():
        raise SourceUnavailable("Overlapping or missing underlying trade identities")
    if not (trades["time"].diff().dropna() >= 0).all():
        raise SourceUnavailable("Trade times contradict trade sequence")
    trades["hour"] = pd.to_datetime(trades["time"], unit="ms", utc=True).dt.floor("h")
    repaired = trades.groupby("hour").agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("quantity", "sum"),
    )
    affected = (bars.index >= START) & (bars.index < END)
    original = bars.loc[affected].to_csv().encode()
    original_hash = hashlib.sha256(original).hexdigest()
    (root / f"{original_hash}-original-cached-bars.csv").write_bytes(original)
    out = pd.concat([bars.loc[~affected], repaired]).sort_index()
    out.index.name = bars.index.name
    if not out.index.is_unique:
        raise SourceUnavailable("Repair produced duplicate intervals")
    record = {
        "version": REPAIR_VERSION,
        "start": str(START),
        "end_exclusive": str(END),
        "source_cached_rows": int(affected.sum()),
        "source_cached_sha256": original_hash,
        "aggregate_trades": len(trades),
        "reconstructed_hours": len(repaired),
        "sources": sources,
        "method": "consecutive trade IDs; UTC OHLC and summed traded quantity",
    }
    out.attrs = {**bars.attrs, REPAIR_KEY: record}
    (root / f"{original_hash}-repair.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return out
