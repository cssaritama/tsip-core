"""Command line interface.

tsip fetch btc       [--source coinbase|binance] [--start 2016-01-01]
tsip fetch sp500     [--source alpaca|stooq|fred] [--start 2016-01-01]   (alias: spx)
tsip fetch nasdaq100 [--source alpaca|stooq|fred] [--start 2016-01-01]
tsip report [--out site/data/report.json]
tsip site   [--report site/data/report.json] [--out dist]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tsip import __version__
from tsip.data.sources import SourceUnavailable

DEFAULT_DATA = "data"
DEFAULT_REPORT = "site/data/report.json"
DEFAULT_HYPOTHESES = "registry/hypotheses.json"


MARKETS = {"btc": "btc", "sp500": "sp500", "spx": "sp500", "nasdaq100": "nasdaq100", "ndx": "nasdaq100"}


def _cmd_fetch(args: argparse.Namespace) -> int:
    from tsip.pipeline import fetch_bitcoin, fetch_equity

    market = MARKETS[args.market]
    try:
        if market == "btc":
            meta = fetch_bitcoin(args.data_dir, source=args.source or "coinbase", start=args.start)
        else:
            meta = fetch_equity(args.data_dir, market, source=args.source or "alpaca", start=args.start)
    except SourceUnavailable as exc:
        print(json.dumps({"status": "unavailable", "market": args.market, "reason": str(exc)}), file=sys.stderr)
        return 3
    print(
        json.dumps({"status": "ok", **{k: meta.get(k) for k in ("path", "rows", "start", "end", "sha256")}}, indent=2)
    )
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from tsip.pipeline import load_inputs
    from tsip.report.build import build_report

    report = build_report(load_inputs(args.data_dir), reps=args.reps, seed=args.seed, hypotheses_path=args.hypotheses)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, allow_nan=False))
    summary = {i["code"]: {"status": i["status"], "grades": i.get("grade_counts")} for i in report["instruments"]}
    print(json.dumps({"report": str(out), "instruments": summary}, indent=2))
    return 0


def _cmd_site(args: argparse.Namespace) -> int:
    from tsip.site import build_site

    path = build_site(args.report, args.out, web_dir=args.web, site_url=args.site_url or None)
    print(json.dumps({"site": str(path)}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tsip", description="Evidence-graded market statistics.")
    parser.add_argument("--version", action="version", version=f"tsip {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="download or update market data into the local store")
    fetch.add_argument("market", choices=sorted(MARKETS))
    fetch.add_argument("--source", help="btc: coinbase|binance; sp500 and nasdaq100: alpaca|stooq|fred")
    fetch.add_argument("--start", default="2016-01-01")
    fetch.add_argument("--data-dir", default=DEFAULT_DATA)
    fetch.set_defaults(func=_cmd_fetch)

    report = sub.add_parser("report", help="compute the evidence report from the local store")
    report.add_argument("--data-dir", default=DEFAULT_DATA)
    report.add_argument("--out", default=DEFAULT_REPORT)
    report.add_argument("--reps", type=int, default=1000)
    report.add_argument("--seed", type=int, default=20261026)
    report.add_argument("--hypotheses", default=DEFAULT_HYPOTHESES)
    report.set_defaults(func=_cmd_report)

    site = sub.add_parser("site", help="assemble the static website")
    site.add_argument("--report", default=DEFAULT_REPORT)
    site.add_argument("--out", default="dist")
    site.add_argument("--web", default=None, help="override the bundled web assets directory")
    site.add_argument("--site-url", default=None, help="primary public address, written as the canonical URL")
    site.set_defaults(func=_cmd_site)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
