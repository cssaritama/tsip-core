"""Evidence engine: dependence-aware resampling, multiple-testing control and grading."""

from tsip.evidence.bootstrap import circular_block_indices, evaluate
from tsip.evidence.card import EvidenceCard, EvidenceItem
from tsip.evidence.grading import GRADE_LABELS, finalize_grades
from tsip.evidence.inference import benjamini_hochberg

__all__ = [
    "GRADE_LABELS",
    "EvidenceCard",
    "EvidenceItem",
    "benjamini_hochberg",
    "circular_block_indices",
    "evaluate",
    "finalize_grades",
]
