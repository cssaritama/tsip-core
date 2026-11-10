"""Builds notebooks/capstone.ipynb (cells only); execute it with: python -m nbconvert --to notebook --execute --inplace notebooks/capstone.ipynb"""

import nbformat as nbf

nb = nbf.v4.new_notebook()
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb.cells = [
    md("""# Do time and space improve the prediction of future returns?

Final project of the Stock Markets Analytics course, built as release 1.0.0 of `tsip-core`. This notebook runs the whole flow by calling the project's modules in `src/tsip/capstone/`; it contains no logic of its own. Every figure below is printed by that code (the written reading is in `docs/CAPSTONE.md`).

**Question.** TSIP describes where price stands in time (calendar coordinates) and in space (against the highs and lows of prior days, weeks, months and quarters). Do those features improve the out-of-sample prediction of the direction of the next 5 sessions for SPY, QQQ, GLD, Bitcoin and Ethereum, beyond the course's standard features, and does a strategy built on the predictions beat buy and hold after costs?

**Protocol.** Specification `specs/0028-time-space-features-for-return-prediction.md`; hypothesis H-2026-016 registered in `registry/hypotheses.json` before any model was trained. Training up to 2021, validation 2022–2023 (all choices), test from 2024 (read once, by a logged command).

**Modes.** `MODE = "file"` reads the stored copy (no network); `MODE = "download"` fetches fresh data from yfinance and FRED first. Data are stored outside Git in `~/tsip_capstone_data` (or `TSIP_CAPSTONE_DATA`)."""),
    code("""MODE = "file"  # or "download"

import contextlib
import io
import json
import warnings
from pathlib import Path

import pandas as pd
from IPython.display import Markdown, display

from tsip.capstone import data, evaluate, features, paper_order, run_models, simulate

store = data.default_store()
results = store / "results"
pd.set_option("display.width", 140)
# The earliest tuning folds (before 2014) have reference columns without values (Bitcoin did not trade);
# the imputer skips them and warns. The warning is expected and silenced here.
warnings.filterwarnings("ignore", message="Skipping features without any observed values")


def quiet(fn, *args):
    \"\"\"Run a module's command-line entry point without its progress lines.\"\"\"
    with contextlib.redirect_stdout(io.StringIO()):
        fn(*args)"""),
    md(
        "## 1. Data\nOne daily frame for the five instruments with reference markets (S&P 500, Nasdaq-100, DAX, gold, oil, Bitcoin, VIX) and FRED macro series, each joined only from values public at the row's close."
    ),
    code("""frame, summary = data.load(MODE, store)
{k: v for k, v in summary.items() if k != "store"}"""),
    md(
        "## 2. Features\n122 columns in named sets. No feature on a row changes when later rows are deleted (`tests/test_capstone_features.py`)."
    ),
    code("""feats, sets = features.build_features(frame)
pd.Series({name: len(cols) for name, cols in sets.items()}, name="columns")"""),
    md(
        "### Exploratory view (whole history, descriptive only)\nShare of positive 5-session periods by instrument, and by weekday (a time feature) and by position of the close in the prior week's range (a space feature)."
    ),
    code("""known = feats[feats["is_positive_growth_5d"].notna()].copy()
known["weekday"] = known["weekday"].map(dict(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])))
known["prior_week_position"] = pd.cut(known["space_week_position"], [-10, 0, 0.25, 0.5, 0.75, 1, 10],
                                      labels=["below low", "0-25%", "25-50%", "50-75%", "75-100%", "above high"])
display((known.groupby("ticker")["is_positive_growth_5d"].mean() * 100).round(1).rename("positive 5-session %"))
days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
display((known.pivot_table(index="weekday", columns="ticker", values="is_positive_growth_5d") * 100).round(1).reindex(days))
display((known.pivot_table(index="prior_week_position", columns="ticker", values="is_positive_growth_5d", observed=True) * 100).round(1))"""),
    md(
        "## 3. Models on the validation period\nLogistic regression here (seconds); `run_all --all-families` adds the decision tree, XGBoost and random forest (step 3 of `docs/CAPSTONE.md` compares all four). Pieces whose results exist are reused."
    ),
    code("""for horizon in (5, 20):
    folder = results / f"h{horizon}"
    run_models.fit(feats, sets, horizon, ["logistic"], list(run_models.M.FEATURE_SETS), folder)
    table = pd.DataFrame(run_models.summarise(folder, horizon)["table"]).set_index("family")
    display(Markdown(f"**Direction of the next {horizon} sessions, validation AUC**"))
    display(table.round(3))"""),
    md(
        "## 4. Strategy simulations on the validation period\nFour strategies on the predictions and pullback buying, with costs per side and idle cash at the 3-month bill rate. Parameters are chosen here and frozen in `registry/capstone_choices_h5.json`. Read the random-walk control in `docs/CAPSTONE.md`: on two years, random walks also reach high Sharpe ratios."
    ),
    code("""quiet(simulate.main, ["--horizon", "5", "--store", str(store)])
display(Markdown(simulate.markdown(json.loads((results / "simulation_h5.json").read_text()))))"""),
    md(
        "## 5. The test period, read once\n`python -m tsip.capstone.evaluate` refuses to run from uncommitted code or a second time; its run is logged in `registry/capstone_test_runs.json`. The notebook only displays the saved result."
    ),
    code("""summary_path = results / "test_h5.json"
walk_path = results / "test_walk_forward.json"
if summary_path.exists():
    walk = json.loads(walk_path.read_text()) if walk_path.exists() else None
    display(Markdown(evaluate.markdown(json.loads(summary_path.read_text()), walk)))
else:
    print("Not run yet: python -m tsip.capstone.evaluate, then --strategies")
print(json.dumps(json.loads(Path(evaluate.RUN_LOG).read_text()), indent=2))"""),
    md(
        "## 6. Broker example (paper trading, educational)\nThe orders strategy sim1 would place from the latest prediction, printed (dry run). `python -m tsip.capstone.paper_order --send` submits them to Alpaca's paper endpoint with simulated money. It is not a signal: the strategy did not beat buy and hold out of sample."
    ),
    code("""paper_order.main(["--notional", "1000"])"""),
    md("""## Reading

The written conclusions, the controls and the limits are in `docs/CAPSTONE.md` (steps 3 to 5). In short: the hypothesis was registered before training, every choice was made on validation, the test period was read once, and the time–space features did not improve the prediction there; the strategies that looked strong on validation did not beat buy and hold. The next study, fixed before any figure, asks a narrower question: when to buy with a fixed monthly budget (`specs/0029-when-to-buy-with-a-monthly-budget.md`)."""),
]
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, "notebooks/capstone.ipynb")
