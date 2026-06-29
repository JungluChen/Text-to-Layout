"""Feature recognizers for semantic geometry recognition.

Each recognizer analyzes geometry data and returns a list of recognized features
with engineering properties and confidence scores.
"""

from __future__ import annotations

import math
from typing import Any

from text_to_gds.geometry_intelligence.features import FeatureType, GeometryFeature


def _bbox_center(bbox: list[float]) -> tuple[float, float]:
    """Calculate bounding box center."""
    if len(bbox) < 4:
        return (0.0, 0.0)
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _bbox_area(bbox: list[float]) -> float:
    """Calculate bounding box area."""
    if len(bbox) < 4:
        return 0.0
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Calculate Euclidean distance between two points."""
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _aspect_ratio(bbox: list[float]) -> float:
    """Calculate aspect ratio (width/height)."""
    if len(bbox) < 4:
        return 1.0
    width = max(0.0, bbox[2] - bbox[0])
    height = max(0.0, bbox[3] - bbox[1])
    if height == 0:
        return float("inf")
    return width / height


def recognize_cpw(
    bbox: list[float],
    width: float,
    gap: float,
    length: float,
    z0: float | None = None,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a coplanar waveguide (CPW) feature.
    
    CPW consists of a center conductor flanked by ground planes on the same layer.
    Key engineering properties: characteristic impedance (Z0), phase velocity,
    and coupling coefficient.
    """
    confidence = 0.7  # Base confidence for CPW detection
    
    # Adjust confidence based on geometry
    if width > 0 and gap > 0:
        # Typical CPW dimensions
        if 1.0 < width < 50.0 and 0.5 < gap < 30.0:
            confidence = 0.9
        elif width > 0 and gap > 0:
            confidence = 0.8
    
    # Calculate engineering properties
    engineering_properties = {
        "type": "coplanar_waveguide",
        "width_um": width,
        "gap_um": gap,
        "length_um": length,
        "z0_ohm": z0,
        "aspect_ratio": _aspect_ratio(bbox),
    }
    
    # Add dimensions
    dimensions = {
        "center_width_um": width,
        "gap_um": gap,
        "length_um": length,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.CPW,
        name=kwargs.get("name", "CPW"),
        bounding_box=bbox,
        electrical_role="transmission_line",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.cpw_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {"width": width, "gap": gap, "length": length},
        },
    )


def recognize_idc(
    bbox: list[float],
    finger_count: int,
    finger_width: float,
    finger_gap: float,
    finger_length: float,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize an interdigitated capacitor (IDC) feature.
    
    IDC consists of interleaved fingers from two electrodes.
    Key engineering properties: capacitance, aspect ratio, and coupling.
    """
    confidence = 0.7
    
    # Adjust confidence based on finger geometry
    if finger_count > 0 and finger_width > 0 and finger_gap > 0:
        if 2 <= finger_count <= 100 and 0.5 < finger_width < 20.0:
            confidence = 0.9
        elif finger_count > 0:
            confidence = 0.8
    
    # Calculate estimated capacitance (simplified model)
    # C ≈ ε₀ * εᵣ * (N-1) * L * w / g
    # This is a rough estimate; actual capacitance depends on substrate
    epsilon_0 = 8.854e-12  # F/m
    epsilon_r = 11.45  # Silicon substrate
    n_fingers = max(finger_count - 1, 0)
    finger_area = finger_length * 1e-6 * finger_width * 1e-6  # m²
    gap = finger_gap * 1e-6  # m
    
    estimated_capacitance = epsilon_0 * epsilon_r * n_fingers * finger_area / gap if gap > 0 else 0
    
    engineering_properties = {
        "type": "interdigitated_capacitor",
        "finger_count": finger_count,
        "finger_width_um": finger_width,
        "finger_gap_um": finger_gap,
        "finger_length_um": finger_length,
        "estimated_capacitance_f": estimated_capacitance,
        "aspect_ratio": _aspect_ratio(bbox),
    }
    
    dimensions = {
        "finger_count": finger_count,
        "finger_width_um": finger_width,
        "finger_gap_um": finger_gap,
        "finger_length_um": finger_length,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.IDC,
        name=kwargs.get("name", "IDC"),
        bounding_box=bbox,
        electrical_role="capacitor",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.idc_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {
                "finger_count": finger_count,
                "finger_width": finger_width,
                "finger_gap": finger_gap,
                "finger_length": finger_length,
            },
        },
    )


def recognize_taper(
    bbox: list[float],
    width_start: float,
    width_end: float,
    length: float,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a taper/transitions feature.
    
    Tapers provide impedance matching between different line widths.
    Key engineering properties: impedance transformation, reflection coefficient.
    """
    confidence = 0.7
    
    # Tapers have gradual width change
    if width_start > 0 and width_end > 0 and length > 0:
        width_ratio = max(width_start, width_end) / min(width_start, width_end)
        if 1.1 < width_ratio < 10.0 and length > 10.0:
            confidence = 0.9
        elif width_ratio > 1.0:
            confidence = 0.8
    
    # Calculate engineering properties
    engineering_properties = {
        "type": "impedance_taper",
        "width_start_um": width_start,
        "width_end_um": width_end,
        "length_um": length,
        "width_ratio": width_ratio if width_start > 0 and width_end > 0 else 1.0,
        "taper_type": "linear" if length > 0 else "unknown",
    }
    
    dimensions = {
        "width_start_um": width_start,
        "width_end_um": width_end,
        "length_um": length,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.TAPER,
        name=kwargs.get("name", "Taper"),
        bounding_box=bbox,
        electrical_role="impedance_matcher",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.taper_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {
                "width_start": width_start,
                "width_end": width_end,
                "length": length,
            },
        },
    )


