"""Solver Agreement Engine.

Never trust a single solver. This module cross-checks a physical quantity
(frequency, Q, impedance, capacitance, ...) computed by two or more independent
sources -- ideally at least two open EM solvers plus an analytical model -- and
emits a deterministic confidence score with an explicit PASS/FAIL threshold.

The confidence model is intentionally simple and monotone:

    reference          = median of the reported values
    max_relative_error = max |value - reference| / |reference|
    passed             = max_relative_error <= tolerance
    confidence_pct     = 100 * (1 - min(1, max_relative_error / (2 * tolerance)))

so confidence is 100% at perfect agreement, 50% at exactly the tolerance
boundary (the worst still-passing case), and 0% at twice the tolerance. A single
source can never produce a non-zero confidence: agreement requires corroboration.
"""

from __future__ import annotations

from statistics import median
from typing import Any


def cross_validate(
    sources: list[dict[str, Any]],
    *,
    quantity: str = "value",
    tolerance_pct: float = 5.0,
) -> dict[str, Any]:
    """Cross-validate one quantity across independent solver/theory sources.

    ``sources`` is a list of ``{"source": str, "value": float}`` entries (extra
    keys are ignored). Entries whose value is ``None`` are treated as a source
    that did not produce a result and are excluded from the comparison.
    """
    if tolerance_pct <= 0.0:
        raise ValueError(f"tolerance_pct must be positive, got {tolerance_pct}")

    usable = [s for s in sources if s.get("value") is not None]
    values = [float(s["value"]) for s in usable]

    if len(usable) < 2:
        return {
            "schema": "text-to-gds.solver-agreement.v1",
            "quantity": quantity,
            "tolerance_pct": tolerance_pct,
            "n_sources": len(usable),
            "sources": [
                {"source": str(s.get("source", "unknown")), "value": s.get("value")}
                for s in usable
            ],
            "reference_value": values[0] if values else None,
            "max_relative_error_pct": None,
            "passed": False,
            "confidence_pct": 0.0,
            "verdict": "insufficient_sources",
            "reason": "agreement requires at least two independent sources; never trust one solver",
        }

    reference = float(median(values))
    if reference == 0.0:
        # Fall back to mean magnitude to avoid division by zero.
        reference = sum(abs(v) for v in values) / len(values) or 1.0

    tolerance = tolerance_pct / 100.0
    detailed = []
    max_rel = 0.0
    for s in usable:
        value = float(s["value"])
        rel = abs(value - reference) / abs(reference)
        max_rel = max(max_rel, rel)
        detailed.append(
            {
                "source": str(s.get("source", "unknown")),
                "value": value,
                "relative_error_pct": round(rel * 100.0, 4),
            }
        )

    passed = max_rel <= tolerance
    confidence = 100.0 * (1.0 - min(1.0, max_rel / (2.0 * tolerance)))
    return {
        "schema": "text-to-gds.solver-agreement.v1",
        "quantity": quantity,
        "tolerance_pct": tolerance_pct,
        "n_sources": len(usable),
        "sources": detailed,
        "reference_value": reference,
        "max_relative_error_pct": round(max_rel * 100.0, 4),
        "passed": passed,
        "confidence_pct": round(confidence, 1),
        "verdict": "agree" if passed else "disagree",
    }
