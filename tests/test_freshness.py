import json

import pandas as pd

from tsip.cli import main
from tsip.data import freshness


def _inst(code, source, end, calendar="XNYS"):
    return {
        "code": code,
        "status": "ok",
        "instrument": {"code": code, "calendar": calendar},
        "sources": [{"source": source, "end": end}],
    }


def _report(**overrides):
    insts = {
        "BTC-USD": _inst("BTC-USD", "coinbase", "2026-10-30 12:00:00+00:00", "24/7"),
        "SPY": _inst("SPY", "alpaca", "2026-10-29 19:30:00+00:00"),
        "QQQ": _inst("QQQ", "alpaca", "2026-10-29 19:30:00+00:00"),
        "SPX": _inst("SPX", "stooq", "2026-10-29 00:00:00"),
        "NDX": _inst("NDX", "stooq", "2026-10-29 00:00:00"),
    }
    insts.update(overrides)
    return {"instruments": [v for v in insts.values() if v is not None]}


NOW = pd.Timestamp("2026-10-30 14:00", tz="UTC")  # Friday, before the US open


def test_all_fresh():
    status = freshness.assess(_report(), now=NOW)
    assert status["overall"] == "fresh"
    assert {r["status"] for r in status["instruments"]} == {"fresh"}


def test_crypto_stale_after_six_hours():
    old = _inst("BTC-USD", "coinbase", "2026-10-30 06:00:00+00:00", "24/7")
    row = next(
        r for r in freshness.assess(_report(**{"BTC-USD": old}), now=NOW)["instruments"] if r["code"] == "BTC-USD"
    )
    assert row["status"] == "stale"


def test_equity_stale_after_a_missed_session():
    old = _inst("SPY", "alpaca", "2026-10-27 19:30:00+00:00")  # Tuesday: Wednesday and Thursday closed since
    status = freshness.assess(_report(SPY=old), now=NOW)
    row = next(r for r in status["instruments"] if r["code"] == "SPY")
    assert row["sessions_behind"] == 2 and row["status"] == "stale"
    assert status["overall"] == "stale"


def test_weekend_is_not_stale():
    monday_morning = pd.Timestamp("2026-11-02 10:00", tz="UTC")
    friday = _inst("SPY", "alpaca", "2026-10-30 19:30:00+00:00")
    row = freshness.assess_instrument("SPY", friday, monday_morning)
    assert row["sessions_behind"] == 0 and row["status"] == "fresh"


def test_missing_instrument_is_stale_and_fallback_is_degraded():
    fallback = _inst("SPX", "fred", "2026-10-29 00:00:00")
    status = freshness.assess(_report(NDX=None, SPX=fallback), now=NOW)
    rows = {r["code"]: r for r in status["instruments"]}
    assert rows["NDX"]["status"] == "stale" and "missing" in rows["NDX"]["reason"]
    assert rows["SPX"]["status"] == "degraded"
    assert status["overall"] == "stale"


def test_degraded_overall_when_nothing_is_stale():
    fallback = _inst("SPX", "fred", "2026-10-29 00:00:00")
    assert freshness.assess(_report(SPX=fallback), now=NOW)["overall"] == "degraded"


def test_check_command_exit_code_and_summary(tmp_path):
    path = tmp_path / "report.json"
    summary = tmp_path / "summary.md"
    path.write_text(json.dumps(_report(NDX=None)))
    assert main(["check", "--report", str(path), "--summary", str(summary)]) == 1
    assert "NDX" in summary.read_text()


def test_fred_close_two_sessions_behind_is_only_degraded():
    # 2026-10-30 20:35 UTC: sessions of 10-29 and 10-30 are closed, FRED still ends on 10-28.
    now = pd.Timestamp("2026-10-30 20:35", tz="UTC")
    row = freshness.assess_instrument("SPX", _inst("SPX", "fred", "2026-10-28 00:00:00"), now)
    assert row["sessions_behind"] == 2 and row["status"] == "degraded"
    late = freshness.assess_instrument("SPX", _inst("SPX", "fred", "2026-10-27 00:00:00"), now)
    assert late["status"] == "stale"
