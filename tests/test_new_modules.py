"""Tests for the AI-Native Quantum CAD Platform modules."""


def test_geometry_intelligence_import():
    """Test that geometry_intelligence module can be imported."""
    from text_to_gds.geometry_intelligence import (
        GeometryFeature,
        FeatureType,
    )
    
    # Test FeatureType enum
    assert FeatureType.CPW.value == "cpw"
    assert FeatureType.IDC.value == "idc"
    assert FeatureType.JOSEPHSON_JUNCTION.value == "josephson_junction"
    
    # Test GeometryFeature creation
    feature = GeometryFeature(
        feature_type=FeatureType.CPW,
        name="Test CPW",
        bounding_box=[0.0, 0.0, 100.0, 10.0],
    )
    assert feature.feature_type == FeatureType.CPW
    assert feature.width_um == 100.0
    assert feature.height_um == 10.0
    assert feature.area_um2 == 1000.0


def test_geometry_intelligence_engine():
    """Test GeometryIntelligenceEngine."""
    from text_to_gds.geometry_intelligence import GeometryIntelligenceEngine
    
    engine = GeometryIntelligenceEngine()
    
    # Test with empty inputs
    result = engine.analyze_layout(
        gds_path="test.gds",
        physics_graph=None,
        extraction_data=None,
        sidecar=None,
    )
    
    assert result["schema"] == "text-to-gds.geometry-graph.v1"
    assert result["source_gds"] == "test.gds"
    assert "features" in result
    assert "summary" in result


def test_design_graph_import():
    """Test that design_graph module can be imported."""
    from text_to_gds.design_graph import (
        DeviceNode,
        NodeType,
    )
    
    # Test NodeType enum
    assert NodeType.DEVICE.value == "device"
    assert NodeType.SUBSYSTEM.value == "subsystem"
    
    # Test node creation
    device = DeviceNode(
        name="Test Device",
        device_type="transmon",
    )
    assert device.node_type == NodeType.DEVICE
    assert device.device_type == "transmon"


def test_design_graph_engine():
    """Test DesignGraphEngine."""
    from text_to_gds.design_graph import DesignGraphEngine
    
    engine = DesignGraphEngine()
    
    # Test with empty inputs
    result = engine.build_design_graph(
        geometry_graph=None,
        physics_graph=None,
        topology_result=None,
        sidecar=None,
    )
    
    assert result["schema"] == "text-to-gds.design-graph.v1"
    assert "nodes" in result
    assert "edges" in result
    assert "summary" in result


def test_topology_reasoning_import():
    """Test that topology_reasoning module can be imported."""
    from text_to_gds.topology_reasoning import (
        EvidenceType,
    )
    
    # Test EvidenceType enum
    assert EvidenceType.GEOMETRY_PRESENT.value == "geometry_present"
    assert EvidenceType.PARAMETER_MATCH.value == "parameter_match"


def test_topology_reasoning_engine():
    """Test TopologyReasoningEngine."""
    from text_to_gds.topology_reasoning import TopologyReasoningEngine
    
    engine = TopologyReasoningEngine()
    
    # Test with minimal features
    features = {
        "jj_count": 1,
        "idc_count": 1,
        "cpw_count": 1,
        "has_ground_plane": True,
        "has_launch_pads": True,
        "port_count": 2,
    }
    
    result = engine.classify_topology(features)
    
    assert result["schema"] == "text-to-gds.topology-reasoning.v1"
    assert "detected_topology" in result
    assert "confidence" in result
    assert "supporting_evidence" in result
    assert "missing_evidence" in result


def test_engineering_rules_import():
    """Test that engineering_rules module can be imported."""
    from text_to_gds.engineering_rules import (
        RuleCategory,
        RuleSeverity,
    )
    
    # Test enums
    assert RuleCategory.MICROWAVE.value == "microwave"
    assert RuleSeverity.ERROR.value == "error"


def test_engineering_rules_engine():
    """Test EngineeringRuleEngine."""
    from text_to_gds.engineering_rules import EngineeringRuleEngine
    
    engine = EngineeringRuleEngine()
    
    # Test with minimal design data
    design_data = {
        "geometry_features": [],
        "device_type": "transmon",
    }
    
    result = engine.evaluate_rules(design_data)
    
    assert result["schema"] == "text-to-gds.engineering-rules.v1"
    assert "summary" in result
    assert "results" in result
    assert "failed_rules" in result


