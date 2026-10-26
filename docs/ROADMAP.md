# Roadmap

| Release | Scope |
|---|---|
| 0.1 | S&P 500 and Bitcoin; level memory, sessions, weekly structure, paths, entries, calendar; evidence grades; daily report; hypothesis register. |
| **0.2** (current) | Nasdaq-100 (QQQ, NDX); long daily index histories; prior-period levels for weeks, months, quarters, half-years and years; "where we are now" analog cards. |
| 0.2.x | Prior-period levels against a drift-and-volatility control; base rates conditioned on the volatility regime (VIX); rolling 6/12/18/24/25-hour windows; Monday range; session break-and-hold; a second daily source for ETF highs and lows; Spanish edition of the site. |
| 0.3 | Predictive track: a unified feature table of time–space coordinates and cross-market variables (VIX, Bitcoin–S&P 500 correlation), gradient-boosted and linear models for forward returns, and strategy simulation against total-return benchmarks. Every model is evaluated with the same evidence rules. |
| 1.0 | End-to-end automation: alerts, a container image, a read-only or paper-trading broker connection and the predictive track on a schedule. |
| 1.1 | Read-only statistics API and an MCP server, so that AI agents and orchestrators can query grades and the current position against prior-period ranges before they act. |
| 1.2 | Bitcoin on-chain cohorts: cost basis of large holders, exchange flows, each published as a hypothesis with its own grade. |
| 1.3 | Insider purchase clusters (SEC Form 4) and institutional holdings (13F, 45-day lag disclosed), with tests of copy strategies after the real reporting delay. |
| 1.4 | Index futures sessions (ES, NQ) once a suitable data feed is in place. |

Items move only when the previous release's statistics are reproducible from a clean checkout.
