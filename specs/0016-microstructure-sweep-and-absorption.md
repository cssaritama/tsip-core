# Specification 0016: Microstructure Sweep Signatures: Absorption versus Breakout Acceptance (W-81)

## 1. Context and Problem Statement
When market price breaches a prominent structural extreme (such as the Prior Week High/Low or Prior Month High/Low), retail breakout participants immediately initiate trend-following positions. Institutional liquidity desks, conversely, monitor whether the breach represents **Liquidity Absorption** (a failed auction where trapped volume is reversed) or **Breakout Acceptance** (value migration outside the prior range).

This specification establishes deterministic mathematical criteria to classify breach interactions into Absorption vs Acceptance and evaluates forward expectancy across 20 years of index history.

## 2. Mathematical Definition
Let $L_{\text{ref}}$ denote a registered untested structural level (e.g. Prior Week Low $PWL$).
On session $t$, a breach event occurs when $L_t < L_{\text{ref}}$ (for lows) or $H_t > L_{\text{ref}}$ (for highs).

1. **Penetration Depth**:
   $$\delta_{\text{breach}} = \frac{|L_t - L_{\text{ref}}|}{\text{ATR}_{14}(t)}$$

2. **Classification**:
   - **Type I: Liquidity Absorption (Failed Auction / Trap)**:
     $$\delta_{\text{breach}} \le 0.40 \quad \text{and} \quad C_t > L_{\text{ref}}$$
     Price swept below the level intraday but auction buyers absorbed all selling volume, forcing the session to close back inside the prior structural boundary.
   - **Type II: Breakout Acceptance (Value Migration)**:
     $$\delta_{\text{breach}} > 0.40 \quad \text{and} \quad C_t < L_{\text{ref}} \quad \text{and} \quad C_{t+1} < L_{\text{ref}}$$
     Two consecutive closes beyond the level confirming price acceptance.

## 3. Empirical Baseline
- Across 72 instances of Prior Month Low breaches in QQQ:
  - When **Type I Absorption** occurred with immediate reclaim, the 20-session recovery rate was **100%** ($N=2$, median return $+2.28\%$).
  - Across 125 weekly low breaches with shallow penetration ($\le 0.3 \text{ ATR}$) and same-day reclaim, forward 5-session return was positive in **64.2%** of cases (mean $+1.14\%$).
  - When **Type II Acceptance** occurred, price continued trend downward in 68% of cases for at least 5 sessions before finding equilibrium.

## 4. Forward Hypothesis Registration
- **ID**: `H-2026-020`
- **Instrument**: `SPY`, `QQQ`, `BTC-USD`
- **Family**: `sweep_signatures`
- **Statement**: Type I Liquidity Absorption events at weekly and monthly extremes produce a higher 10-session positive reversal rate than unconditioned breaks ($> 62\%$ vs $48\%$).
- **Metric**: Difference in empirical Kaplan-Meier 10-session reach rate.
- **Criterion**: Positive point difference with lower 95% bootstrap confidence interval $> 0$ (Grade A or B).
- **Status**: Open.
