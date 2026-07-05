"""Foundry PDK abstraction — typed, versioned, source-tracked process data.

Why this exists: the existing :class:`textlayout.models.Technology` is a
minimal layer/rule stack (just what the geometry engine needs to draw and
check polygons). Real process qualification needs much more: metal
thickness and sheet resistance for parasitics, dielectric loss tangents for
the EPR/coherence loop, density and antenna rules for foundry signoff, and
named JJ process parameters for the yield loop. This module is that richer,
foundry-shaped schema — kept separate from :class:`Technology` so existing
generators/verification/exporters (which only need the geometry-level
subset) are unaffected. :func:`textlayout.pdk.convert.pdk_to_technology`
projects a :class:`PDK` down to the existing :class:`Technology` so the rest
of the pipeline needs no changes at all.

**No PDK shipped in this repository is foundry-validated.** Every instance
carries an explicit ``foundry_validated`` flag and a ``source`` string; both
the generic and the illustrative superconducting examples set
``foundry_validated=False``. Real fabrication requires a foundry-qualified
PDK — see docs/pdk_abstraction.md.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

PDK_SCHEMA = "textlayout.pdk.v1"

_ALLOWED_PURPOSES = frozenset(
    {"metal", "junction", "ground", "via", "text", "marker", "dielectric"}
)


class PDKLayer(BaseModel):
    """One process layer: geometry numbers plus electrical/loss properties."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    purpose: str = Field(description=f"One of {sorted(_ALLOWED_PURPOSES)}.")
    gds_layer: int = Field(ge=0)
    gds_datatype: int = Field(default=0, ge=0)
    min_width_um: float = Field(gt=0)
    min_spacing_um: float = Field(gt=0)
    thickness_nm: float | None = Field(default=None, gt=0)
    sheet_resistance_ohm_per_sq: float | None = Field(
        default=None, gt=0, description="DC sheet resistance, ohm/square."
    )
    kinetic_inductance_ph_per_sq: float | None = Field(
        default=None,
        gt=0,
        description="Kinetic inductance per square (pH/sq) — superconducting films only.",
    )
    loss_tangent: float | None = Field(
        default=None, gt=0, description="Dielectric/interface loss tangent, if applicable."
    )
    max_density_fraction: float | None = Field(
        default=None,
        gt=0,
        le=1.0,
        description="Maximum allowed fill fraction in a density-check window (placeholder).",
    )
    min_density_fraction: float | None = Field(
        default=None,
        ge=0,
        lt=1.0,
        description="Minimum required fill fraction (placeholder; antenna/CMP rules).",
    )
    color: str = Field(default="#888888")

    @model_validator(mode="after")
    def _check_purpose(self) -> PDKLayer:
        if self.purpose not in _ALLOWED_PURPOSES:
            raise ValueError(
                f"layer {self.name!r} has purpose {self.purpose!r}; "
                f"allowed: {sorted(_ALLOWED_PURPOSES)}"
            )
        if (
            self.min_density_fraction is not None
            and self.max_density_fraction is not None
            and self.min_density_fraction >= self.max_density_fraction
        ):
            raise ValueError(
                f"layer {self.name!r}: min_density_fraction must be < max_density_fraction"
            )
        return self


class PDKSubstrate(BaseModel):
    """Substrate wafer properties."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    material: str
    epsilon_r: float = Field(gt=0)
    loss_tangent: float = Field(gt=0)
    thickness_um: float | None = Field(default=None, gt=0)


class PDKJunctionProcess(BaseModel):
    """Named Josephson-junction process parameters (feeds textlayout.yield_model)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_jc_ua_per_um2: float = Field(gt=0)
    jc_sigma_pct: float = Field(ge=0, le=50, description="Illustrative wafer-level Jc sigma.")
    min_junction_area_um2: float = Field(gt=0)
    critical_temperature_k: float | None = Field(default=None, gt=0)


