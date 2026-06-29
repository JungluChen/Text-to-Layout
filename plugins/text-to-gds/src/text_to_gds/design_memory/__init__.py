"""Design Memory module for storing and retrieving design cases.

This module stores every design as an engineering case with layout,
parameters, physics, solver results, measurements, reviews, and
fabrication data. It supports nearest-neighbor search and similarity
search for finding related designs.
"""

from text_to_gds.design_memory.memory import DesignMemory
from text_to_gds.design_memory.types import (
    DesignCase,
    DesignSearchResult,
    DesignSimilarity,
)

__all__ = [
    "DesignMemory",
    "DesignCase",
    "DesignSearchResult",
    "DesignSimilarity",
]
