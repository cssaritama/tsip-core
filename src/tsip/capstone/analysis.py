"""Exploratory and diagnostic analysis for the course project (rubric items on EDA and deep analysis).

Everything here is descriptive and exploratory; nothing changes a registered result.

* ``correlations``: Spearman correlation of every feature with the future return, on training and
  validation rows only (the test period is not used for exploration).
* ``by_group``: on the saved test predictions, the AUC, the precision of the most confident decile
  and the base rate, by instrument and by month of the year.
* ``confident_errors``: the most confident wrong predictions, and where they cluster.
* ``vector_return``: the vector view's approximate return on capital.

    python -m tsip.capstone.analysis --markdown
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tsip.capstone import data, features
from tsip.capstone import models as M

MODEL_COLUMNS = ("LECTURE", "LECTURE+TIME+SPACE")


def correlations(feats: pd.DataFrame, sets: dict, horizon: int = 5, top: int = 15) -> pd.DataFrame:
    """Spearman correlation of each feature with the future return, training and validation rows only."""
    target = f"growth_future_{horizon}d"
    rows = feats[(feats["date"] <= M.VALIDATION_END) & feats[target].notna()]
    out = []
    for group in ("LECTURE", "TIME", "SPACE"):
        for col in sets[group]:
            x = rows[col]
            ok = x.notna()
            if ok.sum() < 500 or x[ok].nunique() < 3:
                continue
            rho = x[ok].rank().corr(rows.loc[ok, target].rank())
            out.append({"feature": col, "set": group, "spearman": float(rho), "rows": int(ok.sum())})
    table = pd.DataFrame(out)
    table["abs"] = table["spearman"].abs()
    return table.sort_values("abs", ascending=False).drop(columns="abs").head(top).reset_index(drop=True)


def _precision_top_decile(y: np.ndarray, p: np.ndarray, cut: float) -> float:
    top = p >= cut
    return float(y[top].mean()) if top.any() else float("nan")


def by_group(pred: pd.DataFrame, horizon: int = 5) -> dict[str, pd.DataFrame]:
    """AUC, precision of the most confident decile (cut fixed on the whole test set) and base rate per group."""
    target = f"is_positive_growth_{horizon}d"
    pred = pred.assign(month_of_year=pd.to_datetime(pred["date"]).dt.month)
    cuts = {c: float(np.quantile(pred[c], 0.9)) for c in MODEL_COLUMNS}
    out = {}
    for key in ("ticker", "month_of_year"):
        rows = []
        for value, g in pred.groupby(key):
            y = g[target].to_numpy()
            row = {key: value, "rows": len(g), "base_rate": float(y.mean())}
            for c in MODEL_COLUMNS:
                row[f"auc {c}"] = M._auc(y, g[c].to_numpy())
                row[f"mean probability {c}"] = float(g[c].mean())
                row[f"precision top decile {c}"] = _precision_top_decile(y, g[c].to_numpy(), cuts[c])
                row[f"top decile rows {c}"] = int((g[c] >= cuts[c]).sum())
            rows.append(row)
        out[key] = pd.DataFrame(rows)
    return out


def confident_errors(pred: pd.DataFrame, column: str = "LECTURE+TIME+SPACE", horizon: int = 5, n: int = 10) -> dict:
    """The most confident wrong calls (probability far from 0.5 on the wrong side) and where they cluster."""
    target = f"is_positive_growth_{horizon}d"
    p = pred[column]
    wrong = pred[((p >= 0.5) & (pred[target] == 0)) | ((p < 0.5) & (pred[target] == 1))].copy()
    wrong["confidence"] = (wrong[column] - 0.5).abs()
    worst = wrong.sort_values("confidence", ascending=False).head(n)
    top_share = wrong[wrong["confidence"] >= wrong["confidence"].quantile(0.9)]
    return {
        "worst": worst[["date", "ticker", column, target, f"growth_future_{horizon}d"]].to_dict("records"),
        "error_rate": float(len(wrong) / len(pred)),
        "confident_errors_by_ticker": top_share["ticker"].value_counts(normalize=True).round(3).to_dict(),
        "confident_errors_by_year": pd.to_datetime(top_share["date"])
        .dt.year.value_counts(normalize=True)
        .sort_index()
        .round(3)
        .to_dict(),
    }


def vector_return(vector: dict) -> float | None:
    """Approximate return on capital of the vector view: total net result over the capital needed."""
    if not vector.get("capital_needed"):
        return None
    return vector["total_net"] / vector["capital_needed"]


def markdown(store: Path) -> str:
    results = store / "results"
    lines = []
    frame, _ = data.load("file", store)
    feats, sets = features.build_features(frame)
    for h in (5, 20):
        corr = correlations(feats, sets, h)
        lines += [
            f"**Correlation with the return of the next {h} rows** (Spearman, training and validation rows, 15 strongest)",
            "",
            "| Feature | Set | Spearman | Rows |",
            "|---|---|---:|---:|",
        ]
        lines += [f"| `{r.feature}` | {r.set} | {r.spearman:+.3f} | {r.rows:,} |" for r in corr.itertuples()]
        lines.append("")
    sim = json.loads((results / "simulation_h5.json").read_text())
    lines += ["**Vector view, approximate return on capital** (bets of 100; total net over the capital needed)", ""]
    lines += [
        "| Period | Feature set | Bets | Hit rate | Total net | Capital needed | Return on capital |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    test = json.loads((results / "test_h5.json").read_text()) if (results / "test_h5.json").exists() else None
    for period, res in (("validation", sim["by_feature_set"]), ("test", test["strategies"] if test else {})):
        for fs, r in res.items():
            v = r["vector"]["sim1"]
            roc = vector_return(v)
            lines.append(
                f"| {period} | {fs} | {v['trades']:,} | {v['hit_rate'] * 100:.1f}% | {v['total_net']:+,.0f} "
                f"| {v['capital_needed']:,.0f} | {roc * 100:+.1f}% |"
            )
    pred_path = results / "test_predictions_h5.csv.gz"
    if pred_path.exists():
        pred = pd.read_csv(pred_path)
        groups = by_group(pred)
        for key, title in (("ticker", "instrument"), ("month_of_year", "month of the year")):
            t = groups[key]
            lines += [
                "",
                f"**Test period by {title}** (direction of the next 5 rows; precision of the 10% most confident calls, "
                "cut fixed on the whole test set; exploratory)",
                "",
                f"| {title.capitalize()} | Rows | Base rate | AUC LECTURE | AUC +TIME+SPACE | Precision top decile LECTURE (rows) "
                "| Precision top decile +TIME+SPACE (rows) |",
                "|---|---:|---:|---:|---:|---|---|",
            ]
            for r in t.to_dict("records"):

                def prec(c, r=r):
                    v = r[f"precision top decile {c}"]
                    return (
                        f"{v * 100:.1f}% ({r[f'top decile rows {c}']})"
                        if not np.isnan(v)
                        else f"- ({r[f'top decile rows {c}']})"
                    )

                lines.append(
                    f"| {r[key]} | {r['rows']} | {r['base_rate'] * 100:.1f}% | {r['auc LECTURE']:.3f} "
                    f"| {r['auc LECTURE+TIME+SPACE']:.3f} | {prec('LECTURE')} | {prec('LECTURE+TIME+SPACE')} |"
                )
        err = confident_errors(pred)
        lines += [
            "",
            f"**Wrong predictions** (LECTURE+TIME+SPACE): error rate {err['error_rate'] * 100:.1f}%. Share of the 10% most "
            "confident errors by instrument: "
            + ", ".join(f"{k} {v * 100:.0f}%" for k, v in err["confident_errors_by_ticker"].items())
            + "; by year: "
            + ", ".join(f"{k} {v * 100:.0f}%" for k, v in err["confident_errors_by_year"].items())
            + ".",
            "",
            "Calibration (mean predicted probability against the base rate): "
            + "; ".join(
                f"{r['ticker']} {r['mean probability LECTURE+TIME+SPACE'] * 100:.1f}% against {r['base_rate'] * 100:.1f}%"
                for r in groups["ticker"].to_dict("records")
            )
            + ".",
            "",
            "| Date | Instrument | Probability | Outcome (positive 5 rows) | Return of the next 5 rows |",
            "|---|---|---:|---:|---:|",
        ]
        for w in err["worst"]:
            lines.append(
                f"| {str(w['date'])[:10]} | {w['ticker']} | {w['LECTURE+TIME+SPACE']:.3f} | {int(w['is_positive_growth_5d'])} "
                f"| {w['growth_future_5d'] * 100:+.1f}% |"
            )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)
    print(markdown(args.store or data.default_store()))


if __name__ == "__main__":
    main()
