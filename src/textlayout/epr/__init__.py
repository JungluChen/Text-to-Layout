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
    FIELD_ENERGY_EXPORT_SCHEMA,
    AnalyticalEPRBackend,
    EPRBackend,
    FieldEnergyImportBackend,
    PyEPRBackend,
    characteristic_gap_um,
    default_epr_backend,
)
from textlayout.epr.coherence import estimate_coherence
from textlayout.epr.materials import (
    MATERIALS_DIR,
    LossChannel,
    MaterialsDB,
    illustrative_silicon_db,
    load_materials_db,
)
from textlayout.epr.models import (
    EPR_SOLVER_BACKED_STATUSES,
    EPR_STATUS_ANALYTICAL,
    EPR_STATUS_EXECUTED,
    EPR_STATUS_FIELD_ENERGY_IMPORTED,
    EPR_STATUS_INPUT_PREPARED,
    EPR_STATUS_SKIPPED,
    CoherenceEstimate,
    EPRResult,
    ParticipationRecord,
)
from textlayout.epr.pdk_bridge import (
    DEFAULT_PDK_NAME,
    materials_db_from_pdk,
    resolve_pdk_path,
)
from textlayout.epr.report import render_markdown, write_epr_report

__all__ = [
    "EPR_SOLVER_BACKED_STATUSES",
    "EPR_STATUS_ANALYTICAL",
    "EPR_STATUS_EXECUTED",
    "EPR_STATUS_FIELD_ENERGY_IMPORTED",
    "EPR_STATUS_INPUT_PREPARED",
    "EPR_STATUS_SKIPPED",
    "DEFAULT_PDK_NAME",
    "FIELD_ENERGY_EXPORT_SCHEMA",
    "MATERIALS_DIR",
    "AnalyticalEPRBackend",
    "CoherenceEstimate",
    "EPRBackend",
    "EPRResult",
    "FieldEnergyImportBackend",
    "LossChannel",
    "MaterialsDB",
    "ParticipationRecord",
    "PyEPRBackend",
    "characteristic_gap_um",
    "default_epr_backend",
    "estimate_coherence",
    "illustrative_silicon_db",
    "load_materials_db",
    "materials_db_from_pdk",
    "resolve_pdk_path",
    "render_markdown",
    "write_epr_report",
]
