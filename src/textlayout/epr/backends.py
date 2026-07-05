"""EPR backends: an honest analytical estimator plus a pluggable pyEPR path.

Backend contract (mirrors the FasterCap / FastHenry adapter philosophy):

- ``available()`` never lies about what is installed.
- ``analyze()`` returns an :class:`EPRResult` whose ``status`` states exactly
  what happened: ``ANALYTICAL_ONLY`` for the scaling model,
  ``SIMULATION_EXECUTED`` only when a real field-solved extraction was parsed,
  ``SKIPPED_SOLVER_ABSENT`` when the requested stack is missing.
- No backend ever invents field-solved numbers.

Analytical model
----------------

``AnalyticalEPRBackend`` implements a documented order-of-magnitude *surface
participation scaling model* for coplanar geometries:

- Bulk substrate participation uses the standard half-space filling factor
  ``p_bulk ≈ ε_r / (ε_r + 1)`` (≈0.92 for silicon).
- Total thin-film surface participation is scaled from a published reference
  point: ``p_surf(g) = P_REF · (G_REF / g)`` with ``P_REF = 3×10⁻³`` at
  ``G_REF = 2 µm`` gap — the order of magnitude reported for few-µm-gap CPW
  (Wenner et al., APL 99, 113513 (2011)).
- The MS : SA : MA split is fixed at 4 : 3 : 2, following the relative
  ordering in the same literature, each channel additionally scaled by its
  interface thickness relative to the 3 nm reference.

This is a *scaling model*, not a field solution: participations carry
``confidence=0.3`` and the result is ``ANALYTICAL_ONLY``. Its purpose is to
make loss participation a first-class, always-available design signal and to
rank channels — not to predict absolute T1. Capacitance accuracy from
FasterCap does **not** imply coherence accuracy from this model.
"""

from __future__ import annotations

import importlib.util
from abc import ABC, abstractmethod

from textlayout.epr.coherence import estimate_coherence
from textlayout.epr.materials import MaterialsDB, illustrative_silicon_db
from textlayout.epr.models import (
    EPR_STATUS_ANALYTICAL,
    EPR_STATUS_SKIPPED,
    EPRResult,
    ParticipationRecord,
)
from textlayout.schemas.dsl import LayoutSpec

#: Reference total surface participation at the reference gap (Wenner 2011 scale).
_P_SURFACE_REF = 3.0e-3
_GAP_REF_UM = 2.0
_THICKNESS_REF_NM = 3.0
#: Relative MS : SA : MA weighting (literature ordering; see module docstring).
_SURFACE_SPLIT = {"metal_substrate": 4.0, "substrate_air": 3.0, "metal_air": 2.0}


class EPRBackend(ABC):
    """One way of obtaining energy participation ratios for a design."""

    name: str

    @abstractmethod
    def available(self) -> bool:
        """True when this backend can actually run on this machine."""

    @abstractmethod
    def analyze(
        self,
        spec: LayoutSpec,
        *,
        frequency_ghz: float,
        materials: MaterialsDB | None = None,
    ) -> EPRResult:
        """Return participations + coherence estimate with honest status."""


def characteristic_gap_um(spec: LayoutSpec) -> tuple[float, str]:
    """Smallest field-defining gap of a spec, with the source of the number."""
    parameters = spec.parameters
    for key in ("gap_um", "spacing_um", "coupling_gap_um"):
        value = parameters.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value), f"parameters.{key}"
    rule = spec.rules.get("min_gap_um")
    if isinstance(rule, (int, float)) and rule > 0:
        return float(rule), "rules.min_gap_um"
    return _GAP_REF_UM, "default_reference_gap"


