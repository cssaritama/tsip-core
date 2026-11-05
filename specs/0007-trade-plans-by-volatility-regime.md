# 0007 Trade plans by volatility regime

**Status:** shipped (0.2.19); specified and pre-registered on 2026-11-05 before any real-data result of this study was seen
**Level:** 2 study · **Open work:** W-36, W-52 · **Decisions:** ADR 0066

## Problem and decision supported

The first real trade-plan results (`tsip-platform/docs/research/RESULTS_2026-11-05_PLAN.md`) show no plan graded A or B when periods are grouped by the prior period's high and low. TSIP's strong evidence is about volatility (how much and when price moves), not about levels. The next question a trader asks is therefore whether the result of the same simple plans depends on the volatility regime the period starts in: calm, normal or volatile against the market's own history.

## Requirements

- R1. For each period in progress (week, month), the report shall classify every past period and the current one by the percentile of its starting ATR (the 14-session ATR at the last session of the prior period) among all earlier sessions' ATR values: calm (below the 33rd percentile), normal, volatile (at or above the 67th). Only sessions before the period's start enter the percentile; at least 250 earlier sessions are required.
- R2. For the periods in today's regime, observed after the same number of sessions as today, the report shall give the six plans of specification 0005 (same path rules, same stop and targets) against all periods at the same point, graded the same way.
- R3. The trade plan tile shall show, under its table, the regime of today's period and the result of the long held to the period's end in that regime, with its grade; the Today panel treats an A in these cards like an A in the plan cards.
- R4. On random walks no item may be graded A or B.

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| G1 | A period's regime uses only ATR values of sessions before the period starts | test |
| G2 | The current period's regime and the analogs' regimes use the same rule and thresholds | test |
| G3 | No A or B on simulated random walks | random-walk test |
| G4 | The tile line names the regime and its percentile; render check passes | render check, browser check |

## Non-goals

- No combination of regime and level state in this version (too few periods per cell).
- No implied volatility (VIX) yet; the regime is the market's own ATR. VIX is a later step once its data terms are read (W-36).

## Data contract

Cards `{code}.plan_regime.{week|month}`, family `plan_regime`, kind `edge`, unit `ATR`, in the section "Trade plan from here". Items and `extra` as in specification 0005. Card `state`: horizon, period, sessions elapsed, `regime` (calm, normal or volatile), `atr_start_pct`, `atr_start_percentile`, `analogs`, `all_periods`, `path_from`, `as_of`.

## Study protocol

- **Unit, path, outcomes, control, bootstrap, holdout:** as in specification 0005.
- **State:** regime at the period's start (R1) instead of the prior high and low.
- **Pre-registration:** H-2026-009 and H-2026-010, registered 2026-11-05, evaluated on weeks from 2026-11-09 only.
- **Expected under a random walk:** zero for every plan in every regime.

## Verification

| ID | Result | Evidence |
|---|---|---|
| G1 | passed | `test_atr_percentile_uses_only_earlier_sessions`: a later value never changes an earlier percentile; 250 earlier sessions required |
| G2 | passed | `test_regime_card_compares_with_all_periods`: today's regime equals the rule applied to its percentile; analogs use the same function |
| G3 | passed | `test_plan_random_walk_has_no_edge` now includes the regime cards (hourly and 30-minute random walks): no A or B |
| G4 | passed | browser check on a synthetic 0.2.19 report: the tile line names the regime and percentile for SPY, QQQ and Bitcoin; render check zero problems on the synthetic report and on the live report of 2026-11-05 14:24 UTC. Real figures: with the first 0.2.19 report |

Hypothesis before the first real run (critical-review rule): most regime cards will be D; if any plan differs, it will be the long held in SPY weeks that started volatile (H-2026-009), with a sample of roughly a third of 562 weeks, so B at most.
