"""Step 4 of the course project: strategy simulations (specification 0028, R9 to R11 and T5).

Everything here runs on the validation period only (prices up to 2023-12-31); the choices made
here are fixed before the single test-period run of step 5. The rule is written in specification
0028, section "Simulation rule".

* ``vector_simulation``: the course's vector view, one fixed bet per signal over the horizon.
* ``run_portfolio``: the exact view, one account with reinvested capital, costs per side, cash
  earning the 3-month bill rate and fund positions changed only on the fund's trading days.
* target builders for sim1 (threshold), sim2 (top k), sim3 (stop loss and volatility filter) and
  sim4 (long-short on crypto); ``accumulate`` for sim5 (pullback buying with monthly deposits).

    python -m tsip.capstone.simulate --horizon 5
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from tsip.capstone import data
from tsip.capstone import models as M

COST_PER_SIDE = {"SPY": 0.0002, "QQQ": 0.0002, "GLD": 0.0002, "BTC-USD": 0.0010, "ETH-USD": 0.0010}
CRYPTO = ("BTC-USD", "ETH-USD")
QUANTILES = (0.5, 0.6, 0.7, 0.8, 0.9)
TOP_K = (1, 3, 5)
STOP_ATR = 2.0
VOL_FILTER_QUANTILE = 0.8
VOL_FILTER_WINDOW = 252
PULLBACK_TRIGGERS = ("atr_1", "atr_2", "atr_3", "prior_month_low")
PULLBACK_LOOKBACK = 63
BLOCK = 20


# ---------------------------------------------------------------- price panel


@dataclass
class Panel:
    """Prices on the union calendar of the instruments (dates by tickers)."""

    adj: pd.DataFrame
    close: pd.DataFrame
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    tradable: pd.DataFrame
    tbill: pd.Series  # percent, known on the date
    cash_return: pd.Series = field(init=False)

    def __post_init__(self):
        gap = self.adj.index.to_series().diff().dt.days.fillna(0).to_numpy()
        prev_rate = self.tbill.shift(1).fillna(0.0).to_numpy()
        self.cash_return = pd.Series((1 + prev_rate / 100) ** (gap / 365) - 1, index=self.adj.index)

    @property
    def tickers(self) -> list[str]:
        return list(self.adj.columns)


def make_panel(frame: pd.DataFrame, *, start=None, end=M.VALIDATION_END, allow_test: bool = False) -> Panel:
    if not allow_test and (end is None or pd.Timestamp(end) > M.VALIDATION_END):
        raise ValueError("simulate reads the test period only through evaluate.py (allow_test=True)")
    f = frame[frame["ticker"].isin(data.UNIVERSE)]
    if start is not None:
        f = f[f["date"] >= pd.Timestamp(start)]
    if end is not None:
        f = f[f["date"] <= pd.Timestamp(end)]

    def wide(col):
        return f.pivot(index="date", columns="ticker", values=col).sort_index()

    adj = wide("adj_close")
    tradable = adj.notna()
    tbill = f.groupby("date")["macro_tbill_3m"].first().reindex(adj.index).ffill().fillna(0.0)
    return Panel(
        adj=adj.ffill(),
        close=wide("close").ffill(),
        open=wide("open"),
        high=wide("high"),
        low=wide("low"),
        tradable=tradable,
        tbill=tbill,
    )


def atr_pct(panel: Panel, window: int = 14) -> pd.DataFrame:
    """ATR as a fraction of the close, from each instrument's own bars (simple mean of the true range)."""
    out = {}
    for t in panel.tickers:
        rows = panel.tradable[t]
        h, lo, c = panel.high[t][rows], panel.low[t][rows], panel.close[t][rows]
        tr = pd.concat([h - lo, (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
        out[t] = (tr.rolling(window).mean() / c).reindex(panel.adj.index)
    return pd.DataFrame(out)


# ---------------------------------------------------------------- exact simulation


@dataclass
class Run:
    equity: pd.Series
    returns: pd.Series
    exposure: pd.Series
    entries: int
    turnover: float


def run_portfolio(panel: Panel, targets: pd.DataFrame, *, delay: int = 0, exits: pd.DataFrame | None = None) -> Run:
    """One account: weights decided at each close, reinvested capital, costs per side, cash at the bill rate.

    ``targets`` are fractions of equity per instrument (negative for shorts). A fund's weight only
    changes on its trading days. ``exits`` holds adjusted fill prices for stop-loss exits: on such a
    day the position's return is computed to the fill, and the target of that day is zero.
    """
    dates = panel.adj.index
    tickers = panel.tickers
    tgt = targets.reindex(index=dates, columns=tickers)
    tgt = tgt.ffill().fillna(0.0)
    if delay:
        tgt = tgt.shift(delay).fillna(0.0)
    W = tgt.to_numpy(dtype=float)
    A = panel.adj.to_numpy(dtype=float)
    can_trade = panel.tradable.to_numpy()
    X = exits.reindex(index=dates, columns=tickers).to_numpy(dtype=float) if exits is not None else None
    cost = np.array([COST_PER_SIDE[t] for t in tickers])
    cash_r = panel.cash_return.to_numpy()
    held = np.zeros(len(tickers))
    current = np.zeros(len(tickers))  # the target in force
    equity = np.empty(len(dates))
    exposure = np.empty(len(dates))
    E, entries, turnover = 1.0, 0, 0.0
    for i in range(len(dates)):
        if i:
            r = np.nan_to_num(A[i] / A[i - 1] - 1)
            if X is not None:
                fill = ~np.isnan(X[i]) & (held != 0)
                r[fill] = X[i][fill] / A[i - 1][fill] - 1
            g = held @ r + (1 - np.abs(held).sum()) * cash_r[i]
            held = held * (1 + r) / (1 + g)
            E *= 1 + g
        want = np.where(can_trade[i], W[i], current)
        change = want != current
        if change.any():
            trade = np.abs(want[change] - held[change])
            E *= 1 - (trade * cost[change]).sum()
            turnover += float(trade.sum())
            entries += int(((current == 0) & (want != 0)).sum())
            held[change] = want[change]
            current = want
        equity[i] = E
        exposure[i] = np.abs(held).sum()
    eq = pd.Series(equity, index=dates)
    return Run(eq, eq.pct_change().fillna(0.0), pd.Series(exposure, index=dates), entries, turnover)


def buy_and_hold(panel: Panel, tickers, *, price: str = "adj") -> Run:
    """Equal weights bought at the first close of each instrument and never rebalanced (one cost)."""
    prices = getattr(panel, price)[list(tickers)]
    first = prices.apply(lambda s: s.first_valid_index())
    start = first.max()
    rel = prices.loc[start:] / prices.loc[start]
    cost = np.mean([COST_PER_SIDE[t] for t in tickers])
    eq = rel.mean(axis=1) * (1 - cost)
    eq = eq.reindex(panel.adj.index).ffill().fillna(1 - cost)
    return Run(eq, eq.pct_change().fillna(0.0), pd.Series(1.0, index=eq.index), len(tickers), 1.0)


# ---------------------------------------------------------------- targets


def probabilities(preds: pd.DataFrame, panel: Panel) -> pd.DataFrame:
    p = preds.pivot(index="date", columns="ticker", values="probability").reindex(columns=panel.tickers)
    return p.reindex(panel.adj.index)  # NaN where the instrument has no prediction that day


def threshold_targets(prob: pd.DataFrame, threshold: float, sleeve: float) -> pd.DataFrame:
    """sim1: long one sleeve while the probability is above the threshold."""
    return (prob > threshold).astype(float).where(prob.notna()) * sleeve


def top_k_targets(prob: pd.DataFrame, threshold: float, k: int) -> pd.DataFrame:
    """sim2: at most k positions, the highest probabilities above the threshold, 1/k each.

    Probabilities are carried over non-trading days so a fund closed at the weekend keeps its rank.
    """
    carried = prob.ffill()
    eligible = carried.where(carried > threshold)
    rank = eligible.rank(axis=1, ascending=False, method="first")
    out = (rank <= k).astype(float) / k
    return out.where(carried.notna())


def stop_and_filter(panel: Panel, base: pd.DataFrame, volatility: pd.DataFrame, *, stop_atr: float = STOP_ATR):
    """sim3: sim1 targets with a stop loss in ATR, a volatility filter on new entries, no re-entry until reset.

    ``panel`` may start before ``base`` so the ATR and the volatility limit have their warm-up.
    Returns the targets and the adjusted fill prices of the stop exits, on the panel's dates.
    """
    atr = atr_pct(panel)
    base = base.reindex(index=panel.adj.index, columns=panel.tickers)
    volatility = volatility.reindex(index=panel.adj.index, columns=panel.tickers)
    targets = base.copy() * np.nan
    exits = pd.DataFrame(np.nan, index=base.index, columns=base.columns)
    for t in base.columns:
        rows = np.flatnonzero(panel.tradable[t].to_numpy())
        vol = volatility[t].iloc[rows]
        limit = vol.shift(1).rolling(VOL_FILTER_WINDOW, min_periods=60).quantile(VOL_FILTER_QUANTILE)
        in_pos, blocked, stop = False, False, np.nan
        for j, i in enumerate(rows):
            want = base[t].iloc[i]
            if np.isnan(want):
                continue
            if in_pos:
                lo, op = panel.low[t].iloc[i], panel.open[t].iloc[i]
                if lo <= stop:
                    fill = min(op, stop) if not np.isnan(op) else stop
                    factor = panel.adj[t].iloc[i] / panel.close[t].iloc[i]
                    exits.iloc[i, exits.columns.get_loc(t)] = fill * factor
                    in_pos, blocked = False, True
                    targets.iloc[i, targets.columns.get_loc(t)] = 0.0
                    continue
                if want == 0:
                    in_pos = False
                targets.iloc[i, targets.columns.get_loc(t)] = want
                continue
            if want == 0:
                blocked = False
                targets.iloc[i, targets.columns.get_loc(t)] = 0.0
                continue
            too_volatile = not np.isnan(limit.iloc[j]) and vol.iloc[j] > limit.iloc[j]
            if blocked or too_volatile or np.isnan(atr[t].iloc[i]):
                targets.iloc[i, targets.columns.get_loc(t)] = 0.0
                continue
            in_pos = True
            stop = panel.close[t].iloc[i] * (1 - stop_atr * atr[t].iloc[i])
            targets.iloc[i, targets.columns.get_loc(t)] = want
    return targets, exits


def long_short_targets(prob: pd.DataFrame, upper: float, lower: float, tickers=CRYPTO) -> pd.DataFrame:
    """sim4: on crypto, half the account long above the upper threshold, half short below the lower one."""
    p = prob[list(tickers)]
    sleeve = 1 / len(tickers)
    out = (p > upper).astype(float) * sleeve - (p < lower).astype(float) * sleeve
    full = pd.DataFrame(0.0, index=prob.index, columns=prob.columns)
    full[list(tickers)] = out.where(p.notna())
    return full


# ---------------------------------------------------------------- vector simulation (course view)


def vector_simulation(preds: pd.DataFrame, threshold: float, horizon: int, *, bet: float = 100.0) -> dict:
    """One fixed bet per signal, held for the horizon, costs on entry and exit; signals overlap."""
    growth = f"growth_future_{horizon}d"
    s = preds[preds["probability"] > threshold].copy()
    if s.empty:
        return {"trades": 0}
    s["cost"] = s["ticker"].map(COST_PER_SIDE) * 2
    s["net"] = bet * (s[growth] - s["cost"])  # growth_future is the return over the horizon
    by_day = s.groupby("date")["net"].count()
    return {
        "trades": len(s),
        "hit_rate": float((s["net"] > 0).mean()),
        "mean_net_per_bet": float(s["net"].mean()),
        "total_net": float(s["net"].sum()),
        "capital_needed": float(by_day.rolling(f"{horizon * 7 // 5 + 1}D").sum().max() * bet),
    }


# ---------------------------------------------------------------- sim5: monthly deposits and pullbacks


def _first_sessions_of_month(dates: pd.DatetimeIndex) -> np.ndarray:
    period = dates.to_period("M")
    return np.r_[True, period[1:] != period[:-1]]


def _last_sessions_of_quarter(dates: pd.DatetimeIndex) -> np.ndarray:
    period = dates.to_period("Q")
    return np.r_[period[1:] != period[:-1], True]


def pullback_signal(panel: Panel, ticker: str, trigger: str) -> pd.Series:
    rows = panel.tradable[ticker]
    c = panel.close[ticker][rows]
    if trigger.startswith("atr_"):
        k = float(trigger.split("_")[1])
        atr = atr_pct(panel)[ticker][rows] * c
        peak = c.rolling(PULLBACK_LOOKBACK, min_periods=1).max()
        return (peak - c) >= k * atr
    if trigger == "prior_month_low":
        lows = panel.low[ticker][rows]
        monthly = lows.groupby(lows.index.to_period("M")).min()
        prior = pd.Series(lows.index.to_period("M") - 1, index=lows.index).map(monthly)
        return c <= prior
    raise ValueError(trigger)


def accumulate(panel: Panel, ticker: str, rule: str, *, start=None, deposit: float = 1.0) -> dict:
    """Wealth from one deposit on each first session of a month, invested by ``rule``.

    Rules: ``lump_sum`` (every deposit of the period invested at the first session), ``monthly``
    (each deposit invested on arrival), ``cash`` (never invested), or a pullback trigger
    (``PULLBACK_TRIGGERS``; cash left on the last session of a quarter is invested then). Cash earns
    the bill rate. A purchase never exceeds the cash available (T5). Triggers are computed on the
    whole panel (warm-up) and the deposits start at ``start``.
    """
    rows = panel.tradable[ticker].to_numpy()
    if start is not None:
        rows = rows & (panel.adj.index >= pd.Timestamp(start))
    dates = panel.adj.index[rows]
    price = panel.adj[ticker].to_numpy()[rows]
    gap = np.r_[0, np.diff(dates.to_numpy()).astype("timedelta64[D]").astype(int)]
    rate = panel.tbill.to_numpy()[rows]
    cash_r = (1 + np.r_[0.0, rate[:-1]] / 100) ** (gap / 365) - 1
    first = _first_sessions_of_month(dates)
    quarter_end = _last_sessions_of_quarter(dates)
    trigger = None
    if rule in PULLBACK_TRIGGERS:
        trigger = pullback_signal(panel, ticker, rule).reindex(dates).fillna(False).to_numpy()
    cost = COST_PER_SIDE[ticker]
    n_deposits = int(first.sum())
    cash, units, buys = 0.0, 0.0, 0
    flows, wealth, cash_share = [], np.empty(len(dates)), np.empty(len(dates))
    for i in range(len(dates)):
        cash *= 1 + cash_r[i]
        if rule == "lump_sum":
            if i == 0:
                cash += deposit * n_deposits
                flows.append((dates[i], -deposit * n_deposits))
        elif first[i]:
            cash += deposit
            flows.append((dates[i], -deposit))
        buy = {
            "lump_sum": i == 0,
            "monthly": bool(first[i]),
            "cash": False,
        }.get(rule)
        if buy is None:
            buy = bool(trigger[i]) or bool(quarter_end[i])
        if buy and cash > 0:
            spend = cash
            assert spend <= cash + 1e-12  # T5: never more than the cash available
            units += spend * (1 - cost) / price[i]
            cash -= spend
            buys += 1
        wealth[i] = cash + units * price[i]
        cash_share[i] = cash / wealth[i] if wealth[i] else 1.0
    flows.append((dates[-1], wealth[-1]))
    contributed = deposit * n_deposits
    return {
        "ticker": ticker,
        "rule": rule,
        "deposits": n_deposits,
        "final_wealth": float(wealth[-1]),
        "multiple": float(wealth[-1] / contributed),
        "money_weighted_return": xirr(flows),
        "purchases": buys,
        "mean_cash_share": float(cash_share.mean()),
        "wealth": pd.Series(wealth, index=dates),
    }


def xirr(flows: list[tuple[pd.Timestamp, float]]) -> float:
    """Annual money-weighted return of dated cash flows (bisection; deposits negative, final value positive)."""
    t0 = flows[0][0]
    years = np.array([(d - t0).days / 365.25 for d, _ in flows])
    amounts = np.array([a for _, a in flows])

    def npv(r):
        return float((amounts / (1 + r) ** years).sum())

    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------- metrics


def _years(index: pd.DatetimeIndex) -> float:
    return (index[-1] - index[0]).days / 365.25


def metrics(run: Run, cash_return: pd.Series) -> dict:
    eq, r = run.equity, run.returns
    years = _years(eq.index)
    per_year = (len(r) - 1) / years
    excess = (r - cash_return.reindex(r.index).fillna(0.0)).iloc[1:]
    yearly = eq / eq.reindex(eq.index - pd.Timedelta(days=365), method="ffill").to_numpy() - 1
    yearly = yearly[eq.index >= eq.index[0] + pd.Timedelta(days=365)]
    return {
        "cagr": float(eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1,
        "sharpe": float(excess.mean() / r.iloc[1:].std() * np.sqrt(per_year)) if r.iloc[1:].std() > 0 else float("nan"),
        "max_drawdown": float((eq / eq.cummax() - 1).min()),
        "rolling_1y_min": float(yearly.min()) if len(yearly) else float("nan"),
        "rolling_1y_median": float(yearly.median()) if len(yearly) else float("nan"),
        "rolling_1y_max": float(yearly.max()) if len(yearly) else float("nan"),
        "exposure": float(run.exposure.mean()),
        "entries": run.entries,
        "turnover": round(run.turnover, 2),
    }


def bootstrap(
    runs: dict[str, Run], cash_return: pd.Series, against: str | None = None, *, reps: int = 1000, seed=M.SEED
):
    """Circular block bootstrap (20-date blocks) of CAGR and Sharpe, and of the CAGR difference to ``against``."""
    rng = np.random.default_rng(seed)
    names = list(runs)
    R = np.column_stack([runs[k].returns.to_numpy()[1:] for k in names])
    c = cash_return.reindex(runs[names[0]].returns.index).fillna(0.0).to_numpy()[1:]
    n = len(R)
    years = _years(runs[names[0]].equity.index)
    per_year = n / years
    cagr, sharpe = [], []
    for _ in range(reps):
        starts = rng.integers(0, n, size=int(np.ceil(n / BLOCK)))
        idx = np.concatenate([(np.arange(s, s + BLOCK) % n) for s in starts])[:n]
        s = R[idx]
        cagr.append(np.prod(1 + s, axis=0) ** (1 / years) - 1)
        sd = s.std(axis=0, ddof=1)
        sharpe.append(
            np.where(sd > 0, (s - c[idx, None]).mean(axis=0) / np.where(sd > 0, sd, 1) * np.sqrt(per_year), np.nan)
        )
    cagr, sharpe = np.array(cagr), np.array(sharpe)
    out = {}
    for j, k in enumerate(names):
        out[k] = {
            "cagr95": np.nanquantile(cagr[:, j], [0.025, 0.975]).tolist(),
            "sharpe95": np.nanquantile(sharpe[:, j], [0.025, 0.975]).tolist(),
        }
        if against is not None and k != against:
            diff = cagr[:, j] - cagr[:, names.index(against)]
            out[k]["cagr_minus_" + against + "95"] = np.quantile(diff, [0.025, 0.975]).tolist()
    return out


# ---------------------------------------------------------------- validation choices (step 4)


def load_predictions(folder: Path, feature_set: str, family: str = "logistic") -> pd.DataFrame:
    return pd.read_csv(folder / f"{family}__{feature_set}.csv.gz", parse_dates=["date"])


def choose(panel: Panel, preds: pd.DataFrame, volatility: pd.DataFrame, horizon: int) -> dict:
    """Every strategy of the rule on one prediction set; parameters chosen by validation Sharpe."""
    sub, prob = sub_panel(panel, preds)
    span = sub.adj.index
    cash = sub.cash_return
    sleeve = 1 / len(panel.tickers)
    levels = {q: float(np.quantile(preds["probability"], q)) for q in QUANTILES}
    out: dict = {"period": [str(span[0].date()), str(span[-1].date())], "thresholds": levels, "trials": []}

    def record(name, params, run):
        m = metrics(run, cash)
        out["trials"].append({"strategy": name, **params, **m})
        return m

    best = {}
    for q, thr in levels.items():
        m = record("sim1", {"quantile": q, "threshold": thr}, run_portfolio(sub, threshold_targets(prob, thr, sleeve)))
        if "sim1" not in best or m["sharpe"] > best["sim1"][1]["sharpe"]:
            best["sim1"] = ({"quantile": q, "threshold": thr}, m)
        for k in TOP_K:
            m = record(
                "sim2", {"quantile": q, "threshold": thr, "k": k}, run_portfolio(sub, top_k_targets(prob, thr, k))
            )
            if "sim2" not in best or m["sharpe"] > best["sim2"][1]["sharpe"]:
                best["sim2"] = ({"quantile": q, "threshold": thr, "k": k}, m)
    thr1 = best["sim1"][0]["threshold"]
    targets3, exits3 = stop_and_filter(panel, threshold_targets(prob, thr1, sleeve), volatility)
    best["sim3"] = (
        {"threshold": thr1, "stop_atr": STOP_ATR},
        record("sim3", {"threshold": thr1}, run_portfolio(sub, targets3, exits=exits3)),
    )
    crypto = preds[preds["ticker"].isin(CRYPTO)]["probability"]
    for q in QUANTILES[1:]:
        up, lo = float(np.quantile(crypto, q)), float(np.quantile(crypto, 1 - q))
        m = record(
            "sim4", {"quantile": q, "upper": up, "lower": lo}, run_portfolio(sub, long_short_targets(prob, up, lo))
        )
        if "sim4" not in best or m["sharpe"] > best["sim4"][1]["sharpe"]:
            best["sim4"] = ({"quantile": q, "upper": up, "lower": lo}, m)
    out["chosen"] = {k: {"params": v[0], **v[1]} for k, v in best.items()}

    out.update(run_chosen(panel, sub, prob, preds, volatility, out["chosen"], horizon))
    return out


def sub_panel(panel: Panel, preds: pd.DataFrame) -> tuple[Panel, pd.DataFrame]:
    """The panel and probabilities cut to the dates the predictions cover (the panel keeps its warm-up)."""
    prob = probabilities(preds, panel)
    span = prob.dropna(how="all").index
    sub = Panel(
        **{k: getattr(panel, k).loc[span[0] : span[-1]] for k in ("adj", "close", "open", "high", "low", "tradable")},
        tbill=panel.tbill.loc[span[0] : span[-1]],
    )
    return sub, prob.loc[span[0] : span[-1]]


def run_chosen(panel, sub, prob, preds, volatility, chosen: dict, horizon: int) -> dict:
    """The strategies with fixed parameters, their one-session delay, the benchmarks and the controls.

    ``chosen`` maps sim1 to sim4 to their parameters (as in ``registry/capstone_choices_h5.json``).
    The same function serves validation (step 4) and the single test-period run (step 5).
    """
    cash = sub.cash_return
    sleeve = 1 / len(panel.tickers)
    p = {k: v.get("params", v) for k, v in chosen.items()}
    p1, p2, p3, p4 = p["sim1"], p["sim2"], p["sim3"], p["sim4"]
    targets3, exits3 = stop_and_filter(
        panel, threshold_targets(prob, p3["threshold"], sleeve), volatility, stop_atr=p3.get("stop_atr", STOP_ATR)
    )

    def build(delay):
        return {
            "sim1": run_portfolio(sub, threshold_targets(prob, p1["threshold"], sleeve), delay=delay),
            "sim2": run_portfolio(sub, top_k_targets(prob, p2["threshold"], p2["k"]), delay=delay),
            "sim3": run_portfolio(sub, targets3, exits=exits3, delay=delay),
            "sim4": run_portfolio(sub, long_short_targets(prob, p4["upper"], p4["lower"]), delay=delay),
        }

    runs = {
        **build(0),
        "buy_hold_equal": buy_and_hold(sub, sub.tickers),
        "buy_hold_crypto": buy_and_hold(sub, CRYPTO),
        "spy_total_return": buy_and_hold(sub, ["SPY"]),
        "spy_price_only": buy_and_hold(sub, ["SPY"], price="close"),
    }
    out = {
        "period": [str(sub.adj.index[0].date()), str(sub.adj.index[-1].date())],
        "metrics": {k: metrics(v, cash) for k, v in runs.items()},
        "delayed_one_session": {k: metrics(v, cash) for k, v in build(1).items()},
        "intervals": bootstrap(runs, cash, against="buy_hold_equal"),
    }
    out["intervals_vs_spy"] = {
        k: v["cagr_minus_spy_total_return95"]
        for k, v in bootstrap(runs, cash, against="spy_total_return").items()
        if "cagr_minus_spy_total_return95" in v
    }
    control = rotation_control(sub, preds, panel, p1["threshold"], sleeve)
    values = control.pop("sharpe_values")
    control["share_at_or_above_actual"] = float(np.mean(np.array(values) >= out["metrics"]["sim1"]["sharpe"]))
    out["rotation_control"] = control
    out["vector"] = {
        "sim1": vector_simulation(preds, p1["threshold"], horizon),
        "all_signals": vector_simulation(preds, -1.0, horizon),
    }
    return out


def rotation_control(sub: Panel, preds: pd.DataFrame, panel: Panel, threshold: float, sleeve: float, reps: int = 100):
    """sim1 with each instrument's probabilities rotated by a random offset across its own dates.

    A rotation keeps the persistence of the signal (how long it stays on or off) and the exposure,
    and breaks only its alignment with prices; a plain shuffle would also remove the persistence.
    """
    rng = np.random.default_rng(M.SEED)
    sharpe, cagr = [], []
    for _ in range(reps):
        shifted = preds.sort_values(["ticker", "date"]).copy()
        for _, idx in shifted.groupby("ticker").indices.items():
            n = len(idx)
            offset = int(rng.integers(n // 10, n - n // 10))
            values = shifted["probability"].to_numpy()[idx]
            shifted.iloc[idx, shifted.columns.get_loc("probability")] = np.roll(values, offset)
        prob = probabilities(shifted, panel).loc[sub.adj.index[0] : sub.adj.index[-1]]
        m = metrics(run_portfolio(sub, threshold_targets(prob, threshold, sleeve)), sub.cash_return)
        sharpe.append(m["sharpe"])
        cagr.append(m["cagr"])
    return {
        "method": "circular rotation per instrument",
        "reps": reps,
        "sharpe_median": float(np.median(sharpe)),
        "sharpe95": np.quantile(sharpe, [0.025, 0.975]).tolist(),
        "share_at_or_above_actual": None,
        "sharpe_values": sharpe,
        "cagr_median": float(np.median(cagr)),
        "cagr95": np.quantile(cagr, [0.025, 0.975]).tolist(),
    }


def pullback_study(panel: Panel, start) -> dict:
    rows, table = [], {}
    for t in panel.tickers:
        for rule in ("lump_sum", "monthly", "cash", *PULLBACK_TRIGGERS):
            r = accumulate(panel, t, rule, start=start)
            r.pop("wealth")
            rows.append(r)
    frame = pd.DataFrame(rows)
    for rule, g in frame.groupby("rule"):
        table[rule] = float(g["money_weighted_return"].mean())
    chosen = max(PULLBACK_TRIGGERS, key=lambda k: table[k])
    return {"rows": rows, "mean_money_weighted_return": table, "chosen_trigger": chosen}


def select_primary(results: dict) -> dict:
    """Among sim1 to sim3 on both feature sets, the highest validation Sharpe (rule of specification 0028)."""
    cands = [(fs, sim, res["chosen"][sim]["sharpe"]) for fs, res in results.items() for sim in ("sim1", "sim2", "sim3")]
    fs, sim, sharpe = max(cands, key=lambda c: c[2])
    return {
        "feature_set": fs,
        "strategy": sim,
        "validation_sharpe": sharpe,
        "params": results[fs]["chosen"][sim]["params"],
    }


def markdown(summary: dict) -> str:
    """The tables of ``docs/CAPSTONE.md`` (step 4) from a summary written by ``main``."""

    def pct(x):
        return f"{x * 100:+.1f}%"

    def iv(pair, scale=100, fmt="{:+.1f}"):
        return f"{fmt.format(pair[0] * scale)} to {fmt.format(pair[1] * scale)}"

    names = {
        "sim1": "sim1 threshold",
        "sim2": "sim2 top k",
        "sim3": "sim3 stop and filter",
        "sim4": "sim4 crypto long-short",
        "buy_hold_equal": "Buy and hold, five equal",
        "buy_hold_crypto": "Buy and hold, crypto",
        "spy_total_return": "SPY with dividends",
        "spy_price_only": "SPY price only",
    }
    lines = []
    for fs, res in summary["by_feature_set"].items():
        lines += [
            f"**{fs}** (period {res['period'][0]} to {res['period'][1]})",
            "",
            "| Strategy | Chosen parameters | CAGR (95% interval) | CAGR minus five equal (95%) | Sharpe | Max drawdown "
            "| Rolling 1y min / median | Exposure | Entries | CAGR, Sharpe with one-session delay |",
            "|---|---|---|---|---:|---:|---|---:|---:|---|",
        ]
        for key, label in names.items():
            m, i = res["metrics"][key], res["intervals"][key]
            params = res["chosen"].get(key, {}).get("params", {})
            shown = ", ".join(
                f"{k} {v:.3f}" if isinstance(v, float) else f"{k} {v}" for k, v in params.items() if k != "stop_atr"
            )
            diff = i.get("cagr_minus_buy_hold_equal95")
            d = res["delayed_one_session"].get(key)
            lines.append(
                f"| {label} | {shown or '-'} | {pct(m['cagr'])} ({iv(i['cagr95'])}) | {iv(diff) if diff else '-'} "
                f"| {m['sharpe']:.2f} | {pct(m['max_drawdown'])} | {pct(m['rolling_1y_min'])} / "
                f"{pct(m['rolling_1y_median'])} | {m['exposure']:.2f} | {m['entries']} "
                f"| {pct(d['cagr']) + ', ' + format(d['sharpe'], '.2f') if d else '-'} |"
            )
        c = res["rotation_control"]
        v = res["vector"]["sim1"]
        lines += [
            "",
            f"Rotation control of sim1 ({c['reps']} rotations): median Sharpe {c['sharpe_median']:.2f} "
            f"(95% {c['sharpe95'][0]:.2f} to {c['sharpe95'][1]:.2f}); share at or above the actual "
            f"{c['share_at_or_above_actual']:.2f}. Vector view of sim1: {v['trades']} bets of 100, hit rate "
            f"{v['hit_rate'] * 100:.1f}%, mean net {v['mean_net_per_bet']:+.2f} per bet.",
            "",
        ]
    p = summary["primary"]
    lines.append(
        f"Strategy carried to the test period: **{p['strategy']} on {p['feature_set']}** "
        f"(validation Sharpe {p['validation_sharpe']:.2f})."
    )
    pb = summary["pullback"]
    rows = pd.DataFrame(pb["rows"])
    table = rows.pivot(index="rule", columns="ticker", values="money_weighted_return")
    order = ["lump_sum", "monthly", "cash", *PULLBACK_TRIGGERS]
    lines += [
        "",
        "Pullback buying (sim5), money-weighted annual return, one unit deposited each month:",
        "",
        "| Rule | " + " | ".join(table.columns) + " | Mean |",
        "|---|" + "---:|" * (len(table.columns) + 1),
    ]
    for rule in order:
        vals = " | ".join(pct(table.loc[rule, t]) for t in table.columns)
        lines.append(f"| {rule} | {vals} | {pct(pb['mean_money_weighted_return'][rule])} |")
    lines.append(f"\nTrigger carried to the test period: **{pb['chosen_trigger']}**.")
    return "\n".join(lines)


def frozen_choices(summary: dict) -> dict:
    """The parameters step 5 must use, taken from a validation summary (nothing else is carried)."""
    return {
        "horizon": summary["horizon"],
        "family": summary["family"],
        "primary": summary["primary"],
        "chosen": {
            fs: {k: v["params"] for k, v in res["chosen"].items()} for fs, res in summary["by_feature_set"].items()
        },
        "pullback_trigger": summary["pullback"]["chosen_trigger"],
        "validation_period": next(iter(summary["by_feature_set"].values()))["period"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizon", type=int, default=5, choices=[5, 20])
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--random-walk", action="store_true", help="control: random-walk prices and their predictions")
    parser.add_argument("--markdown", action="store_true", help="print the tables of an existing summary and stop")
    parser.add_argument("--freeze", type=Path, default=None, help="write the chosen parameters of an existing summary")
    args = parser.parse_args(argv)
    store = args.store or data.default_store()
    results_root = args.results or store / "results"
    tag = f"h{args.horizon}{'_random_walk' if args.random_walk else ''}"
    folder = results_root / tag
    if args.freeze:
        summary = json.loads((results_root / f"simulation_{tag}.json").read_text())
        args.freeze.write_text(json.dumps(frozen_choices(summary), indent=2) + "\n")
        print(f"written {args.freeze}")
        return
    if args.markdown:
        print(markdown(json.loads((results_root / f"simulation_{tag}.json").read_text())))
        return
    frame, _ = data.load("file", store)
    if args.random_walk:
        frame = M.random_walk_frame(frame)  # same seed as the models' control
    from tsip.capstone import features

    feats, _ = features.build_features(frame)
    volatility = feats.pivot(index="date", columns="ticker", values="volatility_20")
    start = M.TRAIN_END + pd.Timedelta(days=1)
    panel = make_panel(frame, start=start - pd.Timedelta(days=400))  # earlier rows: indicator warm-up only
    results = {}
    for fs in ("LECTURE", "LECTURE+TIME+SPACE"):
        results[fs] = choose(panel, load_predictions(folder, fs), volatility, args.horizon)
    summary = {
        "horizon": args.horizon,
        "random_walk": args.random_walk,
        "family": "logistic",
        "by_feature_set": results,
        "primary": select_primary(results),
        "pullback": pullback_study(panel, start),
    }
    out = results_root / f"simulation_{tag}.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"written {out}")
    print(
        json.dumps({"primary": summary["primary"], "pullback_chosen": summary["pullback"]["chosen_trigger"]}, indent=2)
    )


if __name__ == "__main__":
    main()
