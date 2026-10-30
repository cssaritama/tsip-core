# The time–space model

TSIP describes a market with two kinds of coordinates and grades what has followed at each of them. Every study, card and screen belongs to one axis or joins both.

## Time: where we are in the calendar

| Coordinate | Values | Studies |
|---|---|---|
| Hour and session | Bitcoin and Ether: UTC hour; Asia, London, New York, late US. SPY/QQQ: cash-session half-hours; opening hour, midday, closing hour; overnight | `intraday` (returns by hour and session, overnight versus intraday), `sessions` (where the day's high and low form) |
| Day of the week | Monday to Friday (Sunday for crypto) | `calendar` (weekday returns, weekend), `weekly` (where the week's high and low form) |
| Week and turn of the month | Position in the month; last day plus first three | `calendar` (turn of the month) |
| Month of the year | January to December | `calendar` (month-of-year returns) |
| Progress through a period | Sessions elapsed out of the typical count, from week to year | `level_map` (analogs at the same point of the period) |
| Elapsed time since a level formed | Sessions since a period closed | `revisit` (time to revisit a level, open levels) |

## Space: where price stands against its levels

| Coordinate | Values | Studies |
|---|---|---|
| Reference range | The prior (or just-closed) day, week, month, quarter, half-year and year: high, low, open, close | `level_memory` (break and hold rates), `position` (distances in % and ATR, position within the range) |
| Zone | Below, inside or above the reference range; extremes already taken | `level_map` |
| Open levels | Highs and lows of closed periods not traded since | `revisit` |
| First passage | Which side of a range is reached first | `first_passage` (against geometry-matched bands) |

## Where the axes meet

A time–space state is a point on both axes: for example, "week of 2026-11-02, second session, below last week's low, last month's low still open 1.2 ATR away". The questions TSIP answers are always of the form *what has followed from states like this one, and how strong is that evidence?*

- `level_map`: same point in time **and** same zone in space.
- `revisit`: time **to** a point in space.
- `sessions` and `weekly`: **when** in time the period's extremes in space form.

## Rules that apply to both axes

1. Every coordinate is computed from data available at that moment; nothing after it.
2. Every statistic is compared with a control that removes what chance, drift or geometry alone would produce (`docs/METHODOLOGY.md`).
3. Exchange-traded instruments use their own calendar and time zone; crypto uses UTC days and the three regional sessions. Exchange holidays are not modelled on the website's Time panel yet.
