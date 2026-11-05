import importlib.util
import math
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("test_budget", Path(__file__).parents[1] / "tools" / "test_budget.py")
tb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tb)


def test_mde_matches_the_normal_approximation():
    # z(1 - 0.05 / 372) + z(0.8) = 3.643 + 0.842; sqrt((2/3) / (1/3 * 418)) = 0.0692
    assert tb.mde(418, 1 / 3, 186) == pytest.approx(0.310, abs=0.002)
    assert tb.mde(418, 1 / 3, 1) < tb.mde(418, 1 / 3, 186) < tb.mde(418, 1 / 3, 1000)
    assert tb.mde(2000, 0.5, 186) < tb.mde(500, 0.5, 186)
    assert math.isinf(tb.mde(0, 0.5, 1)) and math.isinf(tb.mde(100, 1.0, 1))


def test_grade_a_needs_200_units_in_the_condition():
    assert tb.grade_a_mde(130, 0.5, 150) is None  # months of an ETF: no condition can reach A
    assert tb.grade_a_mde(563, 1 / 3, 150) is None  # weeks split in thirds: 188 each
    value = tb.grade_a_mde(563, 0.5, 150)
    assert value == pytest.approx(max(tb.mde(563, 0.5, 150), tb.holdout_mde(563, 0.5)))
    assert tb.max_cells(2727) == 13 and tb.max_cells(199) == 0


def test_periods_and_ledger_from_a_report():
    assert tb.periods("2016-01-04", "2026-11-04", 2727, "session") == 2727
    assert tb.periods("2016-01-01", "2026-11-04", 0, "quarter") == 43
    assert tb.periods("2016-01-01", "2026-11-04", 0, "month") == 130
    report = {
        "instruments": [
            {
                "code": "SPY",
                "grading": {"edge_tests": 3},
                "coverage": {"daily": {"start": "2016-01-04", "end": "2026-11-04", "rows": 2727}},
                "sections": [
                    {"cards": [{"family": "plan", "items": [{"grade": "D"}, {"grade": "N/A"}]}]},
                    {"cards": [{"family": "levels", "items": [{"grade": "A"}]}]},
                ],
            }
        ]
    }
    (entry,) = tb.ledger(report)
    assert entry["edge_tests"] == 3 and entry["families"] == {"plan": 2, "levels": 1}
    assert entry["grades"] == {"D": 1, "N/A": 1, "A": 1}
    text = tb.render(report, markdown=True)
    assert "| month | 130 | 0 | not reachable |" in text
