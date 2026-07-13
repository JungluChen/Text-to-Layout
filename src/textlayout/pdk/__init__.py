"""Foundry PDK abstraction: typed process schema beyond ``generic_2metal``.

See :mod:`textlayout.pdk.models` for why this exists and how it relates to
:class:`textlayout.models.Technology`. Quick start:

    from textlayout.pdk import load_pdk, pdk_to_technology
    pdk = load_pdk("src/textlayout/knowledge/pdks/example_superconducting_pdk.yaml")
    technology = pdk_to_technology(pdk)   # usable anywhere a Technology is needed

**No PDK shipped in this repository is foundry-validated** — see each YAML's
``foundry_validated`` field and docs/pdk_abstraction.md.
"""

from textlayout.pdk.convert import pdk_to_technology
from textlayout.pdk.drc import DensityCheckResult, check_density, check_layer_exists
from textlayout.pdk.klayout_drc import (
    DRC_REPORT_SCHEMA,
    SUPPORTED_RULES,
    UNSUPPORTED_RULES,
    DRCCheck,
    DRCReport,
    DRCViolation,
    run_drc,
    to_lydrc,
)
from textlayout.pdk.loader import load_pdk, write_pdk
from textlayout.pdk.lvs import (
    LVS_SCHEMA,
    STATUS_MATCH,
    STATUS_MISMATCH,
    STATUS_SKIPPED_NOT_IMPLEMENTED,
    LVSChecker,
    LVSReport,
    Netlist,
    NetlistDevice,
    NotImplementedLVSChecker,
    compare_partial_connectivity_lvs,
    extract_connectivity_nets,
    run_partial_connectivity_lvs,
)
from textlayout.pdk.models import (
    PDKEnclosure,
    PDKOverlap,
    CALIBRATION_FOUNDRY,
    CALIBRATION_ILLUSTRATIVE,
    CALIBRATION_INTERNAL,
    PDK_SCHEMA,
    PDK,
    PDKGrid,
    PDKJunctionProcess,
    PDKLayer,
    PDKSeparation,
    PDKSubstrate,
)
from textlayout.pdk.provenance import (
    PDK_PROVENANCE_SCHEMA,
    PDKProvenance,
    describe_pdk_file,
    find_pdk_provenance_for_technology,
    pdk_from_provenance,
)

__all__ = [
    "CALIBRATION_FOUNDRY",
    "CALIBRATION_ILLUSTRATIVE",
    "CALIBRATION_INTERNAL",
    "LVS_SCHEMA",
    "PDK",
    "PDK_PROVENANCE_SCHEMA",
    "PDKEnclosure",
    "PDKOverlap",
    "PDK_SCHEMA",
    "PDKSeparation",
    "STATUS_MATCH",
    "STATUS_MISMATCH",
    "STATUS_SKIPPED_NOT_IMPLEMENTED",
    "DRC_REPORT_SCHEMA",
    "DRCCheck",
    "DRCReport",
    "DRCViolation",
    "DensityCheckResult",
    "SUPPORTED_RULES",
    "UNSUPPORTED_RULES",
    "LVSChecker",
    "run_drc",
    "run_partial_connectivity_lvs",
    "to_lydrc",
    "LVSReport",
    "Netlist",
    "NetlistDevice",
    "NotImplementedLVSChecker",
    "compare_partial_connectivity_lvs",
    "extract_connectivity_nets",
    "PDKGrid",
    "PDKJunctionProcess",
    "PDKLayer",
    "PDKProvenance",
    "PDKSubstrate",
    "check_density",
    "check_layer_exists",
    "describe_pdk_file",
    "find_pdk_provenance_for_technology",
    "load_pdk",
    "pdk_from_provenance",
    "pdk_to_technology",
    "write_pdk",
]
