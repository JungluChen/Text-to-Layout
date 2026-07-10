"""Geometry Intelligence Engine for semantic geometry recognition.

This module provides intelligent analysis of GDS layouts, recognizing
physical features and their engineering meaning beyond simple polygon extraction.
"""

from textlayout._legacy.geometry_intelligence.engine import GeometryIntelligenceEngine
from textlayout._legacy.geometry_intelligence.features import GeometryFeature, FeatureType
from textlayout._legacy.geometry_intelligence.recognizers import (
    recognize_cpw,
    recognize_idc,
    recognize_taper,
    recognize_launch_pad,
    recognize_bond_pad,
    recognize_squid_loop,
    recognize_josephson_junction,
    recognize_capacitor_paddle,
    recognize_resonator,
    recognize_flux_line,
    recognize_via_fence,
    recognize_airbridge,
    recognize_ground_pocket,
    recognize_ground_bridge,
    recognize_crossover,
    recognize_current_bottleneck,
    recognize_meander,
    recognize_island,
    recognize_coupler,
    recognize_feedline,
)

# Backward compatibility: export the old analyze_geometry function
# This wraps the new engine for existing tests
def analyze_geometry(
    gds_path: str,
    sidecar=None,
    physics_graph=None,
    geometry_extraction=None,
) -> dict:
    """Backward-compatible wrapper for geometry analysis.
    
    Returns the old schema format for backward compatibility.
    """
    from textlayout._legacy.geometry_intelligence.engine import analyze_geometry_intelligence
    
    # Get the new format
    new_result = analyze_geometry_intelligence(
        gds_path=gds_path,
        physics_graph=physics_graph,
        extraction_data=geometry_extraction,
        sidecar=sidecar,
    )
    
    # Convert to old schema format
    features = new_result.get("features", [])
    
    # Extract features by type
    capacitor_paddles = []
    current_bottlenecks = []
    ground_pocket = {"has_ground_plane": False, "ground_polygon_count": 0, "total_ground_area_um2": 0.0}
    airbridge_span = {"count": 0, "bridges": [], "max_span_um": 0.0}
    flux_coupling = {"has_flux_line": False, "flux_port_count": 0, "flux_ports": []}
    cpw_bends = {"count": 0, "segments": []}
    cpw_discontinuities = {"count": 0, "discontinuities": []}
    launch_transitions = {"count": 0, "launches": [], "has_gsg": False}
    stubs = {"count": 0, "stubs": []}
    tapers = {"count": 0, "tapers": []}
    corner_types = {"sharp_corners": 0, "rounded_corners": 0, "mitered_corners": 0}
    critical_dimensions = {}
    symmetry_analysis = {"symmetric": None, "note": "no physics graph available"}
    overall_area_um2 = 0.0
    
    for feature in features:
        feature_type = feature.get("feature_type", "")
        dims = feature.get("dimensions", {})
        props = feature.get("engineering_properties", {})
        bbox = feature.get("bounding_box", [0, 0, 0, 0])
        
        if feature_type == "capacitor_paddle":
            capacitor_paddles.append({
                "name": feature.get("name", ""),
                "bbox_um": bbox,
                "area_um2": (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) if len(bbox) >= 4 else 0,
                "width_um": bbox[2] - bbox[0] if len(bbox) >= 4 else 0,
                "height_um": bbox[3] - bbox[1] if len(bbox) >= 4 else 0,
            })
        elif feature_type == "current_bottleneck":
            current_bottlenecks.append({
                "name": feature.get("name", ""),
                "type": "conductor",
                "min_width_um": dims.get("min_width_um", 0),
                "risk": "high" if dims.get("min_width_um", 10) < 1.0 else "medium",
                "reason": f"narrow trace ({dims.get('min_width_um', 0):.2f} um) may cause current crowding",
            })
        elif feature_type == "ground_pocket":
            ground_pocket["has_ground_plane"] = True
            ground_pocket["ground_polygon_count"] += 1
            ground_pocket["total_ground_area_um2"] += props.get("pocket_area_um2", 0)
        elif feature_type == "airbridge":
            airbridge_span["count"] += 1
            airbridge_span["bridges"].append({"type": "airbridge", "span_um": dims.get("bridge_span_um", 0)})
            airbridge_span["max_span_um"] = max(airbridge_span["max_span_um"], dims.get("bridge_span_um", 0))
        elif feature_type == "flux_line":
            flux_coupling["has_flux_line"] = True
            flux_coupling["flux_port_count"] += 1
            flux_coupling["flux_ports"].append({
                "name": feature.get("name", ""),
                "center_um": [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2] if len(bbox) >= 4 else None,
                "width_um": dims.get("line_width_um", 0),
            })
        elif feature_type == "cpw":
            cpw_bends["count"] += 1
            cpw_bends["segments"].append({
                "name": "cpw",
                "length_um": dims.get("length_um", 0),
                "width_um": dims.get("center_width_um", 0),
            })
        elif feature_type == "launch_pad":
            launch_transitions["count"] += 1
            launch_transitions["launches"].append({
                "name": feature.get("name", ""),
                "center_um": [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2] if len(bbox) >= 4 else None,
                "width_um": dims.get("pad_width_um", 0),
                "layer": None,
            })
        elif feature_type == "josephson_junction":
            critical_dimensions["jj_area_um2"] = dims.get("junction_area_um2", 0)
            critical_dimensions["jj_ic_a"] = props.get("critical_current_ua", 0) * 1e-6
            critical_dimensions["jj_lj_h"] = props.get("josephson_inductance_h", 0)
        elif feature_type == "cpw":
            critical_dimensions["cpw_width_um"] = dims.get("center_width_um", 0)
            critical_dimensions["cpw_gap_um"] = dims.get("gap_um", 0)
            critical_dimensions["cpw_z0_ohm"] = props.get("characteristic_impedance_ohm", 0)
        elif feature_type == "idc":
            critical_dimensions["idc_capacitance_f"] = props.get("capacitance_f", 0)
        
        # Calculate overall area
        if len(bbox) >= 4:
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            overall_area_um2 = max(overall_area_um2, area)
    
    return {
        "schema": "text-to-gds.geometry-features.v1",
        "source_gds": str(gds_path),
        "capacitor_paddles": {
            "count": len(capacitor_paddles),
            "paddles": capacitor_paddles,
            "total_area_um2": sum(p.get("area_um2", 0) for p in capacitor_paddles),
        },
        "current_bottlenecks": {
            "count": len(current_bottlenecks),
            "bottlenecks": current_bottlenecks,
            "highest_risk": current_bottlenecks[0]["risk"] if current_bottlenecks else "none",
        },
        "ground_pocket": ground_pocket,
        "airbridge_span": airbridge_span,
        "flux_coupling": flux_coupling,
        "cpw_bends": cpw_bends,
        "cpw_discontinuities": cpw_discontinuities,
        "launch_transitions": launch_transitions,
        "stubs": stubs,
        "tapers": tapers,
        "corner_types": corner_types,
        "critical_dimensions": critical_dimensions,
        "symmetry_analysis": symmetry_analysis,
        "overall_area_um2": overall_area_um2,
    }

__all__ = [
    "GeometryIntelligenceEngine",
    "GeometryFeature",
    "FeatureType",
    "analyze_geometry",
    "recognize_cpw",
    "recognize_idc",
    "recognize_taper",
    "recognize_launch_pad",
    "recognize_bond_pad",
    "recognize_squid_loop",
    "recognize_josephson_junction",
    "recognize_capacitor_paddle",
    "recognize_resonator",
    "recognize_flux_line",
    "recognize_via_fence",
    "recognize_airbridge",
    "recognize_ground_pocket",
    "recognize_ground_bridge",
    "recognize_crossover",
    "recognize_current_bottleneck",
    "recognize_meander",
    "recognize_island",
    "recognize_coupler",
    "recognize_feedline",
]