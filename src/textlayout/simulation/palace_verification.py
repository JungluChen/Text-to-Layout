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
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.contract import EvidenceStatus

#: v2: sweeps are typed as numerical-domain vs physical-parameter, and the
#: former "electric_and_magnetic_mode_overlap" gate is honestly renamed to
#: "regional_energy_mode_similarity" — it compares regional energy
#: distributions, never true spatial field overlap. v1 reports remain
#: readable through their own committed JSON; nothing rewrites them.
PALACE_VERIFICATION_SCHEMA = "textlayout.palace-verification.v2"

#: Only these sweeps assess how the *computational* domain truncates the
#: problem; they gate numerical-domain convergence. A PML/absorbing-layer
#: thickness sweep joins them when such a boundary is implemented.
REQUIRED_NUMERICAL_SWEEPS = (
    "vacuum_or_air_margin",
    "upper_boundary_distance",
    "lateral_boundary_margin",
)

#: Retained for callers of the v1 vocabulary; the v1 sweep group mixed
#: numerical truncation and physical device parameters, which is exactly the
#: semantic error v2 corrects.
LEGACY_V1_REQUIRED_SWEEPS = (
    "vacuum_domain",
    "substrate_thickness",
    "package_height",
    "lateral_boundary",
)


class SweepCategory(str, Enum):
    """What a sensitivity sweep measures.

    A ``NUMERICAL_DOMAIN`` sweep varies a computational truncation choice
    (air margin, boundary distance); the physics must not depend on it, so it
    participates in the numerical-domain convergence gate. A
    ``PHYSICAL_PARAMETER`` sweep varies the actual device or package (its
    substrate thickness, permittivity); the frequency is *expected* to move,
    and such a sweep must never fail numerical convergence.
    """

    NUMERICAL_DOMAIN = "numerical_domain"
    PHYSICAL_PARAMETER = "physical_parameter"


class VerificationThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    regional_energy_similarity_min: float = Field(default=0.98, gt=0, le=1)
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


class SensitivitySweep(BaseModel):
    """A named sweep, explicitly typed as numerical-domain or physical."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    category: SweepCategory = SweepCategory.NUMERICAL_DOMAIN
    points: list[DomainSweepPoint] = Field(default_factory=list)


#: v1 name, kept importable so existing callers keep working; a bare
#: ``DomainSweep`` defaults to the numerical-domain category.
DomainSweep = SensitivitySweep


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
    sweeps: list[SensitivitySweep] = Field(default_factory=list)
    independent_reference: IndependentReference | None = None
    thresholds: VerificationThresholds = Field(default_factory=VerificationThresholds)

    @property
    def numerical_sweeps(self) -> list[SensitivitySweep]:
        return [s for s in self.sweeps if s.category is SweepCategory.NUMERICAL_DOMAIN]

    @property
    def physical_sweeps(self) -> list[SensitivitySweep]:
        return [s for s in self.sweeps if s.category is SweepCategory.PHYSICAL_PARAMETER]


class SweepSensitivityResult(BaseModel):
    """Per-sweep sensitivity, reported for every sweep of either category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    category: SweepCategory
    points: int
    frequency_sensitivity_percent: float | None = None
    substrate_participation_sensitivity_percent: float | None = None
    vacuum_participation_sensitivity_percent: float | None = None
    #: Only numerical-domain sweeps carry a pass/fail; a physical parameter
    #: is *expected* to move the frequency and is reported without judgement.
    passed: bool | None = None


class PalaceVerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    schema_version: str = PALACE_VERIFICATION_SCHEMA
    design_id: str
    status: EvidenceStatus
    promoted_frequency_ghz: float | None = None
    candidate_frequency_ghz: float | None = None
    gates: list[VerificationGate]
    blockers: list[str]
    numerical_domain_results: list[SweepSensitivityResult] = Field(default_factory=list)
    physical_sensitivity: list[SweepSensitivityResult] = Field(default_factory=list)
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


def _sweep_sensitivity(sweep: SensitivitySweep) -> float | None:
    if len(sweep.points) < 3:
        return None
    values = [point.frequency_ghz for point in sweep.points]
    return (max(values) - min(values)) / (sum(values) / len(values)) * 100.0


def _participation_sensitivity(sweep: SensitivitySweep, region: str) -> float | None:
    values = [
        point.participation_by_region[region]
        for point in sweep.points
        if region in point.participation_by_region
    ]
    if len(values) < 3:
        return None
    mean = sum(values) / len(values)
    return (max(values) - min(values)) / max(mean, 1e-12) * 100.0


def _sweep_result(
    sweep: SensitivitySweep, *, threshold_percent: float | None
) -> SweepSensitivityResult:
    frequency = _sweep_sensitivity(sweep)
    passed: bool | None = None
    if sweep.category is SweepCategory.NUMERICAL_DOMAIN and threshold_percent is not None:
        passed = frequency is not None and frequency < threshold_percent
    return SweepSensitivityResult(
        name=sweep.name,
        category=sweep.category,
        points=len(sweep.points),
        frequency_sensitivity_percent=frequency,
        substrate_participation_sensitivity_percent=_participation_sensitivity(
            sweep, "substrate"
        ),
        vacuum_participation_sensitivity_percent=_participation_sensitivity(sweep, "vacuum"),
        passed=passed,
    )


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
    minimum_similarity = min(overlaps) if overlaps and not overlap_missing else None
    gates.append(
        VerificationGate(
            name="regional_energy_mode_similarity",
            passed=minimum_similarity is not None
            and minimum_similarity > thresholds.regional_energy_similarity_min,
            value=minimum_similarity,
            threshold=thresholds.regional_energy_similarity_min,
            detail=(
                "minimum adjacent-level cosine similarity of regional electric and "
                "magnetic energy distributions; this is not spatial field overlap"
            ),
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

    numerical_by_name = {sweep.name: sweep for sweep in study.numerical_sweeps}
    sensitivities = {
        name: (
            _sweep_sensitivity(numerical_by_name[name]) if name in numerical_by_name else None
        )
        for name in REQUIRED_NUMERICAL_SWEEPS
    }
    completed_sensitivities = [value for value in sensitivities.values() if value is not None]
    worst_sensitivity = (
        max(completed_sensitivities)
        if len(completed_sensitivities) == len(REQUIRED_NUMERICAL_SWEEPS)
        else None
    )
    gates.append(
        VerificationGate(
            name="all_numerical_domain_sweeps_complete",
            passed=all(value is not None for value in sensitivities.values()),
            value=float(len(completed_sensitivities)),
            threshold=float(len(REQUIRED_NUMERICAL_SWEEPS)),
            detail=(
                "air-margin, upper-boundary, and lateral-boundary sweeps need >=3 points; "
                "physical-parameter sweeps are reported separately and never gate this"
            ),
        )
    )
    gates.append(
        VerificationGate(
            name="numerical_domain_frequency_sensitivity_percent",
            passed=worst_sensitivity is not None
            and worst_sensitivity < thresholds.domain_frequency_sensitivity_percent_max,
            value=worst_sensitivity,
            threshold=thresholds.domain_frequency_sensitivity_percent_max,
            detail=json.dumps(sensitivities, sort_keys=True),
        )
    )
    numerical_results = [
        _sweep_result(
            sweep, threshold_percent=thresholds.domain_frequency_sensitivity_percent_max
        )
        for sweep in study.numerical_sweeps
    ]
    physical_results = [
        _sweep_result(sweep, threshold_percent=None) for sweep in study.physical_sweeps
    ]

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
        numerical_domain_results=numerical_results,
        physical_sensitivity=physical_results,
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
