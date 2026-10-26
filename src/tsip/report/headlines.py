"""Plain-language headline for each card, written after grading.

The headline always refers to one item, recorded in ``card.primary`` so the
page can highlight the same numbers the sentence quotes.
"""

from __future__ import annotations

from tsip.evidence.card import EvidenceCard
from tsip.evidence.grading import GRADE_ORDER


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "n/a"
    if unit == "bps":
        return f"{value:+.1f} bps"
    if unit == "pp":
        return f"{value:+.1f} pp"
    return f"{value:+.2f}%"


def _best_index(card: EvidenceCard) -> int:
    return min(
        range(len(card.items)), key=lambda k: (GRADE_ORDER[card.items[k].grade], -abs(card.items[k].estimate or 0))
    )


def headline(card: EvidenceCard) -> str:
    if not card.items:
        return "No data."
    if all(i.grade == "N/A" for i in card.items):
        card.primary = 0
        return "Not enough observations to grade this question yet."
    if card.kind == "base_rate":
        card.primary = 0
        a, b = card.items[0], card.items[1]
        return (
            f"{a.estimate:.0f}% of {card.n_label} trade above the prior high and {b.estimate:.0f}% below the prior low "
            f"(reliability {card.grade})."
        )
    k = _best_index(card)
    best = card.items[k]
    card.primary = k
    grade = f"{best.grade_label.lower()}, {best.grade}"
    if card.family == "paths":
        x = best.extra
        return (
            f"Within {best.label}: naive {x['naive_upper_first_pct']:.0f}% reach the high side first; geometry alone "
            f"predicts {x['geometry_expected_pct']:.0f}%, so the levels add {_fmt(best.estimate, 'pp')} ({grade})."
        )
    if card.family == "entries":
        card.primary = 0
        first = card.items[0]
        fill = first.extra.get("fill_rate_pct", 0.0)
        return (
            f"{_fmt(first.estimate, '%')} per purchase versus plain DCA; the limit fills in {fill:.0f}% of months "
            f"({first.grade_label.lower()}, {first.grade})."
        )
    contrast = card.contrast or "the control"
    if best.grade in {"A", "B", "C"}:
        return f"{best.label}: {_fmt(best.estimate, card.unit)} versus {contrast} ({grade})."
    return f"No reliable effect. Largest deviation: {best.label}, {_fmt(best.estimate, card.unit)} versus {contrast} ({grade})."
