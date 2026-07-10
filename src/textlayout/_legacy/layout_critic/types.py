"""Type definitions for the Layout Critic module."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ReviewCategory(Enum):
    """Categories of review issues."""
    MICROWAVE = "microwave"
    QUANTUM = "quantum"
    FABRICATION = "fabrication"
    PACKAGING = "packaging"
    MEASUREMENT = "measurement"
    CRYOGENIC = "cryogenic"
    LAYOUT = "layout"


class ReviewSeverity(Enum):
    """Severity levels for review issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ReviewIssue:
    """A single issue identified during review."""
    
    id: str
    """Unique identifier for this issue."""
    
    category: ReviewCategory
    """Category of the issue."""
    
    severity: ReviewSeverity
    """Severity of the issue."""
    
    issue: str
    """Description of what is wrong."""
    
    physical_consequence: str
    """How this issue affects device performance."""
    
    supporting_evidence: list[str]
    """Data supporting this issue."""
    
    reference: str
    """Literature or design rule reference."""
    
    suggested_modification: str
    """How to fix this issue."""
    
    expected_improvement: str
    """What improvement to expect after fixing."""
    
    confidence: float
    """Confidence in this review (0.0 to 1.0)."""
    
    location: str = ""
    """Location of the issue in the layout (if applicable)."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity.value,
            "issue": self.issue,
            "physical_consequence": self.physical_consequence,
            "supporting_evidence": self.supporting_evidence,
            "reference": self.reference,
            "suggested_modification": self.suggested_modification,
            "expected_improvement": self.expected_improvement,
            "confidence": self.confidence,
            "location": self.location,
        }


@dataclass
class ReviewReport:
    """Complete review report for a design."""
    
    design_id: str
    """ID of the design being reviewed."""
    
    issues: list[ReviewIssue]
    """All issues identified during review."""
    
    overall_score: float
    """Overall review score (0.0 to 1.0)."""
    
    passed: bool
    """Whether the design passed review."""
    
    summary: str
    """Summary of the review."""
    
    recommendations: list[str]
    """High-level recommendations."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "design_id": self.design_id,
            "issues": [i.to_dict() for i in self.issues],
            "overall_score": self.overall_score,
            "passed": self.passed,
            "summary": self.summary,
            "recommendations": self.recommendations,
        }
