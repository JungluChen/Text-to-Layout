"""LVS (layout-vs-schematic) hooks: schema and interface, honestly limited.

Real LVS extracts a netlist from drawn geometry and compares it, node for
node, against a reference schematic. That extraction (device recognition,
connectivity tracing through vias, parasitic-aware netlisting) is a
significant undertaking on its own and is **not implemented** here. What this
module provides is the *shape* of that problem — a typed netlist schema and
an ``LVSChecker`` interface — so a real extractor can be plugged in later
without changing any caller. The one shipped implementation,
``NotImplementedLVSChecker``, reports its status honestly
(``SKIPPED_NOT_IMPLEMENTED``) rather than fabricating a match/mismatch verdict.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

LVS_SCHEMA = "textlayout.lvs-report.v1"

STATUS_SKIPPED_NOT_IMPLEMENTED = "SKIPPED_NOT_IMPLEMENTED"
STATUS_MATCH = "MATCH"
STATUS_MISMATCH = "MISMATCH"


class NetlistDevice(BaseModel):
    """One device instance in a reference or extracted netlist."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str = Field(description="Instance reference, e.g. 'C1', 'JJ1'.")
    device_type: str = Field(description="e.g. 'capacitor', 'josephson_junction', 'inductor'.")
    nodes: list[str] = Field(description="Net names this device connects to.")
    parameters: dict[str, float] = Field(default_factory=dict)


class Netlist(BaseModel):
    """A flat device-level netlist (reference schematic OR layout-extracted)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=LVS_SCHEMA)
    name: str
    devices: list[NetlistDevice]
    nets: list[str] = Field(description="All net names referenced by devices.")


class LVSReport(BaseModel):
    """Result of comparing an extracted netlist against a reference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=LVS_SCHEMA)
    status: str = Field(description="MATCH | MISMATCH | SKIPPED_NOT_IMPLEMENTED")
    reference_name: str
    extracted_name: str | None = None
    mismatches: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class LVSChecker(ABC):
    """Interface for a layout-vs-schematic checker."""

    @abstractmethod
    def compare(self, reference: Netlist, extracted: Netlist) -> LVSReport:
        """Compare an extracted netlist against a reference; never fabricate a MATCH."""


class NotImplementedLVSChecker(LVSChecker):
    """Honest placeholder: real device/connectivity extraction is not wired yet."""

    def compare(self, reference: Netlist, extracted: Netlist) -> LVSReport:
        return LVSReport(
            status=STATUS_SKIPPED_NOT_IMPLEMENTED,
            reference_name=reference.name,
            extracted_name=extracted.name,
            notes=[
                "Real layout-vs-schematic extraction (device recognition, via "
                "connectivity tracing) is not implemented. This checker never "
                "reports MATCH or MISMATCH without a real comparison.",
            ],
        )
