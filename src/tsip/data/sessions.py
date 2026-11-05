"""Upcoming exchange sessions, published with the report so the page never guesses holidays.

The page's clock needs the next sessions of each exchange-traded instrument: date, open and close in UTC,
and whether the session closes early. They come from the exchange calendar (``exchange_calendars``, the
``calendar`` extra installed by the publication workflow). Without it, weekdays from 09:30 to 16:00 New York
are used and the list is marked approximate. Specification: W-24 in the open work.
"""

from __future__ import annotations

import pandas as pd

NEW_YORK = "America/New_York"


def upcoming_sessions(now: pd.Timestamp | None = None, *, calendar: str = "XNYS", count: int = 12) -> dict:
    """The current session (if it has not closed yet) and the following ones, ``count`` in total."""
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now).tz_convert("UTC")
    start = pd.Timestamp(now.tz_convert(NEW_YORK).date())
    end = start + pd.Timedelta(days=count * 2 + 14)
    try:
        import exchange_calendars as xcals

        cal = xcals.get_calendar(calendar, start=start - pd.Timedelta(days=7), end=end + pd.Timedelta(days=7))
        days = cal.sessions_in_range(start, end)
        rows = []
        for day in days:
            close = cal.session_close(day)
            if close <= now:
                continue
            rows.append(
                {
                    "date": str(pd.Timestamp(day).date()),
                    "open_utc": cal.session_open(day).isoformat(),
                    "close_utc": close.isoformat(),
                    "early_close": bool(close.tz_convert(NEW_YORK).hour < 16),
                }
            )
            if len(rows) == count:
                break
        return {"calendar": calendar, "source": "exchange_calendars", "approximate": False, "sessions": rows}
    except ImportError:
        rows = []
        for day in pd.bdate_range(start, end):
            open_ = pd.Timestamp(f"{day.date()} 09:30", tz=NEW_YORK).tz_convert("UTC")
            close = pd.Timestamp(f"{day.date()} 16:00", tz=NEW_YORK).tz_convert("UTC")
            if close <= now:
                continue
            rows.append(
                {
                    "date": str(day.date()),
                    "open_utc": open_.isoformat(),
                    "close_utc": close.isoformat(),
                    "early_close": False,
                }
            )
            if len(rows) == count:
                break
        return {"calendar": calendar, "source": "weekdays", "approximate": True, "sessions": rows}


__all__ = ["upcoming_sessions"]
