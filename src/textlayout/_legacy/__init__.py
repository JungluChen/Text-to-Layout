"""AI-Native Quantum Design Intelligence Platform.

.. note:: **FROZEN LEGACY PACKAGE.** ``textlayout._legacy`` is maintained only as the
   MCP-server surface and is not actively developed. New work belongs in
   ``src/textlayout`` (see ``docs/ARCHITECTURE.md``). Do not add features here;
   dead-code removal is tracked as a separate, explicitly-scoped follow-up.

Transforms natural-language device descriptions into production-ready
GDS layouts with full physics traceability, multi-agent review, and
closed-loop scientific reasoning.

Pipeline (Stage 2 upgrade):
  Prompt → Engineering Intent → Design Graph → Geometry Intelligence →
  Topology Intelligence → Dependency Graph → Physics Graph → Simulation →
  Measurement → Knowledge Graph → Optimization → Scientific Report

New in v0.3.0:
  - Digital Twin (Stage 7): full design lifecycle record
  - 12-agent Review Committee (Stage 8): Chief Architect through Chief Scientist
  - Real paper knowledge base (Stage 1 study output): 11 reference devices
  - Dependency Graph: performance–geometry–process causal chains
  - Engineering Reasoner: Why? not What?
  - Design Memory: experience accumulation
"""

from textlayout._legacy.reference_compare import golden_compare

# Geometry and topology intelligence
from textlayout._legacy.geometry_intelligence import GeometryIntelligenceEngine
from textlayout._legacy.design_graph import DesignGraphEngine
from textlayout._legacy.topology_reasoning import TopologyReasoningEngine
from textlayout._legacy.engineering_rules import EngineeringRuleEngine

# Knowledge systems
from textlayout._legacy.literature_graph import LiteratureKnowledgeGraph, DESIGN_RULES_FROM_LITERATURE
from textlayout._legacy.design_memory import DesignMemory
from textlayout._legacy.engineering_reasoner import EngineeringReasoner

# Design workflow
from textlayout._legacy.design_optimization import DesignOptimizationEngine
from textlayout._legacy.device_understanding import DeviceUnderstandingEngine
from textlayout._legacy.engineering_visualization import EngineeringVisualizationEngine

# Digital Twin (Stage 7)
from textlayout._legacy.digital_twin import DigitalTwinEngine

# Layout generators
from textlayout._legacy.generators import generate_jpa_layout, generate_transmon_layout

__all__ = [
    "__version__",
    "golden_compare",
    # Geometry and topology
    "GeometryIntelligenceEngine",
    "DesignGraphEngine",
    "TopologyReasoningEngine",
    "EngineeringRuleEngine",
    # Knowledge systems
    "LiteratureKnowledgeGraph",
    "DESIGN_RULES_FROM_LITERATURE",
    "DesignMemory",
    "EngineeringReasoner",
    # Design workflow
    "DesignOptimizationEngine",
    "DeviceUnderstandingEngine",
    "EngineeringVisualizationEngine",
    # Digital Twin
    "DigitalTwinEngine",
    # Generators
    "generate_jpa_layout",
    "generate_transmon_layout",
]

__version__ = "0.3.0"

