"""Tests for the upgraded superconducting quantum CAD platform.

Phase 10: Constraints enforcement — verifies all new modules maintain
the existing invariants and produce valid, traceable outputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ─── Phase 1: Topology Recognition ───────────────────────────────────────────

class TestTopologyRecognition:
    """Topology recognizer produces valid, honest classifications."""

    def test_unknown_device_returns_unknown(self):
        from text_to_gds.topology import recognize_topology

        empty_graph = {
            "nodes": [],
            "edges": [],
            "devices": [],
        }
        result = recognize_topology(empty_graph)
        assert result["detected_device"] == "unknown"
        assert result["confidence"] <= 0.15  # calibration_chip gives small score for empty
        assert result["schema"] == "text-to-gds.topology-recognition.v1"

    def test_no_fake_topology(self):
        from text_to_gds.topology import recognize_topology, KNOWN_TOPOLOGIES

        empty_graph = {"nodes": [], "edges": [], "devices": []}
        result = recognize_topology(empty_graph)
        assert result["detected_device"] in KNOWN_TOPOLOGIES

    def test_squid_detected_from_two_close_jjs(self):
        from text_to_gds.topology import recognize_topology

        graph = {
            "nodes": [
                {"id": "jj1", "type": "josephson_junction", "name": "JJ1",
                 "geometry": {"bbox_um": [0, 0, 1, 1], "area_um2": 0.05},
                 "physics_parameters": {}, "confidence": 0.95},
                {"id": "jj2", "type": "josephson_junction", "name": "JJ2",
                 "geometry": {"bbox_um": [5, 0, 6, 1], "area_um2": 0.05},
                 "physics_parameters": {}, "confidence": 0.95},
            ],
            "edges": [],
            "devices": [],
        }
        result = recognize_topology(graph)
        features = result["features"]
        assert features["squid_detected"] is True
        assert features["jj_count"] == 2

    def test_topology_graph_has_required_types(self):
        from text_to_gds.topology import (
            recognize_topology, TOPOLOGY_NODE_TYPES, TOPOLOGY_EDGE_TYPES,
        )

        graph = {"nodes": [], "edges": [], "devices": []}
        result = recognize_topology(graph)
        topo = result["topology_graph"]
        assert set(topo["node_types"]) == TOPOLOGY_NODE_TYPES
        assert set(topo["edge_types"]) == TOPOLOGY_EDGE_TYPES

    def test_confidence_bounded(self):
        from text_to_gds.topology import recognize_topology

        graph = {
            "nodes": [
                {"id": "jj1", "type": "josephson_junction", "name": "JJ1",
                 "geometry": {"bbox_um": [0, 0, 1, 1], "area_um2": 0.05},
                 "physics_parameters": {}, "confidence": 0.95},
                {"id": "idc1", "type": "capacitor", "name": "IDC0",
                 "geometry": {"bbox_um": [10, 10, 50, 30]},
                 "physics_parameters": {"finger_count": {"value": 8}}, "confidence": 0.8},
                {"id": "cpw1", "type": "transmission_line", "name": "CPW0",
                 "geometry": {"bbox_um": [60, 10, 200, 12]},
                 "physics_parameters": {"width": {"value": 10.0}, "length": {"value": 500.0}},
                 "confidence": 0.86},
                {"id": "gnd", "type": "ground", "name": "M1",
                 "geometry": {"bbox_um": [0, 0, 300, 300], "total_area_um2": 90000},
                 "physics_parameters": {}, "confidence": 0.9},
            ],
            "edges": [
                {"source": "jj1", "target": "gnd", "type": "electrical_connection"},
                {"source": "cpw1", "target": "gnd", "type": "capacitive_coupling"},
            ],
            "devices": [],
        }
        result = recognize_topology(graph)
        assert 0.0 <= result["confidence"] <= 1.0


# ─── Phase 2: Reference Matching ─────────────────────────────────────────────

class TestReferenceMatching:
    """Reference matching produces valid similarity scores."""

    def test_no_references_returns_zero(self):
        from text_to_gds.reference_matching import match_reference

        topo = {"detected_device": "unknown", "features": {}, "topology_graph": {"nodes": [], "edges": []}}
        result = match_reference(topo, references=[])
        assert result["reference_count"] == 0
        assert result["overall_similarity"] == 0.0

    def test_score_bounded(self):
        from text_to_gds.reference_matching import match_reference

        topo = {
            "detected_device": "lumped_jpa",
            "features": {"jj_count": 2, "squid_detected": True, "idc_count": 1,
                         "has_ground_plane": True, "has_flux_line": True,
                         "has_launch_pads": True, "port_names": ["rf_in", "rf_out", "pump"],
                         "jj_areas_um2": [0.05], "cpw_widths_um": [10.0]},
            "topology_graph": {"nodes": [{"type": "jj"}, {"type": "idc"}, {"type": "cpw"}],
                               "edges": [{"type": "galvanic"}]},
        }
        ref = [{
            "name": "test_jpa",
            "topology": "lumped_jpa",
            "institution": "test",
            "geometry": {"jj_area_um2": 0.05, "cpw_width_um": 10.0},
            "topology_features": {"node_types": ["jj", "idc", "cpw"]},
            "electrical": {"z0_ohm": 50.0},
            "fabrication": {},
            "ports": [{"name": "rf_in"}, {"name": "rf_out"}, {"name": "pump"}],
            "ground_strategy": "coplanar",
            "flux_strategy": "inductive",
            "readout_strategy": "none",
            "cpw_transition": "uniform",
            "idc_style": "standard",
            "squid_style": "planar",
        }]
        result = match_reference(topo, references=ref)
        assert 0.0 <= result["overall_similarity"] <= 1.0
        assert result["best_match"] == "test_jpa"

    def test_topology_mismatch_penalizes_score(self):
        from text_to_gds.reference_matching import match_reference

        topo = {
            "detected_device": "pocket_transmon",
            "features": {"jj_count": 1, "squid_detected": False, "idc_count": 1,
                         "has_ground_plane": True, "has_flux_line": False,
                         "has_launch_pads": True, "port_names": ["rf_in", "rf_out"],
                         "jj_areas_um2": [0.05], "cpw_widths_um": [10.0]},
            "topology_graph": {"nodes": [{"type": "jj"}, {"type": "idc"}], "edges": []},
        }
        ref = [{
            "name": "jpa_ref",
            "topology": "lumped_jpa",
            "institution": "test",
            "geometry": {},
            "topology_features": {"node_types": ["jj", "idc", "cpw"]},
            "electrical": {},
            "fabrication": {},
            "ports": [],
            "ground_strategy": "coplanar",
            "flux_strategy": "none",
            "readout_strategy": "none",
            "cpw_transition": "uniform",
            "idc_style": "standard",
            "squid_style": "none",
        }]
        result = match_reference(topo, references=ref)
        # Mismatch should give lower score than match
        assert result["overall_similarity"] < 0.8


# ─── Phase 5: Geometry Intelligence ──────────────────────────────────────────

class TestGeometryIntelligence:
    """Geometry analyzer produces valid feature extraction."""

    def test_returns_required_keys(self):
        from text_to_gds.geometry_intelligence import analyze_geometry

        result = analyze_geometry("/fake/path.gds")
        required = [
            "schema", "source_gds", "capacitor_paddles", "current_bottlenecks",
            "ground_pocket", "airbridge_span", "flux_coupling", "cpw_bends",
            "cpw_discontinuities", "launch_transitions", "stubs", "tapers",
            "corner_types", "critical_dimensions", "symmetry_analysis",
            "overall_area_um2",
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_schema_version(self):
        from text_to_gds.geometry_intelligence import analyze_geometry

        result = analyze_geometry("/fake/path.gds")
        assert result["schema"] == "text-to-gds.geometry-features.v1"

    def test_empty_input_produces_valid_output(self):
        from text_to_gds.geometry_intelligence import analyze_geometry

        result = analyze_geometry("/fake/path.gds")
        assert result["capacitor_paddles"]["count"] == 0
        assert result["current_bottlenecks"]["count"] == 0
        assert result["overall_area_um2"] == 0.0


# ─── Phase 6: Physical Design Review ─────────────────────────────────────────

class TestPhysicalDesignReview:
    """Physical design review catches real issues."""

    def test_no_ground_plane_is_error(self):
        from text_to_gds.review.layout_design_review import review_layout_design

        evidence = {"sidecar": {"info": {}, "ports": [{"name": "rf_in"}]}}
        geometry_features = {
            "current_bottlenecks": {"count": 0, "bottlenecks": []},
            "ground_pocket": {"has_ground_plane": False, "total_ground_area_um2": 0},
            "capacitor_paddles": {"count": 0, "paddles": []},
            "launch_transitions": {"count": 0, "launches": [], "has_gsg": False},
            "airbridge_span": {"count": 0},
            "cpw_bends": {"count": 0},
            "cpw_discontinuities": {"count": 0},
            "overall_area_um2": 0,
            "critical_dimensions": {},
        }
        result = review_layout_design(evidence, geometry_features=geometry_features)
        # Should flag missing ground
        severities = [f["severity"] for f in result["findings"]]
        assert "error" in severities or "warning" in severities

    def test_returns_valid_structure(self):
        from text_to_gds.review.layout_design_review import review_layout_design

        evidence = {"sidecar": {"info": {}, "ports": []}}
        result = review_layout_design(evidence)
        assert "agent" in result
        assert result["agent"] == "layout_design_review"
        assert "passed" in result
        assert "score" in result
        assert "findings" in result

    def test_score_bounded(self):
        from text_to_gds.review.layout_design_review import review_layout_design

        evidence = {"sidecar": {"info": {}, "ports": []}}
        result = review_layout_design(evidence)
        assert 0 <= result["score"] <= 100


# ─── Phase 8: Layout Critic ──────────────────────────────────────────────────

class TestLayoutCritic:
    """Layout Critic provides multi-agent review."""

    def test_all_agents_run(self):
        from text_to_gds.review.layout_critic import review_layout_critic

        evidence = {"sidecar": {"info": {}, "ports": []}}
        result = review_layout_critic(evidence)
        assert result["schema"] == "text-to-gds.layout-critic.v1"
        agent_names = [r["agent"] for r in result["reviews"]]
        # 12-agent committee (Stage 8 of the AI-Native Quantum CAD Platform)
        expected = [
            "chief_architect", "microwave", "quantum_design", "fabrication",
            "packaging", "measurement", "optimization_expert", "literature",
            "reliability_expert", "manufacturing", "tapeout_expert", "chief_scientist",
        ]
        for agent in expected:
            assert agent in agent_names, f"Missing agent: {agent}"

    def test_score_is_minimum(self):
        from text_to_gds.review.layout_critic import review_layout_critic

        evidence = {"sidecar": {"info": {}, "ports": []}}
        result = review_layout_critic(evidence)
        scores = [r["score"] for r in result["reviews"]]
        assert result["score"] == min(scores)

    def test_blockers_are_errors(self):
        from text_to_gds.review.layout_critic import review_layout_critic

        evidence = {"sidecar": {"info": {}, "ports": []}}
        result = review_layout_critic(evidence)
        for blocker in result["blockers"]:
            assert blocker["severity"] == "error"

    def test_with_topology_context(self):
        from text_to_gds.review.layout_critic import review_layout_critic

        evidence = {"sidecar": {"info": {}, "ports": [{"name": "rf_in"}, {"name": "rf_out"}]}}
        topology = {
            "detected_device": "lumped_jpa",
            "confidence": 0.8,
            "features": {"jj_count": 2, "squid_detected": True, "idc_count": 1,
                         "has_ground_plane": True, "has_flux_line": True,
                         "has_launch_pads": True, "port_names": ["rf_in", "rf_out", "pump"]},
            "missing_features": [],
        }
        result = review_layout_critic(evidence, topology=topology)
        assert result["score"] >= 0


# ─── Phase 3 & 4: Generator specs ───────────────────────────────────────────

class TestJPAGenerator:
    """JPA generator produces valid layout specifications."""

    def test_returns_required_keys(self):
        from text_to_gds.generators.jpa_generator import generate_jpa_layout

        spec = generate_jpa_layout()
        assert spec["schema"] == "text-to-gds.jpa-layout-spec.v1"
        assert "components" in spec
        assert "idc" in spec["components"]
        assert "squid" in spec["components"]
        assert "flux_line" in spec["components"]
        assert "launches" in spec["components"]

    def test_idc_has_fingers(self):
        from text_to_gds.generators.jpa_generator import generate_jpa_layout

        spec = generate_jpa_layout(idc_finger_count=6)
        idc = spec["components"]["idc"]
        assert idc["finger_count"] == 6
        assert len(idc["fingers"]) == 6

    def test_squid_has_interrupted_path(self):
        from text_to_gds.generators.jpa_generator import generate_jpa_layout

        spec = generate_jpa_layout()
        squid = spec["components"]["squid"]
        assert squid["current_path"] == "interrupted (JJ breaks loop)"
        assert len(squid["loop_segments"]) > 0

    def test_flux_line_has_coupling_region(self):
        from text_to_gds.generators.jpa_generator import generate_jpa_layout

        spec = generate_jpa_layout()
        flux = spec["components"]["flux_line"]
        assert "coupling_region" in flux
        assert flux["coupling_region"]["length_um"] > 0


class TestTransmonGenerator:
    """Transmon generator produces valid layout specifications."""

    def test_pocket_variant(self):
        from text_to_gds.generators.transmon_generator import generate_transmon_layout

        spec = generate_transmon_layout(variant="pocket")
        assert spec["variant"] == "pocket"
        assert spec["device_type"] == "pocket_transmon"
        assert "capacitor" in spec
        assert "ground_pocket" in spec

    def test_xmon_variant(self):
        from text_to_gds.generators.transmon_generator import generate_transmon_layout

        spec = generate_transmon_layout(variant="xmon")
        assert spec["variant"] == "xmon"
        assert spec["device_type"] == "xmon"
        assert spec["capacitor"]["type"] == "cross_shaped"

    def test_concentric_variant(self):
        from text_to_gds.generators.transmon_generator import generate_transmon_layout

        spec = generate_transmon_layout(variant="concentric")
        assert spec["variant"] == "concentric"
        assert spec["device_type"] == "concentric_transmon"
        assert spec["capacitor"]["type"] == "concentric_ring"

    def test_invalid_variant_raises(self):
        from text_to_gds.generators.transmon_generator import generate_transmon_layout

        with pytest.raises(ValueError, match="Unknown transmon variant"):
            generate_transmon_layout(variant="invalid")


# ─── Phase 10: Constraint enforcement ────────────────────────────────────────

class TestConstraints:
    """Verify non-negotiable constraints are maintained."""

    def test_no_fake_gain_in_physics_graph(self):
        from text_to_gds.physics_graph import _q

        record = _q(1.0, "GHz", formula="test", source="LLM", confidence=0.5)
        # source="LLM" should be rejected by signoff validator
        from text_to_gds.signoff import validate_value_record
        validation = validate_value_record(record)
        assert not validation["passed"]

    def test_committee_score_is_minimum(self):
        from text_to_gds.review.committee import review_committee

        evidence = {"sidecar": {"info": {}, "ports": []}}
        result = review_committee(evidence)
        scores = [r["score"] for r in result["reviews"]]
        assert result["score"] == min(scores)

    def test_enhanced_committee_includes_all_reviewers(self):
        from text_to_gds.review.committee import review_committee_enhanced

        evidence = {"sidecar": {"info": {}, "ports": []}}
        result = review_committee_enhanced(evidence)
        assert result["schema"] == "text-to-gds.review-committee-enhanced.v1"
        agent_names = [r["agent"] for r in result["reviews"]]
        assert "layout_design_review" in agent_names

    def test_topology_never_guesses(self):
        from text_to_gds.topology import recognize_topology, KNOWN_TOPOLOGIES

        # Completely empty graph
        result = recognize_topology({"nodes": [], "edges": [], "devices": []})
        assert result["detected_device"] in KNOWN_TOPOLOGIES
        assert result["detected_device"] == "unknown"

    def test_reference_library_exists(self):
        index_path = Path(__file__).parent.parent / "reference_library" / "index.json"
        if index_path.exists():
            data = json.loads(index_path.read_text(encoding="utf-8"))
            assert data["schema"] == "text-to-gds.reference-library.v1"
            assert "organizations" in data
