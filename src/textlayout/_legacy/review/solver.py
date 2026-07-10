"""Solver reviewer: real solver artifacts only."""

from __future__ import annotations

from typing import Any

from textlayout._legacy.review.base import device_text, finding, review_result

_AGENT = "solver"


def _contains_not_executed(value: Any) -> bool:
    if isinstance(value, str):
        return "NOT EXECUTED" in value.upper()
    if isinstance(value, dict):
        return any(_contains_not_executed(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_not_executed(v) for v in value)
    return False


def _has_gain_claim(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if "gain" in str(key).lower() and item not in (None, [], {}, "SKIPPED"):
                return True
            if _has_gain_claim(item):
                return True
    if isinstance(value, list):
        return any(_has_gain_claim(item) for item in value)
    return False


def review_solver(evidence: dict[str, Any]) -> dict[str, Any]:
    sim = evidence.get("simulation") or {}
    sidecar = evidence.get("sidecar") or {}
    findings: list[dict[str, Any]] = []
    text = device_text(evidence)

    if _contains_not_executed(sim):
        findings.append(
            finding(
                _AGENT,
                "error",
                "A solver panel says NOT EXECUTED and cannot count as signoff.",
                "Remove it from signoff evidence or execute the solver.",
            )
        )

    status = str(sim.get("status", "")).lower()
    adapter_status = str(sim.get("adapter_status", "")).lower()
    executed = status == "executed" or adapter_status == "executed"
    if "jpa" in text and _has_gain_claim(sim) and not executed:
        findings.append(
            finding(
                _AGENT,
                "error",
                "JPA gain is present without an executed nonlinear Josephson solver.",
                "Run JosephsonCircuits/JoSIM pump simulation or mark gain SKIPPED.",
            )
        )

    if "jpa" in text and sidecar.get("info", {}).get("jpa_gain_status") == "SKIPPED":
        findings.append(finding(_AGENT, "info", "JPA gain correctly marked SKIPPED by layout generation.", ""))

    return review_result(_AGENT, findings)
