# Specification 0012: Extreme Multi-Session Expansions and Retracement Velocities (W-78)

## 1. Context and Problem Statement
When major benchmark equity indices (SPY, QQQ) experience extreme short-horizon expansions ($\le -3.5\sigma$ or $\ge 5\%$ drawdowns within 48 hours / 2 trading sessions), retail participants frequently interpret the move as the onset of prolonged structural collapse. Institutional execution desks, conversely, treat tail liquidity sweeps as potential wells where late-selling liquidity is absorbed to rebalance delta exposure.

Currently, operators lack an empirical, scale-invariant reference table answering:
1. When has an expansion of this magnitude occurred historically?
2. What is the historical velocity and Kaplan-Meier probability distribution to reach the 50% impulse equilibrium (mean reversion)?
3. What is the probability of recovering the swept prior period lows versus continuing into persistent trend drawdown?

## 2. Mathematical Definition
Let $C_t$ be the official session closing price on trading day $t$.
A 2-session tail expansion event is triggered when:
$$R_{2d}(t) = \frac{C_t - C_{t-2}}{C_{t-2}} \le \theta_{\text{tail}}$$
where $\theta_{\text{tail}} = -5.0\%$ for QQQ (Nasdaq-100) and $-4.0\%$ for SPY (S&P 500).

For each event $i$:
1. **Impulse Span**: $\Delta_i = C_{t-2} - C_t > 0$.
2. **Equilibrium Level (50% Retracement)**:
   $$L_{\text{eq}, i} = C_t + 0.5 \cdot \Delta_i$$
3. **First Passage Time to Equilibrium**:
   $$\tau_{50, i} = \min \left\{ k \in \{1, \dots, K\} : H_{t+k} \ge L_{\text{eq}, i} \right\}$$
   where $H_{t+k}$ is the session high on day $t+k$, and $K = 60$ sessions.
4. **Post-Event Drawdown**:
   $$D_{\max, i} = \min_{1 \le k \le K} \left( \frac{L_{t+k}}{C_t} - 1 \right)$$

## 3. Empirical Baseline (Kibot 2006–2025 Historical Corpus)
Evaluating 20 years of continuous daily data (5,032 sessions) yields:

### QQQ ($\theta_{\text{tail}} \le -5.0\%$, $N = 41$ independent events):
- **Median Sessions to 50% Equilibrium ($\tau_{50}$)**: **2.0 sessions**.
- **Reach Rate within 10 Sessions**: **80.5%**.
- **Reach Rate within 20 Sessions**: **85.4%**.
- **Median Forward Return at 20 Sessions**: **+3.88%** (63.4% positive).
- **Median Forward Return at 60 Sessions**: **+7.27%** (68.3% positive).

### SPY ($\theta_{\text{tail}} \le -4.0\%$, $N = 54$ independent events):
- **Median Sessions to 50% Equilibrium ($\tau_{50}$)**: **2.0 sessions**.
- **Reach Rate within 10 Sessions**: **87.0%**.
- **Reach Rate within 20 Sessions**: **87.0%**.
- **Median Forward Return at 20 Sessions**: **+3.15%** (64.8% positive).
- **Median Forward Return at 60 Sessions**: **+7.24%** (72.2% positive).

## 4. Prior Low Sweeps and Absorption
When the 2-session expansion penetrates below the Prior Month Low ($L_t < L_{\text{month}-1}$) and the session closes back above that reference level within 48 hours ("Liquidity Absorption"), the empirical 20-session win rate rises to 100% across the sample ($N=2$, median forward return $+2.28\%$). When the level is broken without immediate absorption, median 20-session return remains $+3.32\%$ with a 62.5% recovery rate.

## 5. Formal Forward Hypothesis Registration
- **ID**: `H-2026-016`
- **Instrument**: `QQQ`, `SPY`
- **Family**: `tail_expansions`
- **Statement**: Following a 2-session close-to-close decline exceeding $3.5\sigma$ (or $\le -5\%$ in QQQ / $\le -4\%$ in SPY), the price reaches the 50% expansion midpoint within 10 sessions more frequently than a distance-matched null control from stationary bootstrap resamples.
- **Metric**: Difference in empirical Kaplan-Meier 10-session reach rate against distance control.
- **Criterion**: Positive point difference with lower 95% bootstrap confidence interval $> 0$ (Grade A or B).
- **Status**: Open.
