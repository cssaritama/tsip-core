import numpy as np
import pytest

from tsip.evidence import (
    EvidenceCard,
    EvidenceItem,
    benjamini_hochberg,
    circular_block_indices,
    evaluate,
    finalize_grades,
)
from tsip.evidence.grading import grade_base_rate, grade_edge


def test_block_indices_are_contiguous_and_reproducible():
    rng = np.random.default_rng(1)
    idx = circular_block_indices(10, 4, rng)
    assert len(idx) == 10
    assert ((idx[1:4] - idx[0:3]) % 10 == 1).all()
    assert (circular_block_indices(10, 4, np.random.default_rng(1)) == idx).all()


def test_benjamini_hochberg_matches_reference_values():
    p = np.array([0.01, 0.04, 0.03, 0.20, np.nan])
    q = benjamini_hochberg(p)
    assert q[:4] == pytest.approx([0.04, 0.0533333, 0.0533333, 0.20], rel=1e-4)
    assert np.isnan(q[4])


def test_evaluate_detects_a_planted_effect_and_not_noise():
    rng = np.random.default_rng(0)
    n = 2000
    g = rng.integers(0, 2, n)
    r = rng.normal(0, 1, n) + 0.3 * g

    def stat(u):
        return np.array([u["r"][u["g"] == 1].mean() - u["r"][u["g"] == 0].mean()])

    hit = evaluate({"r": r, "g": g}, stat, block=10, reps=400, seed=1)
    assert hit["p_value"][0] < 0.01 and hit["ci_low"][0] > 0
    noise = evaluate({"r": rng.normal(0, 1, n), "g": g}, stat, block=10, reps=400, seed=1)
    assert noise["ci_low"][0] < 0 < noise["ci_high"][0]


def _item(**kw):
    base = dict(
        label="x",
        estimate=1.0,
        ci_low=0.5,
        ci_high=1.5,
        n=500,
        discovery=1.0,
        holdout=1.0,
        holdout_p=0.01,
        p_value=0.001,
        q_value=0.01,
    )
    base.update(kw)
    return EvidenceItem(**base)


def test_edge_grades_follow_published_rules():
    assert grade_edge(_item()) == "A"
    assert grade_edge(_item(n=150)) == "B"
    assert grade_edge(_item(q_value=0.08, holdout_p=0.5)) == "B"
    assert grade_edge(_item(q_value=0.3, p_value=0.03)) == "C"
    assert grade_edge(_item(q_value=0.6, p_value=0.4)) == "D"
    assert grade_edge(_item(holdout=-0.5, p_value=0.05)) == "F"
    assert grade_edge(_item(n=10)) == "N/A"


def test_base_rate_reliability():
    assert grade_base_rate(_item(estimate=50, ci_low=48, ci_high=52, discovery=50, holdout=51)) == "A"
    assert grade_base_rate(_item(estimate=50, ci_low=47, ci_high=53, discovery=50, holdout=55)) == "B"
    assert grade_base_rate(_item(estimate=50, ci_low=40, ci_high=60, discovery=50, holdout=50)) == "D"


def test_finalize_applies_fdr_across_cards():
    cards = []
    for k, p in enumerate([0.001, 0.04, 0.5]):
        cards.append(
            EvidenceCard(
                id=f"c{k}",
                instrument="X",
                family="calendar",
                kind="edge",
                title="t",
                question="q",
                unit="bps",
                method="m",
                control="c",
                n_label="days",
                period={},
                items=[_item(p_value=p, q_value=None, holdout_p=0.01)],
            )
        )
    meta = finalize_grades(cards)
    assert meta["edge_tests"] == 3
    assert cards[0].items[0].q_value == pytest.approx(0.003)
    assert cards[1].items[0].q_value == pytest.approx(0.06)
    assert [c.grade for c in cards] == ["A", "B", "D"]
