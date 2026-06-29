"""Measurement engineering rules for superconducting circuits."""

from __future__ import annotations

from typing import Any

from text_to_gds.engineering_rules.rules import Rule, RuleCategory, RuleSeverity


def _check_rf_port_count(data: dict[str, Any]) -> bool:
    """Check RF port count for measurement capability."""
    features = data.get("geometry_features", [])
    launch_features = [f for f in features if f.get("feature_type") == "launch_pad"]
    
    # Need at least 2 RF ports for S-parameter measurement
    if len(launch_features) < 2:
        return False
    
    return True


def _message_rf_port_count(data: dict[str, Any]) -> str:
    return "Insufficient RF ports. Need at least 2 ports for S-parameter measurement."


def _recommendation_rf_port_count(data: dict[str, Any]) -> str:
    return "Add RF input and output ports for S-parameter measurement."


def _check_flux_port(data: dict[str, Any]) -> bool:
    """Check flux port availability for tunable devices."""
    features = data.get("geometry_features", [])
    flux_features = [f for f in features if f.get("feature_type") == "flux_line"]
    
    # If device is tunable, need flux port
    device_type = data.get("device_type", "")
    if device_type in ("lumped_jpa", "quarter_wave_jpa", "fluxonium"):
        if len(flux_features) == 0:
            return False
    
    return True


def _message_flux_port(data: dict[str, Any]) -> str:
    return "Tunable device without flux bias port. Cannot control operating point."


def _recommendation_flux_port(data: dict[str, Any]) -> str:
    return "Add flux bias port for tunable device operation."


def _check_dc_port(data: dict[str, Any]) -> bool:
    """Check DC port availability for biasing."""
    features = data.get("geometry_features", [])
    bond_features = [f for f in features if f.get("feature_type") == "bond_pad"]
    
    # Need at least 1 DC port for biasing
    if len(bond_features) == 0:
        return False
    
    return True


def _message_dc_port(data: dict[str, Any]) -> str:
    return "No DC bond pads detected. May limit biasing options."


def _recommendation_dc_port(data: dict[str, Any]) -> str:
    return "Add DC bond pads for biasing and measurement access."


def _check_probe_compatibility(data: dict[str, Any]) -> bool:
    """Check probe compatibility for on-wafer measurement."""
    features = data.get("geometry_features", [])
    launch_features = [f for f in features if f.get("feature_type") == "launch_pad"]
    
    for launch in launch_features:
        props = launch.get("engineering_properties", {})
        gsg_config = props.get("gsg_config", False)
        width = launch.get("dimensions", {}).get("pad_width_um", 0)
        
        # Check GSG probe compatibility
        if not gsg_config and width < 100.0:
            return False
    
    return True


def _message_probe_compatibility(data: dict[str, Any]) -> str:
    return "Launch pads may not be compatible with standard GSG probes."


def _recommendation_probe_compatibility(data: dict[str, Any]) -> str:
    return "Use GSG configuration with >100 um pad width for standard probe compatibility."


# Measurement rules
MEASUREMENT_RULES = [
    Rule(
        name="rf_port_count",
        description="Insufficient RF ports",
        category=RuleCategory.MEASUREMENT,
        severity=RuleSeverity.ERROR,
        check_fn=_check_rf_port_count,
        message_fn=_message_rf_port_count,
        recommendation_fn=_recommendation_rf_port_count,
        affected_subsystem="ports",
        confidence=0.9,
    ),
    Rule(
        name="flux_port",
        description="Tunable device without flux port",
        category=RuleCategory.MEASUREMENT,
        severity=RuleSeverity.WARNING,
        check_fn=_check_flux_port,
        message_fn=_message_flux_port,
        recommendation_fn=_recommendation_flux_port,
        affected_subsystem="flux_line",
        confidence=0.85,
    ),
    Rule(
        name="dc_port",
        description="No DC bond pads detected",
        category=RuleCategory.MEASUREMENT,
        severity=RuleSeverity.WARNING,
        check_fn=_check_dc_port,
        message_fn=_message_dc_port,
        recommendation_fn=_recommendation_dc_port,
        affected_subsystem="ports",
        confidence=0.8,
    ),
    Rule(
        name="probe_compatibility",
        description="Launch pads not probe compatible",
        category=RuleCategory.MEASUREMENT,
        severity=RuleSeverity.WARNING,
        check_fn=_check_probe_compatibility,
        message_fn=_message_probe_compatibility,
        recommendation_fn=_recommendation_probe_compatibility,
        affected_subsystem="ports",
        confidence=0.85,
    ),
]
