"""Topology classifiers with evidence-based reasoning.

Each classifier analyzes geometry features and returns a classification
with supporting evidence, missing evidence, and alternative hypotheses.
"""

from __future__ import annotations

from typing import Any

from textlayout._legacy.topology_reasoning.evidence import EvidenceType, TopologyEvidence, TopologyClassification


def classify_pocket_transmon(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify a pocket transmon topology.
    
    Pocket transmons have:
    - Single Josephson junction
    - Ground plane with pocket
    - Capacitor paddles (IDC or pads)
    - Readout resonator
    - Flux bias line (optional)
    """
    classification = TopologyClassification(topology="pocket_transmon")
    
    # Check for JJ
    jj_count = features.get("jj_count", 0)
    if jj_count == 1:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Single Josephson junction detected",
            supporting=True,
            confidence=0.9,
        ))
    elif jj_count == 0:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No Josephson junction detected",
            supporting=False,
            confidence=1.0,
        ))
        classification.confidence = 0.0
        return classification
    else:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.PARAMETER_MISMATCH,
            description=f"Expected 1 JJ, found {jj_count}",
            supporting=False,
            confidence=0.8,
        ))
        classification.confidence = 0.3
    
    # Check for ground plane
    if features.get("has_ground_plane"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Ground plane present",
            supporting=True,
            confidence=0.9,
        ))
    
    # Check for capacitor paddles
    if features.get("idc_count", 0) > 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="IDC capacitor paddles present",
            supporting=True,
            confidence=0.85,
        ))
    
    # Check for resonator
    if features.get("cpw_count", 0) > 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Readout resonator present",
            supporting=True,
            confidence=0.8,
        ))
    
    # Check for launch pads
    if features.get("has_launch_pads"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Launch pads present",
            supporting=True,
            confidence=0.9,
        ))
    
    # Check for flux line
    if features.get("has_flux_line"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Flux bias line present",
            supporting=True,
            confidence=0.7,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    missing_count = len(classification.missing_evidence)
    
    if supporting_count > 0:
        base_confidence = min(supporting_count / 5.0, 1.0)
        penalty = missing_count * 0.1
        classification.confidence = max(0.0, base_confidence - penalty)
    
    # Add alternative hypotheses
    classification.alternative_hypotheses.append({
        "topology": "xmon",
        "confidence": 0.3,
        "reason": "Similar JJ count, but different capacitor geometry",
    })
    
    classification.classification_reasoning = (
        f"Pocket transmon classification based on {supporting_count} supporting "
        f"features and {missing_count} missing features. "
        f"Key features: single JJ, ground plane, capacitor paddles."
    )
    
    return classification


def classify_xmon(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify an Xmon topology.
    
    Xmons have:
    - Single Josephson junction
    - Cross-shaped capacitor arms
    - Ground plane
    - Fixed frequency (no flux line)
    """
    classification = TopologyClassification(topology="xmon")
    
    # Check for JJ
    jj_count = features.get("jj_count", 0)
    if jj_count == 1:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Single Josephson junction detected",
            supporting=True,
            confidence=0.9,
        ))
    elif jj_count == 0:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No Josephson junction detected",
            supporting=False,
            confidence=1.0,
        ))
        classification.confidence = 0.0
        return classification
    
    # Check for ground plane
    if features.get("has_ground_plane"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Ground plane present",
            supporting=True,
            confidence=0.9,
        ))
    
    # Check for cross-shaped arms (implied by no IDC/CPW)
    if features.get("idc_count", 0) == 0 and features.get("cpw_count", 0) == 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.TOPOLOGICAL_FEATURE,
            description="Cross-shaped arms implied (no IDC/CPW)",
            supporting=True,
            confidence=0.7,
        ))
    
    # Check for fixed frequency (no flux line)
    if not features.get("has_flux_line"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No flux line (fixed frequency compatible)",
            supporting=True,
            confidence=0.8,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    classification.confidence = min(supporting_count / 4.0, 1.0)
    
    classification.alternative_hypotheses.append({
        "topology": "pocket_transmon",
        "confidence": 0.4,
        "reason": "Similar JJ count, but different capacitor geometry",
    })
    
    classification.classification_reasoning = (
        f"Xmon classification based on {supporting_count} supporting features. "
        f"Key features: single JJ, cross-shaped arms, fixed frequency."
    )
    
    return classification


def classify_concentric_transmon(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify a concentric transmon topology.
    
    Concentric transmons have:
    - Single Josephson junction
    - Concentric capacitor geometry
    - Ground plane
    - No SQUID loop
    """
    classification = TopologyClassification(topology="concentric_transmon")
    
    # Check for JJ
    jj_count = features.get("jj_count", 0)
    if jj_count == 1:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Single Josephson junction detected",
            supporting=True,
            confidence=0.9,
        ))
    elif jj_count == 0:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No Josephson junction detected",
            supporting=False,
            confidence=1.0,
        ))
        classification.confidence = 0.0
        return classification
    
    # Check for ground plane
    if features.get("has_ground_plane"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Ground plane present",
            supporting=True,
            confidence=0.8,
        ))
    
    # Check for IDC
    if features.get("idc_count", 0) > 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="IDC present",
            supporting=True,
            confidence=0.7,
        ))
    
    # Check for no SQUID
    if not features.get("squid_detected"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No SQUID loop (concentric pattern)",
            supporting=True,
            confidence=0.8,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    classification.confidence = min(supporting_count / 4.0, 1.0)
    
    classification.alternative_hypotheses.append({
        "topology": "pocket_transmon",
        "confidence": 0.3,
        "reason": "Similar JJ count, but different capacitor geometry",
    })
    
    classification.classification_reasoning = (
        f"Concentric transmon classification based on {supporting_count} supporting features. "
        f"Key features: single JJ, concentric geometry, no SQUID."
    )
    
    return classification


def classify_fluxonium(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify a fluxonium topology.
    
    Fluxoniums have:
    - Single Josephson junction
    - Meander inductor
    - Flux bias line
    - Ground plane
    """
    classification = TopologyClassification(topology="fluxonium")
    
    # Check for JJ
    jj_count = features.get("jj_count", 0)
    if jj_count == 1:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Single Josephson junction detected",
            supporting=True,
            confidence=0.9,
        ))
    elif jj_count == 0:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No Josephson junction detected",
            supporting=False,
            confidence=1.0,
        ))
        classification.confidence = 0.0
        return classification
    
    # Check for ground plane
    if features.get("has_ground_plane"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Ground plane present",
            supporting=True,
            confidence=0.8,
        ))
    
    # Check for meander
    if features.get("has_meander"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Meander inductor present",
            supporting=True,
            confidence=0.9,
        ))
    else:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No meander inductor detected",
            supporting=False,
            confidence=0.9,
        ))
    
    # Check for flux line
    if features.get("has_flux_line"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Flux bias line present",
            supporting=True,
            confidence=0.85,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    missing_count = len(classification.missing_evidence)
    classification.confidence = max(0.0, min(supporting_count / 4.0, 1.0) - missing_count * 0.15)
    
    classification.alternative_hypotheses.append({
        "topology": "pocket_transmon",
        "confidence": 0.2,
        "reason": "Similar JJ count, but fluxonium has meander inductor",
    })
    
    classification.classification_reasoning = (
        f"Fluxonium classification based on {supporting_count} supporting features "
        f"and {missing_count} missing features. "
        f"Key features: single JJ, meander inductor, flux bias line."
    )
    
    return classification


def classify_lumped_jpa(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify a lumped JPA topology.
    
    Lumped JPAs have:
    - SQUID loop (2 JJs)
    - IDC shunt capacitor
    - Flux bias line (pump)
    - RF input/output ports
    """
    classification = TopologyClassification(topology="lumped_jpa")
    
    # Check for SQUID
    if features.get("squid_detected"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="SQUID loop detected",
            supporting=True,
            confidence=0.95,
        ))
    elif features.get("jj_count", 0) >= 1:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="JJ present (no SQUID)",
            supporting=True,
            confidence=0.6,
        ))
    else:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No JJ/SQUID detected",
            supporting=False,
            confidence=1.0,
        ))
        classification.confidence = 0.0
        return classification
    
    # Check for IDC
    if features.get("idc_count", 0) > 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="IDC shunt capacitor present",
            supporting=True,
            confidence=0.9,
        ))
    
    # Check for flux line
    if features.get("has_flux_line"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Flux bias line for pump",
            supporting=True,
            confidence=0.9,
        ))
    
    # Check for launch pads
    if features.get("has_launch_pads"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Launch pads present",
            supporting=True,
            confidence=0.85,
        ))
    
    # Check for port count
    if features.get("port_count", 0) >= 3:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="3+ ports (RF in/out + pump)",
            supporting=True,
            confidence=0.8,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    classification.confidence = min(supporting_count / 5.0, 1.0)
    
    classification.alternative_hypotheses.append({
        "topology": "quarter_wave_jpa",
        "confidence": 0.3,
        "reason": "Similar SQUID, but different transmission line structure",
    })
    
    classification.classification_reasoning = (
        f"Lumped JPA classification based on {supporting_count} supporting features. "
        f"Key features: SQUID loop, IDC capacitor, flux pump."
    )
    
    return classification


def classify_quarter_wave_jpa(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify a quarter-wave JPA topology.
    
    Quarter-wave JPAs have:
    - SQUID loaded transmission line
    - CPW line
    - Flux bias line
    - Ground plane
    """
    classification = TopologyClassification(topology="quarter_wave_jpa")
    
    # Check for SQUID
    if features.get("squid_detected"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="SQUID loaded line detected",
            supporting=True,
            confidence=0.9,
        ))
    elif features.get("jj_count", 0) >= 1:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="JJ present",
            supporting=True,
            confidence=0.6,
        ))
    else:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No JJ detected",
            supporting=False,
            confidence=1.0,
        ))
        classification.confidence = 0.0
        return classification
    
    # Check for CPW
    if features.get("cpw_count", 0) > 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="CPW transmission line present",
            supporting=True,
            confidence=0.85,
        ))
    
    # Check for long CPW
    cpw_lengths = features.get("cpw_lengths_um", [])
    if cpw_lengths:
        max_len = max(cpw_lengths)
        if max_len > 500:
            classification.supporting_evidence.append(TopologyEvidence(
                evidence_type=EvidenceType.DIMENSIONAL_MATCH,
                description=f"Long CPW ({max_len:.0f} um) suggests quarter-wave",
                supporting=True,
                confidence=0.8,
            ))
    
    # Check for flux line
    if features.get("has_flux_line"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Flux bias line present",
            supporting=True,
            confidence=0.85,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    classification.confidence = min(supporting_count / 4.0, 1.0)
    
    classification.alternative_hypotheses.append({
        "topology": "lumped_jpa",
        "confidence": 0.3,
        "reason": "Similar SQUID, but different transmission line structure",
    })
    
    classification.classification_reasoning = (
        f"Quarter-wave JPA classification based on {supporting_count} supporting features. "
        f"Key features: SQUID loaded line, long CPW, flux bias."
    )
    
    return classification


def classify_twpa(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify a TWPA (Traveling Wave Parametric Amplifier) topology.
    
    TWPAs have:
    - JJ array (multiple JJs)
    - CPW line
    - Flux bias line
    - Ground plane
    """
    classification = TopologyClassification(topology="twpa")
    
    # Check for JJ array
    jj_count = features.get("jj_count", 0)
    if jj_count >= 2:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description=f"{jj_count} JJs detected (JJ chain)",
            supporting=True,
            confidence=0.85,
        ))
    elif jj_count == 0:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No JJ detected",
            supporting=False,
            confidence=1.0,
        ))
        classification.confidence = 0.0
        return classification
    
    # Check for CPW
    if features.get("cpw_count", 0) > 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="CPW line present",
            supporting=True,
            confidence=0.8,
        ))
    
    # Check for flux line
    if features.get("has_flux_line"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Flux bias line present",
            supporting=True,
            confidence=0.8,
        ))
    
    # Check for ground plane
    if features.get("has_ground_plane"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Ground plane present",
            supporting=True,
            confidence=0.8,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    classification.confidence = min(supporting_count / 4.0, 1.0)
    
    classification.alternative_hypotheses.append({
        "topology": "jj_array",
        "confidence": 0.2,
        "reason": "Similar JJ count, but TWPA has CPW line",
    })
    
    classification.classification_reasoning = (
        f"TWPA classification based on {supporting_count} supporting features. "
        f"Key features: JJ array, CPW line, flux bias."
    )
    
    return classification


def classify_cpw_resonator(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify a CPW resonator topology.
    
    CPW resonators have:
    - CPW transmission line
    - Ground plane
    - No JJ
    - Launch pads
    """
    classification = TopologyClassification(topology="cpw_resonator")
    
    # Check for no JJ
    if features.get("jj_count", 0) > 0:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="JJ detected (not pure resonator)",
            supporting=False,
            confidence=0.9,
        ))
        classification.confidence = 0.0
        return classification
    
    # Check for CPW
    if features.get("cpw_count", 0) > 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="CPW transmission line present",
            supporting=True,
            confidence=0.9,
        ))
    
    # Check for ground plane
    if features.get("has_ground_plane"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Ground plane present",
            supporting=True,
            confidence=0.85,
        ))
    
    # Check for launch pads
    if features.get("has_launch_pads"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Launch pads present",
            supporting=True,
            confidence=0.9,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    classification.confidence = min(supporting_count / 3.0, 1.0)
    
    classification.alternative_hypotheses.append({
        "topology": "idc_resonator",
        "confidence": 0.2,
        "reason": "Similar resonator structure, but different capacitor type",
    })
    
    classification.classification_reasoning = (
        f"CPW resonator classification based on {supporting_count} supporting features. "
        f"Key features: CPW line, no JJ, ground plane."
    )
    
    return classification


def classify_idc_resonator(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify an IDC resonator topology.
    
    IDC resonators have:
    - IDC capacitor
    - Inductive element (meander or CPW)
    - Ground plane
    - No JJ
    """
    classification = TopologyClassification(topology="idc_resonator")
    
    # Check for no JJ
    if features.get("jj_count", 0) > 0:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="JJ detected (not pure IDC resonator)",
            supporting=False,
            confidence=0.9,
        ))
        classification.confidence = 0.0
        return classification
    
    # Check for IDC
    if features.get("idc_count", 0) > 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="IDC capacitor present",
            supporting=True,
            confidence=0.9,
        ))
    
    # Check for inductive element
    if features.get("has_meander") or features.get("cpw_count", 0) > 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Inductive element present",
            supporting=True,
            confidence=0.85,
        ))
    
    # Check for ground plane
    if features.get("has_ground_plane"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Ground plane present",
            supporting=True,
            confidence=0.85,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    classification.confidence = min(supporting_count / 3.0, 1.0)
    
    classification.alternative_hypotheses.append({
        "topology": "cpw_resonator",
        "confidence": 0.2,
        "reason": "Similar resonator structure, but different capacitor type",
    })
    
    classification.classification_reasoning = (
        f"IDC resonator classification based on {supporting_count} supporting features. "
        f"Key features: IDC capacitor, inductive element, no JJ."
    )
    
    return classification


def classify_jj_array(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify a JJ array topology.
    
    JJ arrays have:
    - Multiple JJs (>=2)
    - No SQUID loop
    - Ground plane
    """
    classification = TopologyClassification(topology="jj_array")
    
    # Check for JJ array
    jj_count = features.get("jj_count", 0)
    if jj_count >= 2:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description=f"{jj_count} JJs detected (array pattern)",
            supporting=True,
            confidence=0.85,
        ))
    elif jj_count == 0:
        classification.missing_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No JJ detected",
            supporting=False,
            confidence=1.0,
        ))
        classification.confidence = 0.0
        return classification
    
    # Check for no SQUID
    if not features.get("squid_detected"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No SQUID loop (array pattern)",
            supporting=True,
            confidence=0.8,
        ))
    
    # Check for ground plane
    if features.get("has_ground_plane"):
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description="Ground plane present",
            supporting=True,
            confidence=0.8,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    classification.confidence = min(supporting_count / 3.0, 1.0)
    
    classification.alternative_hypotheses.append({
        "topology": "twpa",
        "confidence": 0.2,
        "reason": "Similar JJ count, but TWPA has CPW line",
    })
    
    classification.classification_reasoning = (
        f"JJ array classification based on {supporting_count} supporting features. "
        f"Key features: multiple JJs, no SQUID, ground plane."
    )
    
    return classification


