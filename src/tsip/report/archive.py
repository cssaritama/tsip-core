"""Point-in-time archive of published reports.

Every published report is stored once, compressed and fingerprinted, so anyone can reconstruct what
TSIP said on any past date and check that it was not changed afterwards. The archive lives on its
own branch of the repository (``report-archive``); this module only writes files into a directory.

Layout
    reports/YYYY/MM/YYYY-MM-DDTHHMMZ.json.gz   the report as published (gzip, deterministic header)
    index.csv                                   one row per report: time, version, rules, data status,
                                                SHA-256 of the uncompressed JSON, path
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

INDEX_FIELDS = ["generated_at", "version", "rules_version", "data_status", "sha256", "path"]


def archive_report(report_path: str | Path, archive_dir: str | Path) -> dict:
    """Add one report to the archive; does nothing if a report with the same timestamp is already there."""
    raw = Path(report_path).read_bytes()
    report = json.loads(raw)
    generated = report["generated_at"]  # e.g. 2026-11-03T21:56:10+00:00
    stamp = generated[:16].replace(":", "")  # 2026-11-03T2156
    rel = Path("reports") / generated[:4] / generated[5:7] / f"{stamp}Z.json.gz"
    root = Path(archive_dir)
    target = root / rel
    digest = hashlib.sha256(raw).hexdigest()
    index = root / "index.csv"
    rows = []
    if index.exists():
        with index.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    if any(r["generated_at"] == generated for r in rows):
        return {"added": False, "path": rel.as_posix(), "sha256": digest}
    target.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gz:  # mtime 0: same bytes for the same report
        gz.write(raw)
    target.write_bytes(buffer.getvalue())
    rows.append(
        {
            "generated_at": generated,
            "version": report.get("version", ""),
            "rules_version": report.get("rules_version", ""),
            "data_status": (report.get("data_status") or {}).get("overall", ""),
            "sha256": digest,
            "path": rel.as_posix(),
        }
    )
    rows.sort(key=lambda r: r["generated_at"])
    with index.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return {"added": True, "path": rel.as_posix(), "sha256": digest}


def verify_archive(archive_dir: str | Path) -> list[str]:
    """Problems found when re-reading every archived report against its fingerprint (empty if none)."""
    root = Path(archive_dir)
    problems = []
    with (root / "index.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            data = gzip.decompress((root / row["path"]).read_bytes())
            if hashlib.sha256(data).hexdigest() != row["sha256"]:
                problems.append(row["path"])
    return problems


__all__ = ["archive_report", "verify_archive"]
