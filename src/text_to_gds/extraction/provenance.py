"""Provenance tracking for extracted physical quantities."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

_VALID_METHODS = frozenset({"extracted", "estimated", "simulated", "measured"})
_FORBIDDEN_SOURCES = frozenset({"LLM", "llm", "guess", "estimated_by_llm", "", "unknown"})


@dataclass
class ExtractionProvenance:
    """Provenance record for one extracted value."""

    method: str
    source: str
    formula: str
    confidence: float
    unit: str
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.method not in _VALID_METHODS:
            raise ValueError(f"method must be one of {sorted(_VALID_METHODS)}, got '{self.method}'")
        if self.source in _FORBIDDEN_SOURCES:
            raise ValueError(f"source='{self.source}' is forbidden; every value must trace to a real tool")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")


def validate_provenance(prov: ExtractionProvenance) -> list[str]:
    """Return list of error messages; empty if valid."""
    errors: list[str] = []
    if prov.method not in _VALID_METHODS:
        errors.append(f"invalid method '{prov.method}'")
    if prov.source in _FORBIDDEN_SOURCES:
        errors.append(f"forbidden source '{prov.source}'")
    if not (0.0 <= prov.confidence <= 1.0):
        errors.append(f"confidence {prov.confidence} out of range [0, 1]")
    if not prov.formula:
        errors.append("formula is required")
    if not prov.unit:
        errors.append("unit is required")
    return errors


def quantity(
    value: float | int | None,
    unit: str,
    *,
    method_label: str,
    source: str,
    formula: str,
    confidence: float,
    inputs: list[str] | None = None,
    assumptions: list[str] | None = None,
    solver: str | None = None,
) -> dict[str, Any]:
    """Return a canonical extraction quantity dict, compatible with extraction.py."""
    if not (0.0 <= confidence <= 1.0):
        raise ValueError("confidence must be between 0 and 1")
    record: dict[str, Any] = {
        "value": value,
        "unit": unit,
        "method_label": method_label,
        "source": source,
        "formula": formula,
        "confidence": confidence,
    }
    if assumptions:
        record["assumptions"] = assumptions
    if inputs:
        record["inputs"] = inputs
    if solver:
        record["solver"] = solver
    return record
