"""Layout Critic: comprehensive multi-agent review of superconducting device layouts.

Each agent reviews from a specific perspective:
  - Topology
  - Microwave
  - Fabrication
  - Measurement
  - Quantum Design
  - Literature
  - Packaging
  - Manufacturing

Final score = min(scores). Never averages.
"""

from __future__ import annotations

from typing import Any

from textlayout._legacy.review.base import finding, score_from_findings


# ─── Individual agents ─────────────────────────────────────────────────────────

def _review_topology(evidence: dict[str, Any], topology: dict[str, Any] | None) -> dict[str, Any]:
    """Review device topology."""
    agent = "topology"
    findings: list[dict[str, Any]] = []

    if not topology:
        findings.append(finding(agent, "error",
                                "No topology recognition available.",
                                "Run topology recognition before layout review."))
        return _agent_result(agent, findings)

    detected = topology.get("detected_device", "unknown")
    confidence = topology.get("confidence", 0.0)

    if detected == "unknown":
        findings.append(finding(agent, "error",
                                "Device topology could not be classified.",
                                "Verify the layout contains recognizable device features."))
    elif confidence < 0.5:
        findings.append(finding(agent, "warning",
                                f"Topology '{detected}' detected with low confidence ({confidence:.1%}).",
                                "Review the supporting and missing features."))

    missing = topology.get("missing_features", [])
    for feat in missing:
        findings.append(finding(agent, "warning",
                                f"Missing expected feature: {feat}.",
                                f"Add {feat} for a complete {detected} layout."))

    return _agent_result(agent, findings)


def _review_microwave(evidence: dict[str, Any], topology: dict[str, Any] | None,
                       geometry_features: dict[str, Any] | None) -> dict[str, Any]:
    """Review microwave design."""
    agent = "microwave"
    findings: list[dict[str, Any]] = []
    sidecar = evidence.get("sidecar") or {}
    info = sidecar.get("info") or {}
    ports = sidecar.get("ports") or []

    # Port count
    if len(ports) < 2:
        findings.append(finding(agent, "error",
                                "Less than 2 ports; device cannot be measured.",
                                "Add input and output RF ports."))

    # Impedance
    z0 = info.get("impedance_ohm") or info.get("z0_ohm")
    if z0 is not None:
        z = float(z0)
        if not 40.0 <= z <= 80.0:
            findings.append(finding(agent, "warning",
                                    f"CPW impedance {z:.1f} ohm outside typical 40-80 ohm range.",
                                    "Adjust CPW width/gap for 50 ohm target."))

    # CPW without ground
    if topology:
        features = topology.get("features", {})
        if features.get("cpw_count", 0) > 0 and not features.get("has_ground_plane"):
            findings.append(finding(agent, "error",
                                    "CPW detected without ground plane; Z0 is undefined.",
                                    "Add ground planes with defined gap."))

    # S-parameter passivity (if simulation available)
    sim = evidence.get("simulation") or {}
    s_params = sim.get("s_parameters") or {}
    if s_params:
        s11 = abs(float(s_params.get("s11_magnitude", 0.0)))
        s21 = abs(float(s_params.get("s21_magnitude", 0.0)))
        if s11**2 + s21**2 > 1.0:
            findings.append(finding(agent, "error",
                                    f"Passivity violation: |S11|^2 + |S21|^2 = {s11**2 + s21**2:.3f} > 1.",
                                    "Check solver setup; passive devices cannot have gain."))

    return _agent_result(agent, findings)


