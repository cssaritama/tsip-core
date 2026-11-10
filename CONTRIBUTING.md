# Contributing

Thank you for your interest in TSIP.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
ruff check src tests && ruff format --check src tests
```

## Ground rules

* **Every new study ships with a null test.** Run it on a simulated random walk; it must not produce an A or B grade.
* **No look-ahead.** Anything used to form a signal must be known when the signal is observed.
* **No synthetic market data in published output.** Tests may use simulated data; the report may not.
* **Never commit market data, keys or `.env` files.** The `.gitignore` excludes `data/`, `site/` and `dist/`.
* **Document what you change in the same pull request:** methodology in `docs/METHODOLOGY.md`, data sources in `docs/DATA_POLICY.md`, design in `docs/ARCHITECTURE.md` and every user-visible change in `CHANGELOG.md`.
* Keep pull requests focused, with tests, and describe the statistical question the change answers.

## Reporting issues

Please include the command you ran, the data source, the report version and the full error message.

## Rules for every change

These apply to anyone, person or tool, changing this repository.

1. **Read first:** `README.md`, `docs/TIME_SPACE_MODEL.md` (every study sits on the time axis, the space axis or both), `docs/METHODOLOGY.md` and `docs/DATA_POLICY.md`. Website changes also follow `docs/DESIGN.md`.
2. **Specification first:** a new feature or study starts from a specification in `specs/` with acceptance criteria and how each is verified (`specs/README.md`); fixes and small changes need only a test. The specification stays current with the code.
3. **Evidence:** every statistic is an evidence card with sample size, interval, control, holdout, q-value and grade. A new study must pass the random-walk test: on simulated data it gives no A or B grade.
4. **No look-ahead:** inputs are frozen when the event is observed; incomplete windows are excluded or censored, never dropped selectively.
5. **Data:** only derived statistics and distances are published; no bars, price levels, keys or `.env` files enter the repository or the report (`tsip.report.publish.assert_publishable`).
6. **Checks before a change is done:** `pytest`, `ruff check src tests tools`, `ruff format --check src tests tools`, and a report built from a store with an OHLC and a close-only instrument that serialises without non-finite numbers. Website changes also pass `tools/render_check.py` (no console errors, no horizontal scroll, no overlapping chart text).
7. **Document in the same change:** `CHANGELOG.md`, and the methodology, model, design or data policy when they change. New public claims are pre-registered in `registry/hypotheses.json` before results are seen.
8. **Style:** English, conventional-commit messages, no references to the tools used to produce a change.

## Rules and daily review

The rules below hold for everyone who changes this repository, person or tool, and they are checked by code rather than by memory:

```sh
python tools/check_rules.py --since <date of your first commit in this session>
```

It fails when a hypothesis ID is cited that is not in `registry/hypotheses.json`, when two specifications share a number or one is missing from `specs/README.md`, when a tracked file names a tool or an assistant, when public text makes a claim no study can support, when a data file is tracked outside `examples/` and `tests/`, when a commit is not authored by the project owner, or when code under `src/` or `web/` changed without a `CHANGELOG.md` change. It runs in CI on every push, and every day in the **Daily review** workflow (`.github/workflows/daily-review.yml`), which also runs the tests and checks that the published report is fresh. Nothing in this procedure depends on a particular tool: anyone can run the same command, and anyone can read the result in the Actions tab.

Before writing, start from the current `main` on GitHub and take new numbers (specifications, hypotheses) from it; publish each finished step at once, so that whoever works next sees it.
