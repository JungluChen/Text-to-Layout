"""Rule-based AI review committee.

Deterministic reviewers that inspect a generated layout's evidence (sidecar,
simulation, DRC) and emit pass/fail findings. No LLM/API/network: every verdict
is a reproducible function of the inputs, matching the project's local-first,
offline guarantee.
"""

from text_to_gds.review.committee import REVIEWERS, review_committee
from text_to_gds.review.fabrication import review_fabrication
from text_to_gds.review.measurement import review_measurement
from text_to_gds.review.microwave import review_microwave
from text_to_gds.review.physics import review_physics

__all__ = [
    "REVIEWERS",
    "review_committee",
    "review_fabrication",
    "review_measurement",
    "review_microwave",
    "review_physics",
]