def test_literature_graph_import():
    """Test that literature_graph module can be imported."""
    from text_to_gds.literature_graph import (
        DeviceTopology,
    )
    
    # Test DeviceTopology enum
    assert DeviceTopology.POCKET_TRANSMON.value == "pocket_transmon"
    assert DeviceTopology.LUMPED_JPA.value == "lumped_jpa"


def test_literature_graph_engine():
    """Test LiteratureKnowledgeGraph."""
    from text_to_gds.literature_graph import LiteratureKnowledgeGraph
    
    engine = LiteratureKnowledgeGraph()
    
    # Test knowledge graph
    result = engine.get_knowledge_graph()
    
    assert result["schema"] == "text-to-gds.literature-knowledge-graph.v1"
    assert "total_devices" in result
    assert "devices" in result
    assert "devices_by_topology" in result


def test_design_optimization_import():
    """Test that design_optimization module can be imported."""
    from text_to_gds.design_optimization import (
        IterationStatus,
    )
    
    # Test IterationStatus enum
    assert IterationStatus.PENDING.value == "pending"
    assert IterationStatus.ACCEPTED.value == "accepted"


def test_device_understanding_import():
    """Test that device_understanding module can be imported."""
    from text_to_gds.device_understanding import (
        QuestionType,
    )
    
    # Test QuestionType enum
    assert QuestionType.DEVICE_IDENTIFICATION.value == "device_identification"
    assert QuestionType.FEATURE_PURPOSE.value == "feature_purpose"


def test_device_understanding_engine():
    """Test DeviceUnderstandingEngine."""
    from text_to_gds.device_understanding import DeviceUnderstandingEngine
    
    engine = DeviceUnderstandingEngine()
    
    # Test with empty knowledge
    result = engine.answer_all_questions()
    
    assert result["schema"] == "text-to-gds.device-understanding.v1"
    assert "questions" in result
    assert "answers" in result


def test_engineering_visualization_import():
    """Test that engineering_visualization module can be imported."""
    from text_to_gds.engineering_visualization import (
        ViewType,
    )
    
    # Test ViewType enum
    assert ViewType.GEOMETRY_VIEW.value == "geometry_view"
    assert ViewType.TOPOLOGY_VIEW.value == "topology_view"


def test_engineering_visualization_engine():
    """Test EngineeringVisualizationEngine."""
    from text_to_gds.engineering_visualization import EngineeringVisualizationEngine
    
    engine = EngineeringVisualizationEngine()
    
    # Test with empty knowledge
    result = engine.generate_all_views()
    
    assert result["schema"] == "text-to-gds.engineering-visualization.v1"
    assert "total_views" in result
    assert "views" in result


def test_main_package_import():
    """Test that main package imports new modules."""
    from text_to_gds import (
        GeometryIntelligenceEngine,
        DesignGraphEngine,
        TopologyReasoningEngine,
        EngineeringRuleEngine,
        LiteratureKnowledgeGraph,
        DesignOptimizationEngine,
        DeviceUnderstandingEngine,
        EngineeringVisualizationEngine,
    )
    
    # Verify all classes are importable
    assert GeometryIntelligenceEngine is not None
    assert DesignGraphEngine is not None
    assert TopologyReasoningEngine is not None
    assert EngineeringRuleEngine is not None
    assert LiteratureKnowledgeGraph is not None
    assert DesignOptimizationEngine is not None
    assert DeviceUnderstandingEngine is not None
    assert EngineeringVisualizationEngine is not None


def test_version_updated():
    """Test that version is updated to v0.3.0 (AI-Native Quantum CAD Platform)."""
    from text_to_gds import __version__
    assert __version__ == "0.3.0"


# ─── Digital Twin (Stage 7) ───────────────────────────────────────────────────

def test_digital_twin_import():
    """Test Digital Twin module can be imported."""
    from text_to_gds.digital_twin import (
        DigitalTwinEngine,
        DigitalTwin,
    )
    assert DigitalTwinEngine is not None
    assert DigitalTwin is not None


