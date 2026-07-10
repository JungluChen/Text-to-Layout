"""Strict Palace AMR and computational-domain verification gates.

The report produced here is deliberately stricter than a successful Palace
process exit.  A frequency can be reported as ``SIMULATION_EXECUTED`` after a
real solve, but it is promoted to ``PHYSICS_VERIFIED`` only when every mesh,
mode, domain, participation, energy, and independent-reference gate passes.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.contract import EvidenceStatus

PALACE_VERIFICATION_SCHEMA = "textlayout.palace-verification.v1"
REQUIRED_SWEEPS = (
    "vacuum_domain",
    "substrate_thickness",
    "package_height",
    "lateral_boundary",
)


class VerificationThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode_overlap_min: float = Field(default=0.98, gt=0, le=1)
    last_frequency_change_percent_max: float = Field(default=0.2, gt=0)
    global_amr_error_percent_max: float = Field(default=0.5, gt=0)
    domain_frequency_sensitivity_percent_max: float = Field(default=0.2, gt=0)
    participation_change_percent_max: float = Field(default=2.0, gt=0)
    energy_normalization_error_percent_max: float = Field(default=0.1, gt=0)


class PalaceAMRLevel(BaseModel):
    """Solver-owned observables for one mesh or AMR iteration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tag: str
    refinement_kind: Literal["adaptive", "uniform", "uniform_unstructured"]
    polynomial_order: int = Field(ge=1)
    frequency_ghz: float = Field(gt=0)
    global_error_indicator_percent: float | None = Field(default=None, ge=0)
    element_error_indicator_file: str | None = None
    element_error_indicator_sha256: str | None = None
    energy_normalization_error_percent: float | None = Field(default=None, ge=0)
    electric_energy_by_region: dict[str, float] = Field(default_factory=dict)
    magnetic_energy_by_region: dict[str, float] = Field(default_factory=dict)
    participation_by_region: dict[str, float] = Field(default_factory=dict)
    output_file_hashes: dict[str, str] = Field(default_factory=dict)


class DomainSweepPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value_um: float = Field(gt=0)
    frequency_ghz: float = Field(gt=0)
    participation_by_region: dict[str, float] = Field(default_factory=dict)
    output_file_hashes: dict[str, str] = Field(default_factory=dict)


class DomainSweep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    points: list[DomainSweepPoint] = Field(default_factory=list)


class IndependentReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    method: str
    frequency_ghz: float = Field(gt=0)
    tolerance_percent: float = Field(default=2.0, gt=0)
    artifact_sha256: str = Field(min_length=64, max_length=64)


class VerificationGate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    passed: bool
    value: float | None = None
    threshold: float | None = None
    detail: str


class PalaceVerificationStudy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    design_id: str
    solver_name: str = "Palace"
    solver_version: str | None = None
    solver_artifact_hash: str | None = None
    levels: list[PalaceAMRLevel] = Field(default_factory=list)
    sweeps: list[DomainSweep] = Field(default_factory=list)
    independent_reference: IndependentReference | None = None
    thresholds: VerificationThresholds = Field(default_factory=VerificationThresholds)


class PalaceVerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    schema_version: str = PALACE_VERIFICATION_SCHEMA
    design_id: str
    status: EvidenceStatus
    promoted_frequency_ghz: float | None = None
    candidate_frequency_ghz: float | None = None
    gates: list[VerificationGate]
    blockers: list[str]
    study_sha256: str

    @property
    def verified(self) -> bool:
        return self.status is EvidenceStatus.PHYSICS_VERIFIED


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_amr_config(
    base: Mapping[str, Any],
    *,
    output: str,
    polynomial_order: int,
    tolerance_percent: float = 0.5,
    max_iterations: int = 6,
    update_fraction: float = 0.7,
) -> dict[str, Any]:
    """Return a Palace config using its native solution-based AMR schema."""
    if polynomial_order < 1:
        raise ValueError("polynomial_order must be at least 1")
    if not 0 < tolerance_percent < 100:
        raise ValueError("tolerance_percent must lie in (0, 100)")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive")
    if not 0 < update_fraction < 1:
        raise ValueError("update_fraction must lie in (0, 1)")

    config = copy.deepcopy(dict(base))
    model = config.setdefault("Model", {})
    model["Refinement"] = {
        "Tol": tolerance_percent / 100.0,
        "MaxIts": max_iterations,
        "UpdateFraction": update_fraction,
        "Nonconformal": True,
        "SaveAdaptIterations": True,
        "SaveAdaptMesh": True,
    }
    solver = config.setdefault("Solver", {})
    solver["Order"] = polynomial_order
    problem = config.setdefault("Problem", {})
    problem["Output"] = output
    formats = problem.setdefault("OutputFormats", {})
    formats["GridFunction"] = True
    formats["Paraview"] = True
    return config


