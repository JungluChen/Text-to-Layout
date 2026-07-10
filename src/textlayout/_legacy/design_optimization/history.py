"""Optimization history tracking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout._legacy.design_optimization.iteration import OptimizationIteration, IterationStatus


class OptimizationHistory:
    """Tracks the history of optimization iterations."""
    
    def __init__(self) -> None:
        """Initialize the optimization history."""
        self._iterations: list[OptimizationIteration] = []
        self._initial_design: dict[str, Any] | None = None
        self._final_design: dict[str, Any] | None = None
    
    def set_initial_design(self, design: dict[str, Any]) -> None:
        """Set the initial design."""
        self._initial_design = design
    
    def add_iteration(self, iteration: OptimizationIteration) -> None:
        """Add an iteration to the history."""
        self._iterations.append(iteration)
    
    def set_final_design(self, design: dict[str, Any]) -> None:
        """Set the final design."""
        self._final_design = design
    
    def get_iterations(self) -> list[OptimizationIteration]:
        """Get all iterations."""
        return self._iterations
    
    def get_latest_iteration(self) -> OptimizationIteration | None:
        """Get the latest iteration."""
        if self._iterations:
            return self._iterations[-1]
        return None
    
    def get_accepted_iteration(self) -> OptimizationIteration | None:
        """Get the first accepted iteration."""
        for iteration in self._iterations:
            if iteration.status == IterationStatus.ACCEPTED:
                return iteration
        return None
    
    def get_total_improvement(self) -> float:
        """Get total improvement across all iterations."""
        if len(self._iterations) < 2:
            return 0.0
        
        first_score = self._iterations[0].score_before
        last_score = self._iterations[-1].score_after
        
        return last_score - first_score
    
    def get_summary(self) -> dict[str, Any]:
        """Get optimization summary."""
        total_iterations = len(self._iterations)
        accepted_iterations = sum(
            1 for i in self._iterations if i.status == IterationStatus.ACCEPTED
        )
        failed_iterations = sum(
            1 for i in self._iterations if i.status == IterationStatus.FAILED
        )
        
        return {
            "total_iterations": total_iterations,
            "accepted_iterations": accepted_iterations,
            "failed_iterations": failed_iterations,
            "total_improvement": self.get_total_improvement(),
            "initial_score": self._iterations[0].score_before if self._iterations else 0.0,
            "final_score": self._iterations[-1].score_after if self._iterations else 0.0,
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "initial_design": self._initial_design,
            "iterations": [i.to_dict() for i in self._iterations],
            "final_design": self._final_design,
            "summary": self.get_summary(),
        }
    
    def save(self, path: str | Path) -> None:
        """Save history to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
    
    @classmethod
    def load(cls, path: str | Path) -> OptimizationHistory:
        """Load history from JSON file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        
        history = cls()
        history._initial_design = data.get("initial_design")
        history._final_design = data.get("final_design")
        
        for iteration_data in data.get("iterations", []):
            iteration = OptimizationIteration()
            iteration.id = iteration_data.get("id", "")
            iteration.iteration_number = iteration_data.get("iteration_number", 0)
            iteration.status = IterationStatus(iteration_data.get("status", "pending"))
            iteration.start_time = iteration_data.get("start_time")
            iteration.end_time = iteration_data.get("end_time")
            iteration.input_design = iteration_data.get("input_design", {})
            iteration.issues_to_address = iteration_data.get("issues_to_address", [])
            iteration.geometry_modifications = iteration_data.get("geometry_modifications", [])
            iteration.parameter_changes = iteration_data.get("parameter_changes", [])
            iteration.output_design = iteration_data.get("output_design")
            iteration.review_result = iteration_data.get("review_result")
            iteration.solver_results = iteration_data.get("solver_results")
            iteration.score_before = iteration_data.get("score_before", 0.0)
            iteration.score_after = iteration_data.get("score_after", 0.0)
            iteration.improvement = iteration_data.get("improvement", 0.0)
            iteration.reason = iteration_data.get("reason", "")
            iteration.diff_summary = iteration_data.get("diff_summary", "")
            history._iterations.append(iteration)
        
        return history
