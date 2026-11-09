# 0024 · Reference Levels visual hierarchy

Status: implemented for the reference view. Decision task: identify the closest eligible reference on each side of the last complete close before inspecting historical evidence.

## Design contract

- Use the site's light or dark theme throughout. Show the instrument, reference close date and data status before the references. Explicitly label stale snapshots as historical.
- Show at most three nearest untested references above and three below. Display signed percentages, period labels and aligned distances. Bar length measures absolute distance on a common scale for both groups. Values and direction stay readable without color.
- Keep sample size and interval with historical reach rates at 5, 20 and 60 periods in a keyboard-operable disclosure. Display measured zero and missing separately. The marginal rates do not imply order of first touch, a trade signal or depth.
- Filter by the actual reference horizons. A multiple-horizon filter with zero matches displays an empty state. Keep narrow screens readable with a vertical layout and a scroll container for the expanded evidence table.
- Use [WCAG 2.2 non-text contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) for chart marks and focus indication. Maintain at least 4.5:1 on ordinary text and 3:1 on meaningful graphics against their adjacent colors.

## Follow-up

Use the SPY pilot to check whether traders identify both references and the report cutoff without opening the evidence. Verify additional assets, focus order and screen-reader reading order before declaring broader accessibility coverage. Compare the historical-evidence labels against 0019 before adding a paired probability or changing the compact Session Brief.
