"""Tests for the new quantum EDA platform modules."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

# Test Device Classifier
from text_to_gds.device_classifier import (
    DeviceClassifier,
    DeviceType,
    ClassificationResult,
)


class TestDeviceClassifier:
    """Tests for the Device Classifier module."""
    
    def test_classifier_import(self):
        """Test that DeviceClassifier can be imported."""
        assert DeviceClassifier is not None
    
    def test_device_type_enum(self):
        """Test that DeviceType enum has all expected values."""
        assert DeviceType.POCKET_TRANSMON.value == "pocket_transmon"
        assert DeviceType.XMON.value == "xmon"
        assert DeviceType.LUMPED_JPA.value == "lumped_jpa"
        assert DeviceType.TWPA.value == "twpa"
        assert DeviceType.CPW_RESONATOR.value == "cpw_resonator"
    
    def test_classifier_creation(self):
        """Test that DeviceClassifier can be created."""
        classifier = DeviceClassifier()
        assert classifier is not None
    
    def test_classify_with_geometry(self):
        """Test classification with geometry data."""
        classifier = DeviceClassifier()
        
        geometry_graph = {
            "features": [
                {"feature_type": "josephson_junction", "dimensions": {"area": 1e-12}},
                {"feature_type": "capacitor_paddle", "dimensions": {"width": 50e-6}},
                {"feature_type": "ground_pocket", "dimensions": {"width": 200e-6}},
            ]
        }
        
        result = classifier.classify(geometry_graph=geometry_graph)
        
        assert isinstance(result, ClassificationResult)
        assert result.confidence > 0
        assert len(result.evidence) > 0
    
    def test_classify_with_topology(self):
        """Test classification with topology data."""
        classifier = DeviceClassifier()
        
        topology = {
            "device_type": "pocket_transmon",
            "components": [
                {"type": "junction"},
                {"type": "pad"},
            ]
        }
        
        result = classifier.classify(topology=topology)
        
        assert isinstance(result, ClassificationResult)
        assert result.confidence > 0
    
    def test_classification_result_to_dict(self):
        """Test ClassificationResult serialization."""
        classifier = DeviceClassifier()
        
        result = classifier.classify()
        
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "device_type" in d
        assert "confidence" in d
        assert "evidence" in d
        assert "alternatives" in d


# Test Dependency Graph
from text_to_gds.dependency_graph import (
    DependencyGraph,
    DependencyNode,
    DependencyEdge,
    DependencyLayer,
)


class TestDependencyGraph:
    """Tests for the Dependency Graph module."""
    
    def test_dependency_graph_import(self):
        """Test that DependencyGraph can be imported."""
        assert DependencyGraph is not None
    
    def test_dependency_layer_enum(self):
        """Test that DependencyLayer enum has all expected values."""
        assert DependencyLayer.PERFORMANCE.value == "performance"
        assert DependencyLayer.PHYSICS.value == "physics"
        assert DependencyLayer.GEOMETRY.value == "geometry"
        assert DependencyLayer.PROCESS.value == "process"
        assert DependencyLayer.MASK.value == "mask"
    
    def test_dependency_node_creation(self):
        """Test that DependencyNode can be created."""
        node = DependencyNode(
            id="test_node",
            name="Test Node",
            layer=DependencyLayer.GEOMETRY,
            value=100e-6,
            unit="m",
        )
        
        assert node.id == "test_node"
        assert node.layer == DependencyLayer.GEOMETRY
    
    def test_dependency_graph_creation(self):
        """Test that DependencyGraph can be created."""
        graph = DependencyGraph()
        assert graph is not None
    
    def test_build_from_design(self):
        """Test building dependency graph from design data."""
        graph = DependencyGraph()
        
        geometry_graph = {
            "features": [
                {
                    "id": "idc_1",
                    "feature_type": "idc",
                    "dimensions": {"finger_length": 50e-6, "gap": 2e-6},
                },
                {
                    "id": "cpw_1",
                    "feature_type": "cpw",
                    "dimensions": {"width": 10e-6, "gap": 6e-6},
                },
            ]
        }
        
        physics_graph = {
            "nodes": [
                {
                    "id": "jj_1",
                    "type": "josephson_junction",
                    "parameters": {
                        "critical_current": {"value": 1e-6, "unit": "A"},
                        "inductance": {"value": 1e-9, "unit": "H"},
                    },
                },
                {
                    "id": "res_1",
                    "type": "resonator",
                    "parameters": {
                        "frequency": {"value": 5e9, "unit": "Hz"},
                    },
                },
            ]
        }
        
        graph.build_from_design(geometry_graph=geometry_graph, physics_graph=physics_graph)
        
        # Check that nodes were added
        assert len(graph._nodes) > 0
    
    def test_dependency_graph_to_dict(self):
        """Test DependencyGraph serialization."""
        graph = DependencyGraph()
        
        d = graph.to_dict()
        assert isinstance(d, dict)
        assert "nodes" in d
        assert "edges" in d
        assert "layers" in d


# Test Design Memory
from text_to_gds.design_memory import (
    DesignMemory,
    DesignCase,
    DesignSearchResult,
)


class TestDesignMemory:
    """Tests for the Design Memory module."""
    
    def test_design_memory_import(self):
        """Test that DesignMemory can be imported."""
        assert DesignMemory is not None
    
    def test_design_case_creation(self):
        """Test that DesignCase can be created."""
        case = DesignCase(
            id="test_design",
            name="Test Design",
            device_type="pocket_transmon",
            created_at=datetime.now(),
        )
        
        assert case.id == "test_design"
        assert case.device_type == "pocket_transmon"
    
    def test_design_case_to_dict(self):
        """Test DesignCase serialization."""
        case = DesignCase(
            id="test_design",
            name="Test Design",
            device_type="pocket_transmon",
            created_at=datetime.now(),
        )
        
        d = case.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "test_design"
        assert d["device_type"] == "pocket_transmon"
    
    def test_design_memory_creation(self):
        """Test that DesignMemory can be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = DesignMemory(database_path=tmpdir)
            assert memory is not None
    
    def test_store_and_retrieve(self):
        """Test storing and retrieving a design case."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = DesignMemory(database_path=tmpdir)
            
            case = DesignCase(
                id="test_design",
                name="Test Design",
                device_type="pocket_transmon",
                created_at=datetime.now(),
            )
            
            memory.store(case)
            retrieved = memory.retrieve("test_design")
            
            assert retrieved is not None
            assert retrieved.id == "test_design"
    
    def test_search(self):
        """Test searching for designs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = DesignMemory(database_path=tmpdir)
            
            case = DesignCase(
                id="test_design",
                name="Test Design",
                device_type="pocket_transmon",
                created_at=datetime.now(),
                tags=["test", "demo"],
            )
            
            memory.store(case)
            
            results = memory.search({"device_type": "pocket_transmon"})
            assert len(results) > 0