def parse_domain_field_participation(
    path: Path, *, mode: int = 1, region_names: Mapping[int, str] | None = None
) -> tuple[dict[str, float], dict[str, float], float]:
    """Parse Palace ``domain-E.csv`` electric/magnetic fractions and balance."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, skipinitialspace=True))
    if not rows:
        raise ValueError(f"{path}: no domain-energy rows")
    row = next((item for item in rows if int(float(item.get("m", "0"))) == mode), None)
    if row is None:
        raise ValueError(f"{path}: no domain-energy row for mode {mode}")

    electric: dict[str, float] = {}
    magnetic: dict[str, float] = {}
    names = dict(region_names or {})
    for raw_name, raw_value in row.items():
        name = raw_name.strip()
        if name.startswith("p_elec[") and name.endswith("]"):
            index = int(name.removeprefix("p_elec[").removesuffix("]"))
            electric[names.get(index, str(index))] = float(raw_value)
        elif name.startswith("p_mag[") and name.endswith("]"):
            index = int(name.removeprefix("p_mag[").removesuffix("]"))
            magnetic[names.get(index, str(index))] = float(raw_value)
    if not electric or not magnetic:
        raise ValueError(f"{path}: electric and magnetic regional participation are required")
    e_total = float(row["E_elec (J)"])
    m_total = float(row["E_mag (J)"])
    denominator = max((abs(e_total) + abs(m_total)) / 2.0, 1e-300)
    balance_error_percent = abs(e_total - m_total) / denominator * 100.0
    return electric, magnetic, balance_error_percent


def parse_global_error_indicators(path: Path) -> list[float]:
    """Read Palace's global AMR indicator history from ``error-indicators.csv``."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, skipinitialspace=True))
    if not rows:
        raise ValueError(f"{path}: no error-indicator rows")
    values: list[float] = []
    for row in rows:
        candidates = [
            value
            for key, value in row.items()
            if "indicator" in key.strip().lower() or "error" in key.strip().lower()
        ]
        if not candidates:
            raise ValueError(f"{path}: no error-indicator column")
        values.append(float(candidates[-1]) * 100.0)
    return values


def _cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float | None:
    keys = sorted(set(left) | set(right))
    if not keys:
        return None
    a = [left.get(key, 0.0) for key in keys]
    b = [right.get(key, 0.0) for key in keys]
    norm_a = math.sqrt(sum(value * value for value in a))
    norm_b = math.sqrt(sum(value * value for value in b))
    if norm_a == 0 or norm_b == 0:
        return None
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (norm_a * norm_b)))


def _relative_change_percent(first: float, second: float) -> float:
    return abs(second - first) / max(abs(second), 1e-300) * 100.0


def _sweep_sensitivity(sweep: DomainSweep) -> float | None:
    if len(sweep.points) < 3:
        return None
    values = [point.frequency_ghz for point in sweep.points]
    return (max(values) - min(values)) / (sum(values) / len(values)) * 100.0


