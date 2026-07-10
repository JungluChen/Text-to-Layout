"""Canonical, content-addressed evidence — the single source of truth.

Every public artifact (``simulation.json``, ``report.md``, showcase
``README.md``, the top-level README table, ``index.json``,
``PROJECT_STATUS.md``) is a *projection* of a :class:`CanonicalEvidence`
record. Nothing downstream may assert a status or an extracted value that its
canonical record does not carry.

Why this exists
---------------
A resonator openEMS run produced a Touchstone file in which all 401 S-parameter
samples were NaN. The low-level result was corrected to ``SIMULATION_INVALID``,
but eight derived artifacts kept reporting a successfully extracted 3.0 GHz
resonance — a number that is simply the first point of the sweep, because an
``argmin`` over all-NaN magnitudes returns index 0. Statuses were maintained by
hand in each file, so correcting one could not correct the rest.

Provenance rules
----------------
- A path existing on disk is **not** provenance. Every referenced input and
  output file is recorded as a SHA-256 content hash, so a solver output that
  changed after its evidence was written is detectable.
- The extraction configuration is hashed. Two runs of the same parser over the
  same output can disagree if one sampled at the sweep centre and the other at
  the design frequency; without the config hash that difference is invisible.
- A quantity that could not be extracted carries **no** extracted value. The
  withdrawn claim lives in :attr:`superseded`, never in an active field.
- ``confidence_class`` is derived from ``status``, never supplied, so a
  downstream artifact cannot claim more confidence than its status permits.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from textlayout.evidence.contract import (
    ConfidenceClass,
    EvidenceError,
    EvidenceStatus,
    confidence_of,
)

CANONICAL_SCHEMA = "textlayout.canonical-evidence.v2"

#: Statuses whose records must carry no active extracted value.
_NO_ACTIVE_VALUE = frozenset(
    {
        EvidenceStatus.SIMULATION_INVALID,
        EvidenceStatus.CONVERGENCE_FAILED,
        EvidenceStatus.FAILED,
        EvidenceStatus.SKIPPED_SOLVER_ABSENT,
        EvidenceStatus.SIMULATION_INPUT_PREPARED,
    }
)

_FINITE_FIELDS = (
    "target_value",
    "extracted_value",
    "analytical_value",
    "error_percent",
    "tolerance_percent",
    "runtime_seconds",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    """SHA-256 of a file's bytes. Raises if it does not exist."""
    source = Path(path)
    if not source.is_file():
        raise EvidenceError(f"cannot hash missing file: {source}")
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: Any) -> str:
    """Stable hash of a JSON-serialisable object (sorted keys, no whitespace)."""
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


class SupersededClaim(BaseModel):
    """A withdrawn claim, retained for audit. Never an active value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str | None = None
    status: str
    extracted_value: float | str | None = None
    extracted_unit: str | None = None
    why_withdrawn: str


class ConvergenceMetrics(BaseModel):
    """Evidence that the result is insensitive to discretisation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str = Field(description="How convergence was assessed, e.g. 'mesh_refinement'.")
    refinement_levels: int = Field(ge=1)
    delta_percent: float | None = Field(
        default=None, description="Change in the quantity at the finest refinement step."
    )
    threshold_percent: float | None = None
    converged: bool
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _finite(self) -> ConvergenceMetrics:
        for name in ("delta_percent", "threshold_percent"):
            value = getattr(self, name)
            if value is not None and not math.isfinite(value):
                raise EvidenceError(f"convergence.{name} must be finite, got {value!r}")
        return self


