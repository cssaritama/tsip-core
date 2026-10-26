"""Assemble the static website from the web assets and a report."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tsip.report.publish import assert_publishable

PACKAGE_WEB = Path(__file__).resolve().parents[2] / "web"


def build_site(
    report_path: str | Path,
    out_dir: str | Path,
    *,
    web_dir: str | Path | None = None,
    site_url: str | None = None,
) -> Path:
    """Copy the web assets, add the report and, if given, the site's canonical address."""
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
    if site_url:
        _set_canonical(out / "index.html", site_url)
    return out


def _set_canonical(index: Path, site_url: str) -> None:
    """Point search engines and link previews at the primary address when the site has mirrors."""
    url = site_url.rstrip("/") + "/"
    if not url.startswith("https://"):
        raise ValueError(f"site URL must start with https://, got {site_url!r}")
    html = index.read_text(encoding="utf-8")
    tags = f'  <link rel="canonical" href="{url}">\n  <meta property="og:url" content="{url}">\n'
    index.write_text(html.replace("</head>", tags + "</head>", 1), encoding="utf-8")
