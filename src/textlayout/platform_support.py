"""Explicit platform-support and solver-evidence state vocabularies.

These states intentionally prevent a successful import, install, or version
probe from being collapsed into a vague ``ready=True`` claim.
"""

from __future__ import annotations

from enum import Enum


class PlatformSupportState(str, Enum):
    """Evidence-backed support level for a platform or capability."""

    UNTESTED = "UNTESTED"
    CORE_TESTED = "CORE_TESTED"
    CORE_CERTIFIED = "CORE_CERTIFIED"
    SOLVER_PARTIAL = "SOLVER_PARTIAL"
    SOLVER_CERTIFIED = "SOLVER_CERTIFIED"
    UNSUPPORTED = "UNSUPPORTED"


class SolverEvidenceStage(str, Enum):
    """Highest completed stage for one external numerical solver."""

    NOT_INSTALLED = "NOT_INSTALLED"
    FOUND = "FOUND"
    PROBE_PASS = "PROBE_PASS"
    EXECUTION_PASS = "EXECUTION_PASS"
    OUTPUT_PARSED = "OUTPUT_PARSED"
    CONVERGENCE_PROVEN = "CONVERGENCE_PROVEN"


SUPPORT_STATE_VALUES = frozenset(state.value for state in PlatformSupportState)
SOLVER_EVIDENCE_STAGE_VALUES = frozenset(stage.value for stage in SolverEvidenceStage)
