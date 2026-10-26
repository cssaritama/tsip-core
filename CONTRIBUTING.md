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
