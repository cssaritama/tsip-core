# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.8] – 2026-10-30

### Added
- Time–space model (`docs/TIME_SPACE_MODEL.md`): every coordinate and study placed on the time axis (session, hour, weekday, turn of the month, month, period progress, elapsed time) or the space axis (reference ranges, zones, open levels, first passage), and where they meet.
- Time panel on the website: the calendar coordinates of the current or next session in the instrument's own clock (session window, day of the week, month and turn of the month, quarter and year progress), each with the graded statistics for that coordinate and a link to the full finding.

### Changed
- The page is organised in two panels, Time and Space; the findings index is grouped the same way. Title: "Time–Space Intelligence".

## [0.2.7] – 2026-10-30

### Added
- Time to revisit a level (`tsip.studies.revisit`): for closed weeks, months, quarters and years, how often and how soon price trades back at the period's high and low, against arbitrary levels at the same volatility-scaled distance from all other period closes; Kaplan–Meier median times with open levels censored. New report section "Time to revisit".
- Open levels: highs and lows of recent closed periods not traded since, with age and distance in percent and ATR (`open_levels` in the report, a board under the grid on the website).
- Position: distances from the last close to each horizon's reference high and low in percent and in 14-session ATR, and the position within the range (`position` in the report).
- Ether (ETH-USD, Coinbase hourly) as a market: `tsip fetch eth`, scheduled build and data status.

### Fixed
- The grid no longer loses the week and month after a Friday close or at weekends: a closed period now shows the next period's starting position against the period that just closed, with the matching level-memory rates.

### Changed
- The website grid shows a range bar with the last close and the distances; the hero is shorter so the grid is visible without scrolling.

## [0.2.6] – 2026-10-30

### Changed
- New website design (`docs/DESIGN.md`): a time–space grid at the top shows, for the selected market, each horizon's time elapsed, the position of the last close against the prior range, whether the prior high or low has been taken and what followed in comparable past periods, with its grade. SPY, QQQ and Bitcoin lead the market switch; SPX and NDX are labelled index references (ADR 0049). Findings are listed by section with a sticky index; grades are shown as an evidence meter; the data section lists the status of every market. A "what these statistics can and cannot do" section is added. Dark and light colour schemes follow the system setting.
- The site is fully self-contained: one self-hosted variable font (Instrument Sans, SIL Open Font License) and no third-party requests; a test enforces it.
- Data status allows FRED close series two completed sessions of delay: FRED posts a close the next day and the S&P 500 series is sometimes a day later still. The first 0.2.5 run was marked stale for SPX for this reason alone.

## [0.2.5] – 2026-10-30

### Added
- Data status: every report carries `data_status` with the last bar of each expected market (BTC-USD, SPY, QQQ, SPX, NDX) and whether it is fresh, served by a fallback source (degraded) or stale/missing. The website shows it as a strip under the key figures.
- `tsip check` prints the same status, appends a Markdown table to a job summary and exits with an error when a market is stale or missing.

### Changed
- The scheduled build also runs on weekdays after the US close, so the evening report includes the session.
- A run that publishes stale or incomplete data is now marked as failed (a separate status job), instead of showing green because each data step may fail on its own.
- Nasdaq-100 index: FRED `NASDAQ100` daily close is used when the Stooq long history is unavailable, as already done for the S&P 500.

### Documentation
- The trade and hour counts stated for 0.2.4 were independently re-verified against the official Binance archives (1,066,634 aggregate trades, 62 hours, 19 of 20 comparable hours identical).

### Changed
- Dependency update pull requests only widen version ranges when a new release falls outside them; they no longer raise the minimum supported versions of pandas, numpy and the build tools.

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
