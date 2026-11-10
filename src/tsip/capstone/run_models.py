"""Step 3 of the course project: every model family on every feature set, on the validation period.

Resumable in small pieces (each piece is one family and one feature set, and is skipped if its
result already exists), then summarised:

    python -m tsip.capstone.run_models fit --horizon 5 [--families xgboost] [--feature-sets LECTURE]
    python -m tsip.capstone.run_models fit --horizon 5 --random-walk          # control
    python -m tsip.capstone.run_models summarise --horizon 5 [--random-walk]

Pieces go to ``<results>/h<horizon>[_random_walk]/`` (default ``<store>/results``, outside Git): a
JSON record and the validation predictions. The summary adds, per family, the lift of
LECTURE+TIME+SPACE over LECTURE with a block-bootstrap interval, and applies the selection rule of
specification 0028: the family with the highest mean validation AUC over the four feature sets.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from tsip.capstone import data, features
from tsip.capstone import models as M

FAMILIES = ("logistic", "decision_tree", "xgboost", "random_forest")  # simplest first (tie-break order)


def _folder(results: Path, horizon: int, random_walk: bool) -> Path:
    return results / f"h{horizon}{'_random_walk' if random_walk else ''}"


def fit(feats, sets, horizon, families, feature_sets, folder: Path, log=print) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for family in families:
        for feature_set in feature_sets:
            stem = folder / f"{family}__{feature_set}"
            if stem.with_suffix(".json").exists():
                log(f"{family:14s} {feature_set:20s} already done")
                continue
            t0 = time.time()
            fitted, scored, record = M.fit_and_score(feats, sets, family, feature_set, horizon)
            if feature_set == "LECTURE+TIME+SPACE":
                record["permuted_time_space_auc"] = M.permuted_control(fitted, feats, sets, horizon)
            record["seconds"] = round(time.time() - t0, 1)
            scored.to_csv(stem.with_suffix(".csv.gz"), index=False)
            stem.with_suffix(".json").write_text(json.dumps(record, indent=2, default=str))
            log(f"{family:14s} {feature_set:20s} AUC {record['validation_auc']:.4f} ({record['seconds']}s)")


def summarise(folder: Path, horizon: int) -> dict:
    target = f"is_positive_growth_{horizon}d"
    records = {
        (r["family"], r["feature_set"]): r
        for r in (json.loads(p.read_text()) for p in folder.glob("*.json") if "__" in p.name)
    }
    families = [f for f in FAMILIES if all((f, s) in records for s in M.FEATURE_SETS)]
    table, lifts = [], {}
    for family in families:
        row = {"family": family}
        for s in M.FEATURE_SETS:
            row[s] = records[(family, s)]["validation_auc"]
        row["mean"] = float(np.mean([row[s] for s in M.FEATURE_SETS]))
        row["permuted_time_space"] = records[(family, "LECTURE+TIME+SPACE")].get("permuted_time_space_auc")
        full = pd.read_csv(folder / f"{family}__LECTURE+TIME+SPACE.csv.gz", parse_dates=["date"])
        base = pd.read_csv(folder / f"{family}__LECTURE.csv.gz", parse_dates=["date"])
        joined = full.merge(base[["date", "ticker", "probability"]], on=["date", "ticker"], suffixes=("", "_base"))

        def stat(sample, target=target):
            y = sample[target].to_numpy()
            return M._auc(y, sample["probability"].to_numpy()) - M._auc(y, sample["probability_base"].to_numpy())

        lifts[family] = {
            "lift": row["LECTURE+TIME+SPACE"] - row["LECTURE"],
            "block95": M.block_bootstrap_dates(joined, stat, reps=300),
        }
        row.update(
            {
                "lift": lifts[family]["lift"],
                "lift_low": lifts[family]["block95"][0],
                "lift_high": lifts[family]["block95"][1],
            }
        )
        table.append(row)
    best = max(table, key=lambda r: (round(r["mean"], 6), -FAMILIES.index(r["family"]))) if table else None
    base_rate = next(iter(records.values()))["validation_base_rate"] if records else None
    summary = {
        "horizon": horizon,
        "folder": str(folder),
        "validation_base_rate": base_rate,
        "table": table,
        "selected_family": best["family"] if best else None,
        "complete": len(families) == len(FAMILIES),
    }
    (folder / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["fit", "summarise"])
    parser.add_argument("--horizon", type=int, default=5, choices=[5, 20])
    parser.add_argument("--families", nargs="+", default=list(FAMILIES))
    parser.add_argument("--feature-sets", nargs="+", default=list(M.FEATURE_SETS))
    parser.add_argument("--random-walk", action="store_true", help="run on random-walk prices (control)")
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--results", type=Path, default=None, help="folder for results (default: <store>/results)")
    args = parser.parse_args(argv)
    store = args.store or data.default_store()
    folder = _folder(args.results or store / "results", args.horizon, args.random_walk)
    if args.action == "summarise":
        print(json.dumps(summarise(folder, args.horizon), indent=2))
        return
    frame, _ = data.load("file", store)
    if args.random_walk:
        frame = M.random_walk_frame(frame)
    feats, sets = features.build_features(frame)
    fit(feats, sets, args.horizon, args.families, args.feature_sets, folder)


if __name__ == "__main__":
    main()
