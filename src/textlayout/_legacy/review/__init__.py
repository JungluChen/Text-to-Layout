"""Rule-based AI review committee.

Deterministic reviewers that inspect a generated layout's evidence (sidecar,
simulation, DRC) and emit pass/fail findings. No LLM/API/network: every verdict
is a reproducible function of the inputs, matching the project's local-first,
offline guarantee.
"""

from textlayout._legacy.review.committee import (
    REVIEWERS,
    review_committee,
    review_committee_enhanced,
)
from textlayout._legacy.review.fabrication import review_fabrication
from textlayout._legacy.review.final_reviewer import review_final
from textlayout._legacy.review.layout import review_layout_agent
from textlayout._legacy.review.layout_critic import review_layout_critic
from textlayout._legacy.review.layout_design_review import review_layout_design
from textlayout._legacy.review.measurement import review_measurement
from textlayout._legacy.review.microwave import review_microwave
from textlayout._legacy.review.physics import review_physics
from textlayout._legacy.review.reviewer import review_reviewer
from textlayout._legacy.review.solver import review_solver
from textlayout._legacy.review.solver_evidence_agent import review_solver_evidence

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
