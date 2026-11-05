# 0004 Exchange sessions, holidays and early closes in the report

**Status:** shipped (0.2.16)
**Level:** 1 feature · **Open work:** W-24 · **Decisions:** ADR 0064

## Problem and decision supported

The page's clock guessed the next session of SPY and QQQ from the weekday, so on an exchange holiday it announced a session that does not exist (Thanksgiving, 26 November 2026) and it ignored early closes (13:00 New York the day after). "When does it move?" and the Time panel depend on knowing the next real session.

## Requirements

- R1. The report shall publish, for each exchange-traded instrument, the current session if it has not closed and the following ones (twelve in total), with date, open and close in UTC and an early-close flag, from the exchange calendar.
- R2. Without the calendar library, weekdays from 09:30 to 16:00 New York shall be published and marked approximate.
- R3. The page shall take the current or next session from that list, and say when it closes early.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| S1 | Thanksgiving is skipped and the next day is flagged as an early close at 13:00 New York | `test_holidays_and_early_closes_come_from_the_exchange_calendar` |
| S2 | A session in progress is listed first | `test_a_session_in_progress_is_listed_first` |
| S3 | The fallback is marked approximate | `test_weekday_fallback_is_marked_approximate` |
| S4 | With the clock set to 25, 27 (10:10 New York) and 27 November (14:00 New York), the page announces Friday 27 with its early close, a session in progress closing early, and Monday 30 | browser check with a fixed clock |

## Non-goals

- Crypto, which trades every day.
- Exchange calendars other than New York until other exchanges are covered (W-50).

## Data contract

`instruments[].sessions_ahead`: `{"calendar": "XNYS", "source": "exchange_calendars" | "weekdays", "approximate": bool, "sessions": [{"date", "open_utc", "close_utc", "early_close"}]}`.

## Verification

| ID | Result | Evidence |
|---|---|---|
| S1 | passed | `tests/test_exchange_sessions.py` |
| S2 | passed | `tests/test_exchange_sessions.py` |
| S3 | passed | `tests/test_exchange_sessions.py` |
| S4 | passed | fixed-clock browser check, 2026-11-05 |
