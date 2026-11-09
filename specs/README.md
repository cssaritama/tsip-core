# Specifications

TSIP is built with **spec-anchored development with evidence gates**: every feature or study starts from a short specification that states what it is for and how it will be checked, and the specification stays in the repository and is kept current as the product changes. The full way of working is in the private repository (`tsip-platform/docs/operations/WAY_OF_WORKING.md`, ADR 0064); this folder holds the specifications of the public product.

## When a specification is needed

| Level | Change | What is required |
|---|---|---|
| 0 | Fix, copy, style, dependency, refactor without new behaviour | No specification. A regression test or a render check, and a `CHANGELOG.md` line |
| 1 | Feature: a screen element, a report field, a tool | A specification in this folder before the code |
| 2 | Study or public claim | A specification with a study protocol (question, unit, control, statistic, grading, random-walk test) written before the study is run on real data; a public claim is also pre-registered in `registry/hypotheses.json` |

Existing behaviour is specified by the reference documents: `docs/METHODOLOGY.md` (statistics and grading), `docs/TIME_SPACE_MODEL.md` (what each study measures), `docs/DATA_POLICY.md` (what may be published) and `docs/DESIGN.md` (the decision standard and the page). A specification adds to them; when it ships, the reference documents are updated in the same change.

## Life of a specification

1. **Draft:** problem, decision supported, requirements, acceptance criteria, non-goals. Each acceptance criterion names how it is verified (a test, a render check or a founder review).
2. **Approved:** the founder approves the what (problem, criteria, non-goals); the team owns the how. A request made explicitly by the founder counts as approval of the problem, and the criteria are reviewed at delivery.
3. **In progress:** tests are written for the criteria first where possible; implementation follows in small steps.
4. **Shipped (version):** the verification table is filled with what was actually checked, and the status names the release.
5. **Kept current:** a later change to the same behaviour updates the specification in the same commit, or supersedes it with a new one.

## Template

```markdown
# NNNN Title

**Status:** draft | approved | in progress | shipped (version) | superseded by NNNN
**Level:** 1 feature | 2 study · **Open work:** W-xx · **Decisions:** ADR xxxx

## Problem and decision supported
## Requirements
R1. When ..., the report (or page) shall ...
## Acceptance criteria
| ID | Criterion | Verified by |
## Non-goals
## Data contract
## Study protocol (level 2)
## Design notes
## Tasks
## Verification
| ID | Result | Evidence |
```

## Index

| Spec | Title | Status |
|---|---|---|
| [0001](0001-money-terms.md) | Money terms: from here to the end of the period | shipped (0.2.13); items 5 and 6 superseded by 0003 |
| [0002](0002-readable-charts.md) | Readable charts and the render check | shipped (0.2.13) |
| [0003](0003-money-terms-all-horizons-and-costs.md) | Money terms: all horizons side by side, gross grades and cost profiles | shipped (0.2.16) |
| [0004](0004-exchange-sessions.md) | Exchange sessions, holidays and early closes in the report | shipped (0.2.16) |
| [0005](0005-trade-plan-from-here.md) | Trade plan from here: stop, target and expected result against all periods | shipped (0.2.18) |
| [0006](0006-honest-baselines-and-board-triage.md) | Honest baselines and board triage | shipped (0.2.17) |
| [0007](0007-trade-plans-by-volatility-regime.md) | Trade plans by volatility regime | shipped (0.2.19) |
| [0008](0008-time-of-period-extremes.md) | Time of the period's extremes (month and quarter) | shipped 0.2.22 |
| [0009](0009-test-budget.md) | Test budget: which conditions the history can support | shipped 0.2.22 |
| [0010](0010-revisit-of-monday-and-recent-lows.md) | Revisit of Monday's low and of the recent lows | shipped 0.2.23 |
| [0011](0011-hypothesis-evaluations.md) | Evaluation record for the hypothesis register | shipped 0.2.24 |
| [0012](0012-extreme-tail-expansions-and-reversion.md) | Extreme multi-session expansions, trapped volume and retracement velocities | open (W-78) |
| [0013](0013-liquidity-voids-and-auction-imbalances.md) | Liquidity voids, auction imbalances and mean fill dynamics | open (W-79) |
| [0014](0014-session-momentum-and-overnight-transitions.md) | Session-to-session momentum and overnight transitions | open (W-58) |
| [0015](0015-time-space-opportunistic-accumulation.md) | Time–Space opportunistic liquidity accumulation and 20-year alpha proof | open (W-80) |
| [0016](0016-microstructure-sweep-and-absorption.md) | Microstructure sweep signatures: absorption versus breakout acceptance | open (W-81) |
| [0017](0017-institutional-execution-and-risk-matrix.md) | Institutional execution and risk matrix: posture synthesis, bounded stops, and Kelly sizing | blocked research proposal (W-82); display withdrawn |
| [0018](0018-desk-brief-and-pilot.md) | SPY next-session Desk Brief and shadow pilot | proposed (W-83–W-85) |
