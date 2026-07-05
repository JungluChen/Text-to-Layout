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
)
from textlayout.pdk.models import (
    PDK_SCHEMA,
    PDK,
    PDKGrid,
    PDKJunctionProcess,
    PDKLayer,
    PDKSubstrate,
)

__all__ = [
    "LVS_SCHEMA",
    "PDK",
    "PDK_SCHEMA",
    "STATUS_MATCH",
    "STATUS_MISMATCH",
    "STATUS_SKIPPED_NOT_IMPLEMENTED",
    "DensityCheckResult",
    "LVSChecker",
    "LVSReport",
    "Netlist",
    "NetlistDevice",
    "NotImplementedLVSChecker",
    "PDKGrid",
    "PDKJunctionProcess",
    "PDKLayer",
    "PDKSubstrate",
    "check_density",
    "check_layer_exists",
    "load_pdk",
    "pdk_to_technology",
    "write_pdk",
]
