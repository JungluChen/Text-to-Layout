"""Conservative design-level signoff evaluation for the product path.

A single solver may establish Level 4 and may mark one quantity
``PHYSICS_VERIFIED``. Design-level Level 5 is intentionally stronger: at least
two independent solver families must provide canonical, content-addressed
evidence and a computed agreement record covering the same design, scope, and
quantity. Level 6 additionally requires non-synthetic measurement calibration.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence import (
    SOLVER_BACKED_STATUSES,
    CanonicalEvidence,
    QuantityEvidence,
    SolverAgreementRecord,
    solver_family,
)
from textlayout.measurement import CalibrationFile

SIGNOFF_SCHEMA = "textlayout.signoff.v2"

SIGNOFF_LEVELS: tuple[tuple[int, str, str], ...] = (
    (-1, "No geometry", "Geometry was not generated or failed verification."),
    (0, "Geometry generated", "GDS exists and passed layout verification."),
    (1, "DRC passed", "Level 0 plus the design-rule check passed."),
    (2, "Extraction complete", "Level 1 plus extraction/readback completed."),
    (3, "Analytical sanity", "Level 2 plus analytical sanity checks."),
    (
        4,
        "One solver executed",
        "Level 3 plus one valid solver-backed canonical record, or the temporary "
        "single-record `evidence=` compatibility input.",
    ),
    (
        5,
        "Physics signoff",
        "Level 4 plus at least two canonical `PHYSICS_VERIFIED` records from independent "
        "solver families (distinct backends) and a passing computed agreement record for "
        "the same design hash, analysis scope, and quantity.",
    ),
    (
        6,
        "Measurement-calibrated",
        "Level 5 plus a `CalibrationFile` with `synthetic=False`.",
    ),
)
_LEVEL_LABELS = tuple(label for level, label, _ in SIGNOFF_LEVELS if level >= 0)


class SignoffResult(BaseModel):
    """The signoff level a design has actually earned, with why it stopped there."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=SIGNOFF_SCHEMA)
    level: int = Field(ge=-1, le=6)
    label: str
    passed_level_5_physics_signoff: bool
    passed_level_6_measurement_calibrated: bool
    executed_solver_ids: list[str] = Field(default_factory=list)
    executed_solver_evidence_ids: list[str] = Field(default_factory=list)
    executed_solver_families: list[str] = Field(default_factory=list)
    solver_agreement_status: Literal["NOT_PROVIDED", "PASSED", "FAILED"] = "NOT_PROVIDED"
    solver_agreement_passed: bool | None = None
    blockers: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


def evaluate_signoff(
    *,
    geometry_pass: bool,
    drc_passed: bool,
    verification_passed: bool,
    evidence: QuantityEvidence | None = None,
    solver_evidence: Sequence[CanonicalEvidence] = (),
    solver_agreement: SolverAgreementRecord | None = None,
    calibration: CalibrationFile | None = None,
) -> SignoffResult:
    """Evaluate how far a design's evidence chain actually reaches (0-6).

    ``evidence`` remains accepted as a compatibility API, but can establish
    only Level 4. Level 5 requires ``solver_evidence`` containing at least two
    canonical, quantity-verified records from independent solver families and
    a matching ``solver_agreement`` whose pass result is computed from values.
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

    # The product verification gate includes its analytical sanity checks.
    level = 3

    canonical_solver_records = [
        record for record in solver_evidence if record.status in SOLVER_BACKED_STATUSES
    ]
    executed_ids = [record.evidence_id for record in canonical_solver_records]
    executed_families = {
        solver_family(record.solver_name)
        for record in canonical_solver_records
        if record.solver_name
    }
    legacy_solver_backed = evidence is not None and evidence.status in SOLVER_BACKED_STATUSES
    if legacy_solver_backed and evidence is not None and evidence.solver:
        executed_families.add(solver_family(evidence.solver))
    family_list = sorted(executed_families)

    if not canonical_solver_records and not legacy_solver_backed:
        if evidence is None:
            blockers.append("No solver evidence record provided; stopped at Level 3.")
        else:
            blockers.append(
                f"No solver has been executed (evidence.status={evidence.status.value!r}); "
                "stopped at Level 3."
            )
        return _result(level, blockers, executed_ids, family_list, solver_agreement)
    level = 4

    if not canonical_solver_records:
        blockers.append(
            "The compatibility evidence= argument can establish only Level 4. "
            "Level 5 requires canonical evidence from two independent solver "
            "families plus a computed agreement record."
        )
        return _result(level, blockers, executed_ids, family_list, solver_agreement)

    if solver_agreement is None:
        blockers.append(
            "No independent-solver agreement record was provided; stopped at Level 4."
        )
        return _result(level, blockers, executed_ids, family_list, solver_agreement)

    agreement_problems = solver_agreement.validate_against(canonical_solver_records)
    if len(executed_families) < 2:
        agreement_problems.append("fewer than two independent solver families executed")
    if agreement_problems:
        blockers.extend(agreement_problems)
        return _result(level, blockers, executed_ids, family_list, solver_agreement)
    level = 5

    if calibration is None:
        blockers.append(
            "Level 5 (physics signoff) reached, but no measurement correlation "
            "exists. Level 6 requires a real, non-synthetic CalibrationFile "
            "(see textlayout.measurement) -- simulation evidence alone is not enough."
        )
        return _result(level, blockers, executed_ids, family_list, solver_agreement)
    if calibration.synthetic:
        blockers.append(
            "A calibration file exists but is marked synthetic=True (fitted from "
            "example/test data, not a real cooldown). Level 6 requires "
            "synthetic=False -- simulation evidence alone is not enough."
        )
        return _result(level, blockers, executed_ids, family_list, solver_agreement)
    level = 6
    return _result(level, blockers, executed_ids, family_list, solver_agreement)


def _result(
    level: int,
    blockers: list[str],
    executed_solver_evidence_ids: list[str] | None = None,
    executed_solver_families: list[str] | None = None,
    solver_agreement: SolverAgreementRecord | None = None,
) -> SignoffResult:
    return SignoffResult(
        level=level,
        label=_LEVEL_LABELS[level] if level >= 0 else "No geometry",
        passed_level_5_physics_signoff=level >= 5,
        passed_level_6_measurement_calibrated=level >= 6,
        executed_solver_ids=executed_solver_evidence_ids or [],
        executed_solver_evidence_ids=executed_solver_evidence_ids or [],
        executed_solver_families=executed_solver_families or [],
        solver_agreement_status=(
            "NOT_PROVIDED"
            if solver_agreement is None
            else ("PASSED" if level >= 5 else "FAILED")
        ),
        solver_agreement_passed=level >= 5 if solver_agreement else None,
        blockers=blockers,
    )