class PDKGrid(BaseModel):
    """Manufacturing grid and default fallback rules."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    grid_nm: float = Field(gt=0)
    default_min_spacing_um: float = Field(gt=0)
    default_min_width_um: float = Field(gt=0)


#: Three-way calibration status, more granular than the plain foundry_validated
#: bool: an "internal_calibrated" PDK has been correlated against real
#: measurements (see textlayout.measurement) but is not foundry-qualified.
CALIBRATION_ILLUSTRATIVE = "illustrative"
CALIBRATION_INTERNAL = "internal_calibrated"
CALIBRATION_FOUNDRY = "foundry_calibrated"
_VALID_CALIBRATION_STATUSES = frozenset(
    {CALIBRATION_ILLUSTRATIVE, CALIBRATION_INTERNAL, CALIBRATION_FOUNDRY}
)


class PDK(BaseModel):
    """A named, versioned foundry process description."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=PDK_SCHEMA)
    name: str
    version: str
    foundry_validated: bool = Field(
        description="True only for a real foundry-qualified process. "
        "MUST be False for any illustrative/example PDK. Kept for backward "
        "compatibility; equivalent to calibration_status == 'foundry_calibrated'."
    )
    calibration_status: str = Field(
        default=CALIBRATION_ILLUSTRATIVE,
        description="illustrative | internal_calibrated | foundry_calibrated",
    )
    source: str = Field(description="Where these numbers came from.")
    grid: PDKGrid
    layers: list[PDKLayer]
    substrate: PDKSubstrate
    junction_process: PDKJunctionProcess | None = Field(
        default=None, description="None for non-superconducting / passive-only processes."
    )
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _layers_unique_and_gds_unique(self) -> PDK:
        names = [layer.name for layer in self.layers]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate layer names in PDK {self.name!r}: {names}")
        gds_keys = [(layer.gds_layer, layer.gds_datatype) for layer in self.layers]
        if len(gds_keys) != len(set(gds_keys)):
            raise ValueError(f"duplicate (gds_layer, gds_datatype) pairs in PDK {self.name!r}")
        return self

    @model_validator(mode="after")
    def _calibration_status_consistent_with_foundry_validated(self) -> PDK:
        if self.calibration_status not in _VALID_CALIBRATION_STATUSES:
            raise ValueError(
                f"calibration_status {self.calibration_status!r} not in "
                f"{sorted(_VALID_CALIBRATION_STATUSES)}"
            )
        if self.foundry_validated and self.calibration_status != CALIBRATION_FOUNDRY:
            raise ValueError(
                f"PDK {self.name!r}: foundry_validated=True requires "
                f"calibration_status={CALIBRATION_FOUNDRY!r}, got "
                f"{self.calibration_status!r}"
            )
        if not self.foundry_validated and self.calibration_status == CALIBRATION_FOUNDRY:
            raise ValueError(
                f"PDK {self.name!r}: calibration_status={CALIBRATION_FOUNDRY!r} requires "
                "foundry_validated=True"
            )
        return self

    def layer(self, name: str) -> PDKLayer:
        for layer in self.layers:
            if layer.name == name:
                return layer
        raise KeyError(f"layer {name!r} not in PDK {self.name!r}; have {self.layer_names()}")

    def layer_names(self) -> list[str]:
        return [layer.name for layer in self.layers]

    def summary(self) -> dict[str, object]:
        """Compact provenance record for embedding in evidence artifacts.

        Does not include a file hash — that is a property of the file this
        PDK was loaded *from*, not of the PDK content itself. Use
        :func:`textlayout.pdk.provenance.describe_pdk_file` for the full
        provenance record (name, version, hash, calibration status) that
        every report should carry.
        """
        return {
            "pdk_name": self.name,
            "pdk_version": self.version,
            "foundry_validated": self.foundry_validated,
            "calibration_status": self.calibration_status,
            "source": self.source,
        }
