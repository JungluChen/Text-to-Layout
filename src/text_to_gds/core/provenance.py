"""Canonical provenance record for every derived physical quantity.

Every number that leaves this system must have:
  value       — the number itself
  unit        — SI or compatible unit string
  source      — tool/equation name; "LLM" is a fatal error
  equation    — the physics equation used (LaTeX or plain text)
  inputs      — dict of all input parameters (name → value with unit)
  confidence  — float in [0, 1]
  artifact    — path to output file, or None
  method      — "extracted" | "simulated" | "analytical" | "measured"
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_FORBIDDEN_SOURCES = frozenset({"LLM", "llm", "guess", "estimated_by_llm", "", "unknown"})


def _validate_source(source: str) -> None:
    if source in _FORBIDDEN_SOURCES:
        raise ValueError(
            f"source='{source}' is forbidden. "
            "Every derived quantity must trace to a real equation or solver."
        )


@dataclass(frozen=True)
class ProvenanceRecord:
    """Immutable provenance record for one derived physical quantity."""

    value: float
    unit: str
    source: str
    equation: str
    inputs: dict[str, Any]
    confidence: float
    method: str
    artifact: str | None = None

    def __post_init__(self) -> None:
        _validate_source(self.source)
        if not math.isfinite(self.value):
            raise ValueError(f"ProvenanceRecord.value must be finite, got {self.value!r}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        valid_methods = {"extracted", "simulated", "analytical", "measured"}
        if self.method not in valid_methods:
            raise ValueError(f"method must be one of {valid_methods}, got '{self.method}'")

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "equation": self.equation,
            "inputs": dict(self.inputs),
            "confidence": self.confidence,
            "method": self.method,
            "artifact": self.artifact,
        }


def provenance_record(
    value: float,
    unit: str,
    *,
    source: str,
    equation: str,
    inputs: dict[str, Any],
    confidence: float,
    method: str,
    artifact: str | Path | None = None,
) -> ProvenanceRecord:
    """Factory for ProvenanceRecord with path normalisation."""
    return ProvenanceRecord(
        value=value,
        unit=unit,
        source=source,
        equation=equation,
        inputs=dict(inputs),
        confidence=confidence,
        method=method,
        artifact=str(artifact) if artifact is not None else None,
    )


def write_provenance_bundle(
    records: dict[str, ProvenanceRecord],
    output_path: str | Path,
    *,
    schema: str = "text-to-gds.provenance.v1",
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write a dict of named ProvenanceRecords to a JSON file."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, Any] = {
        "schema": schema,
        "quantities": {name: r.to_dict() for name, r in records.items()},
    }
    if extra:
        bundle.update(extra)
    out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return out
