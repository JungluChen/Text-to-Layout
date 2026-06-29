"""Design Optimization Engine for closed-loop design improvement.

This module provides closed-loop optimization for superconducting quantum circuits,
iterating through review, issue identification, geometry modification, and
re-verification.
"""

from text_to_gds.design_optimization.engine import DesignOptimizationEngine
from text_to_gds.design_optimization.iteration import OptimizationIteration, IterationStatus
from text_to_gds.design_optimization.history import OptimizationHistory

__all__ = [
    "DesignOptimizationEngine",
    "OptimizationIteration",
    "IterationStatus",
    "OptimizationHistory",
]
