"""Design graph node types for hierarchical engineering representation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    """Design graph node types."""
    
    DEVICE = "device"
    SUBSYSTEM = "subsystem"
    FUNCTIONAL_BLOCK = "functional_block"
    GEOMETRY_FEATURE = "geometry_feature"
    POLYGON = "polygon"


@dataclass
class DesignNode:
    """Base class for all design graph nodes."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_type: NodeType = NodeType.DEVICE
    name: str = ""
    description: str = ""
    parent_id: str | None = None
    children_ids: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "design_graph"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "properties": self.properties,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass
class DeviceNode(DesignNode):
    """Top-level device node (e.g., JPA, Transmon, Resonator)."""
    
    node_type: NodeType = NodeType.DEVICE
    device_type: str = ""
    operating_frequency_ghz: float | None = None
    target_specifications: dict[str, Any] = field(default_factory=dict)
    topology_confidence: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        base = super().to_dict()
        base.update({
            "device_type": self.device_type,
            "operating_frequency_ghz": self.operating_frequency_ghz,
            "target_specifications": self.target_specifications,
            "topology_confidence": self.topology_confidence,
        })
        return base


@dataclass
class SubsystemNode(DesignNode):
    """Subsystem node (e.g., Resonator, SQUID, Feedline)."""
    
    node_type: NodeType = NodeType.SUBSYSTEM
    subsystem_type: str = ""
    function: str = ""
    key_parameters: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        base = super().to_dict()
        base.update({
            "subsystem_type": self.subsystem_type,
            "function": self.function,
            "key_parameters": self.key_parameters,
        })
        return base


@dataclass
class FunctionalBlockNode(DesignNode):
    """Functional block node (e.g., IDC, CPW segment, Coupler)."""
    
    node_type: NodeType = NodeType.FUNCTIONAL_BLOCK
    block_type: str = ""
    electrical_role: str = ""
    dimensions: dict[str, Any] = field(default_factory=dict)
    engineering_properties: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        base = super().to_dict()
        base.update({
            "block_type": self.block_type,
            "electrical_role": self.electrical_role,
            "dimensions": self.dimensions,
            "engineering_properties": self.engineering_properties,
        })
        return base


@dataclass
class GeometryFeatureNode(DesignNode):
    """Geometry feature node (e.g., Finger, Gap, Pad)."""
    
    node_type: NodeType = NodeType.GEOMETRY_FEATURE
    feature_type: str = ""
    bounding_box: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    dimensions: dict[str, Any] = field(default_factory=dict)
    material: str = ""
    layer: tuple[int, int] = (0, 0)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        base = super().to_dict()
        base.update({
            "feature_type": self.feature_type,
            "bounding_box": self.bounding_box,
            "dimensions": self.dimensions,
            "material": self.material,
            "layer": list(self.layer),
        })
        return base


@dataclass
class PolygonNode(DesignNode):
    """Polygon node (lowest level geometry)."""
    
    node_type: NodeType = NodeType.POLYGON
    vertices: list[list[float]] = field(default_factory=list)
    layer: tuple[int, int] = (0, 0)
    area_um2: float = 0.0
    perimeter_um: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        base = super().to_dict()
        base.update({
            "vertices": self.vertices,
            "layer": list(self.layer),
            "area_um2": self.area_um2,
            "perimeter_um": self.perimeter_um,
        })
        return base