def _review_fabrication(evidence: dict[str, Any], geometry_features: dict[str, Any] | None) -> dict[str, Any]:
    """Review fabrication readiness."""
    agent = "fabrication"
    findings: list[dict[str, Any]] = []

    # DRC
    drc = evidence.get("drc") or {}
    drc_status = str(drc.get("status", "")).lower()
    if not drc_status:
        findings.append(finding(agent, "warning",
                                "No DRC report available.",
                                "Run DRC before claiming fabrication readiness."))
    elif drc_status in ("failed", "error"):
        violations = drc.get("violation_count", drc.get("violations", "?"))
        findings.append(finding(agent, "error",
                                f"DRC failed with {violations} violations.",
                                "Fix all DRC violations before tapeout."))

    # Critical dimensions
    if geometry_features:
        dims = geometry_features.get("critical_dimensions", {})
        jj_area = dims.get("jj_area_um2")
        if jj_area is not None and jj_area < 0.01:
            findings.append(finding(agent, "warning",
                                    f"JJ area {jj_area:.4f} um^2 is very small; fabrication yield risk.",
                                    "Consider increasing JJ area for better yield."))

        cpw_width = dims.get("cpw_width_um")
        if cpw_width is not None and cpw_width < 2.0:
            findings.append(finding(agent, "warning",
                                    f"CPW width {cpw_width:.1f} um is narrow; may have fabrication issues.",
                                    "Widen CPW trace to >3 um for reliable fabrication."))

    # Ground stitching
    if geometry_features:
        ground = geometry_features.get("ground_pocket", {})
        if ground.get("has_ground_plane") and not ground.get("ground_polygon_count"):
            findings.append(finding(agent, "info",
                                    "Ground plane present but no stitching vias detected.",
                                    "Add ground stitching vias at 30-50 um pitch."))

    return _agent_result(agent, findings)


def _review_measurement(evidence: dict[str, Any], topology: dict[str, Any] | None) -> dict[str, Any]:
    """Review measurement accessibility."""
    agent = "measurement"
    findings: list[dict[str, Any]] = []
    sidecar = evidence.get("sidecar") or {}
    ports = sidecar.get("ports") or []
    port_names = [str(p.get("name", "")).lower() for p in ports]

    if len(ports) < 2:
        findings.append(finding(agent, "error",
                                "No measurement ports; device cannot be probed.",
                                "Add RF launch pads for measurement."))

    # Device-specific requirements
    if topology:
        detected = topology.get("detected_device", "unknown")

        if detected in ("lumped_jpa", "quarter_wave_jpa", "twpa"):
            required = {"input": ("in", "rf_in", "signal"),
                        "output": ("out", "rf_out", "readout"),
                        "pump": ("pump", "flux", "bias", "coil")}
            for label, keywords in required.items():
                if not any(any(kw in n for kw in keywords) for n in port_names):
                    findings.append(finding(agent, "warning",
                                            f"No {label} port detected for {detected}.",
                                            f"Add {label} port for complete measurement access."))

        elif detected in ("pocket_transmon", "xmon", "concentric_transmon"):
            required = {"drive": ("drive", "xy"),
                        "readout": ("readout", "ro", "out")}
            for label, keywords in required.items():
                if not any(any(kw in n for kw in keywords) for n in port_names):
                    findings.append(finding(agent, "warning",
                                            f"No {label} port detected for transmon.",
                                            f"Add {label} port for qubit control/readout."))

    return _agent_result(agent, findings)


def _review_quantum_design(evidence: dict[str, Any], topology: dict[str, Any] | None) -> dict[str, Any]:
    """Review quantum design parameters."""
    agent = "quantum_design"
    findings: list[dict[str, Any]] = []

    if not topology:
        return _agent_result(agent, findings)

    features = topology.get("features", {})

    # JJ count vs topology
    detected = topology.get("detected_device", "unknown")
    jj_count = features.get("jj_count", 0)

    if detected in ("pocket_transmon", "xmon", "concentric_transmon", "fluxonium"):
        if jj_count == 0:
            findings.append(finding(agent, "error",
                                    f"{detected} requires at least one JJ; none detected.",
                                    "Add Josephson junction to the layout."))
        elif jj_count > 2:
            findings.append(finding(agent, "warning",
                                    f"{detected} has {jj_count} JJs; typically uses 1-2.",
                                    "Verify JJ count matches intended design."))

    if detected in ("lumped_jpa", "quarter_wave_jpa"):
        if not features.get("squid_detected"):
            findings.append(finding(agent, "warning",
                                    f"{detected} typically uses SQUID; single JJ detected.",
                                    "Consider SQUID for flux-tunable JPA."))

    # Ej/Ec ratio estimate
    if features.get("jj_areas_um2"):
        # Rough estimate: for typical AlOx junction, Ej/Ec ~ 50-200
        area = features["jj_areas_um2"][0]
        if area < 0.01:
            findings.append(finding(agent, "warning",
                                    f"JJ area {area:.4f} um^2 may give low Ej/Ec ratio.",
                                    "Typical transmon uses 0.01-1 um^2 JJ area."))

    return _agent_result(agent, findings)


