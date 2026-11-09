# Specification 0017: Institutional Execution and Risk Matrix (W-82)

**Status: blocked research proposal.** The display was withdrawn in core 3de72ca. The historical text below preserves the proposal. The void-fill frequency is a different endpoint from target-before-stop; the Sharpe thresholds conflict. With the stated inputs quarter Kelly is approximately 12.3%, and a 2% cap would be a separate rule. No sizing or execution claims may be promoted from this specification pending independent validation. See [0018](0018-desk-brief-and-pilot.md) for the proposed desk workflow.

## 1. Context and Problem Statement
Operators currently have access to individual quantitative cards: Time profiles, Space levels, Auction Voids, and Session Momentum. However, an institutional portfolio manager or execution desk requires a unified synthesis that answers:
1. What is the current **Market Posture** (Accumulation, Expansion, Distribution, or Neutral)?
2. What is the mathematical **Trade Action** from the current coordinate?
3. What are the exact bounded execution parameters: Entry, Structural Stop, Target, Expected Value ($E$), and Kelly-optimal position sizing ($f^*$)?

## 2. Mathematical Definition
Let $C_t$ be the latest session close, $\text{ATR}_{14}(t)$ the 14-session ATR, and $L_{\text{ref}}$ the nearest swept low.

### A. Market Posture Classification:
- **Accumulation (Absorption Well)**:
  Triggered when $L_t < L_{\text{pml}} \land C_t > L_{\text{pml}}$ (Type I sweep absorption), OR when a 48h tail drop $\le -3.5\sigma$ reaches the 50% impulse well, OR when an extreme capitulation close occurs ($\pi_t \le 0.20 \land R_{1d} \le -1.5\%$).
- **Distribution (Overhead Exhaustion)**:
  Triggered when $H_t > H_{\text{pmh}} \land C_t < H_{\text{pmh}}$ (overhead liquidity sweep) with relative volume $> 1.5\text{x}$.
- **Expansion (Trend Continuation)**:
  Triggered when price prints 2 consecutive closes outside prior weekly range with momentum $R_{5d} > 1.5\text{ ATR}$.
- **Neutral (Equilibrium Balance)**:
  Price oscillates within the middle 50% of the active range with no active void or swept level within $1.0\text{ ATR}$.

### B. Execution Parameters for Accumulation Setup:
- **Entry Price ($P_{\text{entry}}$)**: $C_t$ (Latest Close).
- **Structural Stop ($P_{\text{stop}}$)**:
  $$P_{\text{stop}} = \min(L_t, L_{\text{ref}}) - 1.2 \cdot \text{ATR}_{14}(t)$$
- **Target Price ($P_{\text{target}}$)**:
  $$P_{\text{target}} = C_t + 1.8 \cdot \text{ATR}_{14}(t) \quad \text{or} \quad M_{\text{void}}$$
- **Asymmetric Risk-Reward Ratio ($R:R$)**:
  $$\text{RR} = \frac{P_{\text{target}} - P_{\text{entry}}}{P_{\text{entry}} - P_{\text{stop}}} \ge 1.30$$
- **Empirical Win Probability ($P_{\text{win}}$)**:
  $71.0\%$ (derived from W-79 auction void and absorption empirical baseline).
- **Kelly Position Sizing ($f^*$)**:
  $$f^* = \frac{P_{\text{win}} \cdot b - (1 - P_{\text{win}})}{b}$$
  where $b = \text{RR}$. With $P_{\text{win}} = 0.71$ and $b = 1.33$, raw Kelly is $\approx 49\%$. Scaled by institutional quarter-Kelly ($0.25 f^*$): **Risk budget $= 2.0\%$ of portfolio equity**.

## 3. Forward Hypothesis Registration
- **ID**: `H-2026-021`
- **Instrument**: `SPY`, `QQQ`
- **Family**: `execution_matrix`
- **Statement**: Trades executed exclusively when the Institutional Posture indicates Accumulation (with $R:R \ge 1.30$ and structural stop) produce a positive net Sharpe ratio $\ge 1.20$ across rolling 3-year periods after all friction costs.
- **Metric**: Annualized net Sharpe ratio after round-trip trading cost.
- **Criterion**: Sharpe ratio $> 1.0$ with $p < 0.05$ against stationary bootstrap control.
- **Status**: Open.
