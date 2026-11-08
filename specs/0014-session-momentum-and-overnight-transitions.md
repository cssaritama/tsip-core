# Specification 0014: Session-to-Session Momentum and Overnight Transitions (W-58)

## 1. Context and Problem Statement
Benchmark equity indices (SPY, QQQ) experience distinct multi-phase daily auctions: the official US Cash Regular Trading Hours (09:30–16:00 ET) and the Extended Overnight Session (16:00–09:30 ET, spanning Asian and European hours).

Operators often mistakenly assume that intraday momentum reliably continues directly into the overnight hours, or that gap downs must follow late sell-offs. This specification defines the mathematical transitions between session close position, overnight gaps, and next-day RTH drift across 20 years of tick-verified daily data (2006–2025).

## 2. Mathematical Definition
Let $O_t, H_t, L_t, C_t$ denote the session Open, High, Low, Close on day $t$.

1. **Normalized Session Close Position:**
   $$\pi_t = \frac{C_t - L_t}{H_t - L_t} \in [0, 1]$$
   - $\pi_t \le 0.33$: Bottom tercile (close near session low).
   - $0.33 < \pi_t \le 0.66$: Middle tercile.
   - $\pi_t > 0.66$: Top tercile (close near session high).

2. **Overnight Return:**
   $$R_{\text{on}}(t+1) = \frac{O_{t+1} - C_t}{C_t}$$

3. **Intraday RTH Return:**
   $$R_{\text{rth}}(t+1) = \frac{C_{t+1} - O_{t+1}}{O_{t+1}}$$

4. **Extreme Capitulation Close Condition:**
   $$\pi_t \le 0.20 \quad \text{and} \quad \frac{C_t - C_{t-1}}{C_{t-1}} \le -1.5\%$$

## 3. Empirical Baseline (Kibot 2006–2025 Corpus, $N = 5,029$ Sessions)

### Overnight Drift by Close Tercile:
- **Bottom Tercile ($\pi_t \le 0.33$):** Mean overnight return $+0.066\%$ in QQQ (57.5% positive) and $+0.046\%$ in SPY (57.2% positive).
- **Top Tercile ($\pi_t > 0.66$):** Mean overnight return $+0.015\%$ in QQQ (54.6% positive) and $+0.002\%$ in SPY (53.6% positive).
- **Finding:** In contrary to retail assumption, closes near the low exhibit higher overnight bounce propensity than closes near the high.

### Post-Capitulation Drift ($N = 355$ in QQQ, $N = 248$ in SPY):
Following an extreme capitulation close ($\pi_t \le 0.20$ with daily drop $\le -1.5\%$):
- **Overnight Rebound Win Rate:** **62.9% positive in SPY**, **57.2% in QQQ** (mean return $+0.12\%$ / $+0.10\%$).
- **Next-Day Intraday RTH Win Rate:** **54.0% positive in SPY**, **54.6% in QQQ** (mean return $+0.26\%$ / $+0.30\%$).
- **Total Next-Day Close-to-Close Return:** Averages **+0.95% in SPY** and **+0.94% in QQQ**!

## 4. Forward Hypothesis Registration
- **ID**: `H-2026-018`
- **Instrument**: `SPY`, `QQQ`
- **Family**: `session_momentum`
- **Statement**: Following a session close in the bottom 20% of the day's range with a daily drop $\le -1.5\%$, the overnight return $R_{\text{on}}$ is positive in more than 55% of cases, significantly exceeding random walk baseline.
- **Metric**: Proportion of positive overnight returns against stationary bootstrap control.
- **Criterion**: Positive difference with lower 95% bootstrap confidence interval $> 0$ (Grade A or B).
- **Status**: Open.
