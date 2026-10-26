"""Evidence cards: the unit of publication.

A card answers one trader question. It holds one or more items (for example
one item per weekday). Each item carries its estimate, interval, sample size,
control, discovery/holdout values and, after report-level multiple-testing
control, a grade.

Two kinds of card exist:

* ``edge`` – an effect measured against a control or null (graded A–F).
* ``base_rate`` – a descriptive frequency (graded on reliability A–D).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np


def _clean(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return None if not math.isfinite(value) else round(value, digits)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, dict):
        return {k: _clean(v, digits) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v, digits) for v in value]
    return value


@dataclass
class EvidenceItem:
    label: str
    estimate: float
    ci_low: float
    ci_high: float
    n: int
    discovery: float
    holdout: float
    holdout_p: float | None = None
    p_value: float | None = None
    q_value: float | None = None
    baseline: float | None = None
    observed: float | None = None
    recent: float | None = None
    grade: str = "N/A"
    grade_label: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class EvidenceCard:
    id: str
    instrument: str
    family: str
    kind: str  # edge | base_rate
    title: str
    question: str
    unit: str  # pp | bps | %
    method: str
    control: str
    n_label: str
    items: list[EvidenceItem]
    period: dict
    notes: list[str] = field(default_factory=list)
    contrast: str = ""  # short form of the control, used in headlines
    primary: int | None = None  # index of the item the headline refers to
    headline: str = ""
    grade: str = "N/A"
    grade_label: str = ""
    state: dict = field(default_factory=dict)  # current-situation cards: where the latest session stands

    def to_dict(self) -> dict:
        return _clean(asdict(self))


def widen_proportions(items: list[EvidenceItem], scale: float = 100.0) -> list[EvidenceItem]:
    """Make proportion intervals at least as wide as the Wilson interval.

    A percentile bootstrap collapses to a zero-width interval when every unit has the
    same outcome (for example 0 of 38), which would overstate reliability. The reported
    interval is the union of the bootstrap and Wilson intervals.
    """
    from tsip.evidence.inference import wilson_interval

    for item in items:
        if item.n <= 0 or item.estimate is None or not math.isfinite(item.estimate):
            continue
        low, high = wilson_interval(item.estimate / scale, item.n)
        if math.isfinite(low):
            item.ci_low = min(item.ci_low, low * scale) if math.isfinite(item.ci_low) else low * scale
            item.ci_high = max(item.ci_high, high * scale) if math.isfinite(item.ci_high) else high * scale
    return items


def items_from_evaluation(
    labels: list[str],
    result: dict,
    *,
    scale: float = 1.0,
    baseline: np.ndarray | None = None,
    observed: np.ndarray | None = None,
    recent: np.ndarray | None = None,
    n_per_item: list[int] | None = None,
) -> list[EvidenceItem]:
    items = []
    for i, label in enumerate(labels):
        items.append(
            EvidenceItem(
                label=label,
                estimate=result["estimate"][i] * scale,
                ci_low=result["ci_low"][i] * scale,
                ci_high=result["ci_high"][i] * scale,
                n=int(n_per_item[i]) if n_per_item is not None else int(result["n"]),
                discovery=result["discovery"][i] * scale,
                holdout=result["holdout"][i] * scale,
                holdout_p=float(result["holdout_p"][i]),
                p_value=float(result["p_value"][i]),
                baseline=None if baseline is None else float(baseline[i]) * scale,
                observed=None if observed is None else float(observed[i]) * scale,
                recent=None if recent is None else float(recent[i]) * scale,
            )
        )
    return items
