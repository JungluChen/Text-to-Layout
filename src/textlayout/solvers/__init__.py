"""Shared external-solver adapter contracts."""

from textlayout.solvers.base import SolverAdapter, SolverExecution, run_subprocess
from textlayout.solvers.josephsoncircuits import JosephsonCircuitsAdapter
from textlayout.solvers.palace import PalaceBackend

__all__ = [
    "JosephsonCircuitsAdapter",
    "PalaceBackend",
    "SolverAdapter",
    "SolverExecution",
    "run_subprocess",
]