# Test Measurement Knowledge Base
from text_to_gds.measurement_kb import (
    MeasurementKnowledgeBase,
    MeasurementRecord,
    MeasurementType,
)


class TestMeasurementKnowledgeBase:
    """Tests for the Measurement Knowledge Base module."""
    
    def test_measurement_kb_import(self):
        """Test that MeasurementKnowledgeBase can be imported."""
        assert MeasurementKnowledgeBase is not None
    
    def test_measurement_type_enum(self):
        """Test that MeasurementType enum has all expected values."""
        assert MeasurementType.S_PARAMETERS.value == "s_parameters"
        assert MeasurementType.TRANSMON_SPECTRUM.value == "transmon_spectrum"
        assert MeasurementType.JPA_GAIN.value == "jpa_gain"
    
    def test_measurement_record_creation(self):
        """Test that MeasurementRecord can be created."""
        record = MeasurementRecord(
            id="test_measurement",
            design_id="test_design",
            measurement_type=MeasurementType.S_PARAMETERS,
            timestamp=datetime.now(),
        )
        
        assert record.id == "test_measurement"
        assert record.measurement_type == MeasurementType.S_PARAMETERS
    
    def test_measurement_kb_creation(self):
        """Test that MeasurementKnowledgeBase can be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = MeasurementKnowledgeBase(database_path=tmpdir)
            assert kb is not None
    
    def test_store_and_retrieve(self):
        """Test storing and retrieving a measurement record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = MeasurementKnowledgeBase(database_path=tmpdir)
            
            record = MeasurementRecord(
                id="test_measurement",
                design_id="test_design",
                measurement_type=MeasurementType.S_PARAMETERS,
                timestamp=datetime.now(),
            )
            
            kb.store(record)
            retrieved = kb.retrieve("test_measurement")
            
            assert retrieved is not None
            assert retrieved.id == "test_measurement"


# Test Layout Critic
from text_to_gds.layout_critic import (
    LayoutCritic,
    ReviewIssue,
    ReviewCategory,
    ReviewSeverity,
    ReviewReport,
)


