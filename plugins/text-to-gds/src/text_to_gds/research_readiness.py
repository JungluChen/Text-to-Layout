"""Unified research-readiness score.

Combines the review committee's per-reviewer axes with the solver-agreement
confidence and the pre-layout feasibility verdict into one gated number. The
gate matches the TRL rule in ``validation.py``: if any axis fails, the aggregate
is capped at the worst axis score, so a single failing axis caps the total.
"""

from __future__ import annotations

from typing import Any


def research_readiness(
    committee: dict[str, Any],
    *,
    feasibility: dict[str, Any] | None = None,
    solver_agreement: dict[str, Any] | None = None,
    weights: dict[str, float] | None = None,
    threshold: int = 90,
) -> dict[str, Any]:
    """Aggregate readiness from committee + agreement + feasibility into one score."""
    axes: dict[str, dict[str, Any]] = {}
    for review in committee.get("reviews", []):
        axes[review["agent"]] = {"score": int(review["score"]), "passed": bool(review["passed"])}

    if solver_agreement is not None:
        axes["solver_agreement"] = {
            "score": int(round(float(solver_agreement.get("confidence_pct", 0.0)))),
            "passed": bool(solver_agreement.get("passed", False)),
        }
    if feasibility is not None:
        accepted = bool(feasibility.get("accepted", False))
        axes["feasibility"] = {"score": 100 if accepted else 0, "passed": accepted}

    if not axes:
        return {
            "schema": "text-to-gds.research-readiness.v1",
            "axes": {},
            "aggregate": 0.0,
            "gated": True,
            "ready": False,
            "reason": "no readiness axes available",
        }

    weights = weights or {name: 1.0 for name in axes}
    total_weight = sum(weights.get(name, 1.0) for name in axes)
    weighted = sum(weights.get(name, 1.0) * axis["score"] for name, axis in axes.items()) / total_weight

    any_fail = any(not axis["passed"] for axis in axes.values())
    worst = min(axis["score"] for axis in axes.values())
    aggregate = min(weighted, worst) if any_fail else weighted

    return {
        "schema": "text-to-gds.research-readiness.v1",
        "axes": axes,
        "aggregate": round(aggregate, 1),
        "gated": any_fail,
        "ready": (not any_fail) and aggregate >= threshold,
        "threshold": threshold,
        "model_validity": (
            "Gated aggregate: a failing axis caps the total at the worst axis score. "
            "'ready' requires every axis to pass and the aggregate to clear the threshold."
        ),
    }
