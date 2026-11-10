"""When to buy with a fixed monthly budget (specification 0029, W-124, hypothesis H-2026-017).

Every rule buys once per complete month, at the close of the session it selects (or at the month's
last session if its trigger does not occur), so all rules invest the same money and pay the same
cost. The statistic is the price advantage of a month: (average adjusted close of the month minus
the adjusted close paid) divided by that average. The average is the exact expected price of a
session drawn at random from the month.

Decisions use only data available at that session's close. Levels, gaps and ranges use the
unadjusted bars; prices paid use the adjusted close, so dividends do not favour days after an
ex-date. Interpretations: B4 uses the low of the most recent completed month, quarter or half-year,
untested if no low since that period closed has reached it; B5 keeps bullish three-session gaps
formed in the last 252 sessions.

    python -m tsip.capstone.timing develop        # development period: all variants, choices frozen
    python -m tsip.capstone.timing confirm        # single logged confirmation run (+ random walks)
    python -m tsip.capstone.timing --markdown     # tables of the saved results
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tsip.capstone import data
from tsip.capstone import evaluate as E
from tsip.capstone import models as M

REPO = E.REPO
CHOICES = REPO / "registry" / "capstone_timing_choices.json"
DEV_END = {
    "SPY": "2015-12-31",
    "QQQ": "2015-12-31",
    "GLD": "2015-12-31",
    "BTC-USD": "2019-12-31",
    "ETH-USD": "2019-12-31",
}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FALL_K = (1.0, 1.5, 2.0)
LOW_HORIZONS = ("month", "quarter", "half")
LOW_D = (0.25, 0.5)
BLOCK = 6
REPS = 2000
MIN_ADVANTAGE = 0.002
Q = 0.05


# ---------------------------------------------------------------- per-instrument sessions


def sessions(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """One instrument's own sessions with the indicators the rules need, each known at that close."""
    g = frame[frame["ticker"] == ticker].sort_values("date").reset_index(drop=True)
    g = g[["date", "open", "high", "low", "close", "adj_close"]].copy()
    g["adj_close"] = g["adj_close"].fillna(g["close"])
    prev = g["close"].shift()
    tr = pd.concat([g["high"] - g["low"], (g["high"] - prev).abs(), (g["low"] - prev).abs()], axis=1).max(axis=1)
    g["tr"] = tr
    g["atr"] = tr.rolling(14).mean()
    g["tr_p90_prev"] = tr.shift().rolling(252, min_periods=120).quantile(0.9)
    g["month"] = g["date"].dt.to_period("M")
    g["session_of_month"] = g.groupby("month").cumcount()
    return g


def complete_months(g: pd.DataFrame) -> list:
    """Months with all their sessions in the data: the last month is dropped (it may still be open)."""
    months = list(g["month"].unique())
    return months[1:-1]  # the first month may also start mid-month


def _period(dates: pd.Series, horizon: str) -> pd.Series:
    if horizon == "month":
        return dates.dt.to_period("M").astype(str)
    if horizon == "quarter":
        return dates.dt.to_period("Q").astype(str)
    return dates.dt.year.astype(str) + "H" + np.where(dates.dt.month <= 6, "1", "2")


def prior_low_signal(g: pd.DataFrame, horizon: str, d: float) -> np.ndarray:
    """True on sessions whose low comes within d ATR of the prior period's low while it was still untested."""
    period = _period(g["date"], horizon).to_numpy()
    low = g["low"].to_numpy()
    atr_prev = g["atr"].shift().to_numpy()
    out = np.zeros(len(g), dtype=bool)
    starts = np.r_[0, np.flatnonzero(period[1:] != period[:-1]) + 1]
    for idx, start in enumerate(starts[1:], start=1):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(g)
        level = low[starts[idx - 1] : start].min()  # the prior period's low
        lowest_since = np.inf
        for t in range(start, end):
            untested = lowest_since > level
            if untested and not np.isnan(atr_prev[t]) and low[t] <= level + d * atr_prev[t]:
                out[t] = True
            lowest_since = min(lowest_since, low[t])
    return out


def fvg_signal(g: pd.DataFrame, keep: int = 252) -> np.ndarray:
    """True on sessions whose low enters the nearest untested bullish gap below the previous close."""
    high, low, close = g["high"].to_numpy(), g["low"].to_numpy(), g["close"].to_numpy()
    out = np.zeros(len(g), dtype=bool)
    zones: list[tuple[int, float, float]] = []  # (formed at, bottom, top), untested so far
    for t in range(len(g)):
        if t >= 1:
            below = [z for z in zones if z[2] < close[t - 1] and t - z[0] <= keep]
            if below:
                nearest = max(below, key=lambda z: z[2])
                if low[t] <= nearest[2]:
                    out[t] = True
            zones = [z for z in zones if low[t] > z[2] and t - z[0] <= keep]  # entered zones are tested
        if t >= 2 and low[t] > high[t - 2]:
            zones.append((t, high[t - 2], low[t]))
    return out


