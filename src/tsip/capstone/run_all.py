"""The whole course-project flow in one command (specification 0028, T6), in two modes.

    python -m tsip.capstone.run_all --mode file        # from the stored copy, no network
    python -m tsip.capstone.run_all --mode download    # fresh data from yfinance and FRED first
    python -m tsip.capstone.run_all --mode update      # only the days since the last stored date

Steps: 1 data, 2 features, 3 models on the validation period (logistic regression by default;
``--all-families`` adds the decision tree, XGBoost and random forest, which take longer),
4 strategy simulations on validation. Step 5, the test period, is never re-run here: it is a single
logged read (``python -m tsip.capstone.evaluate``); its saved tables are printed when they exist.
Every step skips work whose results already exist, so the command can be repeated or resumed.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from tsip.capstone import data, evaluate, extra_sources, features, run_models, simulate


def keep_results_in_step(store: Path, results: Path) -> None:
    """Saved results belong to one data fingerprint; after new data they are set aside (never deleted)."""
    current = json.loads((store / "manifest.json").read_text())["sha256"]
    stamp = results / "data_fingerprint.json"
    if results.exists() and any(results.iterdir()):
        previous = json.loads(stamp.read_text()) if stamp.exists() else None
        if previous is not None and previous != current:
            aside = results.with_name(f"results_{previous['prices'][:12]}")
            results.rename(aside)
            print(f"data changed: earlier results moved to {aside.name}; recomputing")
    results.mkdir(parents=True, exist_ok=True)
    if not stamp.exists():
        stamp.write_text(json.dumps(current, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=["file", "download", "update"], default="file")
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--all-families", action="store_true")
    args = parser.parse_args(argv)
    store = args.store or data.default_store()
    results = store / "results"
    t0 = time.time()

    print("== 1 data")
    frame, summary = data.load(args.mode, store)
    print(json.dumps(summary, indent=2))
    keep_results_in_step(store, results)

    print("== 1b second source (Coinbase daily candles for Bitcoin and Ether; exploratory)")
    if args.mode in ("download", "update"):
        try:
            extra_sources.download(store)
        except Exception as exc:  # network or provider failure must not stop the flow
            print(f"  Coinbase not downloaded: {exc}")
    print(extra_sources.markdown(store).split("\n\n**Coinbase features")[0])

    print("== 2 features")
    feats, sets = features.build_features(frame)
    print({name: len(cols) for name, cols in sets.items()}, f"{feats.shape[1]} columns")

    print("== 3 models (validation period)")
    families = list(run_models.FAMILIES) if args.all_families else ["logistic"]
    for horizon in (5, 20):
        folder = results / f"h{horizon}"
        run_models.fit(feats, sets, horizon, families, list(run_models.M.FEATURE_SETS), folder)
        table = run_models.summarise(folder, horizon)["table"]
        for row in table:
            print(f"  h{horizon} {row['family']:14s} mean AUC {row['mean']:.3f}  lift {row['lift']:+.3f}")

    print("== 4 strategy simulations (validation period)")
    simulate.main(["--horizon", "5", "--store", str(store)])
    tables = simulate.markdown(json.loads((results / "simulation_h5.json").read_text()))
    print("\n".join(line for line in tables.splitlines() if "carried to the test period" in line))

    print("== 5 test period (single logged read; not re-run)")
    if (results / "test_h5.json").exists():
        print(evaluate.markdown(json.loads((results / "test_h5.json").read_text())).split("\n\n**Strategies")[0])
    else:
        print("  not run yet: python -m tsip.capstone.evaluate")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