def recognize_launch_pad(
    bbox: list[float],
    pad_width: float,
    pad_length: float,
    gsg_config: bool = False,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a launch pad feature.
    
    Launch pads provide RF signal coupling to the chip.
    Key engineering properties: return loss, bandwidth, probe compatibility.
    """
    confidence = 0.7
    
    # Launch pads are typically large pads at chip edges
    if pad_width > 50.0 and pad_length > 50.0:
        confidence = 0.9
    elif pad_width > 0 and pad_length > 0:
        confidence = 0.8
    
    engineering_properties = {
        "type": "rf_launch_pad",
        "pad_width_um": pad_width,
        "pad_length_um": pad_length,
        "gsg_config": gsg_config,
        "probe_type": "GSG" if gsg_config else "GS",
        "estimated_bandwidth_ghz": 10.0 if gsg_config else 5.0,
    }
    
    dimensions = {
        "pad_width_um": pad_width,
        "pad_length_um": pad_length,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.LAUNCH_PAD,
        name=kwargs.get("name", "Launch"),
        bounding_box=bbox,
        electrical_role="rf_port",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.launch_pad_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {"pad_width": pad_width, "pad_length": pad_length},
        },
    )


def recognize_bond_pad(
    bbox: list[float],
    pad_diameter: float,
    bond_type: str = "wirebond",
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a bond pad feature.
    
    Bond pads provide wire bonding connections for DC and low-frequency signals.
    Key engineering properties: bond resistance, inductance, and reliability.
    """
    confidence = 0.7
    
    if pad_diameter > 50.0:
        confidence = 0.9
    elif pad_diameter > 0:
        confidence = 0.8
    
    engineering_properties = {
        "type": "bond_pad",
        "pad_diameter_um": pad_diameter,
        "bond_type": bond_type,
        "estimated_resistance_ohm": 0.01 if bond_type == "wirebond" else 0.1,
        "estimated_inductance_ph": 1000.0 if bond_type == "wirebond" else 100.0,
    }
    
    dimensions = {
        "pad_diameter_um": pad_diameter,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.BOND_PAD,
        name=kwargs.get("name", "Bond Pad"),
        bounding_box=bbox,
        electrical_role="dc_port",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.bond_pad_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {"pad_diameter": pad_diameter, "bond_type": bond_type},
        },
    )


