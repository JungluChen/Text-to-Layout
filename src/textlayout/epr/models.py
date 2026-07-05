"""Typed schemas for energy-participation-ratio (EPR) and coherence results.

Every physical number carries its unit in the field name. Every result carries
provenance (backend, method, assumptions, timestamp) and an honesty ``status``
drawn from an EPR-specific five-value vocabulary (distinct from the shared
project-wide vocabulary because an EPR analysis has more real intermediate
states than a plain solver run — geometry can be prepared, field energy can be
imported from a real HFSS/pyEPR export without this project having run the
solver itself, or the whole thing can stay analytical):

- ``EPR_INPUT_PREPARED`` — geometry/mesh input for a real EPR extraction was
  generated; no participation has been computed yet.
- ``FIELD_ENERGY_IMPORTED`` — a real, solver-exported field-energy file (e.g.
  from pyEPR/HFSS) was parsed and participations were computed from it. This
  is real solver-derived evidence even though this project did not run the
  eigenmode solve itself.
- ``EPR_ANALYTICAL_ONLY`` — participations come from a documented scaling
  model, never from a field solution. This is the CI-safe default backend.
- ``EPR_EXECUTED`` — this project ran a real EPR extraction end to end (e.g.
  invoked pyEPR against a live HFSS project) and parsed its output directly.
- ``EPR_SKIPPED_SOLVER_ABSENT`` — the requested EPR solver stack is not
  installed; nothing is claimed.

Capacitance accuracy does not imply coherence accuracy: a geometry can hit its
0.6 pF target exactly and still be a poor qubit if surface-loss participation
is high. That is why these records are separate from, and complementary to,
:class:`textlayout.evidence.QuantityEvidence`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

EPR_SCHEMA = "textlayout.epr-report.v1"

#: Statuses an EPR analysis can honestly report.
EPR_STATUS_INPUT_PREPARED = "EPR_INPUT_PREPARED"
EPR_STATUS_FIELD_ENERGY_IMPORTED = "FIELD_ENERGY_IMPORTED"
EPR_STATUS_ANALYTICAL = "EPR_ANALYTICAL_ONLY"
EPR_STATUS_EXECUTED = "EPR_EXECUTED"
EPR_STATUS_SKIPPED = "EPR_SKIPPED_SOLVER_ABSENT"

#: Statuses that assert a real, solver-derived (not scaling-model) participation.
EPR_SOLVER_BACKED_STATUSES = frozenset({EPR_STATUS_FIELD_ENERGY_IMPORTED, EPR_STATUS_EXECUTED})


class ParticipationRecord(BaseModel):
    """Energy participation of one material region or interface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region: str = Field(description="Geometric region, e.g. 'substrate', 'metal-substrate'.")
    material: str = Field(description="Material or interface name, e.g. 'Si bulk', 'AlOx'.")
    p_electric: float = Field(
        ge=0.0, le=1.0, description="Electric-field energy participation ratio (dimensionless)."
    )
    p_magnetic: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Magnetic participation, when the backend resolves it.",
    )
    tan_delta: float = Field(gt=0.0, description="Loss tangent assigned to this region.")
    q_limit: float | None = Field(
        default=None, gt=0.0, description="Q limit from this channel alone: 1/(p*tanδ)."
    )
    t1_limit_us: float | None = Field(
        default=None, gt=0.0, description="T1 limit from this channel alone (µs)."
    )
    source: str = Field(description="Where the participation number came from.")
    confidence: float = Field(ge=0.0, le=1.0, description="0=guess, 1=field-solved+measured.")
    synthetic: bool = Field(
        default=False, description="True when the value is a fixture/mock, not physics."
    )


class CoherenceEstimate(BaseModel):
    """Total-loss coherence estimate assembled from participation records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frequency_ghz: float = Field(gt=0.0)
    q_total: float = Field(gt=0.0, description="1 / Σ p_i·tanδ_i over all channels.")
    t1_total_us: float = Field(gt=0.0, description="Q_total / ω, in microseconds.")
    dominant_channel: str = Field(description="Region with the largest p·tanδ product.")
    sensitivity_ranking: list[dict[str, float | str]] = Field(
        description="Channels sorted by loss contribution: region, p, tanδ, loss_fraction."
    )
    recommendation: str = Field(description="What to improve first, given the dominant channel.")


class EPRResult(BaseModel):
    """One EPR analysis of one design, with full provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=EPR_SCHEMA)
    component: str
    backend: str = Field(description="Backend name, e.g. 'analytical_surface_scaling', 'pyepr'.")
    status: str = Field(
        description="EPR_INPUT_PREPARED | FIELD_ENERGY_IMPORTED | EPR_ANALYTICAL_ONLY | "
        "EPR_EXECUTED | EPR_SKIPPED_SOLVER_ABSENT"
    )
    frequency_ghz: float | None = Field(default=None, gt=0.0)
    participations: list[ParticipationRecord] = Field(default_factory=list)
    coherence: CoherenceEstimate | None = None
    assumptions: list[str] = Field(
        default_factory=list,
        description="Every modelling assumption, stated explicitly.",
    )
    provenance: dict[str, str] = Field(
        default_factory=dict,
        description="backend version, materials-db id, geometry source, etc.",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    notes: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")
