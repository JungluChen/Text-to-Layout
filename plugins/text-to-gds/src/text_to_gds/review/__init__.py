"""Rule-based AI review committee.

Deterministic reviewers that inspect a generated layout's evidence (sidecar,
simulation, DRC) and emit pass/fail findings. No LLM/API/network: every verdict
is a reproducible function of the inputs, matching the project's local-first,
offline guarantee.
"""

from text_to_gds.review.committee import (
    REVIEWERS,
    review_committee,
    review_committee_enhanced,
)
from text_to_gds.review.fabrication import review_fabrication
from text_to_gds.review.final_reviewer import review_final
from text_to_gds.review.layout import review_layout_agent
from text_to_gds.review.layout_critic import review_layout_critic
from text_to_gds.review.layout_design_review import review_layout_design
from text_to_gds.review.measurement import review_measurement
from text_to_gds.review.microwave import review_microwave
from text_to_gds.review.physics import review_physics
from text_to_gds.review.reviewer import review_reviewer
from text_to_gds.review.solver import review_solver
from text_to_gds.review.solver_evidence_agent import review_solver_evidence

__all__ = [
    "REVIEWERS",
    "review_committee",
    "review_committee_enhanced",
    "review_fabrication",
    "review_final",
    "review_layout_agent",
    "review_layout_critic",
    "review_layout_design",
    "review_measurement",
    "review_microwave",
    "review_physics",
    "review_reviewer",
    "review_solver",
    "review_solver_evidence",
]
