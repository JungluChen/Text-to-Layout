"""Geometry/process acceptance checks for Josephson junction layouts."""

from __future__ import annotations

from typing import Any

from textlayout._legacy.process import DEFAULT_PROCESS


def check_junction(
    extraction: dict[str, Any],
    *,
    critical_current_range_a: tuple[float, float] = (1e-9, 1e-3),
) -> dict[str, Any]:
    junction = extraction.get("junction", {})
    geometry = extraction.get("geometry", {})
    layers = geometry.get("layers", {})
    area = junction.get("area")
    ic = junction.get("ic")
    minimum_area = (
        DEFAULT_PROCESS.rules.min_junction_width_um
        * DEFAULT_PROCESS.rules.min_junction_height_um
    )
    checks = {
        "area": {"passed": area is not None and float(area) > minimum_area, "value_um2": area},
        "minimum_feature": {
            "passed": area is not None and float(area) > minimum_area,
            "minimum_area_um2": minimum_area,
        },
        "electrode_overlap": {
            "passed": all(name in layers and layers[name].get("area_um2", 0.0) > 0.0 for name in ("M1", "JJ", "M2")),
            "required_layers": ["M1", "JJ", "M2"],
        },
        "critical_current": {
            "passed": ic is not None and critical_current_range_a[0] <= float(ic) <= critical_current_range_a[1],
            "value_a": ic,
            "range_a": list(critical_current_range_a),
        },
    }
    failed = [name for name, result in checks.items() if not result["passed"]]
    return {
        "schema": "text-to-gds.junction-check.v1",
        "status": "PASS" if not failed else "FAIL",
        "passed": not failed,
        "checks": checks,
        "failed_checks": failed,
    }
