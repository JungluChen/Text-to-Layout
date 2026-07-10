"""Type definitions for the Dependency Graph module."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DependencyLayer(Enum):
    """Layers in the dependency graph."""
    PERFORMANCE = "performance"
    PHYSICS = "physics"
    GEOMETRY = "geometry"
    PROCESS = "process"
    MASK = "mask"


@dataclass
class DependencyNode:
    """A node in the dependency graph."""
    
    id: str
    """Unique identifier for this node."""
    
    name: str
    """Human-readable name."""
    
    layer: DependencyLayer
    """Which layer this node belongs to."""
    
    value: Any = None
    """Current value of this parameter."""
    
    unit: str = ""
    """Physical unit of the value."""
    
    description: str = ""
    """Description of what this parameter represents."""
    
    source: str = ""
    """Source of the value (geometry, solver, measurement, etc.)."""
    
    confidence: float = 1.0
    """Confidence in the value (0.0 to 1.0)."""
    
    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata about this node."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "layer": self.layer.value,
            "value": self.value,
            "unit": self.unit,
            "description": self.description,
            "source": self.source,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class DependencyEdge:
    """An edge in the dependency graph."""
    
    source_id: str
    """ID of the source node."""
    
    target_id: str
    """ID of the target node."""
    
    relationship: str
    """Type of relationship (causes, affects, depends_on, etc.)."""
    
    sensitivity: float = 0.0
    """Sensitivity of target to source (df/dx)."""
    
    description: str = ""
    """Description of the relationship."""
    
    formula: str = ""
    """Formula describing the relationship (if known)."""
    
    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata about this edge."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship,
            "sensitivity": self.sensitivity,
            "description": self.description,
            "formula": self.formula,
            "metadata": self.metadata,
        }


@dataclass
class CausalPath:
    """A path through the dependency graph showing causality."""
    
    nodes: list[DependencyNode]
    """Nodes in the path, ordered from cause to effect."""
    
    edges: list[DependencyEdge]
    """Edges connecting the nodes."""
    
    total_sensitivity: float = 0.0
    """Total sensitivity along the path."""
    
    description: str = ""
    """Human-readable description of the causal path."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "total_sensitivity": self.total_sensitivity,
            "description": self.description,
        }
