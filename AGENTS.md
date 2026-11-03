# Contributor and automation guide

Rules for anyone, person or tool, changing this repository.

1. **Read first:** `README.md`, `docs/TIME_SPACE_MODEL.md` (every study sits on the time axis, the space axis or both), `docs/METHODOLOGY.md` and `docs/DATA_POLICY.md`. Website changes also follow `docs/DESIGN.md`.
2. **Evidence:** every statistic is an evidence card with sample size, interval, control, holdout, q-value and grade. A new study must pass the random-walk test: on simulated data it gives no A or B grade.
3. **No look-ahead:** inputs are frozen when the event is observed; incomplete windows are excluded or censored, never dropped selectively.
4. **Data:** only derived statistics and distances are published; no bars, price levels, keys or `.env` files enter the repository or the report (`tsip.report.publish.assert_publishable`).
5. **Checks before a change is done:** `pytest`, `ruff check src tests`, `ruff format --check src tests`, and a report built from a store with an OHLC and a close-only instrument that serialises without non-finite numbers.
6. **Document in the same change:** `CHANGELOG.md`, and the methodology, model, design or data policy when they change. New public claims are pre-registered in `registry/hypotheses.json` before results are seen.
7. **Style:** English, conventional-commit messages, no references to the tools used to produce a change.
