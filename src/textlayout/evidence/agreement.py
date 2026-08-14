"""Independent-solver agreement records for design-level physics signoff.

``QuantityEvidence.status == PHYSICS_VERIFIED`` is deliberately a
*quantity-level* statement about one solver meeting one target. Design-level
Level 5 signoff is stronger: two independent solver families must agree about
the same quantity, design, and analysis scope.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from textlayout.evidence.canonical import CanonicalEvidence
from textlayout.evidence.contract import EvidenceError, VERIFIED_STATUSES

AGREEMENT_SCHEMA = "textlayout.solver-agreement.v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UNIT_SCALE: dict[str, tuple[str, float]] = {
    "hz": ("frequency", 1.0),
    "khz": ("frequency", 1e3),
    "mhz": ("frequency", 1e6),
    "ghz": ("frequency", 1e9),
    "f": ("capacitance", 1.0),
    "ff": ("capacitance", 1e-15),
    "pf": ("capacitance", 1e-12),
    "nf": ("capacitance", 1e-9),
    "uf": ("capacitance", 1e-6),
    "h": ("inductance", 1.0),
    "ph": ("inductance", 1e-12),
    "nh": ("inductance", 1e-9),
    "uh": ("inductance", 1e-6),
    "ohm": ("resistance", 1.0),
    "kohm": ("resistance", 1e3),
}


def _normalise_unit(unit: str) -> str:
    return unit.strip().replace("µ", "u").replace("μ", "u").replace("Ω", "ohm").casefold()


def convert_value(value: float, source_unit: str, target_unit: str) -> float:
    """Convert a supported finite value, failing closed on incompatible units."""
    if not math.isfinite(value):
        raise EvidenceError(f"agreement values must be finite, got {value!r}")
    source = _UNIT_SCALE.get(_normalise_unit(source_unit))
    target = _UNIT_SCALE.get(_normalise_unit(target_unit))
    if source is None:
        raise EvidenceError(f"unsupported agreement unit: {source_unit!r}")
    if target is None:
        raise EvidenceError(f"unsupported agreement unit: {target_unit!r}")
    if source[0] != target[0]:
        raise EvidenceError(
            f"cannot compare {source_unit!r} ({source[0]}) with "
            f"{target_unit!r} ({target[0]})"
        )
    return value * source[1] / target[1]


def solver_family(solver_name: str) -> str:
    """Return a stable family identifier, independent of spelling/version."""
    compact = re.sub(r"[^a-z0-9]+", "", solver_name.casefold())
    aliases = (
        ("fastercap", "fastercap"),
        ("fastcap", "fastcap"),
        ("fasthenry", "fasthenry"),
        ("openems", "openems"),
        ("palace", "palace"),
        ("elmer", "elmer"),
        ("scqubits", "scqubits"),
        ("josim", "josim"),
    )
    for marker, family in aliases:
        if marker in compact:
            return family
    return compact


class SolverOutputDigest(BaseModel):
    """One non-empty, content-hashed output owned by a solver run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str
    size_bytes: int = Field(gt=0)

    @field_validator("sha256")
    @classmethod
    def _valid_sha256(cls, value: str) -> str:
        normalised = value.casefold()
        if not _SHA256_RE.fullmatch(normalised):
            raise EvidenceError("solver output sha256 must be a 64-character hex digest")
        return normalised


