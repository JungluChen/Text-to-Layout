"""Visualization view types and structures."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ViewType(str, Enum):
    """Types of visualization views."""
    
    GEOMETRY_VIEW = "geometry_view"
    TOPOLOGY_VIEW = "topology_view"
    CURRENT_FLOW_VIEW = "current_flow_view"
    ELECTRIC_FIELD_VIEW = "electric_field_view"
    MAGNETIC_FIELD_VIEW = "magnetic_field_view"
    CRITICAL_DIMENSION_VIEW = "critical_dimension_view"
    SUBSYSTEM_VIEW = "subsystem_view"
    FEATURE_IMPORTANCE_VIEW = "feature_importance_view"
    DESIGN_GRAPH_VIEW = "design_graph_view"
    REVIEW_OVERLAY = "review_overlay"


@dataclass
class VisualizationView:
    """A visualization view with metadata."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    view_type: ViewType = ViewType.GEOMETRY_VIEW
    title: str = ""
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    figure_path: str | None = None
    confidence: float = 1.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "view_type": self.view_type.value,
            "title": self.title,
            "description": self.description,
            "data": self.data,
            "figure_path": self.figure_path,
            "confidence": self.confidence,
        }
