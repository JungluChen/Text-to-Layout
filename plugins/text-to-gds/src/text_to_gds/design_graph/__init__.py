"""Design Graph module for hierarchical engineering representation.

This module provides a higher abstraction layer than the physics graph,
organizing geometry features into a hierarchical structure:
Device → Subsystem → Functional Block → Geometry Feature → Polygon
"""

from text_to_gds.design_graph.engine import DesignGraphEngine
from text_to_gds.design_graph.nodes import (
    DesignNode,
    DeviceNode,
    SubsystemNode,
    FunctionalBlockNode,
    GeometryFeatureNode,
    PolygonNode,
    NodeType,
)
from text_to_gds.design_graph.edges import DesignEdge, EdgeType

__all__ = [
    "DesignGraphEngine",
    "DesignNode",
    "DeviceNode",
    "SubsystemNode",
    "FunctionalBlockNode",
    "GeometryFeatureNode",
    "PolygonNode",
    "NodeType",
    "DesignEdge",
    "EdgeType",
]