class SolverAgreementMember(BaseModel):
    """The evidence and extracted value contributed by one solver family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1)
    solver_family: str = Field(min_length=1)
    extracted_value: float
    extracted_unit: str = Field(min_length=1)
    outputs: tuple[SolverOutputDigest, ...] = Field(min_length=1)

    @field_validator("solver_family")
    @classmethod
    def _canonical_family(cls, value: str) -> str:
        family = solver_family(value)
        if not family:
            raise EvidenceError("solver_family must identify a solver")
        return family

    @field_validator("extracted_value")
    @classmethod
    def _finite_value(cls, value: float) -> float:
        if not math.isfinite(value):
            raise EvidenceError(f"agreement values must be finite, got {value!r}")
        return value

    @model_validator(mode="after")
    def _unique_output_paths(self) -> SolverAgreementMember:
        paths = [output.path for output in self.outputs]
        if len(paths) != len(set(paths)):
            raise EvidenceError(f"duplicate solver output paths for {self.evidence_id!r}")
        return self


class SolverAgreementRecord(BaseModel):
    """Computed comparison of at least two independent solver families."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=AGREEMENT_SCHEMA)
    design_hash: str
    analysis_scope: str = Field(min_length=1)
    target_quantity: str = Field(min_length=1)
    target_unit: str = Field(min_length=1)
    members: tuple[SolverAgreementMember, ...] = Field(min_length=2)
    tolerance_percent: float = Field(gt=0)

    @field_validator("design_hash")
    @classmethod
    def _valid_design_hash(cls, value: str) -> str:
        normalised = value.casefold()
        if not _SHA256_RE.fullmatch(normalised):
            raise EvidenceError("agreement design_hash must be a SHA-256 hex digest")
        return normalised

    @model_validator(mode="after")
    def _independent_and_convertible(self) -> SolverAgreementRecord:
        evidence_ids = [member.evidence_id for member in self.members]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise EvidenceError("agreement requires distinct canonical evidence IDs")
        if len({member.solver_family for member in self.members}) < 2:
            raise EvidenceError("agreement requires at least two independent solver families")
        for member in self.members:
            convert_value(member.extracted_value, member.extracted_unit, self.target_unit)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def relative_disagreement_percent(self) -> float:
        """Full solver-value spread relative to the absolute arithmetic mean."""
        values = [
            convert_value(member.extracted_value, member.extracted_unit, self.target_unit)
            for member in self.members
        ]
        mean_magnitude = sum(abs(value) for value in values) / len(values)
        spread = max(values) - min(values)
        if mean_magnitude == 0.0:
            return 0.0
        return abs(spread / mean_magnitude) * 100.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        """Whether the computed disagreement is finite and within tolerance."""
        disagreement = self.relative_disagreement_percent
        return math.isfinite(disagreement) and disagreement <= self.tolerance_percent

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(member.evidence_id for member in self.members)

    @property
    def solver_families(self) -> tuple[str, ...]:
        return tuple(sorted({member.solver_family for member in self.members}))

    def validate_against(self, records: Sequence[CanonicalEvidence]) -> list[str]:
        """Return all reasons this agreement does not cover ``records`` honestly."""
        problems: list[str] = []
        by_id = {record.evidence_id: record for record in records}
        for member in self.members:
            record = by_id.get(member.evidence_id)
            if record is None:
                problems.append(f"agreement evidence ID not provided: {member.evidence_id}")
                continue
            if record.design_hash.casefold() != self.design_hash:
                problems.append(f"design hash mismatch for {member.evidence_id}")
            if record.analysis_scope != self.analysis_scope:
                problems.append(f"analysis scope mismatch for {member.evidence_id}")
            if record.target_quantity != self.target_quantity:
                problems.append(f"target quantity mismatch for {member.evidence_id}")
            if record.target_unit is None:
                problems.append(f"target unit missing for {member.evidence_id}")
            else:
                try:
                    convert_value(1.0, record.target_unit, self.target_unit)
                except EvidenceError:
                    problems.append(f"target unit mismatch for {member.evidence_id}")
            if record.status not in VERIFIED_STATUSES:
                problems.append(f"{member.evidence_id} is not quantity-level physics verified")
            if record.solver_name is None:
                problems.append(f"{member.evidence_id} has no solver identity")
            elif solver_family(record.solver_name) != member.solver_family:
                problems.append(f"solver family mismatch for {member.evidence_id}")
            if record.extracted_value != member.extracted_value:
                problems.append(f"extracted value mismatch for {member.evidence_id}")
            if record.extracted_unit != member.extracted_unit:
                problems.append(f"extracted unit mismatch for {member.evidence_id}")
            member_outputs = {output.path: output.sha256 for output in member.outputs}
            if record.output_file_hashes != member_outputs:
                problems.append(f"output hash mismatch for {member.evidence_id}")
        if not self.passed:
            problems.append(
                "solver disagreement exceeds tolerance "
                f"({self.relative_disagreement_percent:.6g}% > {self.tolerance_percent:.6g}%)"
            )
        return problems