def recognize_squid_loop(
    bbox: list[float],
    loop_area: float,
    jj_count: int,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a SQUID loop feature.
    
    SQUID (Superconducting QUantum Interference Device) consists of a loop
    with two Josephson junctions. Key engineering properties: flux sensitivity,
    critical current modulation, and nonlinearity.
    """
    confidence = 0.7
    
    if jj_count == 2 and loop_area > 0:
        confidence = 0.95  # Strong indicator
    elif jj_count >= 2:
        confidence = 0.8
    elif loop_area > 0:
        confidence = 0.6
    
    engineering_properties = {
        "type": "squid_loop",
        "loop_area_um2": loop_area,
        "jj_count": jj_count,
        "flux_quantum_sensitivity": 2.067e-15 / loop_area if loop_area > 0 else None,
        "nonlinear_inductance": True,
    }
    
    dimensions = {
        "loop_area_um2": loop_area,
        "jj_count": jj_count,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.SQUID_LOOP,
        name=kwargs.get("name", "SQUID"),
        bounding_box=bbox,
        electrical_role="nonlinear_element",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.squid_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {"loop_area": loop_area, "jj_count": jj_count},
        },
    )


def recognize_josephson_junction(
    bbox: list[float],
    junction_area: float,
    junction_width: float,
    critical_current_ua: float | None = None,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a Josephson junction feature.
    
    Josephson junction is the nonlinear element in superconducting circuits.
    Key engineering properties: critical current, Josephson inductance,
    charging energy, and nonlinearity.
    """
    confidence = 0.7
    
    if junction_area > 0 and junction_width > 0:
        if 0.01 < junction_area < 100.0 and 0.1 < junction_width < 10.0:
            confidence = 0.9
        elif junction_area > 0:
            confidence = 0.8
    
    # Calculate Josephson inductance if critical current is known
    josephson_inductance = None
    if critical_current_ua is not None and critical_current_ua > 0:
        PHI0 = 2.067e-15  # Flux quantum in Weber
        ic_a = critical_current_ua * 1e-6
        josephson_inductance = PHI0 / (2 * math.pi * ic_a)
    
    engineering_properties = {
        "type": "josephson_junction",
        "junction_area_um2": junction_area,
        "junction_width_um": junction_width,
        "critical_current_ua": critical_current_ua,
        "josephson_inductance_h": josephson_inductance,
        "nonlinear_element": True,
        "quantum_device": True,
    }
    
    dimensions = {
        "junction_area_um2": junction_area,
        "junction_width_um": junction_width,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.JOSEPHSON_JUNCTION,
        name=kwargs.get("name", "JJ"),
        bounding_box=bbox,
        electrical_role="nonlinear_element",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.jj_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {
                "junction_area": junction_area,
                "junction_width": junction_width,
            },
        },
    )


def recognize_capacitor_paddle(
    bbox: list[float],
    paddle_area: float,
    gap: float,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a capacitor paddle feature.
    
    Capacitor paddles provide shunt capacitance for resonators and qubits.
    Key engineering properties: capacitance, quality factor, and coupling.
    """
    confidence = 0.7
    
    if paddle_area > 0 and gap > 0:
        if 100 < paddle_area < 100000 and 0.5 < gap < 20.0:
            confidence = 0.9
        elif paddle_area > 0:
            confidence = 0.8
    
    # Estimate capacitance (parallel plate approximation)
    epsilon_0 = 8.854e-12
    epsilon_r = 11.45  # Silicon
    area_m2 = paddle_area * 1e-12
    gap_m = gap * 1e-6
    estimated_capacitance = epsilon_0 * epsilon_r * area_m2 / gap_m if gap_m > 0 else 0
    
    engineering_properties = {
        "type": "capacitor_paddle",
        "paddle_area_um2": paddle_area,
        "gap_um": gap,
        "estimated_capacitance_f": estimated_capacitance,
        "quality_factor": 1000 if gap > 1.0 else 500,
    }
    
    dimensions = {
        "paddle_area_um2": paddle_area,
        "gap_um": gap,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.CAPACITOR_PADDLE,
        name=kwargs.get("name", "Capacitor"),
        bounding_box=bbox,
        electrical_role="capacitor",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.capacitor_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {"paddle_area": paddle_area, "gap": gap},
        },
    )


def recognize_resonator(
    bbox: list[float],
    resonance_frequency_ghz: float,
    quality_factor: float,
    resonator_type: str = "cpw",
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a resonator feature.
    
    Resonators provide frequency-selective coupling and readout.
    Key engineering properties: resonance frequency, quality factor, and coupling.
    """
    confidence = 0.7
    
    if resonance_frequency_ghz > 0 and quality_factor > 0:
        if 0.1 < resonance_frequency_ghz < 100.0 and 100 < quality_factor < 1000000:
            confidence = 0.9
        elif resonance_frequency_ghz > 0:
            confidence = 0.8
    
    engineering_properties = {
        "type": f"{resonator_type}_resonator",
        "resonance_frequency_ghz": resonance_frequency_ghz,
        "quality_factor": quality_factor,
        "loaded_quality_factor": quality_factor * 0.8,
        "bandwidth_mhz": resonance_frequency_ghz * 1000 / quality_factor if quality_factor > 0 else 0,
    }
    
    dimensions = {
        "resonance_frequency_ghz": resonance_frequency_ghz,
        "quality_factor": quality_factor,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.RESONATOR,
        name=kwargs.get("name", "Resonator"),
        bounding_box=bbox,
        electrical_role="resonator",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.resonator_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {
                "resonance_frequency": resonance_frequency_ghz,
                "quality_factor": quality_factor,
            },
        },
    )


