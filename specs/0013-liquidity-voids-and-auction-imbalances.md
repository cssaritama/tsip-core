# Specification 0013: Liquidity Voids, Auction Imbalances, and Mean Fill Dynamics (W-79)

## 1. Context and Quantitative Motivation
When price moves with extreme directional velocity, standard two-way continuous auction clearing is disrupted. In institutional auction theory, a single-print price displacement creates a **Liquidity Void** (often termed a Fair Value Gap): a range where buy and sell orders were not symmetrically matched.

Traders frequently assume every void must fill immediately. This study formalizes the exact mathematical criteria for institutional voids, establishes their empirical fill velocities across 20 years of tick-verified index data (2006–2025), and tests the magnetic pull of the 50% void midpoint (Consequent Encroachment).

## 2. Mathematical Definition
Let $H_t$ and $L_t$ represent session high and low on day $t$. Let $\text{ATR}_{14}(t)$ be the 14-session average true range.
A 3-session auction imbalance is formed on session $t$ when:

1. **Bearish Displacement Void (Downside Imbalance):**
   $$L_{t-2} > H_t \quad \text{and} \quad \Delta_{\text{void}} = L_{t-2} - H_t \ge \theta_{\text{atr}} \cdot \text{ATR}_{14}(t)$$
   - Void Range: $[H_t, L_{t-2}]$
   - 50% Midpoint (Consequent Encroachment): $M_{\text{void}} = H_t + 0.5 \cdot \Delta_{\text{void}}$

2. **Bullish Displacement Void (Upside Imbalance):**
   $$L_t > H_{t-2} \quad \text{and} \quad \Delta_{\text{void}} = L_t - H_{t-2} \ge \theta_{\text{atr}} \cdot \text{ATR}_{14}(t)$$
   - Void Range: $[H_{t-2}, L_t]$
   - 50% Midpoint: $M_{\text{void}} = H_{t-2} + 0.5 \cdot \Delta_{\text{void}}$

Threshold: $\theta_{\text{atr}} = 0.5$ ATR (filtering out noise to isolate institutional imbalances).

## 3. Empirical Baseline (Kibot 2006–2025 Historical Corpus)

### QQQ ($N = 644$ institutional voids):
- **Median Sessions to Reach 50% Midpoint ($M_{\text{void}}$):** **4.0 sessions**.
- **Reach Rate within 5 Sessions:** **51.6%**.
- **Reach Rate within 20 Sessions:** **70.7%**.
- **Full Void Close Rate within 20 Sessions:** **59.6%**.

### SPY ($N = 687$ institutional voids):
- **Median Sessions to Reach 50% Midpoint ($M_{\text{void}}$):** **3.0 sessions**.
- **Reach Rate within 5 Sessions:** **52.4%**.
- **Reach Rate within 20 Sessions:** **71.0%**.
- **Full Void Close Rate within 20 Sessions:** **61.6%**.

## 4. Forward Hypothesis Registration
- **ID**: `H-2026-017`
- **Instrument**: `SPY`, `QQQ`
- **Family**: `liquidity_voids`
- **Statement**: An institutional 3-session auction void ($\ge 0.5 \text{ ATR}$) reaches its 50% midpoint within 20 sessions more frequently than a distance-matched null control (observed $\ge 70\%$ against $\approx 55\%$ control).
- **Metric**: Difference in empirical Kaplan-Meier 20-session reach rate against distance control.
- **Criterion**: Positive point difference with lower 95% bootstrap confidence interval $> 0$ (Grade A or B).
- **Status**: Open.
