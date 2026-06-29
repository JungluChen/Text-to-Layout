"""Design graph edge types for representing relationships between nodes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EdgeType(str, Enum):
    """Design graph edge types."""
    
    CONTAINS = "contains"
    CONNECTS = "connects"
    COUPLES = "couples"
    FEEDS = "feeds"
    BIASES = "biases"
    GROUNDS = "grounds"
    SHIELDS = "shields"
    ISOLATES = "isolates"


@dataclass
class DesignEdge:
    """Edge in the design graph representing a relationship between nodes."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    edge_type: EdgeType = EdgeType.CONTAINS
    source_id: str = ""
    target_id: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "design_graph"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "edge_type": self.edge_type.value,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "properties": self.properties,
            "confidence": self.confidence,
            "source": self.source,
        }