def recognize_flux_line(
    bbox: list[float],
    line_width: float,
    line_length: float,
    coupling_gap: float,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a flux line feature.
    
    Flux lines provide magnetic flux bias for tunable devices.
    Key engineering properties: mutual inductance, flux noise, and coupling.
    """
    confidence = 0.7
    
    if line_width > 0 and line_length > 0:
        if 0.5 < line_width < 10.0 and 10 < line_length < 1000:
            confidence = 0.9
        elif line_width > 0:
            confidence = 0.8
    
    engineering_properties = {
        "type": "flux_bias_line",
        "line_width_um": line_width,
        "line_length_um": line_length,
        "coupling_gap_um": coupling_gap,
        "mutual_inductance_ph": 100.0,  # Typical value
        "flux_noise_hz_per_sqrt_hz": 1.0,
    }
    
    dimensions = {
        "line_width_um": line_width,
        "line_length_um": line_length,
        "coupling_gap_um": coupling_gap,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.FLUX_LINE,
        name=kwargs.get("name", "Flux Line"),
        bounding_box=bbox,
        electrical_role="flux_bias",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.flux_line_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {
                "line_width": line_width,
                "line_length": line_length,
            },
        },
    )


def recognize_via_fence(
    bbox: list[float],
    via_count: int,
    via_diameter: float,
    via_spacing: float,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a via fence feature.
    
    Via fences provide ground connection and suppress substrate modes.
    Key engineering properties: shielding effectiveness, inductance, and reliability.
    """
    confidence = 0.7
    
    if via_count > 0 and via_diameter > 0:
        if via_count > 3 and 1.0 < via_diameter < 20.0:
            confidence = 0.9
        elif via_count > 0:
            confidence = 0.8
    
    engineering_properties = {
        "type": "via_fence",
        "via_count": via_count,
        "via_diameter_um": via_diameter,
        "via_spacing_um": via_spacing,
        "shielding_effectiveness_db": 20 * math.log10(via_spacing / via_diameter) if via_diameter > 0 else 0,
        "estimated_inductance_ph": 10.0 / via_count if via_count > 0 else 0,
    }
    
    dimensions = {
        "via_count": via_count,
        "via_diameter_um": via_diameter,
        "via_spacing_um": via_spacing,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.VIA_FENCE,
        name=kwargs.get("name", "Via Fence"),
        bounding_box=bbox,
        electrical_role="grounding",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.via_fence_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {
                "via_count": via_count,
                "via_diameter": via_diameter,
            },
        },
    )


