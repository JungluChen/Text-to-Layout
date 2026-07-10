"""Design Optimization Engine for closed-loop design improvement.

This module provides closed-loop optimization for superconducting quantum circuits,
iterating through review, issue identification, geometry modification, and
re-verification.
"""

from textlayout._legacy.design_optimization.engine import DesignOptimizationEngine
from textlayout._legacy.design_optimization.iteration import OptimizationIteration, IterationStatus
from textlayout._legacy.design_optimization.history import OptimizationHistory

__all__ = [
    "DesignOptimizationEngine",
    "OptimizationIteration",
    "IterationStatus",
    "OptimizationHistory",
]
