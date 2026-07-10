"""Final reviewer: provenance and blocking-evidence audit."""

from __future__ import annotations

from typing import Any

from textlayout._legacy.review.base import finding, review_result

_AGENT = "reviewer"


def _source_llm_paths(value: Any, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        if value.get("source") == "LLM":
            paths.append(path)
        for key, item in value.items():
            paths.extend(_source_llm_paths(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_source_llm_paths(item, f"{path}[{index}]"))
    return paths


def review_reviewer(evidence: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    llm_paths = _source_llm_paths(evidence)
    for path in llm_paths:
        findings.append(
            finding(
                _AGENT,
                "error",
                f"Value record has source='LLM' at {path}.",
                "Replace with GDS extraction, process input, measurement, or executed solver output.",
            )
        )
    return review_result(_AGENT, findings)