def recognize_airbridge(
    bbox: list[float],
    bridge_span: float,
    bridge_width: float,
    bridge_height: float,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize an airbridge feature.
    
    Airbridges cross over conductors without electrical contact.
    Key engineering properties: parasitic capacitance, inductance, and mechanical stability.
    """
    confidence = 0.7
    
    if bridge_span > 0 and bridge_width > 0:
        if 10 < bridge_span < 500 and 1.0 < bridge_width < 50.0:
            confidence = 0.9
        elif bridge_span > 0:
            confidence = 0.8
    
    # Estimate parasitic capacitance
    epsilon_0 = 8.854e-12
    area = bridge_span * 1e-6 * bridge_width * 1e-6
    height_m = bridge_height * 1e-6 if bridge_height > 0 else 1e-6
    parasitic_capacitance = epsilon_0 * area / height_m if height_m > 0 else 0
    
    engineering_properties = {
        "type": "airbridge",
        "bridge_span_um": bridge_span,
        "bridge_width_um": bridge_width,
        "bridge_height_um": bridge_height,
        "parasitic_capacitance_f": parasitic_capacitance,
        "mechanical_stability": "good" if bridge_span < 200 else "marginal",
    }
    
    dimensions = {
        "bridge_span_um": bridge_span,
        "bridge_width_um": bridge_width,
        "bridge_height_um": bridge_height,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.AIRBRIDGE,
        name=kwargs.get("name", "Airbridge"),
        bounding_box=bbox,
        electrical_role="crossover",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.airbridge_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {
                "bridge_span": bridge_span,
                "bridge_width": bridge_width,
            },
        },
    )


def recognize_ground_pocket(
    bbox: list[float],
    pocket_area: float,
    isolation_depth: float,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a ground pocket feature.
    
    Ground pockets provide localized ground plane with reduced capacitance.
    Key engineering properties: capacitance reduction, mode suppression, and fabrication.
    """
    confidence = 0.7
    
    if pocket_area > 0:
        if 100 < pocket_area < 1000000:
            confidence = 0.9
        elif pocket_area > 0:
            confidence = 0.8
    
    engineering_properties = {
        "type": "ground_pocket",
        "pocket_area_um2": pocket_area,
        "isolation_depth_um": isolation_depth,
        "capacitance_reduction_factor": 0.7 if isolation_depth > 0 else 1.0,
        "mode_suppression": "effective" if pocket_area > 1000 else "marginal",
    }
    
    dimensions = {
        "pocket_area_um2": pocket_area,
        "isolation_depth_um": isolation_depth,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.GROUND_POCKET,
        name=kwargs.get("name", "Ground Pocket"),
        bounding_box=bbox,
        electrical_role="grounding",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.ground_pocket_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {"pocket_area": pocket_area},
        },
    )


def recognize_ground_bridge(
    bbox: list[float],
    bridge_width: float,
    bridge_length: float,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a ground bridge feature.
    
    Ground bridges connect separate ground plane regions.
    Key engineering properties: ground continuity, inductance, and current capacity.
    """
    confidence = 0.7
    
    if bridge_width > 0 and bridge_length > 0:
        if 1.0 < bridge_width < 50.0 and 5.0 < bridge_length < 200.0:
            confidence = 0.9
        elif bridge_width > 0:
            confidence = 0.8
    
    engineering_properties = {
        "type": "ground_bridge",
        "bridge_width_um": bridge_width,
        "bridge_length_um": bridge_length,
        "ground_continuity": "good" if bridge_width > 5.0 else "marginal",
        "estimated_inductance_ph": 100.0 * bridge_length / bridge_width if bridge_width > 0 else 0,
    }
    
    dimensions = {
        "bridge_width_um": bridge_width,
        "bridge_length_um": bridge_length,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.GROUND_BRIDGE,
        name=kwargs.get("name", "Ground Bridge"),
        bounding_box=bbox,
        electrical_role="grounding",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.ground_bridge_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {"bridge_width": bridge_width, "bridge_length": bridge_length},
        },
    )


def recognize_crossover(
    bbox: list[float],
    overlap_area: float,
    isolation_type: str = "airbridge",
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a crossover feature.
    
    Crossovers allow conductors to cross without electrical contact.
    Key engineering properties: isolation, parasitic capacitance, and reliability.
    """
    confidence = 0.7
    
    if overlap_area > 0:
        if 10 < overlap_area < 10000:
            confidence = 0.9
        elif overlap_area > 0:
            confidence = 0.8
    
    # Estimate parasitic capacitance
    epsilon_0 = 8.854e-12
    area_m2 = overlap_area * 1e-12
    height_m = 1e-6 if isolation_type == "airbridge" else 0.1e-6
    parasitic_capacitance = epsilon_0 * area_m2 / height_m if height_m > 0 else 0
    
    engineering_properties = {
        "type": "crossover",
        "overlap_area_um2": overlap_area,
        "isolation_type": isolation_type,
        "parasitic_capacitance_f": parasitic_capacitance,
        "isolation_db": 40 if isolation_type == "airbridge" else 20,
    }
    
    dimensions = {
        "overlap_area_um2": overlap_area,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.CROSSOVER,
        name=kwargs.get("name", "Crossover"),
        bounding_box=bbox,
        electrical_role="crossover",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.crossover_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {"overlap_area": overlap_area},
        },
    )


