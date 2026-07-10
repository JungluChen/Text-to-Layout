"""Evidence types and structures for topology reasoning."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvidenceType(str, Enum):
    """Types of evidence for topology classification."""
    
    GEOMETRY_PRESENT = "geometry_present"
    GEOMETRY_ABSENT = "geometry_absent"
    PARAMETER_MATCH = "parameter_match"
    PARAMETER_MISMATCH = "parameter_mismatch"
    SPATIAL_RELATION = "spatial_relation"
    ELECTRICAL_CONNECTION = "electrical_connection"
    DIMENSIONAL_MATCH = "dimensional_match"
    TOPOLOGICAL_FEATURE = "topological_feature"


@dataclass
class TopologyEvidence:
    """Evidence for or against a topology classification."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    evidence_type: EvidenceType = EvidenceType.GEOMETRY_PRESENT
    description: str = ""
    supporting: bool = True
    confidence: float = 1.0
    source: str = "topology_reasoning"
    details: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "evidence_type": self.evidence_type.value,
            "description": self.description,
            "supporting": self.supporting,
            "confidence": self.confidence,
            "source": self.source,
            "details": self.details,
        }


@dataclass
class TopologyClassification:
    """Result of topology classification with evidence."""
    
    topology: str = "unknown"
    confidence: float = 0.0
    supporting_evidence: list[TopologyEvidence] = field(default_factory=list)
    missing_evidence: list[TopologyEvidence] = field(default_factory=list)
    alternative_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    classification_reasoning: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "topology": self.topology,
            "confidence": self.confidence,
            "supporting_evidence": [e.to_dict() for e in self.supporting_evidence],
            "missing_evidence": [e.to_dict() for e in self.missing_evidence],
            "alternative_hypotheses": self.alternative_hypotheses,
            "classification_reasoning": self.classification_reasoning,
        }
