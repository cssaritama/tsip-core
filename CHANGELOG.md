# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.2.0] – 2026-10-26

### Added
- Nasdaq-100: QQQ 30-minute bars (Alpaca) and the NDX long daily history, next to SPY and SPX. ETF and index series stay separate instruments.
- Long daily index histories for SPX and NDX, with a check of the first dates that carry genuine daily ranges and genuine opens.
- Prior-period levels for quarters, half-years and years, in addition to days, weeks and months.
- "Where we are now": for the week, month, quarter, half-year and year in progress, the state against the prior period's range and the outcomes of past periods in the same position (analog base rates).
- `tsip fetch sp500|nasdaq100` (`spx` remains an alias).

### Changed
- Calendar periods are complete only if they start on time and have ended; a period in progress never enters a base rate (affects the first and last week or month of a history).
- Grading rules 2026.10.1: proportion intervals are never narrower than the Wilson score interval.
- Gap and open-based studies use only the span of a history with genuine opens.
- Development tooling: the lint and format tool is pinned to an exact version and dependency updates arrive as grouped monthly proposals. File permissions normalized.

## [0.1.0] – 2026-10-26

### Added
- Market data connectors: Coinbase Exchange candles, Binance public data archive (checksum-verified), Alpaca Market Data, FRED and Stooq, with an incremental local store and provenance sidecars.
- Evidence engine: circular block bootstrap, bootstrap p-values, Benjamini–Hochberg q-values, discovery/holdout split and published grading rules (version 2026.10).
- Studies: level memory (day, week, month, Monday), hour-of-day and half-hour returns, crypto session returns, daily and weekly extreme timing against a random-walk baseline, overnight versus intraday returns, prior-week first passage with geometry-matched controls, prior-month-low entry timing, calendar effects.
- Report builder with plain-language headlines and a publication guard that rejects raw price data.
- Static website and a scheduled workflow that refreshes data, rebuilds the report and deploys it.
- Hypothesis register with fingerprinted, pre-registered statements.
- Research toolkit carried over from earlier prototypes (temporal levels, session analytics, cross-market and path studies).

### Changed
- Geometry control for the prior-week first-passage study: per-event controls placed symmetrically around the event's own relative position. The previous design (controls between 10% and 90%, position bins) overstated the edge by about 3 percentage points under a random walk.
