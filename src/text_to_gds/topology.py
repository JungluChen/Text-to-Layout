"""Topology recognition: classify superconducting devices from extracted graph.

Instead of only extracting net-level connectivity, this module builds a
topological graph of physical device elements and classifies the overall
device topology into known categories.

Supported topologies:
  - Pocket Transmon
  - Xmon
  - Concentric Transmon
  - Lumped JPA
  - Quarter-wave JPA
  - TWPA
  - Fluxonium
  - CPW Resonator
  - IDC Resonator
  - Calibration Chip
  - JJ Array
  - UNKNOWN (when classification confidence is insufficient)
"""

from __future__ import annotations

import math
from typing import Any


# ─── Topology definitions ─────────────────────────────────────────────────────

KNOWN_TOPOLOGIES = (
    "pocket_transmon",
    "xmon",
    "concentric_transmon",
    "lumped_jpa",
    "quarter_wave_jpa",
    "twpa",
    "fluxonium",
    "cpw_resonator",
    "idc_resonator",
    "calibration_chip",
    "jj_array",
    "unknown",
)

# Node types in the topology graph
TOPOLOGY_NODE_TYPES = {
    "jj",
    "idc",
    "cpw",
    "ground_plane",
    "island",
    "squid",
    "flux_line",
    "via",
    "launch_pad",
    "resonator",
    "wirebond",
    "bridge",
    "meander",
    "tline",
    "capacitor",
    "coupling_capacitor",
    "port",
}

# Edge types in the topology graph
TOPOLOGY_EDGE_TYPES = {
    "galvanic",
    "capacitive",
    "inductive",
    "microwave",
    "bias",
    "ground_return",
}


def _geometry_center(bbox_um: list[float]) -> tuple[float, float]:
    if len(bbox_um) < 4:
        return (0.0, 0.0)
    return ((bbox_um[0] + bbox_um[2]) / 2.0, (bbox_um[1] + bbox_um[3]) / 2.0)


def _geometry_area(bbox_um: list[float]) -> float:
    if len(bbox_um) < 4:
        return 0.0
    return max(0.0, bbox_um[2] - bbox_um[0]) * max(0.0, bbox_um[3] - bbox_um[1])


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


# ─── Feature extraction from physics graph ────────────────────────────────────

