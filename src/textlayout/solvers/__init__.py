"""Shared external-solver adapter contracts."""

from textlayout.solvers.base import SolverAdapter, SolverExecution, run_subprocess
from textlayout.solvers.josephsoncircuits import JosephsonCircuitsAdapter

__all__ = ["JosephsonCircuitsAdapter", "SolverAdapter", "SolverExecution", "run_subprocess"]