def decide(g: pd.DataFrame, rule: str, params: dict, months) -> pd.Series:
    """Index (row of g) of the purchase session of each month for a rule."""
    trig = None
    if rule == "weekday":
        trig = g["date"].dt.dayofweek.to_numpy() == params["day"]
    elif rule == "after_fall":
        fall = (g["close"].shift() - g["close"]).to_numpy() >= params["k"] * g["atr"].shift().to_numpy()
        trig = fall
    elif rule == "high_range":
        trig = (g["tr"] >= g["tr_p90_prev"]).to_numpy()
    elif rule == "prior_low":
        trig = prior_low_signal(g, params["horizon"], params["d"])
    elif rule == "fvg":
        trig = fvg_signal(g)
    elif rule == "month_low_session":
        trig = g["session_of_month"].to_numpy() == params["session"]
    elif rule == "below_month_open":
        month_open = g.groupby("month")["open"].transform("first").to_numpy()
        trig = (g["session_of_month"].to_numpy() >= 5) & (g["close"].to_numpy() < month_open)
    elif rule == "first_session":
        trig = g["session_of_month"].to_numpy() == 0
    elif rule == "last_session":
        trig = np.zeros(len(g), dtype=bool)
    else:
        raise ValueError(rule)
    out = {}
    month = g["month"].to_numpy()
    for m in months:
        rows = np.flatnonzero(month == m)
        hit = rows[trig[rows]]
        if len(hit):
            pick = hit[0]
            if rule == "after_fall" and params.get("buy") == "next":
                pick = pick + 1 if pick + 1 <= rows[-1] else rows[-1]
        else:
            pick = rows[-1]
        out[m] = pick
    return pd.Series(out)


def advantages(g: pd.DataFrame, picks: pd.Series) -> pd.Series:
    """Price advantage of each month against the month's average adjusted close."""
    avg = g.groupby("month")["adj_close"].mean()
    paid = g["adj_close"].to_numpy()[picks.to_numpy()]
    return pd.Series((avg.loc[picks.index].to_numpy() - paid) / avg.loc[picks.index].to_numpy(), index=picks.index)


def wealth_ratio(g: pd.DataFrame, picks: pd.Series) -> float:
    """Units bought by the rule over the expected units of a random session, one unit of money per month."""
    inv = 1 / g["adj_close"]
    expected = inv.groupby(g["month"]).mean().loc[picks.index].sum()
    return float((1 / g["adj_close"].to_numpy()[picks.to_numpy()]).sum() / expected)


def bootstrap_mean(values: np.ndarray, *, reps: int | None = None, block: int = BLOCK, seed=M.SEED):
    """Mean, 95% interval and one-sided p-value (mean <= 0) by a circular block bootstrap over months."""
    reps = reps or REPS
    rng = np.random.default_rng(seed)
    n = len(values)
    starts = rng.integers(0, n, size=(reps, int(np.ceil(n / block))))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :n] % n
    means = values[idx].mean(axis=1)
    observed = float(values.mean())
    p = float(np.mean(means - observed >= observed))  # centred bootstrap null
    return observed, np.quantile(means, [0.025, 0.975]).tolist(), max(p, 1 / reps)


def bh(p: np.ndarray) -> np.ndarray:
    """Benjamini–Hochberg q-values."""
    order = np.argsort(p)
    ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(q)
    out[order] = np.minimum(q, 1)
    return out


# ---------------------------------------------------------------- variants, development and confirmation


def variants(ticker: str, month_low_session: int | None = None) -> list[tuple[str, str, dict]]:
    days = range(7) if ticker in ("BTC-USD", "ETH-USD") else range(5)
    out = [("B1", "weekday", {"day": d}) for d in days]
    out += [("B2", "after_fall", {"k": k, "buy": b}) for k in FALL_K for b in ("same", "next")]
    out += [("B3", "high_range", {})]
    out += [("B4", "prior_low", {"horizon": h, "d": d}) for h in LOW_HORIZONS for d in LOW_D]
    out += [("B5", "fvg", {})]
    if month_low_session is not None:
        out += [("B6", "month_low_session", {"session": month_low_session})]
    out += [("B7", "below_month_open", {})]
    return out


REFERENCES = [("R", "first_session", {}), ("R", "last_session", {})]