class AnalyticalEPRBackend(EPRBackend):
    """Deterministic, CI-safe surface-participation scaling model."""

    name = "analytical_surface_scaling"

    def available(self) -> bool:
        return True

    def analyze(
        self,
        spec: LayoutSpec,
        *,
        frequency_ghz: float,
        materials: MaterialsDB | None = None,
    ) -> EPRResult:
        db = materials or illustrative_silicon_db()
        gap_um, gap_source = characteristic_gap_um(spec)

        substrate = db.channel("substrate")
        epsilon_r = substrate.epsilon_r or 11.9
        p_bulk = epsilon_r / (epsilon_r + 1.0)

        p_surface_total = _P_SURFACE_REF * (_GAP_REF_UM / gap_um)
        # Cap so bulk + surfaces can never exceed unity even for absurd gaps.
        p_surface_total = min(p_surface_total, 0.05)
        split_norm = sum(_SURFACE_SPLIT.values())

        participations: list[ParticipationRecord] = []
        omega = 2.0 * 3.141592653589793 * frequency_ghz * 1e9

        def record(region: str, p_electric: float) -> ParticipationRecord:
            channel = db.channel(region)
            q_limit = 1.0 / (p_electric * channel.tan_delta)
            return ParticipationRecord(
                region=region,
                material=channel.material,
                p_electric=p_electric,
                tan_delta=channel.tan_delta,
                q_limit=q_limit,
                t1_limit_us=q_limit / omega * 1e6,
                source=f"{self.name}: p_surf scaled from {gap_source}={gap_um:g} um",
                confidence=0.3,
            )

        participations.append(record("substrate", p_bulk))
        for region, weight in _SURFACE_SPLIT.items():
            channel = db.channel(region)
            thickness_scale = (channel.thickness_nm or _THICKNESS_REF_NM) / _THICKNESS_REF_NM
            p_region = p_surface_total * (weight / split_norm) * thickness_scale
            participations.append(record(region, p_region))

        coherence = estimate_coherence(participations, frequency_ghz)
        return EPRResult(
            component=spec.component,
            backend=self.name,
            status=EPR_STATUS_ANALYTICAL,
            frequency_ghz=frequency_ghz,
            participations=participations,
            coherence=coherence,
            assumptions=[
                f"Coplanar surface-participation scaling: p_surf = {_P_SURFACE_REF:g} "
                f"x ({_GAP_REF_UM:g} um / gap); gap taken from {gap_source} = {gap_um:g} um.",
                "MS:SA:MA split fixed at 4:3:2 (literature ordering, not field-solved).",
                f"Bulk filling factor eps_r/(eps_r+1) with eps_r = {epsilon_r:g}.",
                "Junction dielectric participation is NOT modelled by this backend.",
                f"Loss tangents from materials DB {db.name!r} — "
                "ILLUSTRATIVE unless calibration says measured_on_process.",
                "This is an order-of-magnitude scaling model, not a field solution: "
                "channel *ranking* is more trustworthy than absolute T1.",
            ],
            provenance={
                "backend": self.name,
                "materials_db": db.name,
                "geometry_source": gap_source,
                "reference": "Wenner et al., APL 99, 113513 (2011) — scale only",
            },
            notes=[
                "ANALYTICAL_ONLY: capacitance accuracy does not imply coherence accuracy.",
            ],
        )


class PyEPRBackend(EPRBackend):
    """Adapter slot for a real pyEPR / HFSS eigenmode participation extraction.

    Reports ``SKIPPED_SOLVER_ABSENT`` honestly when the pyEPR stack is not
    installed. When pyEPR is present, running a real extraction requires an
    HFSS project — which cannot exist in CI — so this adapter's executable path
    is exercised only in environments that provide one. It never fabricates
    field-solved participations.
    """

    name = "pyepr"

    def available(self) -> bool:
        return importlib.util.find_spec("pyEPR") is not None

    def analyze(
        self,
        spec: LayoutSpec,
        *,
        frequency_ghz: float,
        materials: MaterialsDB | None = None,
    ) -> EPRResult:
        if not self.available():
            return EPRResult(
                component=spec.component,
                backend=self.name,
                status=EPR_STATUS_SKIPPED,
                frequency_ghz=frequency_ghz,
                assumptions=[],
                provenance={"backend": self.name, "reason": "pyEPR not importable"},
                notes=[
                    "pyEPR (and an HFSS eigenmode project) is required for "
                    "field-solved participations; nothing is claimed.",
                ],
            )
        raise NotImplementedError(
            "pyEPR is importable but driving a live HFSS eigenmode project is "
            "not wired yet; use AnalyticalEPRBackend or contribute the "
            "project-file adapter (see docs/epr_coherence.md)."
        )


def default_epr_backend() -> EPRBackend:
    """The backend the closed loop uses when none is specified: always-on analytical."""
    return AnalyticalEPRBackend()
