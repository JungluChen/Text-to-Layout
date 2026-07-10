"""Structured extraction subpackage for superconducting quantum circuit layouts.

Backward-compatible: re-exports all public symbols from the original extraction.py
(now _legacy.py) so that ``from textlayout._legacy.extraction import ...`` continues to work.
"""

# --- Legacy re-exports (preserve backward compatibility) ----------------------
from textlayout._legacy.extraction._legacy import (  # noqa: F401
    ELECTRON_CHARGE_C,
    PHI0_WEBER,
    PLANCK_J_S,
    _junction_overlap_area_um2,
    extract_physical_parameters,
    labels_from_gds,
    layer_bounding_boxes_from_gds,
    quantity,
    summarize_sidecar_parameters,
    write_extraction,
)

# --- New structured extraction API --------------------------------------------
from textlayout._legacy.extraction.provenance import (  # noqa: F401
    ExtractionProvenance,
    validate_provenance,
)
from textlayout._legacy.extraction.provenance import (  # noqa: F401
    quantity as structured_quantity,
)
from textlayout._legacy.extraction.boolean_extract import (  # noqa: F401
    Finding,
    PolygonRecord,
    boolean_overlap,
    boolean_subtract,
    check_no_accidental_overlap,
)
from textlayout._legacy.extraction.cpw_extract import (  # noqa: F401
    CPWExtraction,
    extract_cpw_parameters,
    verify_cpw_gap_continuity,
    verify_ground_plane_connectivity,
)
from textlayout._legacy.extraction.jj_extract import (  # noqa: F401
    JJExtraction,
    SQUIDExtraction,
    extract_junction_areas,
    extract_squid_parameters,
    verify_junction_count,
)

__all__ = [
    # legacy
    "ELECTRON_CHARGE_C",
    "PHI0_WEBER",
    "PLANCK_J_S",
    "extract_physical_parameters",
    "labels_from_gds",
    "layer_bounding_boxes_from_gds",
    "quantity",
    "summarize_sidecar_parameters",
    "write_extraction",
    # provenance
    "ExtractionProvenance",
    "structured_quantity",
    "validate_provenance",
    # boolean
    "Finding",
    "PolygonRecord",
    "boolean_overlap",
    "boolean_subtract",
    "check_no_accidental_overlap",
    # cpw
    "CPWExtraction",
    "extract_cpw_parameters",
    "verify_cpw_gap_continuity",
    "verify_ground_plane_connectivity",
    # jj
    "JJExtraction",
    "SQUIDExtraction",
    "extract_junction_areas",
    "extract_squid_parameters",
    "verify_junction_count",
]
