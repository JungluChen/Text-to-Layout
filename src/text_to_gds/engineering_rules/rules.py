"""Base rule structures for the engineering rule engine."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class RuleCategory(str, Enum):
    """Rule categories."""
    
    MICROWAVE = "microwave"
    QUANTUM = "quantum"
    FABRICATION = "fabrication"
    PACKAGING = "packaging"
    MEASUREMENT = "measurement"
    CRYOGENIC = "cryogenic"


class RuleSeverity(str, Enum):
    """Rule severity levels."""
    
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Rule:
    """Engineering rule definition."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: RuleCategory = RuleCategory.MICROWAVE
    severity: RuleSeverity = RuleSeverity.WARNING
    check_fn: Callable[[dict[str, Any]], bool] | None = None
    message_fn: Callable[[dict[str, Any]], str] | None = None
    recommendation_fn: Callable[[dict[str, Any]], str] | None = None
    affected_subsystem: str = ""
    confidence: float = 1.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "severity": self.severity.value,
            "affected_subsystem": self.affected_subsystem,
            "confidence": self.confidence,
        }


@dataclass
class RuleResult:
    """Result of evaluating a rule."""
    
    rule_id: str = ""
    rule_name: str = ""
    passed: bool = True
    severity: RuleSeverity = RuleSeverity.INFO
    message: str = ""
    recommendation: str = ""
    affected_subsystem: str = ""
    confidence: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)
    supporting_geometry: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
            "recommendation": self.recommendation,
            "affected_subsystem": self.affected_subsystem,
            "confidence": self.confidence,
            "details": self.details,
            "supporting_geometry": self.supporting_geometry,
        }