def split_months(g: pd.DataFrame, ticker: str):
    months = complete_months(g)
    end = pd.Period(DEV_END[ticker], "M")
    return [m for m in months if m <= end], [m for m in months if m > end]


def usual_low_session(g: pd.DataFrame, months) -> int:
    """Session-of-month index where the month's lowest low formed most often (development months only)."""
    sub = g[g["month"].isin(months)]
    idx = sub.loc[sub.groupby("month")["low"].idxmin(), "session_of_month"]
    return int(idx.mode().iloc[0])


def evaluate_rule(g, rule, params, months, *, reps=None) -> dict:
    picks = decide(g, rule, params, months)
    adv = advantages(g, picks).to_numpy()
    mean, ci, p = bootstrap_mean(adv, reps=reps)
    return {
        "months": len(months),
        "mean_advantage": mean,
        "ci95": ci,
        "p_one_sided": p,
        "share_positive": float((adv > 0).mean()),
        "wealth_vs_random": wealth_ratio(g, picks) - 1,
    }


def develop(frame: pd.DataFrame, *, reps=None) -> dict:
    out = {}
    for ticker in data.UNIVERSE:
        g = sessions(frame, ticker)
        dev, _ = split_months(g, ticker)
        low_session = usual_low_session(g, dev)
        rows = []
        for family, rule, params in variants(ticker, low_session) + REFERENCES:
            rows.append(
                {"family": family, "rule": rule, "params": params, **evaluate_rule(g, rule, params, dev, reps=reps)}
            )
        chosen = {}
        for row in rows:
            fam = row["family"]
            if fam in ("R",):
                continue
            key = f"B1_{WEEKDAYS[row['params']['day']]}" if fam == "B1" else fam
            if key not in chosen or row["mean_advantage"] > chosen[key]["mean_advantage"]:
                chosen[key] = row
        out[ticker] = {
            "development_months": [str(dev[0]), str(dev[-1])],
            "usual_low_session": low_session,
            "variants": rows,
            "chosen": {k: {"rule": v["rule"], "params": v["params"]} for k, v in chosen.items()},
        }
    return out


def confirm(frame: pd.DataFrame, choices: dict, *, reps=None) -> dict:
    tests, refs = [], {}
    for ticker in data.UNIVERSE:
        g = sessions(frame, ticker)
        _, conf = split_months(g, ticker)
        for key, c in choices[ticker]["chosen"].items():
            tests.append(
                {"ticker": ticker, "test": key, **c, **evaluate_rule(g, c["rule"], c["params"], conf, reps=reps)}
            )
        refs[ticker] = {
            r: evaluate_rule(g, r, p, conf, reps=reps) | {"period": [str(conf[0]), str(conf[-1])]}
            for _, r, p in REFERENCES
        }
    q = bh(np.array([t["p_one_sided"] for t in tests]))
    for t, qv in zip(tests, q, strict=True):
        t["q"] = float(qv)
        t["passes"] = bool(t["mean_advantage"] >= MIN_ADVANTAGE and qv < Q)
    return {"tests": tests, "references": refs, "n_tests": len(tests)}


def verdict(real: dict, random_walk: dict) -> dict:
    rw_pass = sum(t["passes"] for t in random_walk["tests"])
    by_ticker = {}
    for ticker in data.UNIVERSE:
        passing = [t["test"] for t in real["tests"] if t["ticker"] == ticker and t["passes"]]
        by_ticker[ticker] = {"supported": bool(passing) and rw_pass == 0, "passing": passing}
    return {"random_walk_passes": rw_pass, "by_ticker": by_ticker}


# ---------------------------------------------------------------- tables and command line


