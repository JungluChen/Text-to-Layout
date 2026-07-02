"""The trustworthy evidence contract — one source of truth for physics claims.

Every extracted electrical quantity in this project is reported through
:class:`QuantityEvidence`. The model does not merely *document* the honesty
rules — it *enforces* them structurally in a pydantic validator, so a false
``PHYSICS_VERIFIED`` claim cannot be constructed at all:

- ``PHYSICS_VERIFIED`` requires a named solver, a parser, at least one
  solver-owned output file that exists and is non-empty on disk, an extracted
  value, and an error within tolerance.
- ``SIMULATION_EXECUTED`` requires the same solver-owned output evidence but
  tolerates an out-of-tolerance (or uncompared) result.
- ``ANALYTICAL_ONLY`` must not name a solver or claim solver output files —
  an analytical estimate can never be dressed up as a simulation.
- ``SKIPPED_SOLVER_ABSENT`` and ``SIMULATION_INPUT_PREPARED`` must not carry
  an extracted value: no solver ran, so there is nothing to extract.

CLI, API, tests, and reports all consume this one schema; nothing re-implements
the status logic per module.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceStatus(str, enum.Enum):
    """Honesty vocabulary for a single extracted quantity."""

    ANALYTICAL_ONLY = "ANALYTICAL_ONLY"
    SIMULATION_INPUT_PREPARED = "SIMULATION_INPUT_PREPARED"
    SIMULATION_EXECUTED = "SIMULATION_EXECUTED"
    PHYSICS_VERIFIED = "PHYSICS_VERIFIED"
    FAILED = "FAILED"
    SKIPPED_SOLVER_ABSENT = "SKIPPED_SOLVER_ABSENT"


#: Statuses that assert a real solver produced parseable output.
_SOLVER_OUTPUT_STATUSES = frozenset(
    {EvidenceStatus.SIMULATION_EXECUTED, EvidenceStatus.PHYSICS_VERIFIED}
)


class EvidenceError(ValueError):
    """Raised when an evidence record would violate the honesty contract."""


class QuantityEvidence(BaseModel):
    """Evidence for one extracted quantity versus its design target."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    quantity: str = Field(description="Physical quantity, e.g. 'capacitance'.")
    target_value: float | None = Field(default=None, description="Design target value.")
    target_unit: str | None = Field(default=None, description="Unit of the target value.")
    extracted_value: float | None = Field(
        default=None, description="Value extracted from solver output (never analytical)."
    )
    extracted_unit: str | None = Field(default=None, description="Unit of the extracted value.")
    analytical_value: float | None = Field(
        default=None, description="Analytical estimate, clearly separated from solver output."
    )
    analytical_model: str | None = Field(
        default=None, description="Citation/name of the analytical model, if any."
    )
    error_percent: float | None = Field(
        default=None, description="|extracted - target| / target * 100."
    )
    tolerance_percent: float = Field(default=5.0, gt=0)
    status: EvidenceStatus
    solver: str | None = Field(default=None, description="Solver executable name/version.")
    command: str | None = Field(default=None, description="Exact command line executed.")
    input_files: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
    parser: str | None = Field(default=None, description="Module.function that parsed output.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_honesty(self) -> QuantityEvidence:
        status = self.status
        if status in _SOLVER_OUTPUT_STATUSES:
            if not self.solver:
                raise EvidenceError(f"{status.value} requires a named solver")
            if not self.parser:
                raise EvidenceError(f"{status.value} requires a named output parser")
            if self.extracted_value is None:
                raise EvidenceError(f"{status.value} requires an extracted value")
            if not self.output_files:
                raise EvidenceError(f"{status.value} requires solver-owned output files")
            for name in self.output_files:
                path = Path(name)
                if not path.is_file() or path.stat().st_size == 0:
                    raise EvidenceError(
                        f"{status.value} requires existing, non-empty solver output; "
                        f"missing or empty: {path}"
                    )
        if status is EvidenceStatus.PHYSICS_VERIFIED:
            if self.error_percent is None or self.target_value is None:
                raise EvidenceError(
                    "PHYSICS_VERIFIED requires a target and a computed error_percent"
                )
            if self.error_percent > self.tolerance_percent:
                raise EvidenceError(
                    f"PHYSICS_VERIFIED requires error <= tolerance "
                    f"({self.error_percent:.3f}% > {self.tolerance_percent:.3f}%)"
                )
        if status is EvidenceStatus.ANALYTICAL_ONLY and (self.solver or self.output_files):
            raise EvidenceError("ANALYTICAL_ONLY must not claim a solver or solver output files")
        if (
            status
            in {EvidenceStatus.SKIPPED_SOLVER_ABSENT, EvidenceStatus.SIMULATION_INPUT_PREPARED}
            and self.extracted_value is not None
        ):
            raise EvidenceError(f"{status.value} must not carry an extracted value")
        return self

    @property
    def is_physics_verified(self) -> bool:
        return self.status is EvidenceStatus.PHYSICS_VERIFIED

    def summary_line(self) -> str:
        """One-line human-readable statement of what this record proves."""
        target = (
            f"target {self.target_value} {self.target_unit or ''}".rstrip()
            if self.target_value is not None
            else "no target"
        )
        if self.status is EvidenceStatus.PHYSICS_VERIFIED:
            return (
                f"{self.quantity}: PHYSICS_VERIFIED — {self.solver} extracted "
                f"{self.extracted_value} {self.extracted_unit or ''} vs {target} "
                f"(error {self.error_percent:.2f}% <= {self.tolerance_percent}%)"
            ).replace("  ", " ")
        if self.status is EvidenceStatus.SIMULATION_EXECUTED:
            return (
                f"{self.quantity}: SIMULATION_EXECUTED — {self.solver} extracted "
                f"{self.extracted_value} {self.extracted_unit or ''} vs {target}; "
                "tolerance not met or not compared — NOT physics verified"
            ).replace("  ", " ")
        if self.status is EvidenceStatus.ANALYTICAL_ONLY:
            return (
                f"{self.quantity}: ANALYTICAL_ONLY — estimate "
                f"{self.analytical_value} ({self.analytical_model or 'unnamed model'}); "
                "this is NOT a solver result"
            )
        if self.status is EvidenceStatus.SIMULATION_INPUT_PREPARED:
            return (
                f"{self.quantity}: SIMULATION_INPUT_PREPARED — solver input files exist; "
                "no physics verification was performed"
            )
        if self.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT:
            return (
                f"{self.quantity}: SKIPPED_SOLVER_ABSENT — solver not installed; "
                "no physics verification was performed"
            )
        return f"{self.quantity}: FAILED — solver ran but produced no accepted result"


def compare_extracted_to_target(
    *,
    quantity: str,
    target_value: float,
    target_unit: str,
    extracted_value: float,
    extracted_unit: str,
    tolerance_percent: float,
    solver: str,
    command: str,
    input_files: list[str],
    output_files: list[str],
    parser: str,
    analytical_value: float | None = None,
    analytical_model: str | None = None,
    notes: list[str] | None = None,
) -> QuantityEvidence:
    """Build the post-solve evidence record; the only path to PHYSICS_VERIFIED.

    The status is *computed*, never passed in: within tolerance ->
    PHYSICS_VERIFIED, outside -> SIMULATION_EXECUTED. All structural checks of
    :class:`QuantityEvidence` still apply (output files must exist, etc.).
    """
    if target_value == 0:
        raise EvidenceError("target_value must be non-zero to compute a relative error")
    error_percent = abs(extracted_value - target_value) / abs(target_value) * 100.0
    status = (
        EvidenceStatus.PHYSICS_VERIFIED
        if error_percent <= tolerance_percent
        else EvidenceStatus.SIMULATION_EXECUTED
    )
    return QuantityEvidence(
        quantity=quantity,
        target_value=target_value,
        target_unit=target_unit,
        extracted_value=extracted_value,
        extracted_unit=extracted_unit,
        analytical_value=analytical_value,
        analytical_model=analytical_model,
        error_percent=round(error_percent, 4),
        tolerance_percent=tolerance_percent,
        status=status,
        solver=solver,
        command=command,
        input_files=list(input_files),
        output_files=list(output_files),
        parser=parser,
        notes=list(notes or []),
    )
