"""Microwave engineering rules for superconducting circuits."""

from __future__ import annotations

from typing import Any

from text_to_gds.engineering_rules.rules import Rule, RuleCategory, RuleSeverity


def _check_flux_line_coupling(data: dict[str, Any]) -> bool:
    """Check if flux line is too close to resonator."""
    features = data.get("geometry_features", [])
    flux_lines = [f for f in features if f.get("feature_type") == "flux_line"]
    resonators = [f for f in features if f.get("feature_type") == "resonator"]
    
    for flux in flux_lines:
        for resonator in resonators:
            flux_bbox = flux.get("bounding_box", [0, 0, 0, 0])
            res_bbox = resonator.get("bounding_box", [0, 0, 0, 0])
            
            # Calculate distance between features
            flux_center = ((flux_bbox[0] + flux_bbox[2]) / 2, (flux_bbox[1] + flux_bbox[3]) / 2)
            res_center = ((res_bbox[0] + res_bbox[2]) / 2, (res_bbox[1] + res_bbox[3]) / 2)
            
            distance = ((flux_center[0] - res_center[0])**2 + (flux_center[1] - res_center[1])**2)**0.5
            
            if distance < 50.0:  # Less than 50 um
                return False
    return True


def _message_flux_line_coupling(data: dict[str, Any]) -> str:
    return "Flux line too close to resonator. May increase Purcell loss and unwanted coupling."


def _recommendation_flux_line_coupling(data: dict[str, Any]) -> str:
    return "Increase flux line to resonator distance to >50 um to reduce parasitic coupling."


def _check_cpw_gap_ratio(data: dict[str, Any]) -> bool:
    """Check CPW gap-to-width ratio for impedance control."""
    features = data.get("geometry_features", [])
    cpw_features = [f for f in features if f.get("feature_type") == "cpw"]
    
    for cpw in cpw_features:
        dims = cpw.get("dimensions", {})
        width = dims.get("center_width_um", 0)
        gap = dims.get("gap_um", 0)
        
        if width > 0 and gap > 0:
            ratio = gap / width
            if ratio < 0.3 or ratio > 2.0:
                return False
    return True


def _message_cpw_gap_ratio(data: dict[str, Any]) -> str:
    return "CPW gap-to-width ratio outside typical range (0.3-2.0). May cause impedance mismatch."


def _recommendation_cpw_gap_ratio(data: dict[str, Any]) -> str:
    return "Adjust CPW gap or width to achieve gap/width ratio between 0.3 and 2.0 for 50 ohm impedance."


def _check_idc_aspect_ratio(data: dict[str, Any]) -> bool:
    """Check IDC aspect ratio for fabrication feasibility."""
    features = data.get("geometry_features", [])
    idc_features = [f for f in features if f.get("feature_type") == "idc"]
    
    for idc in idc_features:
        bbox = idc.get("bounding_box", [0, 0, 0, 0])
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        
        if width > 0 and height > 0:
            aspect = max(width / height, height / width)
            if aspect > 10.0:
                return False
    return True


def _message_idc_aspect_ratio(data: dict[str, Any]) -> str:
    return "IDC aspect ratio >10:1. Excessive aspect ratio may cause fabrication issues."


def _recommendation_idc_aspect_ratio(data: dict[str, Any]) -> str:
    return "Reduce IDC aspect ratio to <10:1 for better fabrication yield."


def _check_launch_pad_size(data: dict[str, Any]) -> bool:
    """Check launch pad size for probe compatibility."""
    features = data.get("geometry_features", [])
    launch_features = [f for f in features if f.get("feature_type") == "launch_pad"]
    
    for launch in launch_features:
        dims = launch.get("dimensions", {})
        width = dims.get("pad_width_um", 0)
        length = dims.get("pad_length_um", 0)
        
        if width < 50.0 or length < 50.0:
            return False
    return True


def _message_launch_pad_size(data: dict[str, Any]) -> str:
    return "Launch pad too small for standard GSG probe. May cause poor RF contact."


def _recommendation_launch_pad_size(data: dict[str, Any]) -> str:
    return "Increase launch pad size to >50 um for standard GSG probe compatibility."


def _check_slotline_mode(data: dict[str, Any]) -> bool:
    """Check for potential slotline mode issues."""
    features = data.get("geometry_features", [])
    ground_bridges = [f for f in features if f.get("feature_type") == "ground_bridge"]
    
    # If there are ground bridges, check if they're properly spaced
    if len(ground_bridges) > 1:
        positions = []
        for bridge in ground_bridges:
            bbox = bridge.get("bounding_box", [0, 0, 0, 0])
            center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
            positions.append(center)
        
        # Check spacing between bridges
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                distance = ((positions[i][0] - positions[j][0])**2 + 
                           (positions[i][1] - positions[j][1])**2)**0.5
                if distance > 500.0:  # Bridges too far apart
                    return False
    return True


def _message_slotline_mode(data: dict[str, Any]) -> str:
    return "Ground bridges too far apart. May allow slotline mode propagation."


def _recommendation_slotline_mode(data: dict[str, Any]) -> str:
    return "Add ground bridges every <500 um to suppress slotline modes."


# Microwave rules
MICROWAVE_RULES = [
    Rule(
        name="flux_line_coupling",
        description="Flux line too close to resonator",
        category=RuleCategory.MICROWAVE,
        severity=RuleSeverity.WARNING,
        check_fn=_check_flux_line_coupling,
        message_fn=_message_flux_line_coupling,
        recommendation_fn=_recommendation_flux_line_coupling,
        affected_subsystem="resonator",
        confidence=0.8,
    ),
    Rule(
        name="cpw_gap_ratio",
        description="CPW gap-to-width ratio outside typical range",
        category=RuleCategory.MICROWAVE,
        severity=RuleSeverity.WARNING,
        check_fn=_check_cpw_gap_ratio,
        message_fn=_message_cpw_gap_ratio,
        recommendation_fn=_recommendation_cpw_gap_ratio,
        affected_subsystem="transmission_line",
        confidence=0.9,
    ),
    Rule(
        name="idc_aspect_ratio",
        description="IDC aspect ratio too high",
        category=RuleCategory.MICROWAVE,
        severity=RuleSeverity.WARNING,
        check_fn=_check_idc_aspect_ratio,
        message_fn=_message_idc_aspect_ratio,
        recommendation_fn=_recommendation_idc_aspect_ratio,
        affected_subsystem="capacitor",
        confidence=0.85,
    ),
    Rule(
        name="launch_pad_size",
        description="Launch pad too small for probe",
        category=RuleCategory.MICROWAVE,
        severity=RuleSeverity.ERROR,
        check_fn=_check_launch_pad_size,
        message_fn=_message_launch_pad_size,
        recommendation_fn=_recommendation_launch_pad_size,
        affected_subsystem="ports",
        confidence=0.9,
    ),
    Rule(
        name="slotline_mode",
        description="Ground bridges too far apart",
        category=RuleCategory.MICROWAVE,
        severity=RuleSeverity.WARNING,
        check_fn=_check_slotline_mode,
        message_fn=_message_slotline_mode,
        recommendation_fn=_recommendation_slotline_mode,
        affected_subsystem="grounding",
        confidence=0.75,
    ),
]