def test_digital_twin_create_and_record(tmp_path):
    """Test creating a digital twin and recording data."""
    from text_to_gds.digital_twin import DigitalTwinEngine

    engine = DigitalTwinEngine(database_path=tmp_path / "twins")
    twin_id = engine.create_twin(
        name="JPA_v1",
        device_type="lumped_jpa",
        description="Test JPA for unit tests",
        tags=["test", "jpa"],
    )
    assert twin_id is not None

    # Record geometry
    engine.record_geometry(
        twin_id,
        gds_path="test.gds",
        critical_dimensions={"cpw_width_um": 10.0, "jj_area_um2": 0.05},
        total_area_um2=1e6,
    )

    # Record physics
    engine.record_physics(
        twin_id,
        analytical={"frequency_ghz": 6.0, "impedance_ohm": 50.0},
        extracted={"quality_factor": 1000},
    )

    # Record simulation
    engine.record_simulation(
        twin_id,
        solver="JosephsonCircuits.jl",
        status="EXECUTED",
        results={"gain_db": 15.0, "bandwidth_mhz": 50.0},
        runtime_s=12.3,
    )

    # Record measurement
    engine.record_measurement(
        twin_id,
        measurement_type="gain_db",
        value=14.5,
        unit="dB",
        temperature_mk=20,
        setup="dilution_refrigerator",
    )

    # Get report
    report = engine.generate_report(twin_id)
    assert report["schema"] == "text-to-gds.twin-report.v1"
    assert report["name"] == "JPA_v1"
    assert report["device_type"] == "lumped_jpa"
    assert "JosephsonCircuits.jl" in report["solver_coverage"]
    assert "gain_db" in report["measurement_types"]


def test_digital_twin_reliability_prediction(tmp_path):
    """Test reliability prediction from digital twin."""
    from text_to_gds.digital_twin import DigitalTwinEngine

    engine = DigitalTwinEngine(database_path=tmp_path / "twins")
    twin_id = engine.create_twin(name="Transmon_test", device_type="pocket_transmon")

    # Record some physics
    engine.record_physics(
        twin_id,
        extracted={"resonator_frequency_ghz": 7.0, "quality_factor": 5000},
    )

    rel = engine.predict_reliability(twin_id)
    assert rel is not None
    assert rel.expected_frequency_drift_mhz_per_year is not None
    assert rel.confidence >= 0.0
    assert len(rel.failure_modes) > 0


def test_digital_twin_sim_vs_measurement(tmp_path):
    """Test simulation vs measurement comparison."""
    from text_to_gds.digital_twin import DigitalTwinEngine

    engine = DigitalTwinEngine(database_path=tmp_path / "twins")
    twin_id = engine.create_twin(name="TestDevice", device_type="lumped_jpa")
    engine.record_simulation(
        twin_id, solver="JosephsonCircuits.jl", status="EXECUTED",
        results={"gain_db": 15.0},
    )
    engine.record_measurement(
        twin_id, measurement_type="gain_db", value=14.5, unit="dB",
    )

    comparison = engine.compare_simulation_vs_measurement(twin_id)
    assert comparison["schema"] == "text-to-gds.twin-comparison.v1"
    assert comparison["total_compared"] >= 1
    gain_cmp = next(c for c in comparison["comparisons"] if c["quantity"] == "gain_db")
    assert gain_cmp["agreement"] in ("excellent", "good", "acceptable", "poor")


def test_digital_twin_persistence(tmp_path):
    """Test that digital twins persist across engine restarts."""
    from text_to_gds.digital_twin import DigitalTwinEngine

    db = tmp_path / "twins"
    engine1 = DigitalTwinEngine(database_path=db)
    twin_id = engine1.create_twin(name="PersistenceTest", device_type="xmon")
    engine1.record_physics(twin_id, analytical={"frequency_ghz": 5.5})

    # Load fresh engine
    engine2 = DigitalTwinEngine(database_path=db)
    twin = engine2.get(twin_id)
    assert twin is not None
    assert twin.name == "PersistenceTest"
    assert twin.current_physics is not None
    assert twin.current_physics.analytical["frequency_ghz"] == 5.5


def test_digital_twin_in_main_package():
    """Test DigitalTwinEngine is accessible from main package."""
    from text_to_gds import DigitalTwinEngine
    assert DigitalTwinEngine is not None


# ─── Literature Knowledge Base (Stage 1 study output) ────────────────────────

def test_literature_paper_kb_has_all_topologies():
    """Literature KB covers all major device families."""
    from text_to_gds.literature_graph import (
        ALL_LITERATURE_DEVICES,
        DeviceTopology,
    )
    topologies = {d.topology for d in ALL_LITERATURE_DEVICES}
    required = {
        DeviceTopology.POCKET_TRANSMON,
        DeviceTopology.XMON,
        DeviceTopology.FLUXONIUM,
        DeviceTopology.LUMPED_JPA,
        DeviceTopology.QUARTER_WAVE_JPA,
        DeviceTopology.TWPA,
        DeviceTopology.CPW_RESONATOR,
    }
    missing = required - topologies
    assert not missing, f"Literature KB missing: {missing}"