def classify_calibration_chip(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
) -> TopologyClassification:
    """Classify a calibration chip topology.
    
    Calibration chips have:
    - Multiple CPW lines
    - Multiple IDC structures
    - Multiple ports
    - No JJ
    """
    classification = TopologyClassification(topology="calibration_chip")
    
    # Check for multiple CPW
    cpw_count = features.get("cpw_count", 0)
    if cpw_count >= 2:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description=f"{cpw_count} CPW lines detected",
            supporting=True,
            confidence=0.85,
        ))
    
    # Check for multiple IDC
    idc_count = features.get("idc_count", 0)
    if idc_count >= 2:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description=f"{idc_count} IDC structures detected",
            supporting=True,
            confidence=0.8,
        ))
    
    # Check for multiple ports
    port_count = features.get("port_count", 0)
    if port_count >= 4:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_PRESENT,
            description=f"{port_count} ports detected (multi-device)",
            supporting=True,
            confidence=0.85,
        ))
    
    # Check for no JJ
    if features.get("jj_count", 0) == 0:
        classification.supporting_evidence.append(TopologyEvidence(
            evidence_type=EvidenceType.GEOMETRY_ABSENT,
            description="No JJ detected (test structure)",
            supporting=True,
            confidence=0.9,
        ))
    
    # Calculate confidence
    supporting_count = len(classification.supporting_evidence)
    classification.confidence = min(supporting_count / 4.0, 1.0)
    
    classification.classification_reasoning = (
        f"Calibration chip classification based on {supporting_count} supporting features. "
        f"Key features: multiple CPW/IDC, multiple ports, no JJ."
    )
    
    return classification
