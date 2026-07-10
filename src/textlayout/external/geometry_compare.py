"""Geometry comparison records for external layout interoperability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class GeometryComparison:
    """Auditable comparison between Text-to-Layout output and an external tool."""

    tool: str
    gds_hash_match: bool
    layer_map_match: bool
    ports_match: bool
    bounding_box_match: bool
    connectivity_match: bool
    extracted_quantity_match: bool
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(
            (
                self.gds_hash_match,
                self.layer_map_match,
                self.ports_match,
                self.bounding_box_match,
                self.connectivity_match,
                self.extracted_quantity_match,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "textlayout.external.geometry-comparison.v1",
            "tool": self.tool,
            "passed": self.passed,
            "gds_hash_match": self.gds_hash_match,
            "layer_map_match": self.layer_map_match,
            "ports_match": self.ports_match,
            "bounding_box_match": self.bounding_box_match,
            "connectivity_match": self.connectivity_match,
            "extracted_quantity_match": self.extracted_quantity_match,
            "details": dict(self.details),
        }
