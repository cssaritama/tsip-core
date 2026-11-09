# 0027 · Historical weekly references versus geometry

Status: private research prototype. Freeze this contract before inspecting market results.

## Cohort and primary comparison

- Start with SPY, five regular sessions, and the closest still-untested high above and low below the anchor close from the previous 12 calendar weeks. Require exact calendar coverage for those weeks, the current week through the anchor, and the forward window. Use regular-session OHLC only. The anchor cannot see its forward bars. This weekly-only cohort is narrower than the mixed-horizon live map.
- Use log-return volatility from the previous 60 complete daily returns, including the anchor close. Chronologically split expected session dates 70/30. Use controls from the first 70% whose entire five-session outcome is observed before the split. Score actual levels on the final 30% only.
- Choose up to 20 controls with volatility closest to the anchor, within ±20% of anchor volatility, with a minimum of five. Transfer both signed log distances in volatility units to each control close. This preserves distance asymmetry and normalized width. Controls describe typical paths at similar volatility; they can still differ by regime or weekday.
- Primary statistic: mean difference in upper-first share between real levels and their matched geometric controls, in percentage points. Record lower first, neither and ambiguous for context. Opening gaps resolve ordering without claiming fills. Record exclusions and sample counts.
- Keep holdout session spacing for a circular block bootstrap, with 20-session blocks and a fixed seed. Only compute the exploratory interval with at least 40 matched anchors across at least 40 holdout sessions. The interval conditions on the chosen control pool; reused controls and regime drift can make the uncertainty wider. Do not use this as an evidence grade or a market claim.

## Reproduce and advance

Install the calendar extra. Use an authorized, local daily OHLC CSV with one instrument, adjustment basis and source. Choose the cutoff before running.

```sh
python -m tsip.research.cli matched-weekly-levels --symbol SPY --origin licensed-research --csv /path/to/authorized-daily.csv --as-of 2026-11-06 --out /path/to/local-results.json
```

Use synthetic fixtures to verify mechanics. Independent review must reproduce selected anchors, check calendar and adjustment integrity, test sensitivity to control reuse and volatility regime, and sign off before reporting a market estimate. If results fail to separate from geometry, keep the result as a baseline. The next extension, after review, is time and adverse excursion before the first touch.

Verification: the reproducible synthetic fixture in tests/research/test_matched_levels.py exercised 154 matched anchors, a separate calibration pool and the exploratory interval. Synthetic outputs verify mechanics only. No market result has been produced.
