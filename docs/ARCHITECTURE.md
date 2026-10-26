# Architecture

```
            ┌─────────────── scheduled GitHub Actions run (daily) ───────────────┐
            │                                                                    │
 Coinbase ──┤  tsip fetch btc ──┐                                                │
 Binance  ──┤  tsip fetch btc ──┼──> data/raw/<source>/<instrument>_<tf>.csv.gz  │
 Alpaca   ──┤  tsip fetch spx ──┤     + provenance JSON (cached between runs)    │
 Stooq/FRED─┤                   ┘                                                │
            │                                                                    │
            │  tsip report ── frames ── studies ── evidence ── grading ── guard  │
            │        └──> site/data/report.json (aggregates only)                │
            │                                                                    │
            │  tsip site ──> dist/ ──> GitHub Pages                              │
            └────────────────────────────────────────────────────────────────────┘
```

## Design choices

| Decision | Reason |
|---|---|
| Static site plus a JSON report | No server, no database, no attack surface, free hosting; the report is a versioned artifact. |
| Python core with pandas and numpy only | Reproducible anywhere; optional `exchange_calendars` for calendar checks. |
| Standard-library HTTP client | No network dependency in the core; connectors are testable offline through an injected `getter`. |
| Incremental cache restored between workflow runs | Each daily run downloads only the newest bars. |
| One evidence engine for every study | Studies only define units and a statistic; resampling, holdout, multiple testing and grading are shared. |
| Publication guard | The pipeline cannot deploy raw vendor data, even by mistake. |

## Adding a study

1. Write a function `run(ctx: StudyContext) -> list[EvidenceCard]` in `src/tsip/studies/`.
2. Express the data as time-ordered units (a dict of arrays) and the question as a statistic over units.
3. Call `tsip.evidence.evaluate` with an appropriate block length, then `items_from_evaluation`.
4. Register the module in `tsip.report.build.STUDIES` and add tests, including a random-walk test that must come out ungraded.
