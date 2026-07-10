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
- ``SIMULATION_INVALID`` and ``CONVERGENCE_FAILED`` record that a solver ran
  and its output was rejected. They name the solver but carry no extracted
  value — a rejected number is not a measurement of anything.

No numeric field may be NaN or infinite. ``NaN`` compares ``False`` against
every bound, so an unguarded ``error_percent > tolerance_percent`` check would
silently *admit* a NaN result as PHYSICS_VERIFIED. Non-finite values are
therefore rejected structurally rather than range-checked.

CLI, API, tests, and reports all consume this one schema; nothing re-implements
the status logic per module.
"""

from __future__ import annotations

import enum
import math
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
    #: A solver ran, but its output failed a physical-sanity check
    #: (non-finite, empty, negative energy, resonance at a sweep edge, ...).
    SIMULATION_INVALID = "SIMULATION_INVALID"
    #: A solver ran, but the result did not converge under refinement.
    CONVERGENCE_FAILED = "CONVERGENCE_FAILED"


#: Statuses that assert a real solver produced parseable, usable output.
_SOLVER_OUTPUT_STATUSES = frozenset(
    {EvidenceStatus.SIMULATION_EXECUTED, EvidenceStatus.PHYSICS_VERIFIED}
)

#: Statuses that assert a solver ran but its result was rejected. They name the
#: solver, and must never carry an extracted value.
_SOLVER_REJECTED_STATUSES = frozenset(
    {EvidenceStatus.SIMULATION_INVALID, EvidenceStatus.CONVERGENCE_FAILED}
)

#: Statuses that assert no solver ran at all.
_NO_SOLVER_RAN_STATUSES = frozenset(
    {EvidenceStatus.SKIPPED_SOLVER_ABSENT, EvidenceStatus.SIMULATION_INPUT_PREPARED}
)

#: Every numeric field that must be a finite real number when present.
_FINITE_FIELDS = (
    "target_value",
    "extracted_value",
    "analytical_value",
    "error_percent",
    "tolerance_percent",
)


class ConfidenceClass(enum.IntEnum):
    """How much physical confidence a status is entitled to claim.

    Ordered, so "did this transition increase confidence?" is a comparison
    rather than a hand-maintained list of forbidden pairs.
    """

    #: No usable claim: never ran, ran and was rejected, or was skipped.
    NONE = 0
    #: A closed-form estimate. Not a solver result.
    ANALYTICAL = 1
    #: Solver inputs exist on disk. Still not a solver result.
    PREPARED = 2
    #: A solver ran and produced a finite, parseable value.
    SIMULATED = 3
    #: A solver value agreed with its design target inside tolerance.
    VERIFIED = 4


_CONFIDENCE: dict[EvidenceStatus, ConfidenceClass] = {
    EvidenceStatus.FAILED: ConfidenceClass.NONE,
    EvidenceStatus.SKIPPED_SOLVER_ABSENT: ConfidenceClass.NONE,
    EvidenceStatus.SIMULATION_INVALID: ConfidenceClass.NONE,
    EvidenceStatus.CONVERGENCE_FAILED: ConfidenceClass.NONE,
    EvidenceStatus.ANALYTICAL_ONLY: ConfidenceClass.ANALYTICAL,
    EvidenceStatus.SIMULATION_INPUT_PREPARED: ConfidenceClass.PREPARED,
    EvidenceStatus.SIMULATION_EXECUTED: ConfidenceClass.SIMULATED,
    EvidenceStatus.PHYSICS_VERIFIED: ConfidenceClass.VERIFIED,
}

#: The only sanctioned confidence-*increasing* edges. Everything else that
#: raises confidence is an illegal promotion. Confidence-preserving and
#: confidence-*lowering* edges are always allowed and are not listed here:
#: losing confidence is always honest, so a solver may invalidate any claim at
#: any time, but nothing may gain confidence except by walking this graph.
_PROMOTIONS: frozenset[tuple[EvidenceStatus, EvidenceStatus]] = frozenset(
    {
        # an analytical estimate can have solver inputs prepared for it
        (EvidenceStatus.ANALYTICAL_ONLY, EvidenceStatus.SIMULATION_INPUT_PREPARED),
        # ... and a rejected or never-run quantity can be re-prepared and retried
        (EvidenceStatus.FAILED, EvidenceStatus.SIMULATION_INPUT_PREPARED),
        (EvidenceStatus.SKIPPED_SOLVER_ABSENT, EvidenceStatus.SIMULATION_INPUT_PREPARED),
        (EvidenceStatus.SIMULATION_INVALID, EvidenceStatus.SIMULATION_INPUT_PREPARED),
        (EvidenceStatus.CONVERGENCE_FAILED, EvidenceStatus.SIMULATION_INPUT_PREPARED),
        (EvidenceStatus.FAILED, EvidenceStatus.ANALYTICAL_ONLY),
        (EvidenceStatus.SKIPPED_SOLVER_ABSENT, EvidenceStatus.ANALYTICAL_ONLY),
        (EvidenceStatus.SIMULATION_INVALID, EvidenceStatus.ANALYTICAL_ONLY),
        (EvidenceStatus.CONVERGENCE_FAILED, EvidenceStatus.ANALYTICAL_ONLY),
        # prepared inputs -> the solver actually ran and returned a finite value
        (EvidenceStatus.SIMULATION_INPUT_PREPARED, EvidenceStatus.SIMULATION_EXECUTED),
        # a finite solver value -> compared against target, inside tolerance
        (EvidenceStatus.SIMULATION_EXECUTED, EvidenceStatus.PHYSICS_VERIFIED),
    }
)


LEDGER_SCHEMA = "textlayout.evidence-ledger.v1"


class EvidenceError(ValueError):
    """Raised when an evidence record would violate the honesty contract."""


def confidence_of(status: EvidenceStatus) -> ConfidenceClass:
    """The confidence class a status is entitled to claim."""
    return _CONFIDENCE[status]


def is_legal_transition(old: EvidenceStatus, new: EvidenceStatus) -> bool:
    """Whether evidence may move from ``old`` to ``new``.

    Confidence may always be *lost* (a re-run that fails invalidates an earlier
    PHYSICS_VERIFIED claim) and may always be restated at the same level. It may
    only be *gained* along an edge in :data:`_PROMOTIONS`.
    """
    if confidence_of(new) <= confidence_of(old):
        return True
    return (old, new) in _PROMOTIONS


def validate_transition(old: EvidenceStatus, new: EvidenceStatus) -> None:
    """Raise :class:`EvidenceError` if ``old -> new`` is an illegal promotion."""
    if is_legal_transition(old, new):
        return
    raise EvidenceError(
        f"illegal confidence promotion {old.value} -> {new.value}: "
        f"confidence would rise from {confidence_of(old).name} to "
        f"{confidence_of(new).name} without passing through the sanctioned path "
        f"(prepare inputs -> run solver -> compare to target)"
    )


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
        # Run first: NaN defeats every subsequent comparison, so a non-finite
        # value must be rejected before any tolerance check is attempted.
        for field in _FINITE_FIELDS:
            value = getattr(self, field)
            if value is not None and not math.isfinite(value):
                raise EvidenceError(
                    f"{field} must be a finite number, got {value!r}; a non-finite "
                    "solver output is SIMULATION_INVALID, never a verified quantity"
                )
        if status in _SOLVER_REJECTED_STATUSES:
            if not self.solver:
                raise EvidenceError(f"{status.value} requires a named solver")
            if self.extracted_value is not None:
                raise EvidenceError(
                    f"{status.value} must not carry an extracted value; the solver "
                    "output was rejected, so no quantity was extracted from it"
                )
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
        if status in _NO_SOLVER_RAN_STATUSES and self.extracted_value is not None:
            raise EvidenceError(f"{status.value} must not carry an extracted value")
        return self

    @property
    def is_physics_verified(self) -> bool:
        return self.status is EvidenceStatus.PHYSICS_VERIFIED

    @property
    def confidence_class(self) -> ConfidenceClass:
        """How much physical confidence this record is entitled to claim."""
        return confidence_of(self.status)

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
        if self.status is EvidenceStatus.SIMULATION_INVALID:
            return (
                f"{self.quantity}: SIMULATION_INVALID — {self.solver} ran but its output "
                "failed a physical-sanity check; no quantity was extracted"
            )
        if self.status is EvidenceStatus.CONVERGENCE_FAILED:
            return (
                f"{self.quantity}: CONVERGENCE_FAILED — {self.solver} ran but the result "
                "did not converge under refinement; no quantity was extracted"
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

    The status is *computed*, never passed in: a non-finite extracted value ->
    SIMULATION_INVALID, within tolerance -> PHYSICS_VERIFIED, outside ->
    SIMULATION_EXECUTED. All structural checks of :class:`QuantityEvidence`
    still apply (output files must exist, etc.).
    """
    if target_value == 0:
        raise EvidenceError("target_value must be non-zero to compute a relative error")
    if target_unit.strip().lower() != extracted_unit.strip().lower():
        raise EvidenceError(
            f"unit mismatch: target in {target_unit!r}, extracted in "
            f"{extracted_unit!r}; convert to a common unit before comparison"
        )
    if not math.isfinite(extracted_value):
        # A solver that emits NaN/inf ran, but extracted nothing. Preserve the
        # raw token in the notes for diagnosis; never in a numeric field, where
        # it would defeat every downstream comparison.
        return QuantityEvidence(
            quantity=quantity,
            target_value=target_value,
            target_unit=target_unit,
            extracted_value=None,
            extracted_unit=extracted_unit,
            analytical_value=analytical_value,
            analytical_model=analytical_model,
            tolerance_percent=tolerance_percent,
            status=EvidenceStatus.SIMULATION_INVALID,
            solver=solver,
            command=command,
            input_files=list(input_files),
            output_files=list(output_files),
            parser=parser,
            notes=[
                *(notes or []),
                f"solver returned a non-finite {quantity}: {extracted_value!r}",
            ],
        )
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


