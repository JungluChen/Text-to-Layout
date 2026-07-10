"""Quantum Metal interoperability boundary."""

from __future__ import annotations

from textlayout.external.geometry_compare import GeometryComparison


def empty_comparison() -> GeometryComparison:
    """Return a non-passing placeholder until a real external geometry is supplied."""
    return GeometryComparison(
        tool="Quantum Metal / Qiskit Metal",
        gds_hash_match=False,
        layer_map_match=False,
        ports_match=False,
        bounding_box_match=False,
        connectivity_match=False,
        extracted_quantity_match=False,
        details={"reason": "no external geometry supplied"},
    )
