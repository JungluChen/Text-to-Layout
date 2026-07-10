"""Layout reviewer: polygon validation, ports, nets, and quality mode."""

from __future__ import annotations

from typing import Any

from textlayout._legacy.review.base import finding, review_result

_AGENT = "layout"


def review_layout_agent(evidence: dict[str, Any]) -> dict[str, Any]:
    sidecar = evidence.get("sidecar") or {}
    quality = sidecar.get("quality_record") or {}
    validation = evidence.get("layout_validation") or {}
    findings: list[dict[str, Any]] = []

    if sidecar.get("layout_quality_mode") != "fabrication_real":
        findings.append(
            finding(
                _AGENT,
                "error",
                "Layout was not compiled in fabrication_real mode.",
                "Recompile with layout_quality_mode='fabrication_real'.",
            )
        )

    if quality.get("status") == "unsupported":
        findings.append(
            finding(
                _AGENT,
                "error",
                f"PCell is unsupported in fabrication_real mode: {quality.get('reason', 'no reason provided')}",
                "Use a fabrication-real PCell or return unsupported.",
            )
        )

    ports = sidecar.get("ports") or []
    if not ports:
        findings.append(finding(_AGENT, "error", "No ports are present in the sidecar.", "Add physical ports."))

    if validation:
        if validation.get("passed") is False:
            for item in validation.get("findings") or []:
                if item.get("severity") == "error":
                    findings.append(
                        finding(
                            _AGENT,
                            "error",
                            f"{item.get('check', 'layout')}: {item.get('message', 'layout validation failed')}",
                            "Fix the polygon geometry before signoff.",
                        )
                    )
        elif validation.get("passed") is not True:
            findings.append(finding(_AGENT, "warning", "Layout validation did not return a pass/fail result.", "Run validate_layout_geometry."))
    else:
        findings.append(finding(_AGENT, "warning", "No layout validation report was supplied.", "Run validate_layout_geometry."))

    return review_result(_AGENT, findings)
