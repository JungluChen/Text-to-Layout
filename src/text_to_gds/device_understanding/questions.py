"""Engineering question and answer structures."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QuestionType(str, Enum):
    """Types of engineering questions."""
    
    DEVICE_IDENTIFICATION = "device_identification"
    FEATURE_PURPOSE = "feature_purpose"
    OPERATING_FREQUENCY = "operating_frequency"
    NONLINEAR_ELEMENT = "nonlinear_element"
    CURRENT_FLOW = "current_flow"
    ELECTRIC_FIELD = "electric_field"
    MAGNETIC_FIELD = "magnetic_field"
    BANDWIDTH_LIMIT = "bandwidth_limit"
    COUPLING_MECHANISM = "coupling_mechanism"
    DESIGN_RATIONALE = "design_rationale"


@dataclass
class EngineeringQuestion:
    """An engineering question about the device."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    question_type: QuestionType = QuestionType.DEVICE_IDENTIFICATION
    question_text: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "question_type": self.question_type.value,
            "question_text": self.question_text,
            "context": self.context,
        }


@dataclass
class EngineeringAnswer:
    """An engineering answer with evidence."""
    
    question_id: str = ""
    answer_text: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    supporting_data: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "question_id": self.question_id,
            "answer_text": self.answer_text,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "supporting_data": self.supporting_data,
            "limitations": self.limitations,
        }
