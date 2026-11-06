# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.24] – 2026-11-06

### Added
- Evaluation record for the hypothesis register (`registry/evaluations.json`, W-77): outcome, result, archived report and its fingerprint, attached only when the fingerprint it names matches the registered entry; the register page shows it. First entries: H-2026-011 and H-2026-014, both supported.
- Hypothesis H-2026-015 (Bitcoin and Ether: an untested Monday low is reached before the week ends less often than an equally distant level), registered for evaluation on weeks from 2026-11-09.

## [0.2.23] – 2026-11-06

### Added
- Back to Monday's low and to the last three lows (specification 0010, W-72): when Monday's low is untested later in the week, how often price trades back at it before the week ends and within 5 and 10 sessions; after each week and month close, how often price reaches the nearest and the lowest of the last three periods' lows; all against distance-matched arbitrary levels. Fifteen graded items per market. The Day of the week coordinate shows this week's Monday low when it is still untested.
- Hypothesis H-2026-014 (SPY: Monday's low adds little beyond distance), registered before the first run on real data.
- Hypotheses H-2026-012 and H-2026-013 (Bitcoin month high and Ether month low rarely in the month's last week), registered for evaluation on months from December 2026 only.

### Changed
- The contributor guide is `CONTRIBUTING.md` only; the separate automation guide was merged into it.

## [0.2.22] – 2026-11-06

### Added
- Month and quarter extremes (specification 0008, W-63): in which part of the month (first five sessions, middle, last five; seven days for crypto) and of the quarter (each month) the lowest and highest close form, against the same days in random order (10,000 shuffles per period, which keeps drift, volatility and fat tails), with a driftless random walk as a second reference and the intraday low and high as context. Twelve graded items per market; on the histories from 2016 they are B at best and the page says so; NDX from 1986 can reach A on months. The Time panel shows the current window of the month and quarter with its grade; new section "Month and quarter extremes".
- Hypothesis H-2026-011 (NDX: no timing effect of the month's low beyond the shuffled control), registered before the first run on real data.
- `tools/test_budget.py` (specification 0009): edge tests per instrument by study and grade, and for each horizon the cells a condition can be split into while still able to reach grade A and the smallest effect an A grade can detect. Methodology section 5 states the test budget: every test counted, conditions sized to the history, and conditions revised after their results were seen treated as exploratory.

### Changed
- Specification 0008: monthly and quarterly conditions on the 2016 histories cannot reach grade A (130 months, 43 quarters); the graded monthly test uses the NDX history from 1986, and quarterly items are B at best.

## [0.2.21] – 2026-11-05

### Fixed
- Publication: run #36 failed because the Pages deployment of run #35 (`a015c9a`) was still "in progress" and blocked the new one; the clearing step had skipped it, since it cancelled only deployments whose status it could read. Every earlier Pages deployment is now cancelled unconditionally before deploying and again before the retry (cancelling a finished one is harmless).

## [0.2.20] – 2026-11-05

### Fixed
- Publication: run #35 (0.2.19) built the report but the GitHub Pages deployment timed out after 10 minutes. The 20-minute wait set in 0.2.14 never applied: the deploy action caps its timeout at 600000 ms and said so in a warning. The deployment now waits the real maximum and, if GitHub Pages has not finished, cancels that attempt and tries once more.

## [0.2.19] – 2026-11-05

### Added
- Trade plans by volatility regime (specification 0007): the six plans in past weeks and months that started in today's volatility regime (calm, normal or volatile against all earlier sessions' ATR), graded against all periods at the same point. The trade plan tile names today's regime and its best-graded plan; the Today panel treats an A here like an A in the plan cards. Hypotheses H-2026-009 (SPY) and H-2026-010 (Bitcoin) registered before any real result, evaluated on weeks from 2026-11-09.

## [0.2.18] – 2026-11-05

### Added
- Trade plan from here (specification 0005): for the week and the month in progress, six plans from the latest close, long and short, held to the period's end or with a 1 ATR stop and a 1 or 2 ATR target, followed on intraday bars (a bar that reaches both levels counts as the stop; a gap exits at the open). The report gives each plan's average result in ATR in today's state against all periods at the same point, graded, and how often the target or the stop came first. On the board, a new tile shows the results with the reader's cost subtracted; the Today panel leads with a plan graded A when there is one.

### Changed
- The trading cost is chosen once, at the top of the board, and applies to the trade plan and to the money table's cost rows.
- Figures that round to zero are shown as 0.00, not -0.00.
- Specification 0006 records that two SPY week items at the A limits became B in the first report with the all-period baseline; the hypothesis tested is the same.

## [0.2.17] – 2026-11-05

### Changed
- Money terms compare the periods in today's state with all past periods at the same point, whatever their state, instead of the periods in the other states (specification 0006). Both comparisons test the same hypothesis, but the old one made every difference look larger by the share of the other states in the pool: for SPY on 2026-11-05, ended the week above the close was 63.8% against 52.4% for the other weeks, and is 63.8% against 58.2% for all weeks. The report adds the count of all periods and their excursions and cost thresholds.
- The board opens with a Today panel: at most three facts that apply to the current position, each linked to its tile. Only strong evidence (grade A) leads; the ATR is shown as a measurement.
- In the money table, horizons after the first with no item graded A, B or C are folded into one line with the reason ("no reliable difference", "too little history to grade") and a control to show them. The two cost rows appear only once a cost is chosen.

### Added
- Specification 0005, trade plan from here (approved, not yet run on real data), and the pre-registered hypotheses H-2026-007 and H-2026-008 for SPY, evaluated only on weeks from 2026-11-09.

## [0.2.16] – 2026-11-05

### Changed
- Money terms (specification 0003, approved by the founder): the board shows week, month and quarter side by side in one table, each with the number of past periods it rests on, instead of a switch. The graded items no longer use any cost: "ended above the close" and "ended below the close" replace the cost-based items. The report publishes the share of past periods that ended beyond 37 thresholds in ATR at the start of each period (0 to 3 ATR), and the page converts the reader's trading cost into ATR of each period, from sourced profiles (Binance, Coinbase Advanced, Kraken Pro, EU brokers at EUR 1 per order) or a custom figure, remembered in the browser and shown as descriptive. Thresholds in percent would overstate the share beyond a cost when the past was more volatile than the present. Each column shows its yardstick ("1 ATR = x%"), ATR multiples carry two decimals so that they match the percentages, and the row labels stay in view when the table scrolls sideways on a phone.

### Added
- Exchange sessions in the report (`sessions_ahead`, specification 0004): the current and next sessions of each exchange-traded instrument from the exchange calendar, with early closes. The page's clock uses them, so Thanksgiving (26 November 2026) is skipped and the early close of the next day is announced.
- Render check: fails when a tile's content is wider than the tile (clipped content), which the page-scroll check could not see.

## [0.2.15] – 2026-11-04

### Fixed
- Publication: before deploying, the workflow cancels any earlier GitHub Pages deployment that GitHub still reports as unfinished. Run #28 (0.2.14) was refused with "Deployment request failed ... due to in progress deployment" because the deployment of run #27 never finished on GitHub's side. The step cannot block the deployment.

## [0.2.14] – 2026-11-04

### Fixed
- Publication: the GitHub Pages deployment may take up to 20 minutes instead of 10. Run #27 (0.2.13) built the report correctly but the deployment step stopped with "Timeout reached, aborting!" while GitHub Pages was still deploying, so the site stayed at 0.2.12 and the report was not archived.

### Added
- Specification 0003 (draft, for approval): money terms on all horizons side by side, graded items without cost assumptions, sourced cost profiles.

## [0.2.13] – 2026-11-04

### Added
- **Money terms** (`tsip.studies.money`, specification `specs/0001-money-terms.md`): for the week, month and quarter in progress, how far price travelled above and below the close, and where it ended, in past periods in the same position at the same point, in ATR at the start of the period and in percent. Six graded shares (1 and 2 ATR above and below, ended above or below after a round-trip cost) against other periods at the same point, with the medians and quartiles of the moves. New section "From here to the period's end".
- Website: sixth board tile, "What can be made or lost from here?", with a week, month and quarter switch.
- Specifications in `specs/`: every feature or study starts from a specification with acceptance criteria and how each is verified (`specs/README.md`).
- `tools/render_check.py`: opens the built website in a headless browser at 390 to 1920 px, in both colour schemes, and fails on console errors, horizontal scroll and overlapping chart text (`specs/0002-readable-charts.md`). Ruff now also checks `tools/`.

### Fixed
- Charts no longer overlap: untested-level labels are laid out at least 16 px apart with leader lines and stacked dots; the board's level map places highs above and lows below its axis with its notes as a caption; axis labels of the findings charts are thinned until they no longer touch; the highlighted value of a profile chart sits above its neighbours.

## [0.2.12] – 2026-11-04

### Added
- Website: **At a glance**, a decision board at the top of the page with five questions, each answered with one figure, one visual against its control and its grade: how far the market moves (ATR now, its percentile in the instrument's history, and a ladder of typical magnitudes), when it moves (intraday volatility profile with the current or next slot, and where the day's high and low form against a random walk), where it stands (week, month and quarter ranges in ATR), which levels are in reach (every untested level on one ATR axis, the nearest high and low with reach odds) and what the evidence supports (grade distribution of every effect tested against a control, and the three strongest effects).
- Website: revisit curves in the Space panel, the share of prior highs and lows traded again within each number of sessions against arbitrary levels at the same distance; profile charts in every coordinate of the Time panel.
- Report: volatility regime in each instrument's position (`atr_percentile`, `atr_median_pct`, `atr_history_from`), the percentile of today's 14-session ATR in the instrument's own history.
- Report: revisit curves on the time-to-revisit cards (`extra.curve` on the first item of each side: sessions, real and control shares), computed with the same fully-observed-window rule as the graded items.

### Changed
- Shorter hero text; the design reference (`docs/DESIGN.md`) now states the decision standard and the visual language used everywhere: bar for the observed value, line for its control.
- Facts without enough history are shown muted in the Time panel.
- Development tool Ruff 0.17.3, the update proposed by the dependency pull request of 2026-11-01.

## [0.2.11] – 2026-11-03

### Added
- Volatility clock (`tsip.studies.volatility`): how much more or less price moves in each hour or half-hour, weekday, week of the month, month and quarter than at an average coordinate, with the typical move and range. New section "Volatility clock" on the time axis, and the first facts of every coordinate in the website's Time panel.
- Point-in-time archive: every published report is stored once, compressed and fingerprinted, on the `report-archive` branch (`tsip archive`, new `archive` job in the publication workflow); `--verify-only` re-checks every fingerprint.
- The publication run warns when the repository has had no commit for 45 days, before GitHub's 60-day rule stops scheduled runs.
- Website glossary: pts, bps, control, ATR, grade, recent check.

### Changed
- Differences of percentages are written as "pts" and shown next to the observed and control rates they come from.

## [0.2.10] – 2026-11-03

### Added
- Reach odds for untested levels: for each level, how often price has travelled that far within 5, 20 and 60 sessions from every past session of the same market at the same volatility-scaled distance, with a 95% interval, and the typical time to get there. Levels of several horizons at one price are merged into a single zone that lists them.
- Website: "Untested levels" replaces "Open levels", with a ladder chart of the levels around the last close and the reach odds in the table.

### Changed
- Grades are explained in plain words with their reason. Graded findings are listed first, strongest first; findings without enough history are collapsed at the end of each group with an explanation instead of being mixed with graded ones. Ungraded outcomes in the grid are shown muted with their sample size.

## [0.2.9] – 2026-10-30

### Fixed
- The report build stopped in 0.2.7 and 0.2.8: open levels were computed for close-only series (FRED SPX and NDX), whose missing highs and lows produced non-numeric distances that cannot be written as JSON. Close-only series now have no open levels or position, and any non-finite number left in a report is published as null instead of stopping the build. Regression tests cover both.

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
