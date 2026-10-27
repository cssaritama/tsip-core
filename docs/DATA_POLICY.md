# Data policy

## Sources

| Market | Primary | Cross-check / fallback | Access |
|---|---|---|---|
| Bitcoin (BTC-USD) | Coinbase Exchange public candles, hourly, from 2015 | Binance public data archive (BTC-USDT), hourly, from 2017, SHA-256 verified | No key |
| S&P 500 (SPY) | Alpaca Market Data, 30-minute bars from 2016, adjusted for splits and distributions | — | Free account (bring your own key) |
| S&P 500 (SPX) | Stooq daily index history (long history, checked for genuine ranges and opens) | FRED `SP500` daily close (close-only) | No key |
| Nasdaq-100 (QQQ) | Alpaca Market Data, 30-minute bars from 2016, adjusted for splits and distributions | — | Free account (bring your own key) |
| Nasdaq-100 (NDX) | Stooq daily index history | — | No key |

ETF and index series are separate instruments and are never combined: sessions and intraday questions use the ETFs; prior-period levels over long horizons and calendar questions also use the index histories.

The connectors never fill, interpolate or invent observations. FRED is a close-only series: studies that need opens, highs or lows are skipped rather than approximated.

## What is published

Only **derived, aggregated statistics** (frequencies, means, differences, intervals and grades over years of data) are published. Raw bars are cached locally and in the build environment, and are never committed or deployed. The publication guard (`tsip.report.publish.assert_publishable`) fails the build if the report contains price-series fields or long numeric arrays.

## Provenance

Every cached dataset has a JSON sidecar recording source, instrument, timeframe, price basis, data feed, row count, time coverage, retrieval time and SHA-256. The same fields appear in the report's data section.

## Quality checks published with each report

* Bitcoin: hourly completeness (expected versus present bars) and an independent-feed cross-check: correlation of hourly returns and median close difference between Coinbase BTC-USD and Binance BTC-USDT.
* Off-grid source bars are retained with their original timestamps. They are never moved to a different clock interval by rounding. Cross-feed statistics are unavailable and UTC-day aggregation is rejected when alignment is unresolved. An original source record and a reconstructed analysis bar are different objects.
* February 2018 Binance verification: the checksum-verified hourly archive contains 640 records, 43 off-grid intervals crossing clock-hour boundaries, and one overlapping interval. Its one-minute archive also contains shifted intervals; simply summing minute bars is not an exact repair. Trade-level reconstruction, provenance, overlap reconciliation and coverage checks remain pending. Cached data previously filtered by v0.2.2 need re-acquisition; reading a reduced cache cannot recover missing records.
* S&P 500 and Nasdaq-100: observed sessions versus the New York Stock Exchange calendar.
* Long index histories: the first dates with genuine daily ranges and genuine opens (see the methodology), and how many months were left out.

## Terms of use

Each provider's terms govern the use of its data. Before any commercial use, review the current terms of every source and keep a dated copy. Statistics derived from the data do not transfer any right to the underlying data. This document is not legal advice.

## Verified February 2018 reconstruction (v0.2.4)

The preceding v0.2.3 preservation guard remains the generic policy. The specifically investigated BTC-USDT interval is now repaired during Binance fetch/cache updates when the stored history covers February 9–12, 2018. Three official daily aggregate-trade archives must supply records with consecutive aggregate and underlying trade IDs and nondecreasing timestamps. OHLC and summed quantity are reconstructed by UTC trade hour; no observation is fabricated for hours without trades. The development run reported 1,066,634 records and 62 occupied hours; these figures are pending re-verification against the manifest of the first production run. All affected source dates, including the overlapping regular boundary hour, are replaced in the derived cache only after validation succeeds.

Original affected cached rows, checksum-verified archives and a hash-linked manifest are retained under the data directory's `source_evidence/binance` folder, excluded from Git. A repair marker persists in the cache metadata, so a v0.2.2 cache can recover filtered history and normal incremental updates do not repeat the repair. Histories that do not span the affected dates remain unchanged. Unknown irregular intervals still require investigation; source agreement does not independently certify every underlying exchange trade. On checksum/identity/coverage failure, the existing cache is not rewritten.
