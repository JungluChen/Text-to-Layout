"""Engineering Reasoner module for answering engineering questions.

This module answers engineering questions based on geometry, topology,
physics graph, dependency graph, and solver evidence. It never answers
from prompt - always from the available data sources.
"""

from textlayout._legacy.engineering_reasoner.reasoner import EngineeringReasoner
from textlayout._legacy.engineering_reasoner.types import (
    EngineeringQuestion,
    EngineeringAnswer,
    AnswerSource,
)

__all__ = [
    "EngineeringReasoner",
    "EngineeringQuestion",
    "EngineeringAnswer",
    "AnswerSource",
]
