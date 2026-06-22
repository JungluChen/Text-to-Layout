"""Review committee: run every reviewer and aggregate a conservative verdict."""

from __future__ import annotations

from typing import Any, Callable

from text_to_gds.review.fabrication import review_fabrication
from text_to_gds.review.measurement import review_measurement
from text_to_gds.review.microwave import review_microwave
from text_to_gds.review.physics import review_physics

REVIEWERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "physics": review_physics,
    "microwave": review_microwave,
    "fabrication": review_fabrication,
    "measurement": review_measurement,
}


def review_committee(evidence: dict[str, Any]) -> dict[str, Any]:
    """Run all reviewers over the evidence and aggregate.

    The headline ``score`` is the *minimum* across reviewers, so a single
    error (which costs a reviewer >=40 points) always drags the committee
    score below the 90 acceptance threshold -- the committee can never report
    >=90 while any reviewer has an error.
    """
    reviews = [reviewer(evidence) for reviewer in REVIEWERS.values()]
    error_count = sum(1 for r in reviews for f in r["findings"] if f["severity"] == "error")
    warning_count = sum(1 for r in reviews for f in r["findings"] if f["severity"] == "warning")
    approved = all(r["passed"] for r in reviews)
    score = min(r["score"] for r in reviews) if reviews else 0
    return {
        "schema": "text-to-gds.review-committee.v1",
        "approved": approved,
        "score": score,
        "mean_score": round(sum(r["score"] for r in reviews) / len(reviews), 1) if reviews else 0.0,
        "error_count": error_count,
        "warning_count": warning_count,
        "reviews": reviews,
        "blockers": [
            f for r in reviews for f in r["findings"] if f["severity"] == "error"
        ],
    }
