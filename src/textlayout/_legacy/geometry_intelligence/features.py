"""Geometry feature types and data structures for semantic geometry recognition."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FeatureType(str, Enum):
    """Supported geometry feature types."""
    
    CPW = "cpw"
    IDC = "idc"
    TAPER = "taper"
    LAUNCH_PAD = "launch_pad"
    BOND_PAD = "bond_pad"
    SQUID_LOOP = "squid_loop"
    JOSEPHSON_JUNCTION = "josephson_junction"
    CAPACITOR_PADDLE = "capacitor_paddle"
    RESONATOR = "resonator"
    FLUX_LINE = "flux_line"
    VIA_FENCE = "via_fence"
    AIRBRIDGE = "airbridge"
    GROUND_POCKET = "ground_pocket"
    GROUND_BRIDGE = "ground_bridge"
    CROSSOVER = "crossover"
    CURRENT_BOTTLENECK = "current_bottleneck"
    MEANDER = "meander"
    ISLAND = "island"
    COUPLER = "coupler"
    FEEDLINE = "feedline"
    UNKNOWN = "unknown"


@dataclass
class GeometryFeature:
    """A recognized geometry feature with engineering meaning."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    feature_type: FeatureType = FeatureType.UNKNOWN
    name: str = ""
    bounding_box: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    electrical_role: str = ""
    parent_subsystem: str = ""
    connected_nets: list[str] = field(default_factory=list)
    dimensions: dict[str, Any] = field(default_factory=dict)
    engineering_properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    source: str = "geometry_intelligence"
    provenance: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "feature_type": self.feature_type.value,
            "name": self.name,
            "bounding_box": self.bounding_box,
            "electrical_role": self.electrical_role,
            "parent_subsystem": self.parent_subsystem,
            "connected_nets": self.connected_nets,
            "dimensions": self.dimensions,
            "engineering_properties": self.engineering_properties,
            "confidence": self.confidence,
            "source": self.source,
            "provenance": self.provenance,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeometryFeature:
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            feature_type=FeatureType(data.get("feature_type", "unknown")),
            name=data.get("name", ""),
            bounding_box=data.get("bounding_box", [0.0, 0.0, 0.0, 0.0]),
            electrical_role=data.get("electrical_role", ""),
            parent_subsystem=data.get("parent_subsystem", ""),
            connected_nets=data.get("connected_nets", []),
            dimensions=data.get("dimensions", {}),
            engineering_properties=data.get("engineering_properties", {}),
            confidence=data.get("confidence", 0.0),
            source=data.get("source", "geometry_intelligence"),
            provenance=data.get("provenance", {}),
        )
    
    @property
    def width_um(self) -> float:
        """Feature width in micrometers."""
        if len(self.bounding_box) >= 4:
            return max(0.0, self.bounding_box[2] - self.bounding_box[0])
        return 0.0
    
    @property
    def height_um(self) -> float:
        """Feature height in micrometers."""
        if len(self.bounding_box) >= 4:
            return max(0.0, self.bounding_box[3] - self.bounding_box[1])
        return 0.0
    
    @property
    def area_um2(self) -> float:
        """Feature area in square micrometers."""
        return self.width_um * self.height_um
    
    @property
    def center(self) -> tuple[float, float]:
        """Feature center coordinates."""
        if len(self.bounding_box) >= 4:
            return (
                (self.bounding_box[0] + self.bounding_box[2]) / 2.0,
                (self.bounding_box[1] + self.bounding_box[3]) / 2.0,
            )
        return (0.0, 0.0)