def _review_literature(evidence: dict[str, Any], topology: dict[str, Any] | None) -> dict[str, Any]:
    """Review literature comparison."""
    agent = "literature"
    findings: list[dict[str, Any]] = []

    literature = evidence.get("literature_comparison") or {}
    references = literature.get("references") or []
    comparisons = literature.get("comparisons") or []

    if not references:
        findings.append(finding(agent, "info",
                                "No literature references attached.",
                                "Add reference devices for comparison."))

    if references and not comparisons:
        findings.append(finding(agent, "warning",
                                "References present but no parameter comparisons.",
                                "Compare generated parameters against literature values."))

    return _agent_result(agent, findings)


def _review_packaging(evidence: dict[str, Any], geometry_features: dict[str, Any] | None) -> dict[str, Any]:
    """Review packaging readiness."""
    agent = "packaging"
    findings: list[dict[str, Any]] = []

    if geometry_features:
        launches = geometry_features.get("launch_transitions", {})

        if launches.get("count", 0) == 0:
            findings.append(finding(agent, "warning",
                                    "No launch pads detected for wire bonding.",
                                    "Add GSG launch pads for coaxial connection."))

        if not launches.get("has_gsg"):
            findings.append(finding(agent, "info",
                                    "Launch pads not in GSG configuration.",
                                    "GSG (ground-signal-ground) is standard for CPW probes."))

    # Chip boundary
    sidecar = evidence.get("sidecar") or {}
    info = sidecar.get("info") or {}
    if not info.get("chip_boundary") and not info.get("chip_width_um"):
        findings.append(finding(agent, "info",
                                "No chip boundary defined.",
                                "Define chip boundary for packaging layout."))

    return _agent_result(agent, findings)


def _review_manufacturing(evidence: dict[str, Any], geometry_features: dict[str, Any] | None) -> dict[str, Any]:
    """Review manufacturing readiness."""
    agent = "manufacturing"
    findings: list[dict[str, Any]] = []

    # Layer count
    sidecar = evidence.get("sidecar") or {}
    layers = sidecar.get("layers") or []
    layer_count = len(layers)

    if layer_count == 0:
        findings.append(finding(agent, "warning",
                                "No layer information in sidecar.",
                                "Specify layer stack for manufacturing."))
    elif layer_count > 6:
        findings.append(finding(agent, "info",
                                f"Layout uses {layer_count} layers; verify all are needed.",
                                "Minimize layer count for lower manufacturing cost."))

    # Via count
    if geometry_features:
        bridges = geometry_features.get("airbridge_span", {})
        if bridges.get("count", 0) > 50:
            findings.append(finding(agent, "info",
                                    f"High via/airbridge count ({bridges['count']}); may affect yield.",
                                    "Consider reducing via count where possible."))

    return _agent_result(agent, findings)


# ─── Stage-8 agents: Chief Architect, Optimization Expert, Reliability Expert,
#     Tapeout Expert, Chief Scientist ────────────────────────────────────────────

