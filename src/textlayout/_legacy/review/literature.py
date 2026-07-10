"""Literature reviewer: compare generated physical parameters with cited devices."""

from __future__ import annotations

from typing import Any

from textlayout._legacy.review.base import finding, review_result

_AGENT = "literature"


def review_literature(evidence: dict[str, Any]) -> dict[str, Any]:
    comparison = evidence.get("literature_comparison") or {}
    findings: list[dict[str, Any]] = []
    references = comparison.get("references") or []
    rows = comparison.get("comparisons") or []

    # Literature is required only when a simulation result is present in the evidence
    # (i.e. this is a research-ready device, not a bare layout check).
    has_simulation = bool(evidence.get("simulation"))
    if not references and has_simulation:
        findings.append(
            finding(
                _AGENT,
                "error",
                "No literature reference is attached to the design.",
                "Select at least one comparable published device and record its citation.",
            )
        )
    if not rows and has_simulation:
        findings.append(
            finding(
                _AGENT,
                "error",
                "No generated-to-literature parameter comparison is available.",
                "Compare frequency, impedance, Q, junction parameters, gain, and bandwidth where applicable.",
            )
        )
    tolerance = float(comparison.get("tolerance_fraction", 0.2))
    for row in rows:
        name = str(row.get("parameter", "parameter"))
        generated = row.get("generated")
        reference = row.get("reference")
        if generated is None or reference is None:
            findings.append(
                finding(_AGENT, "error", f"Literature comparison for {name} is incomplete.", "Provide both values and units.")
            )
            continue
        reference_value = float(reference)
        relative_error = (
            abs(float(generated) - reference_value) / abs(reference_value)
            if reference_value != 0.0
            else float("inf")
        )
        if relative_error > tolerance:
            findings.append(
                finding(
                    _AGENT,
                    "warning",
                    f"{name} differs from the cited device by {100.0 * relative_error:.1f}%.",
                    "Document why the design departs from the reference or revise the synthesis.",
                )
            )
    result = review_result(_AGENT, findings)
    result["reference_count"] = len(references)
    result["comparison_count"] = len(rows)
    return result
