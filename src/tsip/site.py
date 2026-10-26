"""Assemble the static website from the web assets and a report."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tsip.report.publish import assert_publishable

PACKAGE_WEB = Path(__file__).resolve().parents[2] / "web"


def build_site(report_path: str | Path, out_dir: str | Path, *, web_dir: str | Path | None = None) -> Path:
    web = Path(web_dir) if web_dir else PACKAGE_WEB
    if not (web / "index.html").exists():
        raise FileNotFoundError(f"web assets not found in {web}")
    report = json.loads(Path(report_path).read_text())
    assert_publishable(report)
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(web, out)
    (out / "data").mkdir(exist_ok=True)
    (out / "data" / "report.json").write_text(json.dumps(report, separators=(",", ":"), allow_nan=False))
    (out / ".nojekyll").write_text("")
    return out
