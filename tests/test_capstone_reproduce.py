"""Reproducibility report: identical stores agree; a changed choice is flagged."""

import copy
import json

from tsip.capstone import models as M
from tsip.capstone import reproduce as R


def _store(path, auc=0.55, k=5):
    (path / "results").mkdir(parents=True)
    (path / "manifest.json").write_text(json.dumps({"rows": {"prices": 10}, "created_utc": "2026-11-10T00:00:00"}))
    for h in (5, 20):
        (path / "results" / f"h{h}").mkdir()
        for fs in M.FEATURE_SETS:
            (path / "results" / f"h{h}" / f"logistic__{fs}.json").write_text(json.dumps({"validation_auc": auc}))
    chosen = {
        "sim1": {"params": {"quantile": 0.5, "threshold": 0.45}},
        "sim2": {"params": {"quantile": 0.5, "threshold": 0.45, "k": k}},
        "sim3": {"params": {"threshold": 0.45, "stop_atr": 2.0}},
        "sim4": {"params": {"quantile": 0.7, "upper": 0.49, "lower": 0.38}},
    }
    sim = {
        "by_feature_set": {"LECTURE": {"chosen": copy.deepcopy(chosen)}},
        "primary": {"strategy": "sim3", "feature_set": "LECTURE", "validation_sharpe": 1.0},
        "pullback": {"chosen_trigger": "prior_month_low"},
    }
    (path / "results" / "simulation_h5.json").write_text(json.dumps(sim))


def test_identical_stores_agree(tmp_path):
    _store(tmp_path / "a")
    _store(tmp_path / "b")
    c = R.compare(tmp_path / "a", tmp_path / "b")
    assert c["max_abs_auc_difference"] == 0 and all(r["same_choice"] for r in c["choices"])


def test_a_changed_choice_is_flagged(tmp_path):
    _store(tmp_path / "a")
    _store(tmp_path / "b", auc=0.56, k=3)
    c = R.compare(tmp_path / "a", tmp_path / "b")
    assert abs(c["max_abs_auc_difference"] - 0.01) < 1e-9
    assert [r["strategy"] for r in c["choices"] if not r["same_choice"]] == ["sim2"]
    assert "**no**" in R.markdown(c)
