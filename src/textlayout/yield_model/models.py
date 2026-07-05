"""Schemas for JJ process variation and Monte Carlo yield results.

Why this module exists: drawing one SQUID loop proves geometry, not
manufacturability. Real wafers have wafer-scale Jc drift, junction-to-junction
local spread, and lithography CD variation — all of which map directly into
qubit-frequency spread. A design targeted at 5.000 GHz on a process with 5% Jc
sigma is a *distribution*, not a number, and chip yield is a statement about
that distribution. These schemas make the distribution explicit and auditable.

All default numbers are ILLUSTRATIVE unless ``calibration`` says
``measured_on_process`` — the measurement-correlation loop is what upgrades
them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

YIELD_SCHEMA = "textlayout.jj-yield-report.v1"


class JJProcessModel(BaseModel):
    """Statistical model of a Josephson-junction fabrication process."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(default="illustrative_jj_process")
    target_jc_ua_per_um2: float = Field(gt=0, description="Design-target Jc (µA/µm²).")
    wafer_jc_mean_ua_per_um2: float | None = Field(
        default=None,
        gt=0,
        description="Wafer-level mean Jc; defaults to the target when None.",
    )
    wafer_jc_sigma_pct: float = Field(
        ge=0, le=50, description="Wafer-to-wafer / chip-common Jc sigma, % of mean."
    )
    local_jc_sigma_pct: float = Field(
        ge=0, le=50, description="Junction-to-junction local Jc sigma, % of mean."
    )
    junction_area_bias_um2: float = Field(
        default=0.0, description="Systematic area bias added to the drawn area (µm²)."
    )
    cd_sigma_nm: float = Field(
        default=0.0, ge=0, description="Lithography CD sigma on each linear dimension (nm)."
    )
    spatial_gradient_pct_per_mm: float = Field(
        default=0.0,
        description="Optional linear Jc gradient across the chip, % of mean per mm.",
    )
    calibration: str = Field(
        default="illustrative",
        description="illustrative | measured_on_process",
    )
    source: str = Field(
        default="illustrative defaults; NOT foundry-calibrated",
        description="Where these statistics came from.",
    )

    @property
    def jc_mean(self) -> float:
        return self.wafer_jc_mean_ua_per_um2 or self.target_jc_ua_per_um2


class JunctionGeometry(BaseModel):
    """Drawn geometry of one junction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    width_um: float = Field(gt=0)
    height_um: float = Field(gt=0)

    @property
    def area_um2(self) -> float:
        return self.width_um * self.height_um


class SquidGeometry(BaseModel):
    """Two-junction SQUID with optional designed asymmetry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    junction_1: JunctionGeometry
    junction_2: JunctionGeometry
    flux_bias_phi0: float = Field(default=0.0, description="Operating flux bias in units of Φ₀.")

    @model_validator(mode="after")
    def _warn_symmetric_half_flux(self) -> SquidGeometry:
        symmetric = abs(self.junction_1.area_um2 - self.junction_2.area_um2) < 1e-12
        near_half = abs(abs(self.flux_bias_phi0) % 1.0 - 0.5) < 1e-6
        if symmetric and near_half:
            raise ValueError(
                "symmetric SQUID biased at half flux has Ic→0 and divergent LJ; "
                "choose a different bias point or an asymmetric design"
            )
        return self


class FrequencyTarget(BaseModel):
    """What 'in spec' means for one mode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_ghz: float = Field(gt=0)
    tolerance_mhz: float = Field(gt=0, description="Half-width of the acceptance window.")


class YieldStatistics(BaseModel):
    """Summary statistics of one Monte Carlo frequency distribution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_samples: int = Field(gt=0)
    mean_ghz: float
    sigma_mhz: float
    p05_ghz: float
    p50_ghz: float
    p95_ghz: float
    min_ghz: float
    max_ghz: float


class WorstCaseCorner(BaseModel):
    """One extreme Monte Carlo draw, with the inputs that produced it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    frequency_ghz: float
    jc_ua_per_um2: float
    area_um2: float
    ic_ua: float
    lj_nh: float


class YieldResult(BaseModel):
    """Full result of a seeded Monte Carlo yield analysis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=YIELD_SCHEMA)
    analysis: str = Field(description="'jj' or 'qubit_array'.")
    process: JJProcessModel
    target: FrequencyTarget
    statistics: YieldStatistics
    hit_rate: float = Field(ge=0, le=1, description="Fraction of samples inside the window.")
    yield_pct: float = Field(ge=0, le=100)
    yield_ci95_pct: tuple[float, float] = Field(
        description="Wilson 95% confidence interval on the yield (percent)."
    )
    worst_corners: list[WorstCaseCorner]
    seed: int
    n_qubits_per_chip: int | None = Field(
        default=None, description="For qubit-array analysis: qubits that must ALL pass."
    )
    chip_yield_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="For qubit-array analysis: fraction of chips with all qubits in spec.",
    )
    chip_yield_ci95_pct: tuple[float, float] | None = Field(
        default=None,
        description="Wilson 95% CI on chip_yield_pct (percent). None for single-junction runs.",
    )
    assumptions: list[str] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)
    synthetic: bool = Field(
        default=True,
        description="True until the process statistics are measured_on_process.",
    )

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")