def _review_chief_architect(
    evidence: dict[str, Any],
    topology: dict[str, Any] | None,
    geometry_features: dict[str, Any] | None,
) -> dict[str, Any]:
    """Chief Architect: overall design philosophy, hierarchy, and system integration."""
    agent = "chief_architect"
    findings: list[dict[str, Any]] = []
    sidecar = evidence.get("sidecar") or {}
    info = sidecar.get("info") or {}

    # Verify design intent was synthesized
    if not info.get("device_type") and (not topology or topology.get("detected_device") == "unknown"):
        findings.append(finding(agent, "error",
                                "No recognizable device architecture.",
                                "Start with synthesize_design_intent() before generating layout."))

    # Hierarchy completeness: chip boundary present
    if not info.get("chip_width_um") and not info.get("chip_boundary"):
        findings.append(finding(agent, "warning",
                                "No chip boundary defined.",
                                "Define chip boundary for system-level integration."))

    # Component symmetry where expected
    if topology and topology.get("detected_device") in ("pocket_transmon", "xmon"):
        features = topology.get("features", {})
        jj_count = features.get("jj_count", 0)
        if jj_count == 2 and not features.get("squid_detected"):
            findings.append(finding(agent, "warning",
                                    "Two JJs present but SQUID not detected; verify symmetry.",
                                    "Ensure JJs form a symmetric SQUID loop for flux tunability."))

    # Verify there is a reference design comparison
    if not evidence.get("reference_comparison") and not evidence.get("literature_comparison"):
        findings.append(finding(agent, "info",
                                "No reference design comparison attached.",
                                "Compare with literature device for architectural validation."))

    return _agent_result(agent, findings)


def _review_optimization_expert(
    evidence: dict[str, Any],
    topology: dict[str, Any] | None,
) -> dict[str, Any]:
    """Optimization Expert: parameter optimization, sensitivity, operating margins."""
    agent = "optimization_expert"
    findings: list[dict[str, Any]] = []
    sidecar = evidence.get("sidecar") or {}
    info = sidecar.get("info") or {}

    # Check that target specifications were provided
    if not info.get("target_specifications") and not info.get("target_frequency_ghz"):
        findings.append(finding(agent, "info",
                                "No target specifications in sidecar.",
                                "Specify target frequency, gain, Q to enable optimization."))

    # For amplifiers: check gain-bandwidth product
    if topology and topology.get("detected_device") in ("lumped_jpa", "quarter_wave_jpa", "twpa"):
        sim = evidence.get("simulation") or {}
        gain = sim.get("gain_db")
        bw = sim.get("bandwidth_mhz")
        if gain is not None and bw is not None:
            try:
                gbp = float(gain) * float(bw)
                if gbp > 500:
                    findings.append(finding(agent, "warning",
                                            f"Gain-bandwidth product {gbp:.0f} dB·MHz may violate GBP limit.",
                                            "Reduce gain or increase coupling for achievable GBP."))
            except (TypeError, ValueError):
                pass

    # For qubits: check anharmonicity
    if topology and topology.get("detected_device") in ("pocket_transmon", "xmon"):
        features = (topology.get("features") or {})
        jj_area = (features.get("jj_areas_um2") or [None])[0]
        if jj_area is not None and float(jj_area) > 2.0:
            findings.append(finding(agent, "warning",
                                    f"Large JJ area ({jj_area:.2f} um^2) reduces anharmonicity.",
                                    "Target jj_area_um2 in 0.02-0.5 range for transmon anharmonicity > 100 MHz."))

    return _agent_result(agent, findings)


