"""Golden reference matching: topology-aware comparison against literature.

Replaces parameter-only comparison with topology-aware evaluation that
considers geometry similarity, topological similarity, device hierarchy,
critical dimensions, port placement, ground strategy, and more.
"""

from __future__ import annotations

import math
from typing import Any


# ─── Similarity scoring helpers ────────────────────────────────────────────────

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _relative_error(generated: float, reference: float) -> float:
    if reference == 0.0:
        return float("inf") if generated != 0.0 else 0.0
    return abs(generated - reference) / abs(reference)


def _dimension_score(
    generated: float | None,
    reference: float | None,
    tolerance: float = 0.2,
) -> float:
    if generated is None or reference is None:
        return 0.5  # unknown is neutral
    err = _relative_error(generated, reference)
    if err <= tolerance:
        return 1.0
    if err <= 2 * tolerance:
        return 0.5
    return 0.0


def _binary_score(a: bool, b: bool) -> float:
    return 1.0 if a == b else 0.0


def _set_overlap_score(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union) if union else 0.0


# ─── Reference device template ────────────────────────────────────────────────

class ReferenceDevice:
    """A literature reference device for topology-aware comparison."""

    def __init__(self, data: dict[str, Any]):
        self.name: str = data.get("name", "unknown")
        self.topology: str = data.get("topology", "unknown")
        self.institution: str = data.get("institution", "")
        self.reference: str = data.get("reference", "")

        # Geometry features
        self.geometry: dict[str, Any] = data.get("geometry", {})
        # Topology features
        self.topology_features: dict[str, Any] = data.get("topology_features", {})
        # Electrical parameters
        self.electrical: dict[str, Any] = data.get("electrical", {})
        # Fabrication parameters
        self.fabrication: dict[str, Any] = data.get("fabrication", {})
        # Port configuration
        self.ports: list[dict[str, Any]] = data.get("ports", [])
        # Ground strategy
        self.ground_strategy: str = data.get("ground_strategy", "coplanar")
        # Flux bias strategy
        self.flux_strategy: str = data.get("flux_strategy", "none")
        # Readout strategy
        self.readout_strategy: str = data.get("readout_strategy", "none")
        # CPW transition style
        self.cpw_transition: str = data.get("cpw_transition", "uniform")
        # IDC style
        self.idc_style: str = data.get("idc_style", "none")
        # SQUID implementation
        self.squid_style: str = data.get("squid_style", "none")


# ─── Main matching function ───────────────────────────────────────────────────

