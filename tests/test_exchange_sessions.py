import builtins

import pandas as pd

from tsip.data.sessions import upcoming_sessions


def test_holidays_and_early_closes_come_from_the_exchange_calendar():
    out = upcoming_sessions(pd.Timestamp("2026-11-24 22:00", tz="UTC"), count=4)
    assert out["source"] == "exchange_calendars" and not out["approximate"]
    dates = [s["date"] for s in out["sessions"]]
    assert dates == ["2026-11-25", "2026-11-27", "2026-11-30", "2026-12-01"]  # Thanksgiving skipped
    friday = out["sessions"][1]
    assert friday["early_close"] and friday["close_utc"].startswith("2026-11-27T18:00")


def test_a_session_in_progress_is_listed_first():
    out = upcoming_sessions(pd.Timestamp("2026-11-05 15:00", tz="UTC"), count=2)
    assert out["sessions"][0]["date"] == "2026-11-05"


def test_weekday_fallback_is_marked_approximate(monkeypatch):
    real_import = builtins.__import__

    def no_calendar(name, *args, **kwargs):
        if name == "exchange_calendars":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_calendar)
    out = upcoming_sessions(pd.Timestamp("2026-11-24 22:00", tz="UTC"), count=3)
    assert out["approximate"] and [s["date"] for s in out["sessions"]] == ["2026-11-25", "2026-11-26", "2026-11-27"]
