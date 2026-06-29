"""Optimization iteration structures."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IterationStatus(str, Enum):
    """Status of an optimization iteration."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass
class OptimizationIteration:
    """A single optimization iteration."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    iteration_number: int = 0
    status: IterationStatus = IterationStatus.PENDING
    start_time: str | None = None
    end_time: str | None = None
    
    # Input state
    input_design: dict[str, Any] = field(default_factory=dict)
    issues_to_address: list[dict[str, Any]] = field(default_factory=list)
    
    # Modifications
    geometry_modifications: list[dict[str, Any]] = field(default_factory=list)
    parameter_changes: list[dict[str, Any]] = field(default_factory=list)
    
    # Output state
    output_design: dict[str, Any] | None = None
    review_result: dict[str, Any] | None = None
    solver_results: dict[str, Any] | None = None
    
    # Metrics
    score_before: float = 0.0
    score_after: float = 0.0
    improvement: float = 0.0
    
    # History
    reason: str = ""
    diff_summary: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "iteration_number": self.iteration_number,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "input_design": self.input_design,
            "issues_to_address": self.issues_to_address,
            "geometry_modifications": self.geometry_modifications,
            "parameter_changes": self.parameter_changes,
            "output_design": self.output_design,
            "review_result": self.review_result,
            "solver_results": self.solver_results,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "improvement": self.improvement,
            "reason": self.reason,
            "diff_summary": self.diff_summary,
        }
