"""Design Optimization Engine - orchestrates closed-loop design improvement.

This engine implements a bounded optimization loop that reviews designs,
identifies issues, modifies geometry, and re-verifies until acceptance
or budget exhaustion.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from text_to_gds.design_optimization.iteration import OptimizationIteration, IterationStatus
from text_to_gds.design_optimization.history import OptimizationHistory


class DesignOptimizationEngine:
    """Main engine for closed-loop design optimization.
    
    This engine implements the optimization loop:
    Review → Issue → Geometry modification → Regenerate → Extract →
    Run solvers → Compare → Accept or Reject
    """
    
    def __init__(self, max_iterations: int = 6) -> None:
        """Initialize the design optimization engine.
        
        Parameters
        ----------
        max_iterations:
            Maximum number of optimization iterations.
        """
        self.max_iterations = max_iterations
        self.history = OptimizationHistory()
        self._generate_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
        self._review_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
        self._repair_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None
    
    def set_functions(
        self,
        generate_fn: Callable[[dict[str, Any]], dict[str, Any]],
        review_fn: Callable[[dict[str, Any]], dict[str, Any]],
        repair_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    ) -> None:
        """Set the generate, review, and repair functions.
        
        Parameters
        ----------
        generate_fn:
            Function that generates design from state.
        review_fn:
            Function that reviews design and returns verdict.
        repair_fn:
            Function that repairs design based on review.
        """
        self._generate_fn = generate_fn
        self._review_fn = review_fn
        self._repair_fn = repair_fn
    
    def optimize(
        self,
        initial_state: dict[str, Any],
        accept_threshold: float = 90.0,
    ) -> dict[str, Any]:
        """Run the optimization loop.
        
        Parameters
        ----------
        initial_state:
            Initial design state.
        accept_threshold:
            Score threshold for acceptance.
        
        Returns
        -------
        dict with optimization_result.json schema.
        """
        if not all([self._generate_fn, self._review_fn, self._repair_fn]):
            return {"error": "Generate, review, and repair functions must be set"}
        
        self.history.set_initial_design(initial_state)
        
        current_state = initial_state
        iteration_number = 0
        
        while iteration_number < self.max_iterations:
            iteration = OptimizationIteration(
                iteration_number=iteration_number,
                status=IterationStatus.IN_PROGRESS,
                start_time=datetime.now().isoformat(),
                input_design=current_state,
            )
            
            # Generate design
            try:
                design = self._generate_fn(current_state)  # type: ignore
            except Exception as e:
                iteration.status = IterationStatus.FAILED
                iteration.reason = f"Generation failed: {e}"
                iteration.end_time = datetime.now().isoformat()
                self.history.add_iteration(iteration)
                break
            
            # Review design
            try:
                review_result = self._review_fn(design)  # type: ignore
            except Exception as e:
                iteration.status = IterationStatus.FAILED
                iteration.reason = f"Review failed: {e}"
                iteration.end_time = datetime.now().isoformat()
                self.history.add_iteration(iteration)
                break
            
            # Extract score
            score = review_result.get("score", 0.0)
            iteration.output_design = design
            iteration.review_result = review_result
            iteration.score_after = score
            
            # Check if accepted
            if score >= accept_threshold:
                iteration.status = IterationStatus.ACCEPTED
                iteration.reason = f"Score {score} >= threshold {accept_threshold}"
                iteration.end_time = datetime.now().isoformat()
                self.history.add_iteration(iteration)
                self.history.set_final_design(design)
                break
            
            # Extract issues
            issues = review_result.get("issues", [])
            iteration.issues_to_address = issues
            
            # Repair design
            try:
                repaired_state = self._repair_fn(current_state, review_result)  # type: ignore
            except Exception as e:
                iteration.status = IterationStatus.FAILED
                iteration.reason = f"Repair failed: {e}"
                iteration.end_time = datetime.now().isoformat()
                self.history.add_iteration(iteration)
                break
            
            # Calculate improvement
            if iteration_number > 0:
                prev_iteration = self.history.get_iterations()[-1]
                iteration.score_before = prev_iteration.score_after
            else:
                iteration.score_before = 0.0
            
            iteration.improvement = iteration.score_after - iteration.score_before
            
            # Complete iteration
            iteration.status = IterationStatus.COMPLETED
            iteration.reason = f"Score {score} < threshold {accept_threshold}"
            iteration.end_time = datetime.now().isoformat()
            self.history.add_iteration(iteration)
            
            # Update state for next iteration
            current_state = repaired_state
            iteration_number += 1
        
        # Build result
        result = self._build_result()
        
        return result
    
    def _build_result(self) -> dict[str, Any]:
        """Build the optimization result."""
        summary = self.history.get_summary()
        accepted = self.history.get_accepted_iteration()
        
        return {
            "schema": "text-to-gds.optimization-result.v1",
            "accepted": accepted is not None,
            "iterations": summary["total_iterations"],
            "final_score": summary["final_score"],
            "total_improvement": summary["total_improvement"],
            "history": self.history.to_dict(),
        }


def run_design_optimization(
    initial_state: dict[str, Any],
    generate_fn: Callable[[dict[str, Any]], dict[str, Any]],
    review_fn: Callable[[dict[str, Any]], dict[str, Any]],
    repair_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    max_iterations: int = 6,
    accept_threshold: float = 90.0,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """High-level function to run design optimization.
    
    Parameters
    ----------
    initial_state:
        Initial design state.
    generate_fn:
        Function that generates design from state.
    review_fn:
        Function that reviews design and returns verdict.
    repair_fn:
        Function that repairs design based on review.
    max_iterations:
        Maximum number of iterations.
    accept_threshold:
        Score threshold for acceptance.
    output_path:
        Optional path to write the optimization result JSON.
    
    Returns
    -------
    dict with optimization_result.json schema.
    """
    engine = DesignOptimizationEngine(max_iterations=max_iterations)
    engine.set_functions(generate_fn, review_fn, repair_fn)
    
    result = engine.optimize(
        initial_state=initial_state,
        accept_threshold=accept_threshold,
    )
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    
    return result
