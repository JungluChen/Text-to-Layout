"""Type definitions for the Device Classifier module."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeviceType(Enum):
    """Recognized quantum device types."""
    POCKET_TRANSMON = "pocket_transmon"
    XMON = "xmon"
    CONCENTRIC_TRANSMON = "concentric_transmon"
    FLUXONIUM = "fluxonium"
    LUMPED_JPA = "lumped_jpa"
    QUARTER_WAVE_JPA = "quarter_wave_jpa"
    TWPA = "twpa"
    IDC_RESONATOR = "idc_resonator"
    CPW_RESONATOR = "cpw_resonator"
    CALIBRATION_CHIP = "calibration_chip"
    JJ_ARRAY = "jj_array"
    UNKNOWN = "unknown"


@dataclass
class ClassificationEvidence:
    """Evidence supporting a device classification."""
    
    feature_type: str
    """Type of evidence (geometry, topology, physics, port, dimension)."""
    
    description: str
    """Human-readable description of the evidence."""
    
    value: Any
    """Numerical or categorical value of the evidence."""
    
    source: str
    """Source of the evidence (geometry_graph, physics_graph, topology, etc.)."""
    
    confidence: float = 1.0
    """Confidence in this evidence (0.0 to 1.0)."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "feature_type": self.feature_type,
            "description": self.description,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class AlternativeHypothesis:
    """Alternative device classification hypothesis."""
    
    device_type: DeviceType
    """Alternative device type."""
    
    confidence: float
    """Confidence in this alternative (0.0 to 1.0)."""
    
    reasoning: str
    """Why this alternative was considered but not selected."""
    
    missing_evidence: list[str] = field(default_factory=list)
    """Evidence that would support this alternative."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "device_type": self.device_type.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "missing_evidence": self.missing_evidence,
        }


@dataclass
class ClassificationResult:
    """Result of device classification."""
    
    device_type: DeviceType
    """Classified device type."""
    
    confidence: float
    """Classification confidence (0.0 to 1.0)."""
    
    evidence: list[ClassificationEvidence]
    """Evidence supporting the classification."""
    
    alternatives: list[AlternativeHypothesis]
    """Alternative hypotheses considered."""
    
    reasoning: str
    """Summary of classification reasoning."""
    
    geometry_features: list[str] = field(default_factory=list)
    """Key geometry features used for classification."""
    
    topology_features: list[str] = field(default_factory=list)
    """Key topology features used for classification."""
    
    physics_features: list[str] = field(default_factory=list)
    """Key physics features used for classification."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "device_type": self.device_type.value,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "alternatives": [a.to_dict() for a in self.alternatives],
            "reasoning": self.reasoning,
            "geometry_features": self.geometry_features,
            "topology_features": self.topology_features,
            "physics_features": self.physics_features,
        }
