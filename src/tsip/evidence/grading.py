"""Grading rules. These are the published, versioned rules of the report.

Edge items (effect against a control or null), after Benjamini–Hochberg
adjustment across every edge item in the instrument report:

* **A – Strong**: q ≤ 0.05, the most recent 30% of the sample (holdout) has
  the same sign with holdout p ≤ 0.10, and at least 200 units.
* **B – Moderate**: q ≤ 0.10 and discovery and holdout have the same sign.
* **C – Weak**: nominal p ≤ 0.05 and the holdout has the same sign, but the
  result does not survive multiple-testing control.
* **D – Inconclusive**: not significant, holdout not contradicting.
* **F – Contradicted**: discovery and holdout disagree in sign while the
  discovery estimate is nominally significant (p ≤ 0.10 in the full sample).
* **N/A – Insufficient sample**: fewer than 30 units.

Base-rate items (a frequency, no null), graded on reliability:

* **A** – 95% interval half-width ≤ 2.5 pp and |holdout − discovery| ≤ 3 pp
* **B** – half-width ≤ 4 pp and drift ≤ 6 pp
* **C** – half-width ≤ 7.5 pp and drift ≤ 10 pp
* **D** – anything wider or less stable (still at least 30 units)

Version 2026.10.1: proportion intervals are never narrower than the Wilson score
interval, so an all-or-nothing sample (for example 0 of 38) cannot look precise.
"""

from __future__ import annotations

import math

import numpy as np

from tsip.evidence.card import EvidenceCard, EvidenceItem
from tsip.evidence.inference import benjamini_hochberg

RULES_VERSION = "2026.10.1"
MIN_UNITS = 30
GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4, "N/A": 5}
GRADE_LABELS = {
    "edge": {
        "A": "Strong evidence",
        "B": "Moderate evidence",
        "C": "Weak evidence",
        "D": "Inconclusive",
        "F": "Contradicted out of sample",
        "N/A": "Insufficient sample",
    },
    "base_rate": {
        "A": "High reliability",
        "B": "Good reliability",
        "C": "Fair reliability",
        "D": "Low reliability",
        "N/A": "Insufficient sample",
    },
}


def _same_sign(a: float | None, b: float | None) -> bool:
    if a is None or b is None or not (math.isfinite(a) and math.isfinite(b)):
        return False
    return (a > 0 and b > 0) or (a < 0 and b < 0)


def grade_edge(item: EvidenceItem) -> str:
    if item.n < MIN_UNITS or item.p_value is None or not math.isfinite(item.p_value):
        return "N/A"
    p, q = item.p_value, item.q_value if item.q_value is not None else 1.0
    hold_p = item.holdout_p if item.holdout_p is not None and math.isfinite(item.holdout_p) else 1.0
    agree = _same_sign(item.discovery, item.holdout)
    if not agree and p <= 0.10 and abs(item.holdout or 0) > 0:
        return "F"
    if q <= 0.05 and agree and _same_sign(item.estimate, item.holdout) and hold_p <= 0.10 and item.n >= 200:
        return "A"
    if q <= 0.10 and agree:
        return "B"
    if p <= 0.05 and agree:
        return "C"
    return "D"


def grade_base_rate(item: EvidenceItem) -> str:
    if item.n < MIN_UNITS:
        return "N/A"
    half_width = (item.ci_high - item.ci_low) / 2
    drift = abs((item.holdout or 0) - (item.discovery or 0))
    if not (math.isfinite(half_width) and math.isfinite(drift)):
        return "D"
    if half_width <= 2.5 and drift <= 3:
        return "A"
    if half_width <= 4 and drift <= 6:
        return "B"
    if half_width <= 7.5 and drift <= 10:
        return "C"
    return "D"


def finalize_grades(cards: list[EvidenceCard]) -> dict:
    """Apply FDR control across every edge item, then grade items and cards."""
    edge_items = [item for card in cards if card.kind == "edge" for item in card.items]
    q_values = benjamini_hochberg(np.array([i.p_value if i.p_value is not None else np.nan for i in edge_items]))
    for item, q in zip(edge_items, q_values, strict=True):
        item.q_value = None if not math.isfinite(q) else float(q)
    for card in cards:
        labels = GRADE_LABELS[card.kind]
        for item in card.items:
            item.grade = grade_edge(item) if card.kind == "edge" else grade_base_rate(item)
            item.grade_label = labels[item.grade]
        if not card.items:
            card.grade = "N/A"
        elif card.kind == "base_rate":
            # Base-rate cards lead with their first two items; the card carries the weaker of the two.
            card.grade = max((i.grade for i in card.items[:2]), key=lambda g: GRADE_ORDER[g])
        else:
            card.grade = min(card.items, key=lambda i: (GRADE_ORDER[i.grade], -abs(i.estimate or 0))).grade
        card.grade_label = labels[card.grade]
    return {"rules_version": RULES_VERSION, "edge_tests": len(edge_items), "fdr_method": "Benjamini-Hochberg"}
