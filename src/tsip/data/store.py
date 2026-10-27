"""Local bar store with incremental updates.

Raw vendor data is cached under a data directory that is excluded from
version control. Each dataset is a gzip CSV plus a JSON sidecar recording
its provenance (source, retrieval time, row count, SHA-256).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tsip.data.schema import BAR_COLUMNS, is_intraday


def dataset_path(data_dir: str | Path, instrument: str, source: str, timeframe: str) -> Path:
    safe = instrument.replace("/", "-").upper()
    return Path(data_dir) / source / f"{safe}_{timeframe}.csv.gz"


def write_bars(bars: pd.DataFrame, path: str | Path, *, extra_meta: dict | None = None) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = bars[BAR_COLUMNS].copy()
    label = "timestamp" if is_intraday(bars.attrs.get("timeframe", "")) else "date"
    frame.index.name = label
    frame.to_csv(path, compression={"method": "gzip", "mtime": 0}, float_format="%.10g")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    meta = {
        **bars.attrs,
        "rows": int(len(frame)),
        "start": str(frame.index[0]) if len(frame) else None,
        "end": str(frame.index[-1]) if len(frame) else None,
        "sha256": digest,
        "written_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **(extra_meta or {}),
    }
    path.with_suffix("").with_suffix(".json").write_text(json.dumps(meta, indent=2, default=str))
    return meta


def read_meta(path: str | Path) -> dict:
    meta_path = Path(path).with_suffix("").with_suffix(".json")
    return json.loads(meta_path.read_text()) if meta_path.exists() else {}


def read_bars(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    meta = read_meta(path)
    timeframe = meta.get("timeframe", "")
    intraday = is_intraday(timeframe)
    label = "timestamp" if intraday else "date"
    frame = pd.read_csv(path, compression="gzip")
    if label not in frame.columns:  # tolerate either label
        label = frame.columns[0]
    index = pd.to_datetime(frame.pop(label), utc=intraday, format="ISO8601")
    frame.index = pd.DatetimeIndex(index)
    if intraday:
        frame.index.name = "timestamp"
    else:
        frame.index = frame.index.normalize()
        frame.index.name = "date"
    frame = frame[BAR_COLUMNS].astype(float)
    frame.attrs = {
        k: meta[k]
        for k in ("instrument", "source", "timeframe", "price_basis", "close_only", "feed", "binance_feb2018_repair")
        if k in meta
    }
    return frame


def merge_incremental(existing: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """Combine cached and freshly downloaded bars.

    Newer observations replace older ones for the same timestamp, which keeps
    vendor corrections. The result is sorted and duplicate-free.
    """
    if existing is None or existing.empty:
        merged = new.copy()
    else:
        merged = pd.concat([existing, new])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    merged.attrs = dict(new.attrs or (existing.attrs if existing is not None else {}))
    if existing is not None and "binance_feb2018_repair" in existing.attrs:
        record = existing.attrs["binance_feb2018_repair"]
        overlaps_repair = bool(
            ((new.index >= pd.Timestamp(record["start"])) & (new.index < pd.Timestamp(record["end_exclusive"]))).any()
        )
        if not overlaps_repair:
            merged.attrs["binance_feb2018_repair"] = record
    return merged
