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
    CompiledDRCRule,
    STANDALONE_SUPPORTED_RULES,
    compile_drc_rules,
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
    run_native_klayout_partial_lvs,
    run_partial_connectivity_lvs,
)
from textlayout.pdk.models import (
    PDKEnclosure,
    PDKOverlap,
    CALIBRATION_FOUNDRY,
    CALIBRATION_ILLUSTRATIVE,
    CALIBRATION_INTERNAL,
    DENSITY_CLIP_TO_ANALYSIS_BOUNDARY,
    DENSITY_EXPLICIT_DENSITY_BOUNDARY,
    DENSITY_FULL_WINDOWS_ONLY,
    PDK_SCHEMA,
    PDK,
    PDKGrid,
    PDKJunctionProcess,
    PDKLayer,
    PDKSeparation,
    PDKSubstrate,
    RuleRequirement,
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
    "DENSITY_CLIP_TO_ANALYSIS_BOUNDARY",
    "DENSITY_EXPLICIT_DENSITY_BOUNDARY",
    "DENSITY_FULL_WINDOWS_ONLY",
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
    "CompiledDRCRule",
    "DensityCheckResult",
    "SUPPORTED_RULES",
    "STANDALONE_SUPPORTED_RULES",
    "UNSUPPORTED_RULES",
    "LVSChecker",
    "run_drc",
    "run_partial_connectivity_lvs",
    "run_native_klayout_partial_lvs",
    "to_lydrc",
    "LVSReport",
    "Netlist",
    "NetlistDevice",
    "NotImplementedLVSChecker",
    "RuleRequirement",
    "compare_partial_connectivity_lvs",
    "extract_connectivity_nets",
    "PDKGrid",
    "PDKJunctionProcess",
    "PDKLayer",
    "PDKProvenance",
    "PDKSubstrate",
    "check_density",
    "check_layer_exists",
    "compile_drc_rules",
    "describe_pdk_file",
    "find_pdk_provenance_for_technology",
    "load_pdk",
    "pdk_from_provenance",
    "pdk_to_technology",
    "write_pdk",
]