def markdown(dev: dict | None, conf: dict | None) -> str:
    def pct(x):
        return f"{x * 100:+.2f}%"

    def label(rule, params):
        if rule == "weekday":
            return f"weekday {WEEKDAYS[params['day']]}"
        return rule.replace("_", " ") + (
            "" if not params else " (" + ", ".join(f"{k} {v}" for k, v in params.items()) + ")"
        )

    lines = []
    if dev:
        lines += [
            "**Development** (mean price advantage against a random session of the month; chosen variant in bold)",
            "",
        ]
        lines += [
            "| Instrument | Months | "
            + " | ".join(["B1 best day", "B2", "B3", "B4", "B5", "B6", "B7", "First session", "Last session"])
            + " |"
        ]
        lines += ["|---|---:|" + "---|" * 9]
        for ticker, d in dev.items():
            rows = d["variants"]
            best_day = max((r for r in rows if r["family"] == "B1"), key=lambda r: r["mean_advantage"])
            cells = [f"{WEEKDAYS[best_day['params']['day']]} {pct(best_day['mean_advantage'])}"]
            for fam in ("B2", "B3", "B4", "B5", "B6", "B7"):
                c = d["chosen"].get(fam)
                if not c:
                    cells.append("-")
                    continue
                r = next(r for r in rows if r["rule"] == c["rule"] and r["params"] == c["params"])
                cells.append(f"{pct(r['mean_advantage'])}")
            for rule in ("first_session", "last_session"):
                r = next(r for r in rows if r["rule"] == rule)
                cells.append(pct(r["mean_advantage"]))
            lines.append(f"| {ticker} | {rows[0]['months']} | " + " | ".join(cells) + " |")
        lines += [""]
    if conf:
        real, rw = conf["real"], conf["random_walk"]
        lines += [
            f"**Confirmation** ({real['n_tests']} tests, Benjamini–Hochberg across all; passes: mean advantage at least "
            f"{MIN_ADVANTAGE * 100:.2f}% and q below {Q})",
            "",
            "| Instrument | Test | Rule | Months | Mean advantage (95%) | Share of months positive | Wealth vs random | q | Passes |",
            "|---|---|---|---:|---|---:|---:|---:|---|",
        ]
        for t in real["tests"]:
            lines.append(
                f"| {t['ticker']} | {t['test']} | {label(t['rule'], t['params'])} | {t['months']} | {pct(t['mean_advantage'])} "
                f"({pct(t['ci95'][0])} to {pct(t['ci95'][1])}) | {t['share_positive'] * 100:.0f}% | {pct(t['wealth_vs_random'])} "
                f"| {t['q']:.3f} | {'yes' if t['passes'] else 'no'} |"
            )
        lines += ["", "| Instrument | Reference | Mean advantage (95%) |", "|---|---|---|"]
        for ticker, refs in real["references"].items():
            for r, v in refs.items():
                lines.append(
                    f"| {ticker} | {r.replace('_', ' ')} | {pct(v['mean_advantage'])} ({pct(v['ci95'][0])} to {pct(v['ci95'][1])}) |"
                )
        v = conf["verdict"]
        lines += [
            "",
            f"Random walks: {v['random_walk_passes']} of {rw['n_tests']} tests pass.",
            "",
            "H-2026-017 by instrument: "
            + "; ".join(
                f"{k} **{'supported' if s['supported'] else 'not supported'}**"
                + (f" ({', '.join(s['passing'])})" if s["passing"] else "")
                for k, s in v["by_ticker"].items()
            )
            + ".",
        ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", nargs="?", choices=["develop", "confirm"])
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--rerun", default=None, help="reason for running the confirmation again (logged)")
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)
    store = args.store or data.default_store()
    results = store / "results"
    results.mkdir(parents=True, exist_ok=True)
    dev_path, conf_path = results / "timing_development.json", results / "timing_confirmation.json"
    if args.markdown:
        dev = json.loads(dev_path.read_text()) if dev_path.exists() else None
        conf = json.loads(conf_path.read_text()) if conf_path.exists() else None
        print(markdown(dev, conf))
        return
    frame, _ = data.load("file", store)
    if args.action == "develop":
        dev = develop(frame)
        dev_path.write_text(json.dumps(dev, indent=2, default=str))
        CHOICES.write_text(
            json.dumps(
                {t: {"chosen": d["chosen"], "development_months": d["development_months"]} for t, d in dev.items()},
                indent=2,
            )
            + "\n"
        )
        print(f"written {dev_path} and {CHOICES}; commit the choices before: python -m tsip.capstone.timing confirm")
        return
    if args.action == "confirm":
        commit, dirty = E.git_state()
        _, _, manifest = data.load_store(store)
        runs = E.open_run(
            E.RUN_LOG,
            commit=commit,
            dirty=dirty,
            fingerprint=manifest["sha256"],
            kind="timing_confirmation",
            rerun=args.rerun,
        )
        choices = json.loads(CHOICES.read_text())
        real = confirm(frame, choices)
        rw_frame = M.random_walk_frame(frame)
        rw_dev = develop(rw_frame, reps=500)
        rw = confirm(rw_frame, {t: {"chosen": d["chosen"]} for t, d in rw_dev.items()})
        out = {"real": real, "random_walk": rw, "verdict": verdict(real, rw), "run": runs[-1]}
        conf_path.write_text(json.dumps(out, indent=2, default=str))
        E.mark_run(E.RUN_LOG, runs, "completed", conf_path)
        print(markdown(None, out))
        return
    parser.error("give develop, confirm or --markdown")


if __name__ == "__main__":
    main()
