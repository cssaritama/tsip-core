"""Specification 0028, T4: the test period is read once, by one logged command; verdict and statistics."""

import json

import numpy as np
import pandas as pd
import pytest

from tsip.capstone import data
from tsip.capstone import evaluate as E

FP = {"prices": "a", "fred": "b"}


def test_verdict_needs_every_condition():
    assert E.verdict(0.03, 0.005, -0.01, -0.02)["supported"]
    assert not E.verdict(0.019, 0.005, -0.01, -0.02)["supported"]  # lift below 0.02
    assert not E.verdict(0.03, -0.001, -0.01, -0.02)["supported"]  # interval touches zero
    assert not E.verdict(0.03, 0.005, 0.001, -0.02)["supported"]  # permuted control shows a lift
    assert not E.verdict(0.03, 0.005, -0.01, 0.002)["supported"]  # random walk shows a lift


def test_lift_interval_is_zero_for_identical_scores_and_positive_for_a_better_one():
    rng = np.random.default_rng(0)
    n = 600
    y = rng.integers(0, 2, n)
    frame = pd.DataFrame(
        {
            "date": np.repeat(pd.date_range("2024-01-01", periods=n // 3), 3),
            "y": y,
            "noise": rng.random(n),
            "good": y * 0.6 + rng.random(n),
        }
    )
    frame["same"] = frame["noise"]
    lift, ci = E.lift_interval(frame, "y", "same", "noise", reps=100)
    assert lift == 0 and ci == [0, 0]
    lift, ci = E.lift_interval(frame, "y", "good", "noise", reps=100)
    assert lift > 0.2 and ci[0] > 0


def test_a_run_is_refused_from_uncommitted_code(tmp_path):
    with pytest.raises(SystemExit):
        E.open_run(tmp_path / "log.json", commit="abc", dirty=True, fingerprint=FP, kind="registered", rerun=None)
    assert not (tmp_path / "log.json").exists()


def test_the_registered_run_happens_once_unless_a_reason_is_logged(tmp_path):
    log = tmp_path / "log.json"
    E.open_run(log, commit="abc", dirty=False, fingerprint=FP, kind="registered", rerun=None)
    assert json.loads(log.read_text())[0]["status"] == "started"  # logged before any test row is read
    with pytest.raises(SystemExit):
        E.open_run(log, commit="abc", dirty=False, fingerprint=FP, kind="registered", rerun=None)
    runs = E.open_run(log, commit="def", dirty=False, fingerprint=FP, kind="registered", rerun="data corrected")
    assert [r["rerun_reason"] for r in runs] == [None, "data corrected"]


def test_phase_two_continues_only_the_same_run_with_the_same_code(tmp_path):
    log = tmp_path / "log.json"
    with pytest.raises(SystemExit):
        E.continue_run(log, commit="abc", dirty=False)  # no phase 1 yet
    runs = E.open_run(log, commit="abc", dirty=False, fingerprint=FP, kind="registered", rerun=None)
    with pytest.raises(SystemExit):
        E.continue_run(log, commit="abc", dirty=False)  # phase 1 not finished
    E.mark_run(log, runs, "models_done", tmp_path / "m.json")
    with pytest.raises(SystemExit):
        E.continue_run(log, commit="other", dirty=False)  # different code
    assert E.continue_run(log, commit="abc", dirty=False)[-1]["status"] == "models_done"


def _store(path, seed=1, start="2017-01-01", end="2024-12-31"):
    rng = np.random.default_rng(seed)
    rows = []
    for t in dict.fromkeys([*data.UNIVERSE, *data.REFERENCES]):
        dates = pd.date_range(start, end, freq="D")
        if "USD" not in t:
            dates = dates[dates.dayofweek < 5]
        c = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, len(dates))))
        w = np.abs(rng.normal(0, 0.006, len(dates)))
        o = c * np.exp(rng.normal(0, 0.003, len(dates)))
        rows.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": t,
                    "open": o,
                    "high": np.maximum(o, c) * np.exp(w),
                    "low": np.minimum(o, c) * np.exp(-w),
                    "close": c,
                    "adj_close": c,
                    "volume": 1e6,
                }
            )
        )
    daily = pd.date_range(start, end, freq="D")
    monthly = pd.date_range(start, end, freq="MS")
    fred = pd.concat(
        [pd.DataFrame({"date": daily, "series": s, "value": v}) for s, v in (("DTB3", 4.0), ("DGS10", 4.2))]
        + [
            pd.DataFrame({"date": monthly, "series": s, "value": v})
            for s, v in (("FEDFUNDS", 4.0), ("CPIAUCSL", 300.0))
        ],
        ignore_index=True,
    )
    data.save(path, pd.concat(rows, ignore_index=True), fred, source="synthetic")


def test_both_phases_run_end_to_end_on_synthetic_data(tmp_path, monkeypatch):
    store = tmp_path / "store"
    _store(store)
    monkeypatch.setattr(E, "RUN_LOG", tmp_path / "runs.json")
    monkeypatch.setattr(E, "REPS", 50)
    monkeypatch.setattr(E, "git_state", lambda repo=None: ("abc123", False))
    args = ["--store", str(store), "--results", str(tmp_path / "results")]
    E.main(args)
    E.main([*args, "--strategies"])
    runs = json.loads((tmp_path / "runs.json").read_text())
    assert [r["status"] for r in runs] == ["completed"] and runs[0]["commit"] == "abc123"
    summary = json.loads((tmp_path / "results" / "test_h5.json").read_text())
    assert summary["strategies"]["LECTURE+TIME+SPACE"]["period"][0] >= "2024-01-01"
    assert "supported" in summary["registered"]["verdict"]
    assert "H-2026-016" in E.markdown(summary)
    with pytest.raises(SystemExit):
        E.main(args)  # a second registered run is refused