class TestLayoutCritic:
    """Tests for the Layout Critic module."""
    
    def test_layout_critic_import(self):
        """Test that LayoutCritic can be imported."""
        assert LayoutCritic is not None
    
    def test_review_category_enum(self):
        """Test that ReviewCategory enum has all expected values."""
        assert ReviewCategory.MICROWAVE.value == "microwave"
        assert ReviewCategory.QUANTUM.value == "quantum"
        assert ReviewCategory.FABRICATION.value == "fabrication"
    
    def test_review_severity_enum(self):
        """Test that ReviewSeverity enum has all expected values."""
        assert ReviewSeverity.ERROR.value == "error"
        assert ReviewSeverity.WARNING.value == "warning"
        assert ReviewSeverity.INFO.value == "info"
    
    def test_layout_critic_creation(self):
        """Test that LayoutCritic can be created."""
        critic = LayoutCritic()
        assert critic is not None
    
    def test_review_with_geometry(self):
        """Test review with geometry data."""
        critic = LayoutCritic()
        
        geometry_graph = {
            "features": [
                {
                    "feature_type": "cpw",
                    "dimensions": {"width": 10e-6, "gap": 6e-6},
                },
                {
                    "feature_type": "josephson_junction",
                    "dimensions": {"area": 1e-12},
                },
            ]
        }
        
        result = critic.review(
            design_id="test_design",
            geometry_graph=geometry_graph,
        )
        
        assert isinstance(result, ReviewReport)
        assert result.design_id == "test_design"
        assert result.overall_score >= 0
        assert result.overall_score <= 1
    
    def test_review_report_to_dict(self):
        """Test ReviewReport serialization."""
        critic = LayoutCritic()
        
        result = critic.review(design_id="test_design")
        
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "design_id" in d
        assert "issues" in d
        assert "overall_score" in d


# Test Engineering Reasoner
from text_to_gds.engineering_reasoner import (
    EngineeringReasoner,
    EngineeringQuestion,
    EngineeringAnswer,
    AnswerSource,
)


class TestEngineeringReasoner:
    """Tests for the Engineering Reasoner module."""
    
    def test_engineering_reasoner_import(self):
        """Test that EngineeringReasoner can be imported."""
        assert EngineeringReasoner is not None
    
    def test_engineering_question_enum(self):
        """Test that EngineeringQuestion enum has all expected values."""
        assert EngineeringQuestion.WHY_BANDWIDTH_LOW.value == "why_bandwidth_low"
        assert EngineeringQuestion.WHY_GAIN_DROPPED.value == "why_gain_dropped"
        assert EngineeringQuestion.HOW_TO_IMPROVE.value == "how_to_improve"
    
    def test_answer_source_enum(self):
        """Test that AnswerSource enum has all expected values."""
        assert AnswerSource.GEOMETRY.value == "geometry"
        assert AnswerSource.PHYSICS_GRAPH.value == "physics_graph"
        assert AnswerSource.SOLVER_EVIDENCE.value == "solver_evidence"
    
    def test_engineering_reasoner_creation(self):
        """Test that EngineeringReasoner can be created."""
        reasoner = EngineeringReasoner()
        assert reasoner is not None
    
    def test_answer_question(self):
        """Test answering an engineering question."""
        reasoner = EngineeringReasoner()
        
        geometry_graph = {
            "features": [
                {
                    "feature_type": "cpw",
                    "dimensions": {"width": 3e-6, "gap": 2e-6},
                },
            ]
        }
        
        result = reasoner.answer(
            question=EngineeringQuestion.WHY_BANDWIDTH_LOW,
            geometry_graph=geometry_graph,
        )
        
        assert isinstance(result, EngineeringAnswer)
        assert result.confidence > 0
        assert len(result.answer) > 0
    
    def test_answer_to_dict(self):
        """Test EngineeringAnswer serialization."""
        reasoner = EngineeringReasoner()
        
        result = reasoner.answer(
            question=EngineeringQuestion.WHY_BANDWIDTH_LOW,
        )
        
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "question" in d
        assert "answer" in d
        assert "confidence" in d


# Test reference library
class TestReferenceLibrary:
    """Tests for the reference library."""
    
    def test_reference_library_exists(self):
        """Test that reference library file exists."""
        lib_path = Path(__file__).parent.parent / "reference_library" / "devices.json"
        assert lib_path.exists()
    
    def test_reference_library_loadable(self):
        """Test that reference library can be loaded."""
        lib_path = Path(__file__).parent.parent / "reference_library" / "devices.json"
        
        with open(lib_path, "r") as f:
            data = json.load(f)
        
        assert "version" in data
        assert "topologies" in data
        assert len(data["topologies"]) > 0
    
    def test_reference_library_has_expected_devices(self):
        """Test that reference library has expected device types."""
        lib_path = Path(__file__).parent.parent / "reference_library" / "devices.json"
        
        with open(lib_path, "r") as f:
            data = json.load(f)
        
        topologies = data["topologies"]
        assert "pocket_transmon" in topologies
        assert "xmon" in topologies
        assert "lumped_jpa" in topologies
        assert "twpa" in topologies
        assert "cpw_resonator" in topologies