def _review_reliability_expert(
    evidence: dict[str, Any],
    geometry_features: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reliability Expert: long-term stability, TLS loss, aging, current crowding."""
    agent = "reliability_expert"
    findings: list[dict[str, Any]] = []

    # TLS participation ratio — surfaces are the main loss channel
    sidecar = evidence.get("sidecar") or {}
    info = sidecar.get("info") or {}
    substrate = info.get("substrate", "")
    if substrate.lower() in ("si", "silicon", ""):
        findings.append(finding(agent, "info",
                                "Substrate not specified or silicon; verify TLS loss.",
                                "Sapphire (Al2O3) and high-resistivity Si offer lower TLS loss."))

    # Electromigration risk from high current density near JJs
    if geometry_features:
        bottlenecks = geometry_features.get("current_bottlenecks", {})
        for bn in bottlenecks.get("bottlenecks", []):
            if bn.get("risk") == "high":
                findings.append(finding(agent, "warning",
                                        f"High current crowding at {bn['name']} is an electromigration risk.",
                                        "Widen narrow trace to reduce current density; critical at JJ contacts."))

    # Junction aging: Al-AlOx-Al JJs show Ic drift ~ 1-2% / year
    sim = evidence.get("simulation") or {}
    if sim.get("junction_count", 0) > 0:
        findings.append(finding(agent, "info",
                                "Al-AlOx JJ shows ~1-2% Ic aging per year at room temperature storage.",
                                "Store wafers at low temperature; plan for frequency re-tuning."))

    # Ground plane completeness prevents stray modes
    if geometry_features:
        ground = geometry_features.get("ground_pocket", {})
        if not ground.get("has_ground_plane"):
            findings.append(finding(agent, "error",
                                    "No ground plane: stray modes cause unpredictable frequency shifts.",
                                    "Add continuous ground plane with controlled gap geometry."))

    return _agent_result(agent, findings)


def _review_tapeout_expert(
    evidence: dict[str, Any],
    geometry_features: dict[str, Any] | None,
) -> dict[str, Any]:
    """Tapeout Expert: DRC cleanliness, layer compliance, export completeness."""
    agent = "tapeout_expert"
    findings: list[dict[str, Any]] = []

    # DRC must pass cleanly
    drc = evidence.get("drc") or {}
    drc_status = str(drc.get("status", "")).lower()
    if drc_status in ("failed", "error"):
        findings.append(finding(agent, "error",
                                f"DRC must pass before tapeout: {drc.get('violation_count', '?')} violations.",
                                "Fix all DRC violations; tapeout with violations risks chip failure."))
    elif not drc_status:
        findings.append(finding(agent, "warning",
                                "DRC report missing; cannot approve tapeout.",
                                "Run run_drc() and attach report before tapeout review."))

    # GDS must be present
    gds_path = evidence.get("gds_path")
    if not gds_path:
        findings.append(finding(agent, "error",
                                "No GDS path in evidence; cannot tapeout without GDS.",
                                "Call compile_layout() to produce GDS before tapeout review."))

    # Sidecar must be present and complete
    sidecar = evidence.get("sidecar") or {}
    missing_sidecar_keys = [k for k in ("pcell", "gds_path", "info", "ports") if k not in sidecar]
    if missing_sidecar_keys:
        findings.append(finding(agent, "warning",
                                f"Sidecar missing keys: {missing_sidecar_keys}.",
                                "Regenerate sidecar with compile_layout() for complete metadata."))

    # Chip boundary must be specified
    info = sidecar.get("info") or {}
    if not info.get("chip_width_um") and not info.get("chip_boundary"):
        findings.append(finding(agent, "error",
                                "Chip boundary not specified; foundry requires explicit chip dimensions.",
                                "Set chip_width_um and chip_height_um in design parameters."))

    # Launch pads required for probe testing
    if geometry_features:
        launches = geometry_features.get("launch_transitions", {})
        if launches.get("count", 0) < 2:
            findings.append(finding(agent, "warning",
                                    "Fewer than 2 launch pads; chip may not be probeable.",
                                    "Add GSG launch pads for on-wafer RF measurement."))

    return _agent_result(agent, findings)


def _review_chief_scientist(
    evidence: dict[str, Any],
    topology: dict[str, Any] | None,
) -> dict[str, Any]:
    """Chief Scientist: scientific validity, provenance, measurement-backed claims."""
    agent = "chief_scientist"
    findings: list[dict[str, Any]] = []

    # All physics claims must be traceable — no LLM source
    extraction = evidence.get("extraction") or {}
    quantities = extraction.get("quantities") or []
    llm_sourced = [q for q in quantities if str(q.get("source", "")).upper() == "LLM"]
    if llm_sourced:
        for q in llm_sourced:
            findings.append(finding(agent, "error",
                                    f"Quantity '{q.get('name', '?')}' has source='LLM'; this is forbidden.",
                                    "Derive all quantities from geometry, simulation, or measurement."))

    # Fabrication process must be documented for scientific reproducibility
    sidecar = evidence.get("sidecar") or {}
    info = sidecar.get("info") or {}
    if not info.get("fabrication_process") and not info.get("process"):
        findings.append(finding(agent, "info",
                                "Fabrication process not documented.",
                                "Add process name and critical current density for reproducibility."))

    # Simulation evidence required for any quantitative performance claim
    sim = evidence.get("simulation") or {}
    if sim and sim.get("status") not in ("EXECUTED", "executed"):
        if info.get("target_gain_db") or info.get("target_frequency_ghz"):
            findings.append(finding(agent, "warning",
                                    "Performance targets specified but no executed simulation.",
                                    "Run at least one EM or circuit solver before claiming performance."))

    # Literature comparison for novel devices
    if topology and topology.get("detected_device") not in ("unknown", "calibration_chip"):
        if not evidence.get("literature_comparison"):
            findings.append(finding(agent, "info",
                                    "No literature comparison for non-trivial device.",
                                    "Compare with best published performance in the same topology class."))

    return _agent_result(agent, findings)


# ─── Aggregation ──────────────────────────────────────────────────────────────

def _agent_result(agent: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    has_error = any(f["severity"] == "error" for f in findings)
    return {
        "agent": agent,
        "passed": not has_error,
        "score": score_from_findings(findings),
        "findings": findings,
    }


def review_layout_critic(
    evidence: dict[str, Any],
    *,
    topology: dict[str, Any] | None = None,
    geometry_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the full LayoutCritic review.

    Parameters
    ----------
    evidence:
        Standard evidence dict.
    topology:
        Output of ``recognize_topology()``.
    geometry_features:
        Output of ``analyze_geometry()``.

    Returns
    -------
    dict with approved, score, reviews, blockers.
    """
    # 12-agent committee (Stage 8 of the AI-Native Quantum CAD Platform)
    agents = [
        ("chief_architect",     lambda: _review_chief_architect(evidence, topology, geometry_features)),
        ("microwave",           lambda: _review_microwave(evidence, topology, geometry_features)),
        ("quantum_design",      lambda: _review_quantum_design(evidence, topology)),
        ("fabrication",         lambda: _review_fabrication(evidence, geometry_features)),
        ("packaging",           lambda: _review_packaging(evidence, geometry_features)),
        ("measurement",         lambda: _review_measurement(evidence, topology)),
        ("optimization_expert", lambda: _review_optimization_expert(evidence, topology)),
        ("literature",          lambda: _review_literature(evidence, topology)),
        ("reliability_expert",  lambda: _review_reliability_expert(evidence, geometry_features)),
        ("manufacturing",       lambda: _review_manufacturing(evidence, geometry_features)),
        ("tapeout_expert",      lambda: _review_tapeout_expert(evidence, geometry_features)),
        ("chief_scientist",     lambda: _review_chief_scientist(evidence, topology)),
    ]

    reviews = []
    for name, fn in agents:
        try:
            review = fn()
        except Exception as exc:  # noqa: BLE001
            review = {
                "agent": name,
                "passed": False,
                "score": 0,
                "findings": [finding(name, "error", f"Agent crashed: {exc}", "Fix agent code.")],
            }
        reviews.append(review)

    approved = all(r["passed"] for r in reviews)
    score = min(r["score"] for r in reviews) if reviews else 0

    return {
        "schema": "text-to-gds.layout-critic.v1",
        "approved": approved,
        "score": score,
        "reviews": reviews,
        "blockers": [
            f for r in reviews for f in r["findings"] if f["severity"] == "error"
        ],
    }
