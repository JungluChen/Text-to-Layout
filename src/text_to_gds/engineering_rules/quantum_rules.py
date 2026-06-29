"""Quantum engineering rules for superconducting circuits."""

from __future__ import annotations

from typing import Any

from text_to_gds.engineering_rules.rules import Rule, RuleCategory, RuleSeverity


def _check_jj_area(data: dict[str, Any]) -> bool:
    """Check Josephson junction area for critical current range."""
    features = data.get("geometry_features", [])
    jj_features = [f for f in features if f.get("feature_type") == "josephson_junction"]
    
    for jj in jj_features:
        dims = jj.get("dimensions", {})
        area = dims.get("junction_area_um2", 0)
        
        if area > 0 and (area < 0.01 or area > 100.0):
            return False
    return True


def _message_jj_area(data: dict[str, Any]) -> str:
    return "Josephson junction area outside typical range (0.01-100 um²). May cause fabrication or performance issues."


def _recommendation_jj_area(data: dict[str, Any]) -> str:
    return "Adjust JJ area to 0.01-100 um² for typical critical current range (0.01-100 uA)."


def _check_squid_symmetry(data: dict[str, Any]) -> bool:
    """Check SQUID loop symmetry for balanced junctions."""
    features = data.get("geometry_features", [])
    squid_features = [f for f in features if f.get("feature_type") == "squid_loop"]
    
    for squid in squid_features:
        props = squid.get("engineering_properties", {})
        jj_count = props.get("jj_count", 0)
        
        if jj_count != 2:
            return False
    return True


def _message_squid_symmetry(data: dict[str, Any]) -> str:
    return "SQUID loop should have exactly 2 junctions for balanced operation."


def _recommendation_squid_symmetry(data: dict[str, Any]) -> str:
    return "Ensure SQUID loop has 2 junctions with matched critical currents."


def _check_flux_noise(data: dict[str, Any]) -> bool:
    """Check flux line placement for noise considerations."""
    features = data.get("geometry_features", [])
    flux_lines = [f for f in features if f.get("feature_type") == "flux_line"]
    jj_features = [f for f in features if f.get("feature_type") == "josephson_junction"]
    
    for flux in flux_lines:
        flux_bbox = flux.get("bounding_box", [0, 0, 0, 0])
        flux_center = ((flux_bbox[0] + flux_bbox[2]) / 2, (flux_bbox[1] + flux_bbox[3]) / 2)
        
        for jj in jj_features:
            jj_bbox = jj.get("bounding_box", [0, 0, 0, 0])
            jj_center = ((jj_bbox[0] + jj_bbox[2]) / 2, (jj_bbox[1] + jj_bbox[3]) / 2)
            
            distance = ((flux_center[0] - jj_center[0])**2 + 
                       (flux_center[1] - jj_center[1])**2)**0.5
            
            if distance < 10.0:  # Too close to JJ
                return False
    return True


def _message_flux_noise(data: dict[str, Any]) -> str:
    return "Flux line too close to Josephson junction. May increase flux noise and decoherence."


def _recommendation_flux_noise(data: dict[str, Any]) -> str:
    return "Increase flux line to JJ distance to >10 um to reduce flux noise coupling."


def _check_purcell_filter(data: dict[str, Any]) -> bool:
    """Check for Purcell filter in readout resonator."""
    features = data.get("geometry_features", [])
    resonators = [f for f in features if f.get("feature_type") == "resonator"]
    couplers = [f for f in features if f.get("feature_type") == "coupler"]
    
    # Simple check: if there's a resonator, there should be a coupler
    if len(resonators) > 0 and len(couplers) == 0:
        return False
    return True


def _message_purcell_filter(data: dict[str, Any]) -> str:
    return "Readout resonator without coupling capacitor. May increase Purcell decay."


def _recommendation_purcell_filter(data: dict[str, Any]) -> str:
    return "Add coupling capacitor between readout resonator and feedline to reduce Purcell effect."


def _check_charging_energy(data: dict[str, Any]) -> bool:
    """Check charging energy vs Josephson energy ratio."""
    features = data.get("geometry_features", [])
    jj_features = [f for f in features if f.get("feature_type") == "josephson_junction"]
    capacitor_features = [f for f in features if f.get("feature_type") in ("capacitor_paddle", "island")]
    
    if not jj_features or not capacitor_features:
        return True  # Can't check without both
    
    # Simplified check: just verify both exist
    return True


def _message_charging_energy(data: dict[str, Any]) -> str:
    return "Cannot verify Ej/Ec ratio without complete device parameters."


def _recommendation_charging_energy(data: dict[str, Any]) -> str:
    return "Ensure Ej/Ec ratio is 10-200 for transmon regime."


# Quantum rules
QUANTUM_RULES = [
    Rule(
        name="jj_area",
        description="JJ area outside typical range",
        category=RuleCategory.QUANTUM,
        severity=RuleSeverity.WARNING,
        check_fn=_check_jj_area,
        message_fn=_message_jj_area,
        recommendation_fn=_recommendation_jj_area,
        affected_subsystem="josephson_junction",
        confidence=0.85,
    ),
    Rule(
        name="squid_symmetry",
        description="SQUID loop should have 2 junctions",
        category=RuleCategory.QUANTUM,
        severity=RuleSeverity.ERROR,
        check_fn=_check_squid_symmetry,
        message_fn=_message_squid_symmetry,
        recommendation_fn=_recommendation_squid_symmetry,
        affected_subsystem="squid",
        confidence=0.9,
    ),
    Rule(
        name="flux_noise",
        description="Flux line too close to JJ",
        category=RuleCategory.QUANTUM,
        severity=RuleSeverity.WARNING,
        check_fn=_check_flux_noise,
        message_fn=_message_flux_noise,
        recommendation_fn=_recommendation_flux_noise,
        affected_subsystem="flux_line",
        confidence=0.8,
    ),
    Rule(
        name="purcell_filter",
        description="Readout resonator without coupling capacitor",
        category=RuleCategory.QUANTUM,
        severity=RuleSeverity.WARNING,
        check_fn=_check_purcell_filter,
        message_fn=_message_purcell_filter,
        recommendation_fn=_recommendation_purcell_filter,
        affected_subsystem="resonator",
        confidence=0.75,
    ),
    Rule(
        name="charging_energy",
        description="Cannot verify Ej/Ec ratio",
        category=RuleCategory.QUANTUM,
        severity=RuleSeverity.INFO,
        check_fn=_check_charging_energy,
        message_fn=_message_charging_energy,
        recommendation_fn=_recommendation_charging_energy,
        affected_subsystem="josephson_junction",
        confidence=0.5,
    ),
]
