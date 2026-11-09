# 0018 · Desk Brief and shadow pilot

Status: proposed. Baseline: 0.2.24. One audience for the first experiment: a US equity ETF swing trader preparing the next regular session after the SPY close. The job is deciding which scenario deserves preparation and which can wait. QQQ and crypto remain available in research.

## Interface contract

| Layer | Content | Behavior |
|---|---|---|
| Brief | Instrument, venue/session, market-data cutoff, report age, coverage state; one reference above and one below, with distance in percent; one relevant conditional comparison when eligible | One desktop viewport at 1440 × 900. No carousel. Plain-language verdict when evidence is insufficient. |
| Scenario | A reference level, what would invalidate its relevance, fixed horizon, observed frequency, comparable baseline and uncertainty | On demand. Keep descriptive observations distinct from conditional comparisons. Do not infer fills from touches. |
| Evidence | Sample, interval, baseline definition, holdout, grade where applicable, data lineage, report fingerprint and methodology version | One click from the claim. The same archived snapshot can be replayed later. |
| Research | Full time/space map, volatility, calendar, money and trade-plan studies | Explicit navigation. Preserve access and deep links. Label simulated plans and their assumptions. |

Only display prices where cleared. Show percentages with explicit units and as-of time. Label session clock and report age separately. If data is stale, missing, degraded for the required measure, or validation is pending, suppress the affected current scenario and explain why. Avoid directional labels on descriptive cards. A qualifying comparison needs an independent reviewer and an applicability check for the selected asset and horizon. Current grade alone does not grant eligibility.

## Acceptance and sequence

1. **Contract** · Product owner signs the single user, decision, data state definitions and first-view content. Product Designer produces a clickable prototype with normal, stale, missing and insufficient-evidence snapshots.
2. **Integrity** · Data and Quant close or isolate W-01/W-02/W-03 for each promoted card. Test incomplete sessions/periods, adjusted-history revisions and mismatched historical analog zones. Missing/stale and close-only fixtures must never show an unavailable current scenario.
3. **Evidence** · Independent reviewer reproduces one eligible comparison from its archive. Freeze the universe, timing, baseline, selection rules and costs before scoring the pilot. Check comparability of volatility and distance. Record rejection as a first-class outcome.
4. **Display** · Verify desktop and phone with keyboard/touch, both colour schemes, and stale/empty states. Existing research remains reachable. Run W-45 in CI on synthetic and archive fixtures. Replaying the same report and version must yield the same evidence.
5. **Shadow pilot** · Proposed design: 5–8 professional users, 10 sessions, paired and counterbalanced comparison of Brief and existing board. Use identical dated snapshots and record the decision before revealing outcomes. Pre-register provisional success as median time to identify relevant levels and data status ≤30 seconds and ≥25% faster than the current board, at least 80% correct interpretation of baseline versus conditional evidence, and zero instances of treating stale data as current. Record changed preparations and mistaken actions with reasons. Small pilot estimates usability, not economic value. A separate prospective economic evaluation would require executable prices, costs, slippage, risk and explicit approval.
6. **Release** · Private pilot only after approved use rights, operational owner and rollback drill. Save a pilot scorecard and founder decision before wider access.

Out of pilot scope: signals, sizing, Kelly, order routing, brokerage, new asset classes and real-time claims. No implementation or study is marked complete by this specification.
