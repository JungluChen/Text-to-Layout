"""Literature Knowledge Graph for comparing with published devices.

This module provides structured representation of literature devices and
feature-by-feature comparison with generated designs. The knowledge base
contains engineering data extracted from key publications at IBM, Google,
Yale, MIT, ETH, IQM, NIST, Rigetti, Oxford.
"""

from text_to_gds.literature_graph.engine import LiteratureKnowledgeGraph
from text_to_gds.literature_graph.devices import LiteratureDevice, DeviceTopology
from text_to_gds.literature_graph.comparison import FeatureComparison, ComparisonResult
from text_to_gds.literature_graph.paper_kb import (
    ALL_LITERATURE_DEVICES,
    DESIGN_RULES_FROM_LITERATURE,
    get_all_literature_devices,
    get_best_reference,
)

__all__ = [
    "LiteratureKnowledgeGraph",
    "LiteratureDevice",
    "DeviceTopology",
    "FeatureComparison",
    "ComparisonResult",
    "ALL_LITERATURE_DEVICES",
    "DESIGN_RULES_FROM_LITERATURE",
    "get_all_literature_devices",
    "get_best_reference",
]