def match_reference(
    topology_result: dict[str, Any],
    geometry_features: dict[str, Any] | None = None,
    references: list[dict[str, Any]] | None = None,
    *,
    electrical_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare the generated device against literature references.

    Parameters
    ----------
    topology_result:
        Output of ``recognize_topology()``.
    geometry_features:
        Output of ``analyze_geometry()``.
    references:
        List of reference device dicts.
    electrical_params:
        Optional extracted electrical parameters (Z0, frequency, Q, etc.).

    Returns
    -------
    dict with similarity scores and per-reference comparisons.
    """
    if not references:
        return {
            "schema": "text-to-gds.reference-matching.v1",
            "reference_count": 0,
            "best_match": None,
            "comparisons": [],
            "overall_similarity": 0.0,
        }

    detected = topology_result.get("detected_device", "unknown")
    features = topology_result.get("features", {})
    topo_graph = topology_result.get("topology_graph", {})

    # Build generated device feature sets
    gen_node_types = {n.get("type", "") for n in topo_graph.get("nodes", [])}
    gen_edge_types = {e.get("type", "") for e in topo_graph.get("edges", [])}
    gen_ports = set(features.get("port_names", []))

    comparisons: list[dict[str, Any]] = []

    for ref_data in references:
        ref = ReferenceDevice(ref_data)
        comp = _compare_single(
            detected=detected,
            features=features,
            gen_node_types=gen_node_types,
            gen_edge_types=gen_edge_types,
            gen_ports=gen_ports,
            geometry_features=geometry_features,
            electrical_params=electrical_params,
            reference=ref,
        )
        comparisons.append(comp)

    comparisons.sort(key=lambda c: c["total_score"], reverse=True)
    best = comparisons[0] if comparisons else None

    return {
        "schema": "text-to-gds.reference-matching.v1",
        "reference_count": len(references),
        "best_match": best["reference_name"] if best else None,
        "best_score": best["total_score"] if best else 0.0,
        "comparisons": comparisons,
        "overall_similarity": best["total_score"] if best else 0.0,
    }


def _compare_single(
    detected: str,
    features: dict[str, Any],
    gen_node_types: set[str],
    gen_edge_types: set[str],
    gen_ports: set[str],
    geometry_features: dict[str, Any] | None,
    electrical_params: dict[str, Any] | None,
    reference: ReferenceDevice,
) -> dict[str, Any]:
    """Compare generated device against one reference."""

    # 1. Topological similarity (25%)
    topo_score = _compare_topology(detected, gen_node_types, reference)

    # 2. Geometry similarity (20%)
    geom_score = _compare_geometry(features, geometry_features, reference)

    # 3. Electrical similarity (20%)
    elec_score = _compare_electrical(electrical_params, reference)

    # 4. Fabrication similarity (15%)
    fab_score = _compare_fabrication(features, reference)

    # 5. Port placement (10%)
    port_score = _compare_ports(gen_ports, reference)

    # 6. Ground strategy (5%)
    ground_score = _compare_ground_strategy(features, reference)

    # 7. Flux strategy (5%)
    flux_score = _compare_flux_strategy(features, reference)

    total = (
        0.25 * topo_score
        + 0.20 * geom_score
        + 0.20 * elec_score
        + 0.15 * fab_score
        + 0.10 * port_score
        + 0.05 * ground_score
        + 0.05 * flux_score
    )

    return {
        "reference_name": reference.name,
        "reference_topology": reference.topology,
        "reference_institution": reference.institution,
        "total_score": round(total, 3),
        "breakdown": {
            "topology": round(topo_score, 3),
            "geometry": round(geom_score, 3),
            "electrical": round(elec_score, 3),
            "fabrication": round(fab_score, 3),
            "ports": round(port_score, 3),
            "ground_strategy": round(ground_score, 3),
            "flux_strategy": round(flux_score, 3),
        },
        "topology_match": detected == reference.topology,
        "literature_distance": round(1.0 - total, 3),
    }


def _compare_topology(
    detected: str,
    gen_node_types: set[str],
    ref: ReferenceDevice,
) -> float:
    """Compare topology type and element presence."""
    topo_match = 1.0 if detected == ref.topology else 0.0

    ref_nodes = set(ref.topology_features.get("node_types", []))
    node_sim = _set_overlap_score(gen_node_types, ref_nodes)

    return 0.7 * topo_match + 0.3 * node_sim


def _compare_geometry(
    features: dict[str, Any],
    geometry_features: dict[str, Any] | None,
    ref: ReferenceDevice,
) -> float:
    """Compare geometric dimensions and proportions."""
    scores: list[float] = []

    # JJ area
    gen_jj = features.get("jj_areas_um2", [])
    ref_jj = ref.geometry.get("jj_area_um2")
    if gen_jj and ref_jj:
        scores.append(_dimension_score(gen_jj[0], ref_jj, tolerance=0.3))

    # CPW width
    gen_cpw_w = features.get("cpw_widths_um", [])
    ref_cpw_w = ref.geometry.get("cpw_width_um")
    if gen_cpw_w and ref_cpw_w:
        scores.append(_dimension_score(gen_cpw_w[0], ref_cpw_w, tolerance=0.2))

    # Overall area
    if geometry_features:
        gen_area = geometry_features.get("overall_area_um2", 0.0)
        ref_area = ref.geometry.get("chip_area_um2")
        if gen_area and ref_area:
            scores.append(_dimension_score(gen_area, ref_area, tolerance=0.5))

    return sum(scores) / len(scores) if scores else 0.5


def _compare_electrical(
    electrical_params: dict[str, Any] | None,
    ref: ReferenceDevice,
) -> float:
    """Compare electrical parameters."""
    if not electrical_params:
        return 0.5

    scores: list[float] = []

    gen_z0 = electrical_params.get("z0_ohm")
    ref_z0 = ref.electrical.get("z0_ohm")
    if gen_z0 is not None and ref_z0 is not None:
        scores.append(_dimension_score(float(gen_z0), float(ref_z0), tolerance=0.15))

    gen_freq = electrical_params.get("frequency_ghz")
    ref_freq = ref.electrical.get("frequency_ghz")
    if gen_freq is not None and ref_freq is not None:
        scores.append(_dimension_score(float(gen_freq), float(ref_freq), tolerance=0.1))

    gen_q = electrical_params.get("quality_factor")
    ref_q = ref.electrical.get("quality_factor")
    if gen_q is not None and ref_q is not None:
        scores.append(_dimension_score(float(gen_q), float(ref_q), tolerance=0.3))

    gen_gain = electrical_params.get("gain_db")
    ref_gain = ref.electrical.get("gain_db")
    if gen_gain is not None and ref_gain is not None:
        scores.append(_dimension_score(float(gen_gain), float(ref_gain), tolerance=0.2))

    return sum(scores) / len(scores) if scores else 0.5


def _compare_fabrication(
    features: dict[str, Any],
    ref: ReferenceDevice,
) -> float:
    """Compare fabrication parameters."""
    scores: list[float] = []

    # IDC style
    gen_idc = len(features.get("idc_finger_counts", [])) > 0
    ref_idc = ref.idc_style != "none"
    scores.append(_binary_score(gen_idc, ref_idc))

    # Ground plane
    gen_ground = features.get("has_ground_plane", False)
    ref_ground = ref.ground_strategy != "none"
    scores.append(_binary_score(gen_ground, ref_ground))

    # Launch pads
    gen_launch = features.get("has_launch_pads", False)
    ref_launch = len(ref.ports) >= 2
    scores.append(_binary_score(gen_launch, ref_launch))

    return sum(scores) / len(scores) if scores else 0.5


def _compare_ports(
    gen_ports: set[str],
    ref: ReferenceDevice,
) -> float:
    """Compare port configuration."""
    ref_port_names = {p.get("name", "").lower() for p in ref.ports}
    if not ref_port_names:
        return 0.5
    return _set_overlap_score(gen_ports, ref_port_names)


def _compare_ground_strategy(
    features: dict[str, Any],
    ref: ReferenceDevice,
) -> float:
    """Compare ground strategy."""
    gen_has_ground = features.get("has_ground_plane", False)
    ref_has_ground = ref.ground_strategy != "none"
    return _binary_score(gen_has_ground, ref_has_ground)


def _compare_flux_strategy(
    features: dict[str, Any],
    ref: ReferenceDevice,
) -> float:
    """Compare flux bias strategy."""
    gen_flux = features.get("has_flux_line", False)
    ref_flux = ref.flux_strategy != "none"
    return _binary_score(gen_flux, ref_flux)