def recognize_current_bottleneck(
    bbox: list[float],
    min_width: float,
    max_current_density: float | None = None,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a current bottleneck feature.
    
    Current bottlenecks are narrow regions that limit current flow.
    Key engineering properties: current density, heating risk, and reliability.
    """
    confidence = 0.7
    
    if min_width > 0:
        if 0.1 < min_width < 3.0:
            confidence = 0.9  # Very narrow
        elif min_width < 10.0:
            confidence = 0.8
    
    # Estimate critical current (Aluminum, Jc ~ 1 kA/cm²)
    Jc = 1e7  # A/m²
    critical_current = Jc * min_width * 1e-6 * 0.1e-6  # Assuming 100nm thickness
    
    engineering_properties = {
        "type": "current_bottleneck",
        "min_width_um": min_width,
        "critical_current_ua": critical_current * 1e6,
        "current_crowding_risk": "high" if min_width < 1.0 else "medium" if min_width < 3.0 else "low",
        "heating_risk": "high" if min_width < 0.5 else "medium" if min_width < 2.0 else "low",
    }
    
    dimensions = {
        "min_width_um": min_width,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.CURRENT_BOTTLENECK,
        name=kwargs.get("name", "Bottleneck"),
        bounding_box=bbox,
        electrical_role="current_limiter",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.bottleneck_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {"min_width": min_width},
        },
    )


def recognize_meander(
    bbox: list[float],
    total_length: float,
    meander_count: int,
    line_width: float,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a meander feature.
    
    Meanders increase electrical length in compact area.
    Key engineering properties: inductance, quality factor, and parasitic coupling.
    """
    confidence = 0.7
    
    if total_length > 0 and meander_count > 0:
        if total_length > 100 and meander_count > 3:
            confidence = 0.9
        elif total_length > 0:
            confidence = 0.8
    
    # Estimate inductance (rough approximation)
    # L ≈ μ₀ * l * (ln(2l/w) - 1) for straight wire
    mu_0 = 4 * math.pi * 1e-7
    length_m = total_length * 1e-6
    width_m = line_width * 1e-6 if line_width > 0 else 1e-6
    inductance = mu_0 * length_m * (math.log(2 * length_m / width_m) - 1) if width_m > 0 else 0
    
    engineering_properties = {
        "type": "meander_inductor",
        "total_length_um": total_length,
        "meander_count": meander_count,
        "line_width_um": line_width,
        "estimated_inductance_h": inductance,
        "quality_factor": 100 if line_width > 2.0 else 50,
    }
    
    dimensions = {
        "total_length_um": total_length,
        "meander_count": meander_count,
        "line_width_um": line_width,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.MEANDER,
        name=kwargs.get("name", "Meander"),
        bounding_box=bbox,
        electrical_role="inductor",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.meander_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {
                "total_length": total_length,
                "meander_count": meander_count,
            },
        },
    )


