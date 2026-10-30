"""Data freshness: is every expected market in the report, and is its last bar recent enough?

A build can succeed while a data source fails quietly (the fetch steps of the scheduled job are
allowed to fail so one provider cannot stop the others). This module turns that silence into a
visible status that the report, the website and the scheduled job all read.

Status per instrument
    fresh     the last bar is as recent as the source can be expected to be
    stale     the last bar is older than that
    degraded  present, but only from a fallback source (for example a close-only series)
Overall status
    fresh     every expected instrument is fresh
    degraded  nothing is stale or missing, but at least one instrument is degraded
    stale     at least one expected instrument is stale or missing
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

# Instruments the scheduled build is expected to publish, and the source each one should come from.
EXPECTED = {
    "BTC-USD": {"source": "coinbase", "calendar": "24/7"},
    "ETH-USD": {"source": "coinbase", "calendar": "24/7"},
    "SPY": {"source": "alpaca", "calendar": "XNYS"},
    "QQQ": {"source": "alpaca", "calendar": "XNYS"},
    "SPX": {"source": "stooq", "calendar": "XNYS"},
    "NDX": {"source": "stooq", "calendar": "XNYS"},
}
# Allowed delay. Hourly crypto bars: hours. Exchange data: completed sessions after the last bar.
MAX_CRYPTO_AGE_HOURS = 6.0
# FRED posts a close the next day and the S&P 500 series sometimes one day later still.
MAX_SESSIONS_BEHIND = {"alpaca": 0, "stooq": 1, "fred": 2}
SESSION_CLOSE_NY = pd.Timedelta(hours=16, minutes=30)  # regular close plus a margin for late bars


def _utc(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def completed_sessions(after: pd.Timestamp, now: pd.Timestamp, calendar: str = "XNYS") -> int:
    """Number of exchange sessions after the date of ``after`` whose close is before ``now``."""
    first = (pd.Timestamp(after.date()) + pd.Timedelta(days=1)).normalize()
    last = pd.Timestamp(now.tz_convert("America/New_York").date())
    if first > last:
        return 0
    try:
        import exchange_calendars as xcals

        cal = xcals.get_calendar(calendar, start=first - pd.Timedelta(days=7), end=last + pd.Timedelta(days=7))
        sessions = pd.DatetimeIndex(cal.sessions_in_range(first, last)).tz_localize(None)
    except ImportError:  # optional dependency: weekdays are a close approximation
        sessions = pd.bdate_range(first, last)
    closes = [(s + SESSION_CLOSE_NY).tz_localize("America/New_York") for s in sessions]
    return sum(1 for c in closes if c <= now)


def assess_instrument(code: str, inst: dict | None, now: pd.Timestamp) -> dict:
    expected = EXPECTED.get(code, {})
    if inst is None or inst.get("status") != "ok" or not inst.get("sources"):
        return {"code": code, "status": "stale", "reason": "missing from this build", "last_bar": None}
    primary = inst["sources"][0]
    source = primary.get("source")
    last = _utc(primary["end"])
    out = {
        "code": code,
        "source": source,
        "last_bar": last.isoformat(),
        "age_hours": round((now - last) / pd.Timedelta(hours=1), 1),
    }
    if expected.get("calendar") == "24/7" or inst.get("instrument", {}).get("calendar") == "24/7":
        out["status"] = "fresh" if out["age_hours"] <= MAX_CRYPTO_AGE_HOURS else "stale"
        out["allowed"] = f"{MAX_CRYPTO_AGE_HOURS:g} hours"
    else:
        behind = completed_sessions(last, now)
        allowed = MAX_SESSIONS_BEHIND.get(source, 1)
        out.update(sessions_behind=behind, allowed=f"{allowed} completed session(s)")
        out["status"] = "fresh" if behind <= allowed else "stale"
    if out["status"] == "fresh" and expected.get("source") and source != expected["source"]:
        out["status"] = "degraded"
        out["reason"] = f"served by the fallback source {source}; expected {expected['source']}"
    elif out["status"] == "stale":
        out["reason"] = f"last bar {last.strftime('%Y-%m-%d %H:%M')} UTC is older than allowed ({out['allowed']})"
    return out


def assess(report: dict, now: datetime | pd.Timestamp | None = None) -> dict:
    """Freshness of every expected instrument in a report (``now`` defaults to the current time)."""
    now = _utc(now if now is not None else datetime.now(timezone.utc))
    by_code = {i["code"]: i for i in report.get("instruments", [])}
    codes = list(EXPECTED) + [c for c in by_code if c not in EXPECTED]
    rows = [assess_instrument(code, by_code.get(code), now) for code in codes]
    statuses = {r["status"] for r in rows}
    overall = "stale" if "stale" in statuses else "degraded" if "degraded" in statuses else "fresh"
    return {"checked_at": now.isoformat(timespec="seconds"), "overall": overall, "instruments": rows}


def to_markdown(status: dict) -> str:
    icon = {"fresh": "OK", "degraded": "WARN", "stale": "FAIL"}
    lines = [
        f"### Data status: {status['overall']} ({status['checked_at']})",
        "",
        "| Instrument | Status | Source | Last bar (UTC) | Note |",
        "|---|---|---|---|---|",
    ]
    for r in status["instruments"]:
        last = (r.get("last_bar") or "-")[:16].replace("T", " ")
        lines.append(
            f"| {r['code']} | {icon[r['status']]} {r['status']} | {r.get('source', '-')} | {last} | {r.get('reason', '')} |"
        )
    return "\n".join(lines) + "\n"


__all__ = ["EXPECTED", "assess", "assess_instrument", "completed_sessions", "to_markdown"]
