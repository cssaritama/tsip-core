# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.4] – 2026-10-27

### Fixed
- Reconstruct February 9–11, 2018 Binance BTC-USDT UTC hourly bars from checksum-verified official aggregate trades. Verify contiguous aggregate/underlying trade IDs, timestamps, prices and quantities before replacing affected dates. Retain original cached rows and raw trade archives with a repair manifest outside Git.
- Automatically migrate sufficiently long existing Binance caches, including v0.2.2 stores whose irregular rows were filtered out. Persist the repair revision across cache reads and incremental updates; subsequent fetches do not repeat the migration.
- The development run reported 1,066,634 aggregate trades and 62 reconstructed occupied UTC hours, with nineteen of twenty comparable regular source hours matching OHLC and volume; the remaining overlapping boundary hour is replaced from trades as well. These figures are pending re-verification against the repair manifest written by the first production run. No empty hour is invented. This repairs the documented interval defect, not every possible source-quality issue.

## [0.2.3] – 2026-10-27

### Fixed
- Preserve off-grid Binance source bars and cached timestamps unchanged. The proposed folding repair was rejected after inspecting the official February 2018 archive: 43 hourly bars cross hour boundaries and one interval overlaps its predecessor. Flooring cannot reconstruct these observations.
- Suppress cross-feed statistics and reject UTC-day aggregation when interval alignment is unresolved; retained data are not silently erased or represented as repaired. Other vendors' session-aligned timestamps remain unchanged.
- Exact reconstruction of the affected Binance intervals remains pending trade-level data verification. Existing caches from v0.2.2 may require a full re-download to recover previously filtered observations.

## [0.2.2] – 2026-10-26

### Fixed
- Binance archive bars that open off the minute grid (they appear around exchange outages such as February 2018) are left out, and stored data with sub-second timestamps loads correctly. The first production build stopped on them.
- A study or an instrument that fails no longer stops the whole report: the error goes to the build log and the report lists the skipped study or marks the instrument unavailable. The Binance cross-check is optional.

## [0.2.1] – 2026-10-26

### Added
- About section crediting the author, with links to the GitHub profile and the source code.
- Optional deployment to Cloudflare Pages (a free `pages.dev` address, no custom domain needed) alongside GitHub Pages. `tsip site --site-url` writes the canonical address so search engines index one copy.

### Changed
- On small screens the navigation scrolls inside the header instead of widening the page.
- Roadmap: 1.0 brings end-to-end automation and the statistics API with an MCP server for AI agents follows in 1.1, ahead of on-chain cohorts, filings and futures; volatility regimes (VIX) join 0.2.x and the predictive track. The contributing guide asks for documentation in the same pull request as the change.

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
