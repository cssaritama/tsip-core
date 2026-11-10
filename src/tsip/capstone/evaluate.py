"""Step 5 of the course project: the single test-period evaluation (specification 0028, T4).

The rule is written in specification 0028, section "Evaluation rule", and was committed before
this module first ran. The run:

1. refuses to start from a working tree with uncommitted changes, and refuses a second run unless
   ``--rerun "<reason>"`` is given; every run is logged in ``registry/capstone_test_runs.json``
   (time, commit, data fingerprint, reason) before the test period is read;
2. fits the logistic model of step 3 on the training period only, for the four feature sets, and
   scores the test period (from 2024-01-01);
3. computes the registered lift with a circular block bootstrap, the permuted and random-walk
   controls, and the verdict of H-2026-016;
4. runs the strategies with the parameters frozen in ``registry/capstone_choices_h5.json``.

    python -m tsip.capstone.evaluate                   # registered run, phase 1: models, controls, verdict
    python -m tsip.capstone.evaluate --strategies      # phase 2 of the same run: frozen strategies
    python -m tsip.capstone.evaluate --walk-forward 5  # exploratory: yearly refits (5 or 20 rows)
    python -m tsip.capstone.evaluate --markdown        # tables of the saved summary
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from tsip.capstone import data, features
from tsip.capstone import models as M
from tsip.capstone import simulate as S

REPO = Path(__file__).resolve().parents[3]
RUN_LOG = REPO / "registry" / "capstone_test_runs.json"
CHOICES = REPO / "registry" / "capstone_choices_h5.json"
TEST_START = M.VALIDATION_END + pd.Timedelta(days=1)
FAMILY = "logistic"
HORIZON = 5
REPS = 2000
MIN_LIFT = 0.02


# ---------------------------------------------------------------- single-read guard


def git_state(repo: Path = REPO) -> tuple[str, bool]:
    """Commit of the working tree and whether it has uncommitted changes other than the run log."""
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True, check=True
    )
    log = RUN_LOG.relative_to(repo).as_posix() if RUN_LOG.is_relative_to(repo) else None
    changes = [line for line in status.stdout.splitlines() if line.strip() and not (log and line.endswith(log))]
    return commit.stdout.strip(), bool(changes)


def open_run(log: Path, *, commit: str, dirty: bool, fingerprint: dict, kind: str, rerun: str | None) -> list:
    """Check the guard and append the run to the log before any test row is read."""
    if dirty:
        raise SystemExit("Refused: commit every change first, so the run records the code that produced it.")
    runs = json.loads(log.read_text()) if log.exists() else []
    previous = [r for r in runs if r["kind"] == kind]
    if previous and not rerun:
        raise SystemExit(
            f"Refused: the {kind} run already happened on {previous[0]['started_utc']} (commit {previous[0]['commit']}). "
            'Give --rerun "<reason>" to run again; the reason is logged.'
        )
    runs.append(
        {
            "kind": kind,
            "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "commit": commit,
            "data_sha256": fingerprint,
            "rerun_reason": rerun,
            "status": "started",
        }
    )
    log.write_text(json.dumps(runs, indent=2) + "\n")
    return runs


def mark_run(log: Path, runs: list, status: str, summary_path: Path) -> None:
    runs[-1]["status"] = status
    runs[-1].setdefault("outputs", []).append(summary_path.name)
    log.write_text(json.dumps(runs, indent=2) + "\n")


def continue_run(log: Path, *, commit: str, dirty: bool) -> list:
    """Phase 2 continues the registered run whose phase 1 finished, with the same code; nothing else."""
    if dirty:
        raise SystemExit("Refused: commit every change first.")
    runs = json.loads(log.read_text()) if log.exists() else []
    registered = [r for r in runs if r["kind"] == "registered"]
    if not registered or registered[-1]["status"] != "models_done":
        raise SystemExit("Refused: phase 2 needs a registered run whose phase 1 (models) finished and phase 2 did not.")
    if registered[-1]["commit"] != commit:
        raise SystemExit(
            f"Refused: phase 1 ran with commit {registered[-1]['commit']}; phase 2 must use the same code."
        )
    if runs[-1] is not registered[-1]:
        raise SystemExit("Refused: another run was logged after phase 1.")
    return runs


# ---------------------------------------------------------------- statistics


def lift_interval(
    frame: pd.DataFrame, target: str, a: str, b: str, *, reps: int | None = None, block: int = 20, seed=M.SEED
):
    """AUC(a) minus AUC(b) and its circular block bootstrap interval over dates (all tickers of a date kept)."""
    from sklearn.metrics import roc_auc_score

    reps = reps or REPS
    dates = np.sort(frame["date"].unique())
    pos = {d: i for i, d in enumerate(dates)}
    codes = frame["date"].map(pos).to_numpy()
    order = np.argsort(codes, kind="stable")
    bounds = np.searchsorted(codes[order], np.arange(len(dates) + 1))
    groups = [order[bounds[i] : bounds[i + 1]] for i in range(len(dates))]
    y, pa, pb = frame[target].to_numpy(), frame[a].to_numpy(), frame[b].to_numpy()
    point = roc_auc_score(y, pa) - roc_auc_score(y, pb)
    rng = np.random.default_rng(seed)
    n = len(dates)
    out = []
    for _ in range(reps):
        starts = rng.integers(0, n, size=int(np.ceil(n / block)))
        picked = np.concatenate([(np.arange(s, s + block) % n) for s in starts])[:n]
        rows = np.concatenate([groups[i] for i in picked])
        if len(np.unique(y[rows])) < 2:
            continue
        out.append(roc_auc_score(y[rows], pa[rows]) - roc_auc_score(y[rows], pb[rows]))
    return float(point), np.quantile(out, [0.025, 0.975]).tolist()


def verdict(lift: float, low: float, permuted_low: float, random_walk_low: float) -> dict:
    """H-2026-016 criterion of specification 0028: lift >= 0.02, interval above zero, controls without lift."""
    checks = {
        "lift_at_least_0.02": lift >= MIN_LIFT,
        "interval_excludes_zero": low > 0,
        "permuted_control_shows_no_lift": permuted_low <= 0,
        "random_walk_control_shows_no_lift": random_walk_low <= 0,
    }
    return {"supported": all(checks.values()), "checks": checks}


def fit_score(feats, sets, feature_set: str, train: pd.DataFrame, score: pd.DataFrame, horizon: int):
    """Tune and fit on ``train`` exactly as step 3, then the probabilities on ``score``."""
    cols = M.columns_for(sets, feature_set)
    target = f"is_positive_growth_{horizon}d"
    params, _ = M.tune(FAMILY, train[cols], train[target].to_numpy(), train["date"])
    model = M.make_model(FAMILY, params).fit(train[cols], train[target].to_numpy())
    return model, cols, params, model.predict_proba(score[cols])[:, 1]


def score_period(frame: pd.DataFrame, horizon: int, feature_sets) -> tuple[pd.DataFrame, dict, dict]:
    feats, sets = features.build_features(frame)
    parts = M.split(feats, horizon, allow_test=True)
    train, val, test = parts["train"], parts["validation"], parts["test"]
    target = f"is_positive_growth_{horizon}d"
    scored = test[["date", "ticker", target, f"growth_future_{horizon}d"]].copy()
    info, fitted = {}, {}
    for fs in feature_sets:
        model, cols, params, p = fit_score(feats, sets, fs, train, test, horizon)
        scored[fs] = p
        val_auc = M._auc(val[target].to_numpy(), model.predict_proba(val[cols])[:, 1])
        info[fs] = {
            "params": params,
            "test_auc": M._auc(scored[target].to_numpy(), p),
            "validation_auc_refit": val_auc,
            "test_auc_by_ticker": {
                t: M._auc(g[target].to_numpy(), g[fs].to_numpy()) for t, g in scored.groupby("ticker")
            },
        }
        fitted[fs] = (model, cols)
    info["_rows"] = {"train": len(train), "validation": len(val), "test": len(test)}
    info["_base_rate"] = float(scored[target].mean())
    return scored, info, {"feats": feats, "sets": sets, "test": test, "fitted": fitted}


def permuted_scores(ctx: dict, horizon: int, seed=M.SEED) -> np.ndarray:
    model, cols = ctx["fitted"]["LECTURE+TIME+SPACE"]
    test = ctx["test"].copy()
    shuffled = [c for c in ctx["sets"]["TIME"] + ctx["sets"]["SPACE"] if c in cols]
    rng = np.random.default_rng(seed)
    for _, idx in test.groupby("ticker").indices.items():
        perm = rng.permutation(idx)
        test.iloc[idx, [test.columns.get_loc(c) for c in shuffled]] = test.iloc[perm][shuffled].to_numpy()
    return model.predict_proba(test[cols])[:, 1]


# ---------------------------------------------------------------- the registered run


def models_phase(store: Path, results: Path) -> dict:
    """Phase 1: the four models on the test period, the registered lift, both controls and the verdict."""
    frame, _ = data.load("file", store)
    target = f"is_positive_growth_{HORIZON}d"
    scored, info, ctx = score_period(frame, HORIZON, list(M.FEATURE_SETS))
    lift, ci = lift_interval(scored, target, "LECTURE+TIME+SPACE", "LECTURE")
    scored["permuted"] = permuted_scores(ctx, HORIZON)
    p_lift, p_ci = lift_interval(scored, target, "permuted", "LECTURE")
    exploratory = {
        fs: dict(zip(("lift", "ci95"), lift_interval(scored, target, fs, "LECTURE"), strict=True))
        for fs in ("LECTURE+TIME", "LECTURE+SPACE")
    }
    rw_scored, rw_info, _ = score_period(M.random_walk_frame(frame), HORIZON, ["LECTURE", "LECTURE+TIME+SPACE"])
    rw_lift, rw_ci = lift_interval(rw_scored, target, "LECTURE+TIME+SPACE", "LECTURE")
    scored.to_csv(results / f"test_predictions_h{HORIZON}.csv.gz", index=False)
    return {
        "horizon": HORIZON,
        "family": FAMILY,
        "test_start": str(TEST_START.date()),
        "models": info,
        "registered": {"lift": lift, "ci95": ci, "verdict": verdict(lift, ci[0], p_ci[0], rw_ci[0])},
        "permuted_control": {"lift": p_lift, "ci95": p_ci},
        "random_walk_control": {
            "lift": rw_lift,
            "ci95": rw_ci,
            "auc": {k: rw_info[k]["test_auc"] for k in ("LECTURE", "LECTURE+TIME+SPACE")},
        },
        "exploratory_lifts": exploratory,
    }


def strategies_phase(store: Path, results: Path, models: dict) -> dict:
    """Phase 2: the strategies with the frozen parameters on the test predictions of phase 1."""
    frame, _ = data.load("file", store)
    feats, _ = features.build_features(frame)
    target = f"is_positive_growth_{HORIZON}d"
    scored = pd.read_csv(results / f"test_predictions_h{HORIZON}.csv.gz", parse_dates=["date"])
    choices = json.loads(CHOICES.read_text())
    volatility = feats.pivot(index="date", columns="ticker", values="volatility_20")
    panel = S.make_panel(frame, start=TEST_START - pd.Timedelta(days=400), end=None, allow_test=True)
    strategies = {}
    for fs in ("LECTURE", "LECTURE+TIME+SPACE"):
        preds = scored[["date", "ticker", target, f"growth_future_{HORIZON}d", fs]].rename(columns={fs: "probability"})
        sub, prob = S.sub_panel(panel, preds)
        strategies[fs] = S.run_chosen(panel, sub, prob, preds, volatility, choices["chosen"][fs], HORIZON)
    primary = choices["primary"]
    pm = strategies[primary["feature_set"]]
    claim = {
        "strategy": primary["strategy"],
        "feature_set": primary["feature_set"],
        "cagr": pm["metrics"][primary["strategy"]]["cagr"],
        "buy_hold_equal_cagr": pm["metrics"]["buy_hold_equal"]["cagr"],
        "spy_total_return_cagr": pm["metrics"]["spy_total_return"]["cagr"],
    }
    claim["beats_both_benchmarks"] = claim["cagr"] > max(claim["buy_hold_equal_cagr"], claim["spy_total_return_cagr"])
    pull = S.pullback_study(panel, TEST_START)
    pull["frozen_trigger"] = choices["pullback_trigger"]
    return {**models, "strategies": strategies, "benchmark_claim": claim, "pullback": pull}


# ---------------------------------------------------------------- exploratory: walk-forward and 20 rows


def walk_forward(store: Path, horizons=(5, 20)) -> dict:
    """Refit at the start of each test year on every earlier row (purged), score that year; both horizons."""
    frame, _ = data.load("file", store)
    feats, sets = features.build_features(frame)
    out = {}
    for horizon in horizons:
        target = f"is_positive_growth_{horizon}d"
        known = feats[feats[target].notna()]
        years = sorted({d.year for d in known["date"] if d >= TEST_START})
        parts = []
        for year in years:
            start = pd.Timestamp(year=year, month=1, day=1)
            before = known[known["date"] < start]
            keep = np.ones(len(before), dtype=bool)
            for _, idx in before.groupby("ticker").indices.items():
                keep[idx[-horizon:]] = False  # their labels look into the scored year
            train = before[keep]
            score = known[(known["date"] >= start) & (known["date"] < pd.Timestamp(year=year + 1, month=1, day=1))]
            block = score[["date", "ticker", target]].copy()
            for fs in ("LECTURE", "LECTURE+TIME+SPACE"):
                block[fs] = fit_score(feats, sets, fs, train, score, horizon)[3]
            parts.append(block)
        scored = pd.concat(parts, ignore_index=True)
        lift, ci = lift_interval(scored, target, "LECTURE+TIME+SPACE", "LECTURE")
        out[f"h{horizon}"] = {
            "years": years,
            "auc": {
                fs: M._auc(scored[target].to_numpy(), scored[fs].to_numpy()) for fs in ("LECTURE", "LECTURE+TIME+SPACE")
            },
            "lift": lift,
            "ci95": ci,
            "base_rate": float(scored[target].mean()),
        }
    return out


# ---------------------------------------------------------------- tables


def markdown(summary: dict, walk: dict | None = None) -> str:
    def pct(x):
        return f"{x * 100:+.1f}%"

    m, r = summary["models"], summary["registered"]
    lines = [
        f"Rows: training {m['_rows']['train']:,}, validation {m['_rows']['validation']:,}, test {m['_rows']['test']:,} "
        f"(test base rate {m['_base_rate'] * 100:.1f}% positive).",
        "",
        "| Feature set | Test AUC | Validation AUC (refit, check) |",
        "|---|---:|---:|",
    ]
    for fs in M.FEATURE_SETS:
        lines.append(f"| {fs} | {m[fs]['test_auc']:.3f} | {m[fs]['validation_auc_refit']:.3f} |")
    v = r["verdict"]
    lines += [
        "",
        "| Statistic | Lift over LECTURE | 95% interval |",
        "|---|---:|---|",
        f"| **Registered: LECTURE+TIME+SPACE** | **{r['lift']:+.4f}** | {r['ci95'][0]:+.4f} to {r['ci95'][1]:+.4f} |",
    ]
    for fs, e in summary["exploratory_lifts"].items():
        lines.append(f"| {fs} (exploratory) | {e['lift']:+.4f} | {e['ci95'][0]:+.4f} to {e['ci95'][1]:+.4f} |")
    pc, rc = summary["permuted_control"], summary["random_walk_control"]
    lines += [
        f"| Control: TIME and SPACE shuffled | {pc['lift']:+.4f} | {pc['ci95'][0]:+.4f} to {pc['ci95'][1]:+.4f} |",
        f"| Control: random walk | {rc['lift']:+.4f} | {rc['ci95'][0]:+.4f} to {rc['ci95'][1]:+.4f} |",
        "",
        "H-2026-016: **"
        + ("supported" if v["supported"] else "rejected")
        + "** ("
        + "; ".join(f"{k.replace('_', ' ')}: {'yes' if ok else 'no'}" for k, ok in v["checks"].items())
        + ").",
        "",
    ]
    for fs, res in summary["strategies"].items():
        lines += [
            f"**Strategies on {fs}** (test period {res['period'][0]} to {res['period'][1]}, frozen parameters)",
            "",
            "| Strategy | CAGR (95%) | CAGR minus five equal (95%) | CAGR minus SPY with dividends (95%) | Sharpe "
            "| Max drawdown | Exposure | Entries | One-session delay: CAGR, Sharpe |",
            "|---|---|---|---|---:|---:|---:|---:|---|",
        ]
        for key in (
            "sim1",
            "sim2",
            "sim3",
            "sim4",
            "buy_hold_equal",
            "buy_hold_crypto",
            "spy_total_return",
            "spy_price_only",
        ):
            mm, ii = res["metrics"][key], res["intervals"][key]
            d1 = ii.get("cagr_minus_buy_hold_equal95")
            d2 = res["intervals_vs_spy"].get(key)
            dl = res["delayed_one_session"].get(key)
            lines.append(
                f"| {key} | {pct(mm['cagr'])} ({pct(ii['cagr95'][0])} to {pct(ii['cagr95'][1])}) "
                f"| {pct(d1[0]) + ' to ' + pct(d1[1]) if d1 else '-'} | {pct(d2[0]) + ' to ' + pct(d2[1]) if d2 else '-'} "
                f"| {mm['sharpe']:.2f} | {pct(mm['max_drawdown'])} | {mm['exposure']:.2f} | {mm['entries']} "
                f"| {pct(dl['cagr']) + ', ' + format(dl['sharpe'], '.2f') if dl else '-'} |"
            )
        c = res["rotation_control"]
        lines += [
            "",
            f"Rotation control of sim1: median Sharpe {c['sharpe_median']:.2f} (95% {c['sharpe95'][0]:.2f} to "
            f"{c['sharpe95'][1]:.2f}); share at or above the actual {c['share_at_or_above_actual']:.2f}.",
            "",
        ]
    cl = summary["benchmark_claim"]
    lines.append(
        f"Benchmark comparison (registered strategy {cl['strategy']} on {cl['feature_set']}): CAGR {pct(cl['cagr'])} against "
        f"{pct(cl['buy_hold_equal_cagr'])} (five equal) and {pct(cl['spy_total_return_cagr'])} (SPY with dividends): "
        + (
            "**above both**."
            if cl["beats_both_benchmarks"]
            else "**not above both**; the rubric's exceptional-returns point is not claimed."
        )
    )
    pb = summary["pullback"]
    rows = pd.DataFrame(pb["rows"]).pivot(index="rule", columns="ticker", values="money_weighted_return")
    lines += [
        "",
        f"Pullback buying, money-weighted annual return (frozen trigger: {pb['frozen_trigger']}):",
        "",
        "| Rule | " + " | ".join(rows.columns) + " | Mean |",
        "|---|" + "---:|" * (len(rows.columns) + 1),
    ]
    for rule in ("lump_sum", "monthly", "cash", *S.PULLBACK_TRIGGERS):
        mark = " (frozen)" if rule == pb["frozen_trigger"] else ""
        lines.append(
            f"| {rule}{mark} | "
            + " | ".join(pct(rows.loc[rule, t]) for t in rows.columns)
            + f" | {pct(pb['mean_money_weighted_return'][rule])} |"
        )
    if walk:
        lines += [
            "",
            "Walk-forward check (exploratory; refitted at the start of each test year on all earlier rows):",
            "",
            "| Horizon | AUC LECTURE | AUC +TIME+SPACE | Lift (95%) |",
            "|---|---:|---:|---|",
        ]
        for h, w in walk.items():
            lines.append(
                f"| {h[1:]} rows | {w['auc']['LECTURE']:.3f} | {w['auc']['LECTURE+TIME+SPACE']:.3f} "
                f"| {w['lift']:+.4f} ({w['ci95'][0]:+.4f} to {w['ci95'][1]:+.4f}) |"
            )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--rerun", default=None, help="reason for running again (logged)")
    parser.add_argument("--strategies", action="store_true", help="phase 2 of the registered run: frozen strategies")
    parser.add_argument(
        "--walk-forward", type=int, choices=[5, 20], default=None, help="exploratory yearly refits, one horizon"
    )
    parser.add_argument("--markdown", action="store_true", help="print the tables of the saved summaries and stop")
    args = parser.parse_args(argv)
    store = args.store or data.default_store()
    results = args.results or store / "results"
    results.mkdir(parents=True, exist_ok=True)
    summary_path, walk_path = results / "test_h5.json", results / "test_walk_forward.json"
    if args.markdown:
        walk = json.loads(walk_path.read_text()) if walk_path.exists() else None
        print(markdown(json.loads(summary_path.read_text()), walk))
        return
    commit, dirty = git_state()
    _, _, manifest = data.load_store(store)
    models_path = results / "test_models_h5.json"
    if args.strategies:
        runs = continue_run(RUN_LOG, commit=commit, dirty=dirty)
        out = strategies_phase(store, results, json.loads(models_path.read_text()))
        out["run"] = runs[-1]
        summary_path.write_text(json.dumps(out, indent=2, default=str))
        mark_run(RUN_LOG, runs, "completed", summary_path)
        print(f"written {summary_path}")
        return
    kind = f"walk_forward_h{args.walk_forward}" if args.walk_forward else "registered"
    runs = open_run(RUN_LOG, commit=commit, dirty=dirty, fingerprint=manifest["sha256"], kind=kind, rerun=args.rerun)
    if args.walk_forward:
        walk = json.loads(walk_path.read_text()) if walk_path.exists() else {}
        out = walk_forward(store, (args.walk_forward,))
        out[f"h{args.walk_forward}"]["run"] = runs[-1]
        walk.update(out)
        walk_path.write_text(json.dumps(walk, indent=2, default=str))
        mark_run(RUN_LOG, runs, "completed", walk_path)
        print(f"written {walk_path}")
        return
    out = models_phase(store, results)
    out["run"] = runs[-1]
    models_path.write_text(json.dumps(out, indent=2, default=str))
    mark_run(RUN_LOG, runs, "models_done", models_path)
    print(f"written {models_path}")
    print(json.dumps(out["registered"], indent=2))
    print("next: python -m tsip.capstone.evaluate --strategies")


if __name__ == "__main__":
    main()
