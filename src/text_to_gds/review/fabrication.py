"""Fabrication reviewer: DRC violations and a tapeout-readiness score."""

from __future__ import annotations

from typing import Any

from text_to_gds.review.base import finding, review_result

_AGENT = "fabrication"


def review_fabrication(evidence: dict[str, Any]) -> dict[str, Any]:
    drc = evidence.get("drc") or {}
    findings: list[dict[str, Any]] = []

    if not drc:
        findings.append(
            finding(_AGENT, "warning", "No DRC report provided; tapeout readiness unknown.",
                    "Run run_drc or run_process_drc and re-review.")
        )
    else:
        violations = drc.get("violations") or []
        for violation in violations:
            severity = violation.get("severity", "error")
            severity = severity if severity in {"error", "warning", "info"} else "error"
            findings.append(
                finding(_AGENT, severity,
                        f"{violation.get('rule', 'rule')}: {violation.get('message', 'violation')}",
                        "Adjust geometry (width/spacing/enclosure) to meet the rule.")
            )
        if not violations and drc.get("status") == "passed":
            findings.append(finding(_AGENT, "info", "DRC passed with no violations.", ""))

    result = review_result(_AGENT, findings)
    result["tapeout_readiness"] = result["score"]
    return result