def assess_palace_verification(study: PalaceVerificationStudy) -> PalaceVerificationReport:
    """Evaluate every required gate; promotion is all-or-nothing."""
    thresholds = study.thresholds
    levels = study.levels
    gates: list[VerificationGate] = []

    adaptive = len(levels) >= 3 and all(level.refinement_kind == "adaptive" for level in levels)
    gates.append(
        VerificationGate(
            name="palace_adaptive_mesh_refinement",
            passed=adaptive,
            value=float(len(levels)),
            threshold=3.0,
            detail="at least three solver-owned adaptive iterations are required",
        )
    )

    indicator_metadata = bool(levels) and all(
        level.global_error_indicator_percent is not None
        and level.element_error_indicator_file
        and level.element_error_indicator_sha256
        for level in levels
    )
    gates.append(
        VerificationGate(
            name="element_wise_error_indicators_recorded",
            passed=indicator_metadata,
            detail="every level must hash Palace's element indicator field and global indicator",
        )
    )

    order_metadata = bool(levels) and all(level.polynomial_order >= 1 for level in levels)
    gates.append(
        VerificationGate(
            name="polynomial_order_metadata_recorded",
            passed=order_metadata,
            detail="finite-element order is recorded for every level",
        )
    )

    overlaps: list[float] = []
    overlap_missing = False
    for previous, current in zip(levels, levels[1:]):
        e_overlap = _cosine(previous.electric_energy_by_region, current.electric_energy_by_region)
        h_overlap = _cosine(previous.magnetic_energy_by_region, current.magnetic_energy_by_region)
        if e_overlap is None or h_overlap is None:
            overlap_missing = True
        else:
            overlaps.append(min(e_overlap, h_overlap))
    minimum_overlap = min(overlaps) if overlaps and not overlap_missing else None
    gates.append(
        VerificationGate(
            name="electric_and_magnetic_mode_overlap",
            passed=minimum_overlap is not None and minimum_overlap > thresholds.mode_overlap_min,
            value=minimum_overlap,
            threshold=thresholds.mode_overlap_min,
            detail="minimum adjacent-level overlap; strict greater-than comparison",
        )
    )

    frequency_change = (
        _relative_change_percent(levels[-2].frequency_ghz, levels[-1].frequency_ghz)
        if len(levels) >= 2
        else None
    )
    gates.append(
        VerificationGate(
            name="last_level_frequency_change_percent",
            passed=frequency_change is not None
            and frequency_change < thresholds.last_frequency_change_percent_max,
            value=frequency_change,
            threshold=thresholds.last_frequency_change_percent_max,
            detail="change between the two finest accepted levels",
        )
    )

    global_error = levels[-1].global_error_indicator_percent if levels else None
    gates.append(
        VerificationGate(
            name="global_amr_error_indicator_percent",
            passed=global_error is not None
            and global_error < thresholds.global_amr_error_percent_max,
            value=global_error,
            threshold=thresholds.global_amr_error_percent_max,
            detail="Palace global estimator on the final adaptive iteration",
        )
    )

    by_name = {sweep.name: sweep for sweep in study.sweeps}
    sensitivities = {
        name: _sweep_sensitivity(by_name[name]) if name in by_name else None
        for name in REQUIRED_SWEEPS
    }
    completed_sensitivities = [value for value in sensitivities.values() if value is not None]
    worst_sensitivity = max(completed_sensitivities) if len(completed_sensitivities) == 4 else None
    gates.append(
        VerificationGate(
            name="all_domain_sweeps_complete",
            passed=all(value is not None for value in sensitivities.values()),
            value=float(len(completed_sensitivities)),
            threshold=4.0,
            detail="vacuum, substrate, package-height, and lateral-boundary sweeps need >=3 points",
        )
    )
    gates.append(
        VerificationGate(
            name="domain_size_frequency_sensitivity_percent",
            passed=worst_sensitivity is not None
            and worst_sensitivity < thresholds.domain_frequency_sensitivity_percent_max,
            value=worst_sensitivity,
            threshold=thresholds.domain_frequency_sensitivity_percent_max,
            detail=json.dumps(sensitivities, sort_keys=True),
        )
    )

    participation_change: float | None = None
    if len(levels) >= 2:
        regions = set(levels[-2].participation_by_region) | set(levels[-1].participation_by_region)
        if regions:
            participation_change = max(
                _relative_change_percent(
                    levels[-2].participation_by_region.get(region, 0.0),
                    levels[-1].participation_by_region.get(region, 0.0),
                )
                for region in regions
            )
    gates.append(
        VerificationGate(
            name="participation_change_percent",
            passed=participation_change is not None
            and participation_change < thresholds.participation_change_percent_max,
            value=participation_change,
            threshold=thresholds.participation_change_percent_max,
            detail="worst regional participation change across the final two levels",
        )
    )

    energy_error = (
        max(
            level.energy_normalization_error_percent
            for level in levels
            if level.energy_normalization_error_percent is not None
        )
        if levels and all(level.energy_normalization_error_percent is not None for level in levels)
        else None
    )
    gates.append(
        VerificationGate(
            name="energy_normalization_error_percent",
            passed=energy_error is not None
            and energy_error < thresholds.energy_normalization_error_percent_max,
            value=energy_error,
            threshold=thresholds.energy_normalization_error_percent_max,
            detail="maximum electric/magnetic eigenmode energy-balance error",
        )
    )

    reference = study.independent_reference
    reference_error = (
        _relative_change_percent(reference.frequency_ghz, levels[-1].frequency_ghz)
        if reference is not None and levels
        else None
    )
    gates.append(
        VerificationGate(
            name="independent_reference_target",
            passed=reference is not None
            and reference_error is not None
            and reference_error <= reference.tolerance_percent,
            value=reference_error,
            threshold=reference.tolerance_percent if reference else None,
            detail=reference.method if reference else "no independent reference artifact supplied",
        )
    )

    blockers = [gate.name for gate in gates if not gate.passed]
    candidate = levels[-1].frequency_ghz if levels else None
    status = (
        EvidenceStatus.PHYSICS_VERIFIED
        if not blockers and candidate is not None
        else EvidenceStatus.SIMULATION_EXECUTED
        if candidate is not None
        else EvidenceStatus.SIMULATION_INPUT_PREPARED
    )
    study_payload = json.dumps(study.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return PalaceVerificationReport(
        design_id=study.design_id,
        status=status,
        promoted_frequency_ghz=candidate if status is EvidenceStatus.PHYSICS_VERIFIED else None,
        candidate_frequency_ghz=candidate,
        gates=gates,
        blockers=blockers,
        study_sha256=hashlib.sha256(study_payload.encode("utf-8")).hexdigest(),
    )


def write_report(report: PalaceVerificationReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path
