"""Reproducibility across downloads: the validation results of two data stores side by side.

    python -m tsip.capstone.reproduce <store_a> <store_b> [--markdown]

Compares, for the logistic model, the validation AUC of every feature set at 5 and 20 rows, and the
choices of the strategy simulations (``simulation_h5.json``) of two stores built by ``run_all``.
Data revisions by the provider between downloads show up here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tsip.capstone import models as M


def compare(a: Path, b: Path) -> dict:
    ra, rb = a / "results", b / "results"
    manifests = [json.loads((s / "manifest.json").read_text()) for s in (a, b)]
    aucs = []
    for h in (5, 20):
        for fs in M.FEATURE_SETS:
            x = json.loads((ra / f"h{h}" / f"logistic__{fs}.json").read_text())["validation_auc"]
            y = json.loads((rb / f"h{h}" / f"logistic__{fs}.json").read_text())["validation_auc"]
            aucs.append({"horizon": h, "feature_set": fs, "a": x, "b": y, "difference": y - x})
    sa, sb = (json.loads((r / "simulation_h5.json").read_text()) for r in (ra, rb))
    choices = []
    for fs in sa["by_feature_set"]:
        for sim in ("sim1", "sim2", "sim3", "sim4"):
            pa, pb = (
                sa["by_feature_set"][fs]["chosen"][sim]["params"],
                sb["by_feature_set"][fs]["chosen"][sim]["params"],
            )
            same_structure = {k: v for k, v in pa.items() if not isinstance(v, float)} == {
                k: v for k, v in pb.items() if not isinstance(v, float)
            } and pa.get("quantile") == pb.get("quantile")
            choices.append({"feature_set": fs, "strategy": sim, "a": pa, "b": pb, "same_choice": same_structure})
    return {
        "rows": [m["rows"] for m in manifests],
        "created_utc": [m["created_utc"] for m in manifests],
        "auc": aucs,
        "max_abs_auc_difference": max(abs(r["difference"]) for r in aucs),
        "choices": choices,
        "primary": [sa["primary"], sb["primary"]],
        "pullback_trigger": [sa["pullback"]["chosen_trigger"], sb["pullback"]["chosen_trigger"]],
    }


def markdown(c: dict) -> str:
    def p(params):
        return ", ".join(f"{k} {v:.4f}" if isinstance(v, float) else f"{k} {v}" for k, v in params.items())

    lines = [
        f"Downloads: {c['created_utc'][0]} ({c['rows'][0]['prices']:,} price rows) and {c['created_utc'][1]} "
        f"({c['rows'][1]['prices']:,} price rows). Largest validation AUC difference: {c['max_abs_auc_difference']:.4f}.",
        "",
        "| Horizon | Feature set | AUC, first | AUC, second | Difference |",
        "|---|---|---:|---:|---:|",
    ]
    lines += [
        f"| {r['horizon']} | {r['feature_set']} | {r['a']:.4f} | {r['b']:.4f} | {r['difference']:+.4f} |"
        for r in c["auc"]
    ]
    lines += ["", "| Feature set | Strategy | Chosen, first | Chosen, second | Same choice |", "|---|---|---|---|---|"]
    lines += [
        f"| {r['feature_set']} | {r['strategy']} | {p(r['a'])} | {p(r['b'])} | {'yes' if r['same_choice'] else '**no**'} |"
        for r in c["choices"]
    ]
    pa, pb = c["primary"]
    lines += [
        "",
        f"Strategy carried to the test period: {pa['strategy']} on {pa['feature_set']} (validation Sharpe "
        f"{pa['validation_sharpe']:.2f}) and {pb['strategy']} on {pb['feature_set']} ({pb['validation_sharpe']:.2f}); "
        f"pullback trigger {c['pullback_trigger'][0]} and {c['pullback_trigger'][1]}.",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("store_a", type=Path)
    parser.add_argument("store_b", type=Path)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)
    c = compare(args.store_a, args.store_b)
    print(markdown(c) if args.markdown else json.dumps(c, indent=2))


if __name__ == "__main__":
    main()
