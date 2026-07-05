"""Energy-participation-ratio (EPR) analysis and coherence estimation.

Public API:

- :class:`EPRBackend`, :class:`AnalyticalEPRBackend`, :class:`PyEPRBackend`
- :func:`default_epr_backend`
- :func:`estimate_coherence`
- :class:`EPRResult`, :class:`ParticipationRecord`, :class:`CoherenceEstimate`
- :class:`MaterialsDB`, :class:`LossChannel`, :func:`illustrative_silicon_db`
- :func:`write_epr_report`
"""

from textlayout.epr.backends import (
    AnalyticalEPRBackend,
    EPRBackend,
    PyEPRBackend,
    characteristic_gap_um,
    default_epr_backend,
)
from textlayout.epr.coherence import estimate_coherence
from textlayout.epr.materials import LossChannel, MaterialsDB, illustrative_silicon_db
from textlayout.epr.models import (
    EPR_STATUS_ANALYTICAL,
    EPR_STATUS_EXECUTED,
    EPR_STATUS_SKIPPED,
    CoherenceEstimate,
    EPRResult,
    ParticipationRecord,
)
from textlayout.epr.report import render_markdown, write_epr_report

__all__ = [
    "EPR_STATUS_ANALYTICAL",
    "EPR_STATUS_EXECUTED",
    "EPR_STATUS_SKIPPED",
    "AnalyticalEPRBackend",
    "CoherenceEstimate",
    "EPRBackend",
    "EPRResult",
    "LossChannel",
    "MaterialsDB",
    "ParticipationRecord",
    "PyEPRBackend",
    "characteristic_gap_um",
    "default_epr_backend",
    "estimate_coherence",
    "illustrative_silicon_db",
    "render_markdown",
    "write_epr_report",
]