def _extract_features(
    graph: dict[str, Any],
    geometry_extraction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract topological features from the physics graph and geometry extraction."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    devices = graph.get("devices", [])

    features: dict[str, Any] = {
        "jj_count": 0,
        "idc_count": 0,
        "cpw_count": 0,
        "squid_detected": False,
        "has_ground_plane": False,
        "has_flux_line": False,
        "has_launch_pads": False,
        "has_resonator": False,
        "has_island": False,
        "has_wirebond": False,
        "has_bridge": False,
        "has_meander": False,
        "port_count": 0,
        "port_names": [],
        "device_types": [],
        "jj_areas_um2": [],
        "jj_positions": [],
        "squid_separation_um": None,
        "cpw_widths_um": [],
        "cpw_lengths_um": [],
        "idc_finger_counts": [],
        "capacitance_types": [],
        "has_coupling_capacitor": False,
        "ground_connectivity": False,
        "edge_types_present": set(),
    }

    for node in nodes:
        ntype = node.get("type", "")
        name = node.get("name", "")
        geom = node.get("geometry", {})
        params = node.get("physics_parameters", {})
        bbox = geom.get("bbox_um", [0, 0, 0, 0])

        if ntype == "josephson_junction":
            features["jj_count"] += 1
            area = geom.get("area_um2", 0.0)
            if area:
                features["jj_areas_um2"].append(float(area))
            features["jj_positions"].append(_geometry_center(bbox))

        elif ntype == "capacitor":
            features["idc_count"] += 1
            finger_count = params.get("finger_count", {})
            if isinstance(finger_count, dict):
                features["idc_finger_counts"].append(int(finger_count.get("value", 0)))
            elif isinstance(finger_count, (int, float)):
                features["idc_finger_counts"].append(int(finger_count))
            features["capacitance_types"].append(name)

        elif ntype == "transmission_line":
            features["cpw_count"] += 1
            width = params.get("width", {})
            length = params.get("length", {})
            if isinstance(width, dict) and "value" in width:
                features["cpw_widths_um"].append(float(width["value"]))
            if isinstance(length, dict) and "value" in length:
                features["cpw_lengths_um"].append(float(length["value"]))

        elif ntype == "ground":
            features["has_ground_plane"] = True
            features["ground_connectivity"] = True

        elif ntype == "port":
            features["port_count"] += 1
            features["port_names"].append(name.lower())

    for edge in edges:
        etype = edge.get("type", "")
        features["edge_types_present"].add(etype)

    for device in devices:
        dtype = device.get("type", "")
        if dtype not in features["device_types"]:
            features["device_types"].append(dtype)

    # Detect SQUID from two JJ devices
    if features["jj_count"] >= 2 and len(features["jj_positions"]) >= 2:
        dist = _distance(features["jj_positions"][0], features["jj_positions"][1])
        if dist <= 30.0:
            features["squid_detected"] = True
            features["squid_separation_um"] = dist

    # Detect flux line from port names
    flux_keywords = {"flux", "bias", "coil", "dc"}
    features["has_flux_line"] = any(
        any(kw in pname for kw in flux_keywords) for pname in features["port_names"]
    )

    # Detect launch pads from port names
    launch_keywords = {"rf", "in", "out", "signal", "pump", "readout", "drive", "xy"}
    features["has_launch_pads"] = sum(
        1 for pname in features["port_names"]
        if any(kw in pname for kw in launch_keywords)
    ) >= 2

    # Detect resonator from CPW + sidecar info
    sidecar_device = ""
    if geometry_extraction:
        sidecar_device = str(geometry_extraction.get("device_type", "")).lower()

    features["has_resonator"] = (
        features["cpw_count"] > 0
        and any(kw in sidecar_device for kw in ("resonator", "cpw"))
    )

    features["features_list"] = sorted(features["edge_types_present"])
    return features


# ─── Topology classification rules ────────────────────────────────────────────

def _classify_pocket_transmon(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["jj_count"] == 1:
        score += 30
        supporting.append("single JJ")
    elif features["jj_count"] == 0:
        missing.append("no JJ detected")
        return "unknown", 0.0, supporting, missing

    if features["squid_detected"]:
        score -= 10
        missing.append("SQUID detected (not pocket transmon)")

    if features["has_ground_plane"]:
        score += 15
        supporting.append("ground plane present")

    if features["idc_count"] > 0:
        score += 25
        supporting.append("IDC capacitor paddles")

    if features["cpw_count"] > 0:
        score += 10
        supporting.append("readout resonator present")

    if features["has_launch_pads"]:
        score += 10
        supporting.append("launch pads present")

    if features["port_count"] >= 2:
        score += 5
        supporting.append("adequate port count")

    if features["has_flux_line"]:
        score += 5
        supporting.append("flux bias line")

    confidence = min(score / 100.0, 1.0)
    topology = "pocket_transmon" if score >= 50 else "unknown"
    return topology, confidence, supporting, missing


def _classify_xmon(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["jj_count"] == 1:
        score += 30
        supporting.append("single JJ")
    elif features["jj_count"] == 0:
        missing.append("no JJ detected")
        return "unknown", 0.0, supporting, missing

    if features["has_ground_plane"]:
        score += 15
        supporting.append("ground plane present")

    # Xmon has cross-shaped capacitor arms (typically 4)
    if features["idc_count"] == 0 and features["cpw_count"] == 0:
        score += 5
        supporting.append("cross-shaped arms implied (no IDC/CPW)")

    if features["has_launch_pads"]:
        score += 10
        supporting.append("launch pads present")

    if features["port_count"] >= 2:
        score += 5
        supporting.append("adequate port count")

    if not features["squid_detected"] and not features["has_flux_line"]:
        score += 5
        supporting.append("fixed-frequency compatible")

    confidence = min(score / 100.0, 1.0)
    topology = "xmon" if score >= 45 else "unknown"
    return topology, confidence, supporting, missing


def _classify_concentric_transmon(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["jj_count"] == 1:
        score += 30
        supporting.append("single JJ")
    elif features["jj_count"] == 0:
        missing.append("no JJ detected")
        return "unknown", 0.0, supporting, missing

    if features["has_ground_plane"]:
        score += 10
        supporting.append("ground plane present")

    if features["idc_count"] > 0:
        score += 15
        supporting.append("IDC present")

    if not features["squid_detected"]:
        score += 5
        supporting.append("no SQUID (concentric pattern)")

    confidence = min(score / 100.0, 1.0)
    topology = "concentric_transmon" if score >= 40 else "unknown"
    return topology, confidence, supporting, missing


def _classify_lumped_jpa(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["squid_detected"]:
        score += 35
        supporting.append("SQUID loop detected")
    elif features["jj_count"] >= 1:
        score += 15
        supporting.append("JJ present (no SQUID)")
    else:
        missing.append("no JJ/SQUID detected")
        return "unknown", 0.0, supporting, missing

    if features["idc_count"] > 0:
        score += 25
        supporting.append("IDC shunt capacitor")

    if features["has_flux_line"]:
        score += 15
        supporting.append("flux bias line for pump")

    if features["cpw_count"] > 0:
        score += 10
        supporting.append("CPW feed line")

    if features["has_launch_pads"]:
        score += 10
        supporting.append("launch pads present")

    if features["port_count"] >= 3:
        score += 5
        supporting.append("3+ ports (RF in/out + pump)")

    confidence = min(score / 100.0, 1.0)
    topology = "lumped_jpa" if score >= 50 else "unknown"
    return topology, confidence, supporting, missing


def _classify_quarter_wave_jpa(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["squid_detected"]:
        score += 30
        supporting.append("SQUID loaded line")
    elif features["jj_count"] >= 1:
        score += 15
        supporting.append("JJ present")
    else:
        missing.append("no JJ detected")
        return "unknown", 0.0, supporting, missing

    if features["cpw_count"] > 0:
        score += 25
        supporting.append("CPW transmission line")

    if features["has_ground_plane"]:
        score += 10
        supporting.append("ground plane present")

    if features["has_flux_line"]:
        score += 15
        supporting.append("flux bias line")

    if features["has_launch_pads"]:
        score += 10
        supporting.append("launch pads present")

    # Long CPW with JJ suggests quarter-wave
    if features["cpw_lengths_um"]:
        max_len = max(features["cpw_lengths_um"])
        if max_len > 500:
            score += 10
            supporting.append(f"long CPW ({max_len:.0f} um)")

    confidence = min(score / 100.0, 1.0)
    topology = "quarter_wave_jpa" if score >= 50 else "unknown"
    return topology, confidence, supporting, missing


def _classify_twpa(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["jj_count"] >= 2:
        score += 25
        supporting.append(f"{features['jj_count']} JJs (JJ chain)")
    elif features["jj_count"] == 0:
        missing.append("no JJ detected")
        return "unknown", 0.0, supporting, missing

    if features["cpw_count"] > 0:
        score += 20
        supporting.append("CPW line present")

    if features["has_ground_plane"]:
        score += 10
        supporting.append("ground plane present")

    if features["has_flux_line"]:
        score += 15
        supporting.append("flux bias line")

    if features["has_launch_pads"]:
        score += 10
        supporting.append("launch pads present")

    if features["port_count"] >= 2:
        score += 5
        supporting.append("adequate port count")

    confidence = min(score / 100.0, 1.0)
    topology = "twpa" if score >= 45 else "unknown"
    return topology, confidence, supporting, missing


def _classify_fluxonium(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["jj_count"] == 1:
        score += 30
        supporting.append("single JJ")
    elif features["jj_count"] == 0:
        missing.append("no JJ detected")
        return "unknown", 0.0, supporting, missing

    if features["has_ground_plane"]:
        score += 10
        supporting.append("ground plane present")

    if features["has_meander"]:
        score += 25
        supporting.append("meander inductor")

    if features["has_flux_line"]:
        score += 20
        supporting.append("flux bias line")

    if features["has_launch_pads"]:
        score += 10
        supporting.append("launch pads present")

    confidence = min(score / 100.0, 1.0)
    topology = "fluxonium" if score >= 50 else "unknown"
    return topology, confidence, supporting, missing


def _classify_cpw_resonator(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["jj_count"] > 0:
        missing.append("JJ detected (not pure resonator)")
        return "unknown", 0.0, supporting, missing

    if features["cpw_count"] > 0:
        score += 35
        supporting.append("CPW transmission line")

    if features["has_ground_plane"]:
        score += 20
        supporting.append("ground plane present")

    if features["has_launch_pads"]:
        score += 15
        supporting.append("launch pads present")

    if features["port_count"] >= 2:
        score += 10
        supporting.append("adequate port count")

    if features["has_coupling_capacitor"]:
        score += 10
        supporting.append("coupling capacitor present")

    confidence = min(score / 100.0, 1.0)
    topology = "cpw_resonator" if score >= 45 else "unknown"
    return topology, confidence, supporting, missing


def _classify_idc_resonator(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["jj_count"] > 0:
        missing.append("JJ detected (not pure IDC resonator)")
        return "unknown", 0.0, supporting, missing

    if features["idc_count"] > 0:
        score += 35
        supporting.append("IDC capacitor")

    if features["has_meander"] or features["cpw_count"] > 0:
        score += 20
        supporting.append("inductive element present")

    if features["has_ground_plane"]:
        score += 15
        supporting.append("ground plane present")

    if features["has_launch_pads"]:
        score += 10
        supporting.append("launch pads present")

    if features["port_count"] >= 2:
        score += 10
        supporting.append("adequate port count")

    confidence = min(score / 100.0, 1.0)
    topology = "idc_resonator" if score >= 45 else "unknown"
    return topology, confidence, supporting, missing


def _classify_jj_array(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["jj_count"] >= 2:
        score += 30
        supporting.append(f"{features['jj_count']} JJs in array")
    elif features["jj_count"] == 0:
        missing.append("no JJ detected")
        return "unknown", 0.0, supporting, missing

    if not features["squid_detected"]:
        score += 10
        supporting.append("no SQUID loop (array pattern)")

    if features["has_ground_plane"]:
        score += 10
        supporting.append("ground plane present")

    if features["has_launch_pads"]:
        score += 10
        supporting.append("launch pads present")

    confidence = min(score / 100.0, 1.0)
    topology = "jj_array" if score >= 35 else "unknown"
    return topology, confidence, supporting, missing


def _classify_calibration_chip(features: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    supporting: list[str] = []
    missing: list[str] = []

    if features["cpw_count"] >= 2:
        score += 20
        supporting.append(f"{features['cpw_count']} CPW lines")

    if features["idc_count"] >= 2:
        score += 15
        supporting.append(f"{features['idc_count']} IDC structures")

    if features["port_count"] >= 4:
        score += 20
        supporting.append(f"{features['port_count']} ports (multi-device)")

    if features["has_ground_plane"]:
        score += 10
        supporting.append("ground plane present")

    if features["jj_count"] == 0:
        score += 10
        supporting.append("no JJ (test structure)")

    confidence = min(score / 100.0, 1.0)
    topology = "calibration_chip" if score >= 40 else "unknown"
    return topology, confidence, supporting, missing


# ─── Main classifier ──────────────────────────────────────────────────────────

_CLASSIFIERS = [
    _classify_lumped_jpa,
    _classify_quarter_wave_jpa,
    _classify_pocket_transmon,
    _classify_xmon,
    _classify_concentric_transmon,
    _classify_twpa,
    _classify_fluxonium,
    _classify_cpw_resonator,
    _classify_idc_resonator,
    _classify_jj_array,
    _classify_calibration_chip,
]


def recognize_topology(
    graph: dict[str, Any],
    geometry_extraction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify the device topology from the physics graph and geometry extraction.

    Parameters
    ----------
    graph:
        Output of ``extract_physics_graph()``.
    geometry_extraction:
        Optional output of ``extract_geometry()`` for richer polygon features.

    Returns
    -------
    dict with keys: detected_device, confidence, supporting_features,
    missing_features, topology_graph, features.
    """
    features = _extract_features(graph, geometry_extraction)

    best_topology = "unknown"
    best_confidence = 0.0
    best_supporting: list[str] = []
    best_missing: list[str] = []

    for classifier in _CLASSIFIERS:
        topology, confidence, supporting, missing = classifier(features)
        if confidence > best_confidence:
            best_topology = topology
            best_confidence = confidence
            best_supporting = supporting
            best_missing = missing

    # Build topology graph representation
    topology_nodes: list[dict[str, Any]] = []
    topology_edges: list[dict[str, Any]] = []

    for i, node in enumerate(graph.get("nodes", [])):
        topo_node_type = _map_node_type(node.get("type", ""), features)
        topology_nodes.append({
            "id": node.get("id", f"n{i}"),
            "type": topo_node_type,
            "name": node.get("name", ""),
        })

    for edge in graph.get("edges", []):
        topo_edge_type = _map_edge_type(edge.get("type", ""), features)
        topology_edges.append({
            "source": edge.get("source", ""),
            "target": edge.get("target", ""),
            "type": topo_edge_type,
        })

    # Remove set for JSON serialization
    features_serializable = {k: v for k, v in features.items() if k != "edge_types_present"}
    features_serializable["edge_types_present"] = sorted(features.get("edge_types_present", set()))

    return {
        "schema": "text-to-gds.topology-recognition.v1",
        "detected_device": best_topology,
        "confidence": round(best_confidence, 3),
        "supporting_features": best_supporting,
        "missing_features": best_missing,
        "topology_graph": {
            "nodes": topology_nodes,
            "edges": topology_edges,
            "node_types": sorted(TOPOLOGY_NODE_TYPES),
            "edge_types": sorted(TOPOLOGY_EDGE_TYPES),
        },
        "features": features_serializable,
    }


def _map_node_type(physics_type: str, features: dict[str, Any]) -> str:
    mapping = {
        "josephson_junction": "jj",
        "capacitor": "idc",
        "transmission_line": "cpw",
        "ground": "ground_plane",
        "inductor": "meander",
        "port": "port",
    }
    return mapping.get(physics_type, "capacitor")


def _map_edge_type(physics_edge: str, features: dict[str, Any]) -> str:
    mapping = {
        "electrical_connection": "galvanic",
        "capacitive_coupling": "capacitive",
        "mutual_inductance": "inductive",
        "microwave_port": "microwave",
    }
    return mapping.get(physics_edge, "galvanic")
