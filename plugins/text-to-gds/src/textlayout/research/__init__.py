"""Research / evidence layer: first-principles models that justify a layout.

The first stage of the safe pipeline. Given a component and a physical target,
produce a :class:`ResearchReport` with equations, references, an analytical
estimate, design rationale, limitations, and a recommended simulation — the
evidence that explains *why* the geometry should work, before any EM solve.
"""

from __future__ import annotations

from textlayout.research.engine import has_research, research, research_components
from textlayout.research.models import Equation, Reference, ResearchReport

__all__ = [
    "Equation",
    "Reference",
    "ResearchReport",
    "has_research",
    "research",
    "research_components",
]
