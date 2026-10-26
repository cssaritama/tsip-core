# TSIP · Time–Space Intelligence

[![CI](https://github.com/cssaritama/tsip-core/actions/workflows/ci.yml/badge.svg)](https://github.com/cssaritama/tsip-core/actions/workflows/ci.yml)
[![Report](https://github.com/cssaritama/tsip-core/actions/workflows/publish.yml/badge.svg)](https://github.com/cssaritama/tsip-core/actions/workflows/publish.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.12-informational)

**Everyone shows you the odds. We show you which odds are real.**

**▶ Live report: [cssaritama.github.io/tsip-core](https://cssaritama.github.io/tsip-core/)**, rebuilt every day from public market data.

Traders are surrounded by statistics: *"the prior-day high gets taken 60% of the time"*, *"Mondays set the weekly low"*, *"buy the dip at last month's low"*. Most of these numbers are real frequencies and most of them are misleading, because they are never compared with what chance alone would produce.

TSIP measures how the **S&P 500** and **Bitcoin** move through **time** (sessions, hours, days, weeks, months) and **price levels** (the prior period's high, low, open and close), and it grades every statistic against a control:

| Every figure ships with | Why it matters |
|---|---|
| Sample size and a 95% interval | A rate from 40 observations is not a rate from 4,000. |
| A control | A random-walk baseline for timing questions; geometry-matched levels for price-level questions. |
| Dependence-aware uncertainty | Market days are not independent; intervals use a circular block bootstrap. |
| An out-of-sample check | The most recent 30% of the data has to agree with the rest. |
| Multiple-testing control | Asking 100 questions produces 5 false "edges" at p < 0.05; q-values (Benjamini–Hochberg) correct for it. |
| A grade | **A–F** for edges, **A–D** reliability for base rates, under [published rules](docs/METHODOLOGY.md). |

## What a control changes: one example

On SPY from 2006 to 2025, when price closes back inside the prior week's range, the high side of that range is reached first within ten sessions **63%** of the time. That looks like an edge. But a close sitting high inside a range reaches the top first more often for purely mechanical reasons. Control bands of the same width at the same relative position reach the top first **62%** of the time. The prior-week levels add about **one percentage point** (grade C). The headline number was mostly geometry.

## What is in the report

| Section | Questions |
|---|---|
| Level memory | How often the day, week and month trade through the prior high or low; whether the break holds at the close; Monday high and low. |
| Sessions and intraday | Hour-of-day (Bitcoin) and half-hour (US cash session) returns; Asia, London and New York session returns; where the daily high and low form versus a random walk; overnight versus intraday returns. |
| Weekly structure | Which weekday sets the weekly high and low versus a random walk. |
| Paths and entries | Which side of the prior-week range breaks first, after geometry; whether a limit order at the prior month's low beats plain dollar-cost averaging. |
| Calendar | Day of week, weekend, turn of the month, month of year. |

## Quick start

```bash
python -m pip install -e ".[dev]"
pytest

# Bitcoin, hourly, from Coinbase's public market data (no key required)
tsip fetch btc --source coinbase --start 2016-01-01
tsip fetch btc --source binance  --start 2018-01-01   # independent cross-check feed

# S&P 500: SPY 30-minute bars with a free Alpaca account, or daily index data without one
export ALPACA_API_KEY_ID=...  ALPACA_API_SECRET_KEY=...
tsip fetch spx --source alpaca --start 2016-01-01     # or: --source stooq | --source fred

tsip report            # writes site/data/report.json
tsip site              # assembles the static site in dist/
python -m http.server --directory dist 8000
```

Downloads are incremental and cached under `data/` (excluded from version control). Credentials are read from the environment and never written to disk.

## Architecture

```
src/tsip/
  data/        canonical bar schema, local store, connectors (Coinbase, Binance archive, Alpaca, FRED, Stooq), quality checks
  frames.py    daily/weekly/monthly aggregation, crypto sessions with daylight-saving handling, intraday path matrices
  evidence/    circular block bootstrap, bootstrap p-values, Benjamini–Hochberg, grading rules, evidence cards
  studies/     level memory, sessions and intraday, first passage with geometry control, entry timing, calendar
  report/      report assembly, headlines, publication guard (no raw prices leave the pipeline)
  research/    exploratory research toolkit (temporal levels, session analytics, cross-market studies)
web/           static front end (no framework, no tracking)
registry/      pre-registered hypotheses, fingerprinted and evaluated later on new data
```

A scheduled GitHub Actions workflow fetches new data, rebuilds the report and deploys the site. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Principles

1. **No look-ahead.** Levels are frozen when a signal is observed; paths start at the next bar.
2. **Nothing is filled or invented.** Missing bars stay missing; close-only series never receive synthetic highs and lows.
3. **Instruments are never mixed.** SPX (index points), SPY (ETF dollars) and ES (futures) are different instruments and are labelled as such.
4. **Only derived statistics are published.** The publication guard rejects any output that looks like a price series. See [docs/DATA_POLICY.md](docs/DATA_POLICY.md).
5. **Negative results are results.** Most questions in the report end in grade D. That is the product working.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md): longer intraday history, Nasdaq-100, futures sessions, Bitcoin on-chain cohorts, insider and institutional filings, a statistics API, and a predictive modelling track that is held to the same standard of evidence.

## Disclaimer

Research and education only. Nothing in this repository or on the website is investment advice or an offer or solicitation to buy or sell any security or digital asset. Historical frequencies do not guarantee future outcomes.

## License

Code: [Apache License 2.0](LICENSE). Market data remains the property of its providers and is not redistributed.
© 2026 Carlos Saritama.