class EvidenceLedger:
    """Append-only history of one quantity's evidence, refusing illegal promotion.

    A design is re-run many times: inputs are prepared, a solver runs, a mesh is
    refined, a target is compared. Each step replaces the previous claim. The
    ledger is what stops a later step from *quietly raising* the confidence of
    an earlier one -- for example a re-run that skipped because the solver
    disappeared must not leave the old PHYSICS_VERIFIED claim standing, and a
    record cannot jump from SKIPPED_SOLVER_ABSENT to PHYSICS_VERIFIED without a
    solver having run in between.

    Demotion is always permitted: losing confidence is always honest.

        >>> ledger = EvidenceLedger("capacitance")
        >>> ledger.record(prepared)      # doctest: +SKIP
        >>> ledger.record(verified)      # doctest: +SKIP  (illegal: no solver ran)
        Traceback (most recent call last):
        EvidenceError: illegal confidence promotion ...
    """

    def __init__(self, quantity: str, history: list[QuantityEvidence] | None = None) -> None:
        self.quantity = quantity
        self._history: list[QuantityEvidence] = []
        for record in history or []:
            self.record(record)

    @property
    def history(self) -> tuple[QuantityEvidence, ...]:
        return tuple(self._history)

    @property
    def current(self) -> QuantityEvidence | None:
        """The most recent claim, or None if nothing has been recorded."""
        return self._history[-1] if self._history else None

    def record(self, evidence: QuantityEvidence) -> QuantityEvidence:
        """Append ``evidence``, raising EvidenceError on an illegal promotion."""
        if evidence.quantity != self.quantity:
            raise EvidenceError(
                f"ledger tracks {self.quantity!r}, refusing record for {evidence.quantity!r}"
            )
        previous = self.current
        if previous is not None:
            validate_transition(previous.status, evidence.status)
        self._history.append(evidence)
        return evidence

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": LEDGER_SCHEMA,
            "quantity": self.quantity,
            "current_status": self.current.status.value if self.current else None,
            "current_confidence": (
                self.current.confidence_class.name if self.current else ConfidenceClass.NONE.name
            ),
            "history": [record.model_dump(mode="json") for record in self._history],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> EvidenceLedger:
        """Rebuild a ledger, re-validating every transition in the stored history.

        A ledger file that was hand-edited to promote a claim will not load.
        """
        quantity = payload.get("quantity")
        if not isinstance(quantity, str):
            raise EvidenceError("evidence ledger requires a string 'quantity'")
        raw_history = payload.get("history", [])
        if not isinstance(raw_history, list):
            raise EvidenceError("evidence ledger 'history' must be a list")
        return cls(quantity, [QuantityEvidence.model_validate(item) for item in raw_history])
