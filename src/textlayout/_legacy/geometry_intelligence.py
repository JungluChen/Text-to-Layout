"""Geometry intelligence: extract rich geometric features from GDS layout.

Analyzes the physical geometry of a generated layout and produces a structured
feature set for design review, topology matching, and literature comparison.
"""

from __future__ import annotations

import math
from typing import Any


def _centroid(bbox: list[float]) -> tuple[float, float]:
    if len(bbox) < 4:
        return (0.0, 0.0)
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _area(bbox: list[float]) -> float:
    if len(bbox) < 4:
        return 0.0
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _bbox_width(bbox: list[float]) -> float:
    return max(0.0, bbox[2] - bbox[0])


def _bbox_height(bbox: list[float]) -> float:
    return max(0.0, bbox[3] - bbox[1])


def analyze_geometry(
    gds_path: str,
    sidecar: dict[str, Any] | None = None,
    physics_graph: dict[str, Any] | None = None,
    geometry_extraction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract geometric features from a GDS layout.

    Parameters
    ----------
    gds_path:
        Path to the GDS file.
    sidecar:
        Optional sidecar metadata.
    physics_graph:
        Optional output of extract_physics_graph().
    geometry_extraction:
        Optional output of extract_geometry().

    Returns
    -------
    dict with geometry_features.json schema.
    """
    sidecar = sidecar or {}
    info = sidecar.get("info") or {}
    ports = sidecar.get("ports") or []

    features: dict[str, Any] = {
        "schema": "text-to-gds.geometry-features.v1",
        "source_gds": str(gds_path),
        "capacitor_paddles": _analyze_capacitor_paddles(physics_graph, info),
        "current_bottlenecks": _analyze_current_bottlenecks(physics_graph, geometry_extraction),
        "ground_pocket": _analyze_ground_pocket(physics_graph, info),
        "airbridge_span": _analyze_airbridge_span(geometry_extraction),
        "flux_coupling": _analyze_flux_coupling(physics_graph, ports),
        "cpw_bends": _analyze_cpw_bends(geometry_extraction),
        "cpw_discontinuities": _analyze_cpw_discontinuities(geometry_extraction),
        "launch_transitions": _analyze_launch_transitions(ports, info),
        "stubs": _analyze_stubs(geometry_extraction),
        "tapers": _analyze_tapers(geometry_extraction),
        "corner_types": _analyze_corner_types(geometry_extraction),
        "critical_dimensions": _extract_critical_dimensions(physics_graph, info),
        "symmetry_analysis": _analyze_symmetry(physics_graph),
        "overall_area_um2": _compute_overall_area(physics_graph),
    }

    return features


def _analyze_capacitor_paddles(
    physics_graph: dict[str, Any] | None,
    info: dict[str, Any],
) -> dict[str, Any]:
    """Analyze capacitor paddle geometry."""
    paddles: list[dict[str, Any]] = []

    if physics_graph:
        for node in physics_graph.get("nodes", []):
            if node.get("type") == "capacitor":
                geom = node.get("geometry", {})
                params = node.get("physics_parameters", {})
                bbox = geom.get("bbox_um", [0, 0, 0, 0])
                paddles.append({
                    "name": node.get("name", ""),
                    "bbox_um": bbox,
                    "area_um2": _area(bbox),
                    "width_um": _bbox_width(bbox),
                    "height_um": _bbox_height(bbox),
                    "finger_count": params.get("finger_count", {}).get("value")
                    if isinstance(params.get("finger_count"), dict) else None,
                    "capacitance_f": params.get("capacitance", {}).get("value")
                    if isinstance(params.get("capacitance"), dict) else None,
                })

    if not paddles and info:
        area = float(info.get("capacitor_area_um2", 0.0) or 0.0)
        if area > 0:
            paddles.append({
                "name": "C0",
                "area_um2": area,
                "source": "sidecar",
            })

    return {
        "count": len(paddles),
        "paddles": paddles,
        "total_area_um2": sum(p.get("area_um2", 0.0) for p in paddles),
    }


def _analyze_current_bottlenecks(
    physics_graph: dict[str, Any] | None,
    geometry_extraction: dict[str, Any] | None,
) -> dict[str, Any]:
    """Identify regions of high current density."""
    bottlenecks: list[dict[str, Any]] = []

    if physics_graph:
        for node in physics_graph.get("nodes", []):
            geom = node.get("geometry", {})
            bbox = geom.get("bbox_um", [0, 0, 0, 0])
            width = min(_bbox_width(bbox), _bbox_height(bbox))
            if 0 < width < 3.0 and node.get("type") in ("conductor", "josephson_junction"):
                bottlenecks.append({
                    "name": node.get("name", ""),
                    "type": node.get("type", ""),
                    "min_width_um": round(width, 3),
                    "risk": "high" if width < 1.0 else "medium",
                    "reason": f"narrow trace ({width:.2f} um) may cause current crowding",
                })

    if geometry_extraction:
        for device in geometry_extraction.get("devices", []):
            dtype = device.get("device_type", "")
            params = device.get("parameters", {})
            if dtype == "jj":
                bridge_w = float(params.get("bridge_width_um", 0.0))
                if 0 < bridge_w < 1.0:
                    bottlenecks.append({
                        "name": "JJ_bridge",
                        "type": "josephson_junction",
                        "min_width_um": round(bridge_w, 3),
                        "risk": "high",
                        "reason": f"narrow JJ bridge ({bridge_w:.2f} um)",
                    })

    return {
        "count": len(bottlenecks),
        "bottlenecks": bottlenecks,
        "highest_risk": bottlenecks[0]["risk"] if bottlenecks else "none",
    }


def _analyze_ground_pocket(
    physics_graph: dict[str, Any] | None,
    info: dict[str, Any],
) -> dict[str, Any]:
    """Analyze ground pocket structure."""
    has_ground = False
    ground_areas: list[float] = []

    if physics_graph:
        for node in physics_graph.get("nodes", []):
            if node.get("type") == "ground":
                has_ground = True
                geom = node.get("geometry", {})
                area = geom.get("total_area_um2", geom.get("area_um2", 0.0))
                if area:
                    ground_areas.append(float(area))

    if not has_ground:
        has_ground = bool(info.get("has_ground_plane") or info.get("ground_plane"))

    return {
        "has_ground_plane": has_ground,
        "ground_polygon_count": len(ground_areas),
        "total_ground_area_um2": sum(ground_areas),
    }


def _analyze_airbridge_span(geometry_extraction: dict[str, Any] | None) -> dict[str, Any]:
    """Analyze airbridge span requirements."""
    bridges: list[dict[str, Any]] = []

    if geometry_extraction:
        for device in geometry_extraction.get("devices", []):
            if device.get("device_type") == "via":
                params = device.get("parameters", {})
                area = float(params.get("area_um2", 0.0))
                bridges.append({
                    "type": "via",
                    "area_um2": area,
                })

    return {
        "count": len(bridges),
        "bridges": bridges,
        "max_span_um": max((b.get("span_um", 0.0) for b in bridges), default=0.0),
    }


def _analyze_flux_coupling(
    physics_graph: dict[str, Any] | None,
    ports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyze flux coupling line geometry."""
    flux_ports = [
        p for p in ports
        if any(kw in str(p.get("name", "")).lower() for kw in ("flux", "bias", "coil", "dc"))
    ]

    return {
        "has_flux_line": len(flux_ports) > 0,
        "flux_port_count": len(flux_ports),
        "flux_ports": [
            {
                "name": p.get("name", ""),
                "center_um": p.get("center"),
                "width_um": p.get("width"),
            }
            for p in flux_ports
        ],
    }


def _analyze_cpw_bends(geometry_extraction: dict[str, Any] | None) -> dict[str, Any]:
    """Analyze CPW bend geometry."""
    bends: list[dict[str, Any]] = []

    if geometry_extraction:
        for device in geometry_extraction.get("devices", []):
            if device.get("device_type") in ("cpw", "tline"):
                params = device.get("parameters", {})
                length = float(params.get("length_um", 0.0))
                width = float(params.get("center_width_um", params.get("trace_width_um", 0.0)))
                if length > 0:
                    bends.append({
                        "name": device.get("device_type", ""),
                        "length_um": round(length, 2),
                        "width_um": round(width, 3),
                    })

    return {
        "count": len(bends),
        "segments": bends,
    }


def _analyze_cpw_discontinuities(geometry_extraction: dict[str, Any] | None) -> dict[str, Any]:
    """Identify CPW discontinuities."""
    discontinuities: list[dict[str, Any]] = []

    if geometry_extraction:
        devices = geometry_extraction.get("devices", [])
        cpw_devices = [d for d in devices if d.get("device_type") in ("cpw", "tline")]
        for i in range(len(cpw_devices) - 1):
            d1 = cpw_devices[i]
            d2 = cpw_devices[i + 1]
            w1 = float(d1.get("parameters", {}).get("center_width_um", 0.0))
            w2 = float(d2.get("parameters", {}).get("center_width_um", 0.0))
            if w1 > 0 and w2 > 0 and abs(w1 - w2) / max(w1, w2) > 0.1:
                discontinuities.append({
                    "type": "width_step",
                    "from_width_um": round(w1, 3),
                    "to_width_um": round(w2, 3),
                    "severity": "warning" if abs(w1 - w2) / max(w1, w2) > 0.3 else "info",
                })

    return {
        "count": len(discontinuities),
        "discontinuities": discontinuities,
    }


def _analyze_launch_transitions(
    ports: list[dict[str, Any]],
    info: dict[str, Any],
) -> dict[str, Any]:
    """Analyze launch pad transitions."""
    launches: list[dict[str, Any]] = []

    for port in ports:
        name = str(port.get("name", "")).lower()
        if any(kw in name for kw in ("rf", "in", "out", "signal", "pump", "readout", "drive", "xy")):
            launches.append({
                "name": port.get("name", ""),
                "center_um": port.get("center"),
                "width_um": port.get("width"),
                "layer": port.get("layer"),
            })

    return {
        "count": len(launches),
        "launches": launches,
        "has_gsg": any("gsg" in str(p.get("name", "")).lower() for p in launches),
    }


def _analyze_stubs(geometry_extraction: dict[str, Any] | None) -> dict[str, Any]:
    """Analyze stub resonators or open-ended traces."""
    return {"count": 0, "stubs": []}


def _analyze_tapers(geometry_extraction: dict[str, Any] | None) -> dict[str, Any]:
    """Analyze CPW tapers and transitions."""
    tapers: list[dict[str, Any]] = []

    if geometry_extraction:
        devices = geometry_extraction.get("devices", [])
        for device in devices:
            params = device.get("parameters", {})
            aspect = float(params.get("aspect_ratio", 0.0))
            if aspect > 10.0 and device.get("device_type") in ("cpw", "tline"):
                tapers.append({
                    "device": device.get("device_type", ""),
                    "aspect_ratio": round(aspect, 2),
                })

    return {
        "count": len(tapers),
        "tapers": tapers,
    }


def _analyze_corner_types(geometry_extraction: dict[str, Any] | None) -> dict[str, Any]:
    """Analyze corner types in the layout."""
    return {
        "sharp_corners": 0,
        "rounded_corners": 0,
        "mitered_corners": 0,
        "note": "corner analysis requires vertex-level polygon inspection",
    }


def _extract_critical_dimensions(
    physics_graph: dict[str, Any] | None,
    info: dict[str, Any],
) -> dict[str, Any]:
    """Extract critical dimensions from the layout."""
    dims: dict[str, Any] = {}

    if physics_graph:
        for node in physics_graph.get("nodes", []):
            geom = node.get("geometry", {})
            params = node.get("physics_parameters", {})

            if node.get("type") == "josephson_junction":
                dims["jj_area_um2"] = geom.get("area_um2")
                ic = params.get("critical_current", {})
                if isinstance(ic, dict) and "value" in ic:
                    dims["jj_ic_a"] = ic["value"]
                lj = params.get("josephson_inductance", {})
                if isinstance(lj, dict) and "value" in lj:
                    dims["jj_lj_h"] = lj["value"]

            elif node.get("type") == "transmission_line":
                w = params.get("width", {})
                g = params.get("gap", {})
                z0 = params.get("z0", {})
                if isinstance(w, dict) and "value" in w:
                    dims["cpw_width_um"] = w["value"]
                if isinstance(g, dict) and "value" in g:
                    dims["cpw_gap_um"] = g["value"]
                if isinstance(z0, dict) and "value" in z0:
                    dims["cpw_z0_ohm"] = z0["value"]

            elif node.get("type") == "capacitor":
                cap = params.get("capacitance", {})
                if isinstance(cap, dict) and "value" in cap:
                    dims["idc_capacitance_f"] = cap["value"]

    if info:
        dims.setdefault("trace_width_um", info.get("trace_width_um"))
        dims.setdefault("length_um", info.get("length_um"))

    return dims


def _analyze_symmetry(physics_graph: dict[str, Any] | None) -> dict[str, Any]:
    """Analyze layout symmetry."""
    if not physics_graph:
        return {"symmetric": None, "note": "no physics graph available"}

    positions: list[tuple[float, float]] = []
    for node in physics_graph.get("nodes", []):
        geom = node.get("geometry", {})
        bbox = geom.get("bbox_um", [0, 0, 0, 0])
        center = _centroid(bbox)
        if center != (0.0, 0.0):
            positions.append(center)

    if len(positions) < 2:
        return {"symmetric": None, "note": "insufficient data"}

    cx = sum(p[0] for p in positions) / len(positions)
    cy = sum(p[1] for p in positions) / len(positions)

    symmetric_x = all(abs(p[0] - cx) < 5.0 for p in positions)
    symmetric_y = all(abs(p[1] - cy) < 5.0 for p in positions)

    return {
        "symmetric": symmetric_x or symmetric_y,
        "x_symmetric": symmetric_x,
        "y_symmetric": symmetric_y,
        "center_um": [round(cx, 2), round(cy, 2)],
    }


def _compute_overall_area(physics_graph: dict[str, Any] | None) -> float:
    """Compute overall bounding area of all nodes."""
    if not physics_graph:
        return 0.0

    x_min = float("inf")
    y_min = float("inf")
    x_max = float("-inf")
    y_max = float("-inf")

    for node in physics_graph.get("nodes", []):
        bbox = node.get("geometry", {}).get("bbox_um", [0, 0, 0, 0])
        if len(bbox) >= 4:
            x_min = min(x_min, bbox[0])
            y_min = min(y_min, bbox[1])
            x_max = max(x_max, bbox[2])
            y_max = max(y_max, bbox[3])

    if x_min == float("inf"):
        return 0.0

    return (x_max - x_min) * (y_max - y_min)
