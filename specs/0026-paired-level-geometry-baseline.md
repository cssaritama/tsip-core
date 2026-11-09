# 0026 · Paired-level geometry baseline

Status: private descriptive runner implemented. W-90/W-97 require further research and independent approval before display.

## Decision

When a trader chooses one level above and one below the close, what usually happens at those distances over a fixed window? Answer upper first, lower first, neither, and order ambiguous. Show typical time among observed first touches and count strict opening gaps separately. This informs which scenario to prepare and how long to keep watching.

## Estimand and controls

- Apply the same signed close-relative distances at each historical close. Start at the next regular session. Use the XNYS calendar, preserve holidays and exclude windows with missing sessions or insufficient follow-up. The cutoff must be a complete session date.
- The open resolves order when at or beyond a barrier. An open strictly beyond it is a gap. An inside open with both levels reached in the same bar is ambiguous. Shares sum to one across eligible windows. Ambiguity bounds assign all ambiguous windows to each side in turn and express ordering uncertainty only.
- This is a fixed-distance baseline with overlapping windows. It has no sampling interval, volatility matching, calibration, strategy or execution price. It cannot identify the incremental effect of actual reference levels. See [competing-events methodology](https://pmc.ncbi.nlm.nih.gov/articles/PMC4741409/) for the distinction between competing events and ordinary censoring.

## Reproduce

Install the calendar extra and use an authorized local CSV containing date, open, high, low, close and at least 40 rows. Select cutoff, distances and horizon before running. Save only aggregates in approved locations.

```sh
python -m tsip.research.cli paired-levels --symbol SPY --origin licensed-research --csv /path/to/authorized-daily.csv --as-of 2026-11-06 --down-pct=-0.358 --up-pct=5.48 --horizon 5 --out /path/to/local-results.json
```

## Promotion gates

1. Register the actual level selection, cutoff, horizon and volatility-matched comparison before scoring. Reconstruct levels strictly as of each historical anchor. Use one instrument, source and adjustment basis.
2. Require block-aware uncertainty, chronological holdout with a gap, and independent challenge. Check ambiguity and abstain if uncertainty prevents a meaningful distinction.
3. Test whether the comparison changes a desk decision before promotion. Assess costs, gaps and executable prices separately for any economic claim.

Follow-on questions: How long should a scenario remain relevant? How far does the price typically move against it before the first touch? Does a volatility regime or scheduled event improve the baseline? Does any result survive costs? Use the gates in spec 0021.

Verification: synthetic CLI dry run produced 131 eligible windows and five terminal exclusions. Focused regression fixtures exercised all four outcomes, strict opening gaps, ambiguous bars, holidays, missing sessions and the cutoff. No empirical market result was produced.
