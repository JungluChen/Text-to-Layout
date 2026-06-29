"""Fabrication engineering rules for superconducting circuits."""

from __future__ import annotations

from typing import Any

from text_to_gds.engineering_rules.rules import Rule, RuleCategory, RuleSeverity


def _check_min_width(data: dict[str, Any]) -> bool:
    """Check minimum feature width for fabrication."""
    features = data.get("geometry_features", [])
    
    for feature in features:
        dims = feature.get("dimensions", {})
        
        # Check various width parameters
        for key in ["center_width_um", "line_width_um", "finger_width_um", "min_width_um"]:
            width = dims.get(key, 0)
            if width > 0 and width < 1.0:
                return False
    
    return True


def _message_min_width(data: dict[str, Any]) -> str:
    return "Feature width below 1 um. May cause fabrication issues with standard processes."


def _recommendation_min_width(data: dict[str, Any]) -> str:
    return "Increase feature width to >1 um for standard fabrication processes."


def _check_min_spacing(data: dict[str, Any]) -> bool:
    """Check minimum spacing between features."""
    features = data.get("geometry_features", [])
    
    # Simple check: verify no overlapping bounding boxes (excluding connections)
    for i, f1 in enumerate(features):
        for j, f2 in enumerate(features):
            if i >= j:
                continue
            
            bbox1 = f1.get("bounding_box", [0, 0, 0, 0])
            bbox2 = f2.get("bounding_box", [0, 0, 0, 0])
            
            # Check for overlap
            if (bbox1[0] < bbox2[2] and bbox1[2] > bbox2[0] and
                bbox1[1] < bbox2[3] and bbox1[3] > bbox2[1]):
                # Check if they're supposed to be connected
                connected_nets = f1.get("connected_nets", [])
                if f2.get("id") not in connected_nets:
                    return False
    
    return True


def _message_min_spacing(data: dict[str, Any]) -> str:
    return "Features too close or overlapping. May cause short circuits."


def _recommendation_min_spacing(data: dict[str, Any]) -> str:
    return "Increase spacing between unconnected features to >1 um."


def _check_jj_overlap(data: dict[str, Any]) -> bool:
    """Check Josephson junction overlap area."""
    features = data.get("geometry_features", [])
    jj_features = [f for f in features if f.get("feature_type") == "josephson_junction"]
    
    for jj in jj_features:
        dims = jj.get("dimensions", {})
        area = dims.get("junction_area_um2", 0)
        
        if area > 0 and area < 0.01:
            return False
    
    return True


def _message_jj_overlap(data: dict[str, Any]) -> str:
    return "JJ overlap area too small. May cause unreliable junction formation."


def _recommendation_jj_overlap(data: dict[str, Any]) -> str:
    return "Increase JJ overlap area to >0.01 um² for reliable junction formation."


def _check_via_enclosure(data: dict[str, Any]) -> bool:
    """Check via enclosure rules."""
    features = data.get("geometry_features", [])
    via_features = [f for f in features if f.get("feature_type") == "via_fence"]
    
    for via in via_features:
        dims = via.get("dimensions", {})
        diameter = dims.get("via_diameter_um", 0)
        
        if diameter > 0 and diameter < 2.0:
            return False
    
    return True


def _message_via_enclosure(data: dict[str, Any]) -> str:
    return "Via diameter too small. May cause unreliable via formation."


def _recommendation_via_enclosure(data: dict[str, Any]) -> str:
    return "Increase via diameter to >2 um for reliable via formation."


def _check_airbridge_clearance(data: dict[str, Any]) -> bool:
    """Check airbridge clearance rules."""
    features = data.get("geometry_features", [])
    airbridge_features = [f for f in features if f.get("feature_type") == "airbridge"]
    
    for bridge in airbridge_features:
        dims = bridge.get("dimensions", {})
        span = dims.get("bridge_span_um", 0)
        
        if span > 200.0:
            return False
    
    return True


def _message_airbridge_clearance(data: dict[str, Any]) -> str:
    return "Airbridge span >200 um. May cause mechanical instability."


def _recommendation_airbridge_clearance(data: dict[str, Any]) -> str:
    return "Reduce airbridge span to <200 um for mechanical reliability."


# Fabrication rules
FABRICATION_RULES = [
    Rule(
        name="min_width",
        description="Feature width below minimum",
        category=RuleCategory.FABRICATION,
        severity=RuleSeverity.ERROR,
        check_fn=_check_min_width,
        message_fn=_message_min_width,
        recommendation_fn=_recommendation_min_width,
        affected_subsystem="all",
        confidence=0.9,
    ),
    Rule(
        name="min_spacing",
        description="Features too close or overlapping",
        category=RuleCategory.FABRICATION,
        severity=RuleSeverity.ERROR,
        check_fn=_check_min_spacing,
        message_fn=_message_min_spacing,
        recommendation_fn=_recommendation_min_spacing,
        affected_subsystem="all",
        confidence=0.85,
    ),
    Rule(
        name="jj_overlap",
        description="JJ overlap area too small",
        category=RuleCategory.FABRICATION,
        severity=RuleSeverity.WARNING,
        check_fn=_check_jj_overlap,
        message_fn=_message_jj_overlap,
        recommendation_fn=_recommendation_jj_overlap,
        affected_subsystem="josephson_junction",
        confidence=0.8,
    ),
    Rule(
        name="via_enclosure",
        description="Via diameter too small",
        category=RuleCategory.FABRICATION,
        severity=RuleSeverity.WARNING,
        check_fn=_check_via_enclosure,
        message_fn=_message_via_enclosure,
        recommendation_fn=_recommendation_via_enclosure,
        affected_subsystem="via_fence",
        confidence=0.85,
    ),
    Rule(
        name="airbridge_clearance",
        description="Airbridge span too large",
        category=RuleCategory.FABRICATION,
        severity=RuleSeverity.WARNING,
        check_fn=_check_airbridge_clearance,
        message_fn=_message_airbridge_clearance,
        recommendation_fn=_recommendation_airbridge_clearance,
        affected_subsystem="airbridge",
        confidence=0.8,
    ),
]