class CanonicalEvidence(BaseModel):
    """One solver-backed (or explicitly non-solver) claim about one quantity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=CANONICAL_SCHEMA)
    evidence_id: str = Field(description="Deterministic content-addressed id.")

    design_id: str
    design_hash: str = Field(description="SHA-256 of the typed DSL (layout.json).")
    geometry_hash: str | None = Field(
        default=None, description="SHA-256 of the exported GDS."
    )
    component: str
    analysis_scope: str = Field(
        description="What the claim covers, e.g. 'embedded_idc_region' vs 'full_tile'."
    )

    target_quantity: str
    target_value: float | None = None
    target_unit: str | None = None
    extracted_quantity: str | None = None
    extracted_value: float | None = None
    extracted_unit: str | None = None
    analytical_value: float | None = None
    analytical_model: str | None = None
    tolerance_percent: float = Field(default=5.0, gt=0)
    error_percent: float | None = None

    status: EvidenceStatus

    solver_name: str | None = None
    solver_version: str | None = None
    solver_executable_sha256: str | None = None
    container_digest: str | None = None
    command: list[str] = Field(default_factory=list)
    return_code: int | None = None
    runtime_seconds: float | None = None

    input_file_hashes: dict[str, str] = Field(default_factory=dict)
    output_file_hashes: dict[str, str] = Field(default_factory=dict)

    parser: str | None = None
    parser_version: str | None = None
    extraction_config: dict[str, Any] = Field(default_factory=dict)
    extraction_config_hash: str | None = None

    convergence: ConvergenceMetrics | None = None

    git_commit: str | None = None
    environment_hash: str | None = Field(
        default=None, description="SHA-256 of the lock file the run used."
    )
    timestamp: str

    warnings: list[str] = Field(default_factory=list)
    invalidation_reason: str | None = None
    skip_reason: str | None = None
    failure_reason: str | None = None

    #: Gaps we know about and refuse to paper over. A historical run whose
    #: binary was never hashed records "solver_executable_hash_unrecorded"
    #: rather than silently pretending the provenance is complete.
    provenance_gaps: list[str] = Field(default_factory=list)

    superseded: SupersededClaim | None = None
    supersedes_evidence_id: str | None = None

    @property
    def confidence_class(self) -> ConfidenceClass:
        """Derived, never supplied: a record cannot over-claim its own status."""
        return confidence_of(self.status)

    @model_validator(mode="after")
    def _enforce(self) -> CanonicalEvidence:
        # NaN defeats every later comparison, so reject it first.
        for name in _FINITE_FIELDS:
            value = getattr(self, name)
            if value is not None and not math.isfinite(value):
                raise EvidenceError(f"{name} must be finite, got {value!r}")

        if self.status in _NO_ACTIVE_VALUE and self.extracted_value is not None:
            raise EvidenceError(
                f"{self.status.value} must not carry an active extracted_value; "
                "a withdrawn number belongs in `superseded`"
            )
        if self.status is EvidenceStatus.SIMULATION_INVALID and not self.invalidation_reason:
            raise EvidenceError("SIMULATION_INVALID requires an invalidation_reason")
        if self.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT and not self.skip_reason:
            raise EvidenceError("SKIPPED_SOLVER_ABSENT requires a skip_reason")

        solver_backed = self.status in {
            EvidenceStatus.SIMULATION_EXECUTED,
            EvidenceStatus.PHYSICS_VERIFIED,
        }
        if solver_backed:
            if not self.solver_name:
                raise EvidenceError(f"{self.status.value} requires solver_name")
            if not self.parser:
                raise EvidenceError(f"{self.status.value} requires a parser")
            if self.extracted_value is None:
                raise EvidenceError(f"{self.status.value} requires an extracted_value")
            if not self.output_file_hashes:
                raise EvidenceError(
                    f"{self.status.value} requires output_file_hashes; a path on disk "
                    "is not provenance"
                )
            if not self.extraction_config_hash:
                raise EvidenceError(
                    f"{self.status.value} requires extraction_config_hash: the same "
                    "parser over the same output can disagree under a different config"
                )

        if self.status is EvidenceStatus.PHYSICS_VERIFIED:
            if self.convergence is None or not self.convergence.converged:
                raise EvidenceError(
                    "PHYSICS_VERIFIED requires convergence metrics reporting converged=True"
                )
            if self.target_value is None or self.error_percent is None:
                raise EvidenceError(
                    "PHYSICS_VERIFIED requires a target and a computed error_percent"
                )
            if abs(self.error_percent) > self.tolerance_percent:
                raise EvidenceError(
                    f"PHYSICS_VERIFIED requires |error| <= tolerance "
                    f"({abs(self.error_percent):.4f}% > {self.tolerance_percent:.4f}%)"
                )

        if self.status is EvidenceStatus.ANALYTICAL_ONLY and (
            self.solver_name or self.output_file_hashes
        ):
            raise EvidenceError(
                "ANALYTICAL_ONLY must not name a solver or claim solver output files"
            )

        if self.solver_executable_sha256 is None and self.container_digest is None:
            if solver_backed and "solver_executable_hash_unrecorded" not in self.provenance_gaps:
                raise EvidenceError(
                    "a solver-backed record without solver_executable_sha256 or "
                    "container_digest must declare the gap in provenance_gaps"
                )
        return self

    def verify_output_hashes(self, root: str | Path) -> list[str]:
        """Re-hash every referenced output file; return a list of mismatches.

        This is what catches a solver output edited after its evidence was
        written -- the failure mode a path check cannot see.
        """
        problems: list[str] = []
        base = Path(root)
        for relative, expected in sorted(self.output_file_hashes.items()):
            path = base / relative
            if not path.is_file():
                problems.append(f"missing output file: {relative}")
                continue
            actual = sha256_file(path)
            if actual != expected:
                problems.append(
                    f"{relative}: recorded sha256 {expected[:12]}... but file hashes "
                    f"{actual[:12]}... (output changed after evidence was written)"
                )
        return problems

    def to_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["confidence_class"] = self.confidence_class.name
        return payload


def compute_evidence_id(
    *,
    design_id: str,
    target_quantity: str,
    output_file_hashes: dict[str, str],
    extraction_config_hash: str | None,
) -> str:
    """Deterministic id: same design + quantity + outputs + config -> same id."""
    return sha256_json(
        {
            "design_id": design_id,
            "target_quantity": target_quantity,
            "outputs": dict(sorted(output_file_hashes.items())),
            "extraction_config_hash": extraction_config_hash,
        }
    )[:32]


def load_canonical(path: str | Path) -> CanonicalEvidence:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    payload.pop("confidence_class", None)  # derived, never an input
    return CanonicalEvidence.model_validate(payload)


def write_canonical(evidence: CanonicalEvidence, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence.to_dict(), indent=2) + "\n", encoding="utf-8")
    return target
