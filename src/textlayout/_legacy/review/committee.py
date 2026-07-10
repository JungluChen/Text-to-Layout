"""Review committee: run every reviewer and aggregate a conservative verdict."""

from __future__ import annotations

from typing import Any, Callable

from textlayout._legacy.review.fabrication import review_fabrication
from textlayout._legacy.review.final_reviewer import review_final
from textlayout._legacy.review.literature import review_literature
from textlayout._legacy.review.layout import review_layout_agent
from textlayout._legacy.review.layout_critic import review_layout_critic
from textlayout._legacy.review.layout_design_review import review_layout_design
from textlayout._legacy.review.measurement import review_measurement
from textlayout._legacy.review.microwave import review_microwave
from textlayout._legacy.review.physics import review_physics
from textlayout._legacy.review.reviewer import review_reviewer
from textlayout._legacy.review.solver import review_solver
from textlayout._legacy.review.solver_evidence_agent import review_solver_evidence

REVIEWERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "layout": review_layout_agent,
    "physics": review_physics,
    "microwave": review_microwave,
    "fabrication": review_fabrication,
    "solver": review_solver,
    "solver_evidence": review_solver_evidence,
    "measurement": review_measurement,
    "literature": review_literature,
    "layout_design_review": review_layout_design,
    "reviewer": review_reviewer,
    "final": review_final,
}


def _auto_topology(evidence: dict[str, Any]) -> dict[str, Any] | None:
    """Auto-compute topology from evidence if not already provided."""
    if "topology" in evidence and isinstance(evidence["topology"], dict):
        return evidence["topology"]
    graph = evidence.get("physics_graph")
    if not graph:
        return None
    try:
        from textlayout._legacy.topology import recognize_topology

        return recognize_topology(graph)
    except Exception:
        return None


def _auto_geometry(evidence: dict[str, Any], topology: dict[str, Any] | None) -> dict[str, Any] | None:
    """Auto-compute geometry features from evidence if not already provided."""
    if "geometry_features" in evidence and isinstance(evidence["geometry_features"], dict):
        return evidence["geometry_features"]
    gds_path = evidence.get("gds_path")
    if not gds_path:
        return None
    try:
        from textlayout._legacy.geometry_intelligence import analyze_geometry

        return analyze_geometry(
            gds_path,
            sidecar=evidence.get("sidecar"),
            physics_graph=evidence.get("physics_graph"),
        )
    except Exception:
        return None


def review_committee(evidence: dict[str, Any]) -> dict[str, Any]:
    """Run all reviewers over the evidence and aggregate.

    The headline ``score`` is the *minimum* across reviewers, so a single
    error (which costs a reviewer >=40 points) always drags the committee
    score below the 90 acceptance threshold -- the committee can never report
    >=90 while any reviewer has an error.

    Automatically computes topology and geometry features from evidence
    when not explicitly provided, and passes them to reviewers that
    benefit from engineering context.
    """
    topology = _auto_topology(evidence)
    geometry_features = _auto_geometry(evidence, topology)

    enriched_evidence = {**evidence}
    if topology is not None:
        enriched_evidence["topology"] = topology
    if geometry_features is not None:
        enriched_evidence["geometry_features"] = geometry_features

    reviews = [reviewer(enriched_evidence) for reviewer in REVIEWERS.values()]
    error_count = sum(1 for r in reviews for f in r["findings"] if f["severity"] == "error")
    warning_count = sum(1 for r in reviews for f in r["findings"] if f["severity"] == "warning")
    approved = all(r["passed"] for r in reviews)
    score = min(r["score"] for r in reviews) if reviews else 0

    result: dict[str, Any] = {
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
    if topology is not None:
        result["topology"] = {
            "detected_device": topology.get("detected_device"),
            "confidence": topology.get("confidence"),
        }
    if geometry_features is not None:
        result["geometry_features_summary"] = {
            "overall_area_um2": geometry_features.get("overall_area_um2", 0.0),
            "capacitor_paddles": geometry_features.get("capacitor_paddles", {}).get("count", 0),
            "current_bottlenecks": geometry_features.get("current_bottlenecks", {}).get("count", 0),
        }
    return result


def review_committee_enhanced(
    evidence: dict[str, Any],
    *,
    topology: dict[str, Any] | None = None,
    geometry_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enhanced review committee with topology-aware and layout critic agents.

    Runs the standard committee plus the layout critic with topology and
    geometry feature context.
    """
    # Run standard committee
    base = review_committee(evidence)

    # Run layout critic with full context
    critic = review_layout_critic(evidence, topology=topology, geometry_features=geometry_features)

    # Merge: take minimum score, union blockers
    all_reviews = base["reviews"] + critic["reviews"]
    error_count = sum(1 for r in all_reviews for f in r["findings"] if f["severity"] == "error")
    warning_count = sum(1 for r in all_reviews for f in r["findings"] if f["severity"] == "warning")
    approved = base["approved"] and critic["approved"]
    score = min(base["score"], critic["score"])

    return {
        "schema": "text-to-gds.review-committee-enhanced.v1",
        "approved": approved,
        "score": score,
        "mean_score": round(sum(r["score"] for r in all_reviews) / len(all_reviews), 1) if all_reviews else 0.0,
        "error_count": error_count,
        "warning_count": warning_count,
        "reviews": all_reviews,
        "blockers": [
            f for r in all_reviews for f in r["findings"] if f["severity"] == "error"
        ],
        "topology": topology,
        "geometry_features_summary": {
            "overall_area_um2": (geometry_features or {}).get("overall_area_um2", 0.0),
            "capacitor_paddles": (geometry_features or {}).get("capacitor_paddles", {}).get("count", 0),
            "current_bottlenecks": (geometry_features or {}).get("current_bottlenecks", {}).get("count", 0),
        } if geometry_features else None,
    }
