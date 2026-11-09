# 0023 · Complete equity sessions for daily context

Status: regression fix for W-01/F01 and pilot gate W-84. Other W-01 findings remain open.

## Failure reproduced

The 2026-11-09 report generated at 18:43 UTC labeled SPY fresh, used a last 30-minute bar starting at 18:00 UTC and dated its daily reference map 2026-11-09. That regular session had not closed. The aggregation accepted days with at least seven bars and could infer completeness from the densest day in the sample. Freshness used the last raw bar date, masking an incomplete completed-session record.

## Contract

- SPY and QQQ daily OHLC and path inputs require exact expected bar starts between the calendar open and close, with no missing or displaced slots. Exclude the ongoing session and respect shortened sessions. Use only standard sessions in same-clock intraday profiles.
- Intraday feed recency remains visible. Equity decision freshness uses the last complete daily session and the exchange calendar, including its early close plus the existing 30-minute grace.
- An earlier complete session may remain current before today's close. Missing a completed session after grace is stale. Existing archived reports remain immutable.
- Validate ordinary sessions, early close, off-grid bars, incomplete sessions, before-close snapshots and the freshness grace. Replay the same dry-run fixture only after screening it for complete-session eligibility.
