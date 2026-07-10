"""Type definitions for the Engineering Reasoner module."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EngineeringQuestion(Enum):
    """Types of engineering questions the reasoner can answer."""
    WHY_BANDWIDTH_LOW = "why_bandwidth_low"
    WHY_GAIN_DROPPED = "why_gain_dropped"
    WHY_Q_CHANGED = "why_q_changed"
    WHY_RESONANCE_SHIFTED = "why_resonance_shifted"
    WHERE_CURRENT_CONCENTRATES = "where_current_concentrates"
    WHERE_ELECTRIC_FIELD_CONCENTRATES = "where_electric_field_concentrates"
    WHICH_GEOMETRY_DOMINATES_CAPACITANCE = "which_geometry_dominates_capacitance"
    WHICH_GEOMETRY_DOMINATES_INDUCTANCE = "which_geometry_dominates_inductance"
    WHAT_LIMITS_PERFORMANCE = "what_limits_performance"
    HOW_TO_IMPROVE = "how_to_improve"
    CUSTOM = "custom"


class AnswerSource(Enum):
    """Sources for engineering answers."""
    GEOMETRY = "geometry"
    TOPOLOGY = "topology"
    PHYSICS_GRAPH = "physics_graph"
    DEPENDENCY_GRAPH = "dependency_graph"
    SOLVER_EVIDENCE = "solver_evidence"
    MEASUREMENT = "measurement"
    LITERATURE = "literature"
    NONE = "none"


@dataclass
class EngineeringAnswer:
    """An answer to an engineering question."""
    
    question: EngineeringQuestion
    """The question that was asked."""
    
    answer: str
    """The answer text."""
    
    sources: list[AnswerSource]
    """Sources used to generate the answer."""
    
    confidence: float
    """Confidence in the answer (0.0 to 1.0)."""
    
    evidence: list[dict[str, Any]]
    """Supporting evidence for the answer."""
    
    reasoning: str
    """Step-by-step reasoning for the answer."""
    
    alternatives: list[str] = field(default_factory=list)
    """Alternative explanations or solutions."""
    
    references: list[str] = field(default_factory=list)
    """Literature references supporting the answer."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "question": self.question.value,
            "answer": self.answer,
            "sources": [s.value for s in self.sources],
            "confidence": self.confidence,
            "evidence": self.evidence,
            "reasoning": self.reasoning,
            "alternatives": self.alternatives,
            "references": self.references,
        }
