"""Signoff-level evaluation for the textlayout product path.

Sprint 4's explicit requirement: **Level 6 requires measurement correlation,
not only simulation.** A design that hits Level 5 (physics-verified by a real
executed solver) still has not been checked against a fabricated device — it
is a simulation, not a measurement. Level 6 is reserved for exactly that gap
being closed: a non-synthetic :class:`~textlayout.measurement.CalibrationFile`
correlating this design's prediction against a real cooldown must exist.

Levels are sequential and gated: each level requires every prior level to
already hold. A design cannot skip from Level 3 straight to claiming Level 6.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence import EvidenceStatus, QuantityEvidence
from textlayout.measurement import CalibrationFile

SIGNOFF_SCHEMA = "textlayout.signoff.v1"

_LEVEL_LABELS: tuple[str, ...] = (
    "Geometry generated",
    "DRC passed",
    "Extraction complete",
    "Analytical sanity",
    "One solver executed",
    "Physics signoff",
    "Measurement-calibrated",
)


class SignoffResult(BaseModel):
    """The signoff level a design has actually earned, with why it stopped there."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=SIGNOFF_SCHEMA)
    level: int = Field(ge=-1, le=6)
    label: str
    passed_level_5_physics_signoff: bool
    passed_level_6_measurement_calibrated: bool
    blockers: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


def evaluate_signoff(
    *,
    geometry_pass: bool,
    drc_passed: bool,
    verification_passed: bool,
    evidence: QuantityEvidence | None = None,
    calibration: CalibrationFile | None = None,
) -> SignoffResult:
    """Evaluate how far a design's evidence chain actually reaches (0-6).

    ``evidence`` is the capacitance/inductance/frequency evidence record
    (:class:`~textlayout.evidence.QuantityEvidence`) whose ``status`` decides
    Levels 4-5. ``calibration`` is a fitted, non-synthetic
    :class:`~textlayout.measurement.CalibrationFile` correlating this design
    against real measured devices — required, and required non-synthetic,
    for Level 6.
    """
    blockers: list[str] = []

    if not geometry_pass:
        return SignoffResult(
            level=-1,
            label="No geometry",
            passed_level_5_physics_signoff=False,
            passed_level_6_measurement_calibrated=False,
            blockers=["Geometry was not generated or failed verification."],
        )
    level = 0

    if not drc_passed:
        blockers.append("DRC did not pass; stopped at Level 0.")
        return _result(level, blockers)
    level = 1

    if not verification_passed:
        blockers.append("Extraction/verification is incomplete; stopped at Level 1.")
        return _result(level, blockers)
    level = 2

    # Level 3 (analytical sanity) is implied by verification_passed already
    # having checked positive dimensions, layer legality, and design rules.
    level = 3

    if evidence is None:
        blockers.append("No solver evidence record provided; stopped at Level 3.")
        return _result(level, blockers)

    solver_backed = evidence.status in (
        EvidenceStatus.SIMULATION_EXECUTED,
        EvidenceStatus.PHYSICS_VERIFIED,
    )
    if not solver_backed:
        blockers.append(
            f"No solver has been executed (evidence.status={evidence.status.value!r}); "
            "stopped at Level 3."
        )
        return _result(level, blockers)
    level = 4

    if not evidence.is_physics_verified:
        blockers.append(
            f"Solver executed but result is outside tolerance "
            f"(error {evidence.error_percent}% > {evidence.tolerance_percent}%); "
            "stopped at Level 4."
        )
        return _result(level, blockers)
    level = 5

    if calibration is None:
        blockers.append(
            "Level 5 (physics signoff) reached, but no measurement correlation "
            "exists. Level 6 requires a real, non-synthetic CalibrationFile "
            "(see textlayout.measurement) -- simulation evidence alone is not enough."
        )
        return _result(level, blockers)
    if calibration.synthetic:
        blockers.append(
            "A calibration file exists but is marked synthetic=True (fitted from "
            "example/test data, not a real cooldown). Level 6 requires "
            "synthetic=False -- simulation evidence alone is not enough."
        )
        return _result(level, blockers)
    level = 6
    return _result(level, blockers)


def _result(level: int, blockers: list[str]) -> SignoffResult:
    return SignoffResult(
        level=level,
        label=_LEVEL_LABELS[level] if level >= 0 else "No geometry",
        passed_level_5_physics_signoff=level >= 5,
        passed_level_6_measurement_calibrated=level >= 6,
        blockers=blockers,
    )
