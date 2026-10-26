# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's *Report a vulnerability* button on this repository (Security → Advisories). Do not open a public issue. You will receive an acknowledgement within five working days.

## Scope

* The Python package and command line interface.
* The GitHub Actions workflows.
* The static website.

## Secrets

The only secrets the project uses are optional market data credentials (`ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`). They are read from the environment or from GitHub Actions secrets and are never written to disk or logs. The website has no server, no cookies and no third-party scripts.
