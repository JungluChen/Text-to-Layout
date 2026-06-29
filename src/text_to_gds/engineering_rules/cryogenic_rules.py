"""Cryogenic engineering rules for superconducting circuits."""

from __future__ import annotations

from typing import Any

from text_to_gds.engineering_rules.rules import Rule, RuleCategory, RuleSeverity


def _check_thermal_mass(data: dict[str, Any]) -> bool:
    """Check thermal mass for cooldown time."""
    features = data.get("geometry_features", [])
    
    # Calculate total feature area
    total_area = 0.0
    for feature in features:
        bbox = feature.get("bounding_box", [0, 0, 0, 0])
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        total_area += area
    
    # Large area may cause long cooldown
    if total_area > 1e6:  # >1 mm²
        return False
    
    return True


def _message_thermal_mass(data: dict[str, Any]) -> str:
    return "Large feature area may cause long cooldown times."


def _recommendation_thermal_mass(data: dict[str, Any]) -> str:
    return "Consider thermalization features or distributed ground plane for faster cooldown."


def _check_filtration(data: dict[str, Any]) -> bool:
    """Check for filtration on DC lines."""
    features = data.get("geometry_features", [])
    bond_features = [f for f in features if f.get("feature_type") == "bond_pad"]
    
    # Need RC filters on DC lines for noise reduction
    # Simplified check: just verify DC ports exist
    if len(bond_features) == 0:
        return True  # No DC ports, no filter needed
    
    # In real design, would check for filter components
    return True


def _message_filtration(data: dict[str, Any]) -> str:
    return "DC lines may need RC filtering for noise reduction."


def _recommendation_filtration(data: dict[str, Any]) -> str:
    return "Add RC filters (10-100 kHz cutoff) on DC bias lines."


def _check_heat_load(data: dict[str, Any]) -> bool:
    """Check heat load from signal lines."""
    features = data.get("geometry_features", [])
    launch_features = [f for f in features if f.get("feature_type") == "launch_pad"]
    
    # Multiple RF lines increase heat load
    if len(launch_features) > 4:
        return False
    
    return True


def _message_heat_load(data: dict[str, Any]) -> str:
    return "Many RF lines may increase heat load on cryostat."


def _recommendation_heat_load(data: dict[str, Any]) -> str:
    return "Minimize number of RF lines or use attenuators to reduce heat load."


def _check_thermal_anchor(data: dict[str, Any]) -> bool:
    """Check for thermal anchor points."""
    features = data.get("geometry_features", [])
    ground_features = [f for f in features if f.get("feature_type") in ("ground_pocket", "ground_bridge")]
    
    # Need ground connections for thermal anchoring
    if len(ground_features) == 0:
        return False
    
    return True


def _message_thermal_anchor(data: dict[str, Any]) -> str:
    return "No ground connections for thermal anchoring."


def _recommendation_thermal_anchor(data: dict[str, Any]) -> str:
    return "Add ground connections to thermalize device to ground plane."


# Cryogenic rules
CRYOGENIC_RULES = [
    Rule(
        name="thermal_mass",
        description="Large feature area",
        category=RuleCategory.CRYOGENIC,
        severity=RuleSeverity.INFO,
        check_fn=_check_thermal_mass,
        message_fn=_message_thermal_mass,
        recommendation_fn=_recommendation_thermal_mass,
        affected_subsystem="cryogenic",
        confidence=0.7,
    ),
    Rule(
        name="filtration",
        description="DC lines may need filtering",
        category=RuleCategory.CRYOGENIC,
        severity=RuleSeverity.INFO,
        check_fn=_check_filtration,
        message_fn=_message_filtration,
        recommendation_fn=_recommendation_filtration,
        affected_subsystem="cryogenic",
        confidence=0.6,
    ),
    Rule(
        name="heat_load",
        description="Many RF lines",
        category=RuleCategory.CRYOGENIC,
        severity=RuleSeverity.WARNING,
        check_fn=_check_heat_load,
        message_fn=_message_heat_load,
        recommendation_fn=_recommendation_heat_load,
        affected_subsystem="cryogenic",
        confidence=0.75,
    ),
    Rule(
        name="thermal_anchor",
        description="No ground connections",
        category=RuleCategory.CRYOGENIC,
        severity=RuleSeverity.WARNING,
        check_fn=_check_thermal_anchor,
        message_fn=_message_thermal_anchor,
        recommendation_fn=_recommendation_thermal_anchor,
        affected_subsystem="cryogenic",
        confidence=0.8,
    ),
]