def test_literature_kb_all_devices_have_references():
    """Every literature device must cite a real paper."""
    from text_to_gds.literature_graph import ALL_LITERATURE_DEVICES
    for device in ALL_LITERATURE_DEVICES:
        assert device.reference, f"Device '{device.name}' has no reference"
        assert device.year is not None, f"Device '{device.name}' has no year"


def test_literature_kb_design_rules_present():
    """Design rules extracted from literature must be present."""
    from text_to_gds.literature_graph import DESIGN_RULES_FROM_LITERATURE
    required_rules = ["cpw_impedance", "jj_area_transmon", "ground_stitching"]
    for rule in required_rules:
        assert rule in DESIGN_RULES_FROM_LITERATURE, f"Design rule '{rule}' missing"
        assert "source" in DESIGN_RULES_FROM_LITERATURE[rule], f"Rule '{rule}' missing source"


def test_literature_kb_get_best_reference():
    """get_best_reference returns matching device or None for unknown."""
    from text_to_gds.literature_graph import get_best_reference
    jpa = get_best_reference("lumped_jpa")
    assert jpa is not None
    assert jpa.topology.value == "lumped_jpa"

    unknown = get_best_reference("nonexistent_topology_xyz")
    assert unknown is None


def test_knowledge_graph_has_11_plus_devices():
    """Knowledge graph has at least 11 literature devices."""
    from text_to_gds.literature_graph import LiteratureKnowledgeGraph
    engine = LiteratureKnowledgeGraph()
    kg = engine.get_knowledge_graph()
    assert kg["total_devices"] >= 11


# ─── 12-agent committee (Stage 8) ─────────────────────────────────────────────

def test_12_agent_committee_runs():
    """12-agent layout critic review runs without error."""
    from text_to_gds.review.layout_critic import review_layout_critic
    result = review_layout_critic({"sidecar": {"info": {}, "ports": []}})
    agent_names = [r["agent"] for r in result["reviews"]]
    assert len(agent_names) == 12, f"Expected 12 agents, got {len(agent_names)}: {agent_names}"


def test_12_agent_committee_score_is_minimum():
    """Final score is minimum across all 12 agents."""
    from text_to_gds.review.layout_critic import review_layout_critic
    result = review_layout_critic({"sidecar": {"info": {}, "ports": []}})
    scores = [r["score"] for r in result["reviews"]]
    assert result["score"] == min(scores)


def test_chief_scientist_blocks_llm_source():
    """Chief Scientist blocks LLM-sourced quantities."""
    from text_to_gds.review.layout_critic import review_layout_critic
    evidence = {
        "sidecar": {"info": {}, "ports": []},
        "extraction": {
            "quantities": [{"name": "frequency_ghz", "source": "LLM", "value": 5.0}]
        },
    }
    result = review_layout_critic(evidence)
    scientist = next(r for r in result["reviews"] if r["agent"] == "chief_scientist")
    errors = [f for f in scientist["findings"] if f["severity"] == "error"]
    assert errors, "Chief Scientist should block LLM-sourced quantities"


def test_tapeout_expert_blocks_missing_gds():
    """Tapeout Expert blocks review when GDS path is missing."""
    from text_to_gds.review.layout_critic import review_layout_critic
    evidence = {"sidecar": {"info": {}, "ports": []}}
    result = review_layout_critic(evidence)
    tapeout = next(r for r in result["reviews"] if r["agent"] == "tapeout_expert")
    errors = [f for f in tapeout["findings"] if f["severity"] == "error"]
    assert errors, "Tapeout Expert should block when GDS missing"


# ─── Generators ───────────────────────────────────────────────────────────────

def test_generators_importable():
    """Layout generators module is importable."""
    from text_to_gds.generators import generate_jpa_layout, generate_transmon_layout
    assert generate_jpa_layout is not None
    assert generate_transmon_layout is not None


def test_generate_jpa_layout():
    """JPA layout generator returns valid specification."""
    from text_to_gds.generators import generate_jpa_layout
    spec = generate_jpa_layout(
        frequency_ghz=6.0,
        gain_db=15.0,
        idc_finger_count=8,
    )
    assert spec is not None
    assert isinstance(spec, dict)


def test_generate_transmon_layout():
    """Transmon layout generator returns valid specification."""
    from text_to_gds.generators import generate_transmon_layout
    spec = generate_transmon_layout(variant="pocket", frequency_ghz=5.0)
    assert spec is not None
    assert isinstance(spec, dict)
