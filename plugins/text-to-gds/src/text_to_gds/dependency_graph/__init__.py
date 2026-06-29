"""Dependency Graph module for performance-geometry-process mapping.

This module builds a directed acyclic graph (DAG) showing how performance
metrics depend on physics parameters, which depend on geometry, which depends
on process parameters, which depend on mask layout.

Example dependency chain:
    Frequency → Capacitance → IDC overlap → Finger Length → Lithography Bias

This enables answering questions like:
- "Why did the frequency shift?"
- "Which geometry dominates capacitance?"
- "How does process variation affect performance?"
"""

from text_to_gds.dependency_graph.graph import DependencyGraph
from text_to_gds.dependency_graph.types import (
    DependencyNode,
    DependencyEdge,
    DependencyLayer,
    CausalPath,
)

__all__ = [
    "DependencyGraph",
    "DependencyNode",
    "DependencyEdge",
    "DependencyLayer",
    "CausalPath",
]
