"""Packaging engineering rules for superconducting circuits."""

from __future__ import annotations

from typing import Any

from text_to_gds.engineering_rules.rules import Rule, RuleCategory, RuleSeverity


def _check_wirebond_count(data: dict[str, Any]) -> bool:
    """Check wirebond count for reliable grounding."""
    features = data.get("geometry_features", [])
    bond_features = [f for f in features if f.get("feature_type") == "bond_pad"]
    
    # Need at least 2 wirebonds for good grounding
    if len(bond_features) < 2:
        return False
    
    return True


def _message_wirebond_count(data: dict[str, Any]) -> str:
    return "Insufficient wirebond pads. May cause poor grounding and increased inductance."


def _recommendation_wirebond_count(data: dict[str, Any]) -> str:
    return "Add at least 2 wirebond pads for reliable ground connection."


def _check_wirebond_placement(data: dict[str, Any]) -> bool:
    """Check wirebond placement near critical features."""
    features = data.get("geometry_features", [])
    bond_features = [f for f in features if f.get("feature_type") == "bond_pad"]
    jj_features = [f for f in features if f.get("feature_type") == "josephson_junction"]
    
    for bond in bond_features:
        bond_bbox = bond.get("bounding_box", [0, 0, 0, 0])
        bond_center = ((bond_bbox[0] + bond_bbox[2]) / 2, (bond_bbox[1] + bond_bbox[3]) / 2)
        
        for jj in jj_features:
            jj_bbox = jj.get("bounding_box", [0, 0, 0, 0])
            jj_center = ((jj_bbox[0] + jj_bbox[2]) / 2, (jj_bbox[1] + jj_bbox[3]) / 2)
            
            distance = ((bond_center[0] - jj_center[0])**2 + 
                       (bond_center[1] - jj_center[1])**2)**0.5
            
            if distance < 50.0:  # Too close to JJ
                return False
    
    return True


def _message_wirebond_placement(data: dict[str, Any]) -> str:
    return "Wirebond too close to Josephson junction. May cause mechanical stress or flux trapping."


def _recommendation_wirebond_placement(data: dict[str, Any]) -> str:
    return "Move wirebond pads >50 um away from Josephson junctions."


def _check_chip_edge_clearance(data: dict[str, Any]) -> bool:
    """Check chip edge clearance for features."""
    features = data.get("geometry_features", [])
    
    chip_size = data.get("chip_size_um", [10000, 10000])  # Default 10mm x 10mm
    
    for feature in features:
        bbox = feature.get("bounding_box", [0, 0, 0, 0])
        
        # Check if feature is too close to chip edge
        if bbox[0] < 100.0 or bbox[1] < 100.0:
            return False
        if bbox[2] > chip_size[0] - 100.0 or bbox[3] > chip_size[1] - 100.0:
            return False
    
    return True


def _message_chip_edge_clearance(data: dict[str, Any]) -> str:
    return "Feature too close to chip edge. May cause handling or dicing issues."


def _recommendation_chip_edge_clearance(data: dict[str, Any]) -> str:
    return "Maintain >100 um clearance from chip edge for all features."


def _check_grounding_strategy(data: dict[str, Any]) -> bool:
    """Check grounding strategy for consistent ground potential."""
    features = data.get("geometry_features", [])
    ground_features = [f for f in features if f.get("feature_type") in ("ground_pocket", "ground_bridge")]
    
    # Need at least one ground feature
    if len(ground_features) == 0:
        return False
    
    return True


def _message_grounding_strategy(data: dict[str, Any]) -> str:
    return "No ground plane or ground bridges detected. May cause ground loops."


def _recommendation_grounding_strategy(data: dict[str, Any]) -> str:
    return "Add ground plane with via fencing for consistent ground potential."


# Packaging rules
PACKAGING_RULES = [
    Rule(
        name="wirebond_count",
        description="Insufficient wirebond pads",
        category=RuleCategory.PACKAGING,
        severity=RuleSeverity.WARNING,
        check_fn=_check_wirebond_count,
        message_fn=_message_wirebond_count,
        recommendation_fn=_recommendation_wirebond_count,
        affected_subsystem="packaging",
        confidence=0.8,
    ),
    Rule(
        name="wirebond_placement",
        description="Wirebond too close to JJ",
        category=RuleCategory.PACKAGING,
        severity=RuleSeverity.WARNING,
        check_fn=_check_wirebond_placement,
        message_fn=_message_wirebond_placement,
        recommendation_fn=_recommendation_wirebond_placement,
        affected_subsystem="packaging",
        confidence=0.85,
    ),
    Rule(
        name="chip_edge_clearance",
        description="Feature too close to chip edge",
        category=RuleCategory.PACKAGING,
        severity=RuleSeverity.WARNING,
        check_fn=_check_chip_edge_clearance,
        message_fn=_message_chip_edge_clearance,
        recommendation_fn=_recommendation_chip_edge_clearance,
        affected_subsystem="packaging",
        confidence=0.9,
    ),
    Rule(
        name="grounding_strategy",
        description="No ground plane detected",
        category=RuleCategory.PACKAGING,
        severity=RuleSeverity.WARNING,
        check_fn=_check_grounding_strategy,
        message_fn=_message_grounding_strategy,
        recommendation_fn=_recommendation_grounding_strategy,
        affected_subsystem="grounding",
        confidence=0.85,
    ),
]