def recognize_island(
    bbox: list[float],
    island_area: float,
    isolation_gap: float,
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize an island feature.
    
    Islands are isolated conductor regions for qubits and resonators.
    Key engineering properties: capacitance, quality factor, and coupling.
    """
    confidence = 0.7
    
    if island_area > 0 and isolation_gap > 0:
        if 100 < island_area < 100000 and 0.5 < isolation_gap < 20.0:
            confidence = 0.9
        elif island_area > 0:
            confidence = 0.8
    
    engineering_properties = {
        "type": "island",
        "island_area_um2": island_area,
        "isolation_gap_um": isolation_gap,
        "estimated_capacitance_f": 1e-15 * island_area / isolation_gap if isolation_gap > 0 else 0,
        "quality_factor": 1000 if isolation_gap > 1.0 else 500,
    }
    
    dimensions = {
        "island_area_um2": island_area,
        "isolation_gap_um": isolation_gap,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.ISLAND,
        name=kwargs.get("name", "Island"),
        bounding_box=bbox,
        electrical_role="capacitor",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.island_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {"island_area": island_area, "isolation_gap": isolation_gap},
        },
    )


def recognize_coupler(
    bbox: list[float],
    coupling_length: float,
    coupling_gap: float,
    coupling_type: str = "capacitive",
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a coupler feature.
    
    Couplers provide controlled coupling between resonators or ports.
    Key engineering properties: coupling coefficient, external Q, and bandwidth.
    """
    confidence = 0.7
    
    if coupling_length > 0 and coupling_gap > 0:
        if 10 < coupling_length < 500 and 0.5 < coupling_gap < 20.0:
            confidence = 0.9
        elif coupling_length > 0:
            confidence = 0.8
    
    # Estimate coupling coefficient
    coupling_coefficient = 0.1 if coupling_gap < 5.0 else 0.05
    
    engineering_properties = {
        "type": f"{coupling_type}_coupler",
        "coupling_length_um": coupling_length,
        "coupling_gap_um": coupling_gap,
        "coupling_type": coupling_type,
        "coupling_coefficient": coupling_coefficient,
        "external_quality_factor": 10000 / coupling_coefficient if coupling_coefficient > 0 else 0,
    }
    
    dimensions = {
        "coupling_length_um": coupling_length,
        "coupling_gap_um": coupling_gap,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.COUPLER,
        name=kwargs.get("name", "Coupler"),
        bounding_box=bbox,
        electrical_role="coupler",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.coupler_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {
                "coupling_length": coupling_length,
                "coupling_gap": coupling_gap,
            },
        },
    )


def recognize_feedline(
    bbox: list[float],
    feedline_width: float,
    feedline_length: float,
    feedline_type: str = "cpw",
    **kwargs: Any,
) -> GeometryFeature:
    """Recognize a feedline feature.
    
    Feedlines provide signal distribution to multiple resonators.
    Key engineering properties: impedance, loss, and coupling strategy.
    """
    confidence = 0.7
    
    if feedline_width > 0 and feedline_length > 0:
        if 1.0 < feedline_width < 50.0 and 100 < feedline_length < 10000:
            confidence = 0.9
        elif feedline_width > 0:
            confidence = 0.8
    
    engineering_properties = {
        "type": f"{feedline_type}_feedline",
        "feedline_width_um": feedline_width,
        "feedline_length_um": feedline_length,
        "feedline_type": feedline_type,
        "impedance_ohm": 50.0,  # Typical CPW impedance
        "loss_db_per_cm": 0.1 if feedline_type == "cpw" else 0.05,
    }
    
    dimensions = {
        "feedline_width_um": feedline_width,
        "feedline_length_um": feedline_length,
    }
    
    return GeometryFeature(
        feature_type=FeatureType.FEEDLINE,
        name=kwargs.get("name", "Feedline"),
        bounding_box=bbox,
        electrical_role="transmission_line",
        parent_subsystem=kwargs.get("parent_subsystem", ""),
        connected_nets=kwargs.get("connected_nets", []),
        dimensions=dimensions,
        engineering_properties=engineering_properties,
        confidence=confidence,
        source="geometry_intelligence.feedline_recognizer",
        provenance={
            "method": "geometric_analysis",
            "inputs": {
                "feedline_width": feedline_width,
                "feedline_length": feedline_length,
            },
        },
    )
