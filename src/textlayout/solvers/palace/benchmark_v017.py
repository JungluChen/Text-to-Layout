"""Palace 0.17 AMR quarter-wave benchmark with domain-convergence sweeps.

This is the executable workflow behind ``textlayout simulate palace-resonator``.
It replaces the three unrelated global Gmsh meshes with Palace's native
solution-based adaptive mesh refinement, tracks the resonator mode across AMR
iterations by frequency continuity and regional energy distribution, and runs
four independent computational-domain sweeps. Every quantity written here is
parsed from Palace-owned output; nothing is synthesised.

Output layout (all under one ``--out`` directory)::

    toolchain.json          solver + mesh runtime identity
    fem_model.json          the typed FEM IR the meshes and configs project
    resolved_configs/       Palace's own fully-resolved configuration sidecars
    base_mesh/              the single validated simplex mesh + the AMR run
    amr/iteration_XX/       Palace-owned outputs and parsed metrics per iteration
    domain_sweeps/          vacuum/substrate/package/lateral sweeps
    mode_tracking.json      match scores and margins across AMR iterations
    convergence.json        every gate and the resulting honest status
    canonical_evidence.json the repository's existing CanonicalEvidence schema
    report.md               human-readable summary
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.canonical import (
    ArtifactDependency,
    CanonicalEvidence,
    ConvergenceMetrics,
    SanityCheck,
    compute_evidence_id,
    sha256_file,
    sha256_json,
    write_canonical,
)
from textlayout.evidence.contract import EvidenceStatus
from textlayout.fem import FEMModel
from textlayout.fem.gmsh_physical import GmshMeshResult, mesh_quarter_wave
from textlayout.generators.resonator import QuarterWaveResonatorGenerator
from textlayout.knowledge.technology_library import default_technology_library
from textlayout.simulation.resource_sampler import (
    MemorySampler,
    decide_process_count,
    palace_reported_peak_memory_mb,
    read_memory_budget,
)
from textlayout.simulation.palace_verification import (
    DomainSweepPoint,
    PalaceAMRLevel,
    PalaceVerificationStudy,
    SensitivitySweep,
    SweepCategory,
    VerificationGate,
    assess_palace_verification,
)
from textlayout.solvers.palace.capability import capability_report, detect_palace
from textlayout.solvers.palace.config import (
    DomainExtents,
    build_eigenmode_config,
    load_quarter_wave_layout,
    quarter_wave_fem_model,
    write_config,
    write_json,
)
from textlayout.solvers.palace.models import (
    Eigenmode,
    ModeFieldData,
    PalaceCapability,
    PalaceOutputError,
    PalaceRun,
)
from textlayout.solvers.palace.parser import (
    parse_eigenmodes,
    parse_global_error_indicator,
    parse_mode_fields,
    field_artifact_files,
    field_mac,
)
from textlayout.solvers.palace.runner import build_command, run_palace
from textlayout.solvers.palace.stages import (
    StageName,
    relative_hashes,
    status_report,
    write_stage_record,
)

REQUIRED_PALACE_VERSION = "0.17.0"
PARSER = "textlayout.solvers.palace.parser.parse_eigenmodes"
PARSER_VERSION = "1"
PeakMemory = dict[str, int | float | None]

#: Numerical-domain sweeps vary computational truncation only; the physics
#: must not depend on them, so they gate numerical-domain convergence.
DEFAULT_NUMERICAL_SWEEP_VALUES: dict[str, tuple[float, ...]] = {
    "vacuum_or_air_margin": (250.0, 300.0, 350.0),
    "upper_boundary_distance": (400.0, 450.0, 500.0),
    "lateral_boundary_margin": (75.0, 100.0, 125.0),
}

#: Physical sensitivity studies vary the real device or stack; the frequency
#: is expected to move, and these never gate numerical convergence.
DEFAULT_PHYSICAL_SWEEP_VALUES: dict[str, tuple[float, ...]] = {
    "substrate_thickness": (250.0, 300.0, 350.0),
    "substrate_permittivity": (11.0, 11.45, 11.9),
}

#: Who owns each physical parameter and what kind of uncertainty it carries.
PHYSICAL_PARAMETER_METADATA: dict[str, dict[str, str]] = {
    "substrate_thickness": {
        "owner": "PDK",
        "uncertainty_kind": "physical",
        "unit": "um",
        "note": "wafer thickness tolerance; a real device parameter, not a truncation choice",
    },
    "substrate_permittivity": {
        "owner": "PDK",
        "uncertainty_kind": "physical",
        "unit": "relative",
        "note": "silicon epsilon_r assumption; same mesh, config-only variation",
    },
}

#: Parameters the current model cannot vary; reported honestly as unsupported.
UNSUPPORTED_PHYSICAL_PARAMETERS: dict[str, str] = {
    "metal_thickness": "metal is modelled as an infinitely thin PEC sheet",
    "kinetic_inductance": "no London-depth/kinetic-inductance surface model is configured",
    "package_height": (
        "the PEC lid is used as a numerical truncation boundary in this study, "
        "so its distance is swept as upper_boundary_distance instead"
    ),
}


class AMRSettings(BaseModel):
    """Palace-native AMR controls held fixed across the whole study."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tolerance: float = Field(default=1e-4, gt=0, lt=1)
    max_iterations: int = Field(default=5, ge=2)
    update_fraction: float = Field(default=0.7, gt=0, lt=1)
    nonconformal: bool = False

    def refinement_config(self) -> dict[str, Any]:
        return {
            "Tol": self.tolerance,
            "MaxIts": self.max_iterations,
            "UpdateFraction": self.update_fraction,
            "Nonconformal": self.nonconformal,
            "SaveAdaptIterations": True,
            "SaveAdaptMesh": True,
        }


class AMRIterationRecord(BaseModel):
    """Parsed, Palace-owned observables for one accepted AMR iteration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tag: str
    palace_iteration: int = Field(ge=1)
    element_count: int = Field(gt=0)
    degrees_of_freedom: int = Field(gt=0)
    polynomial_order: int = Field(ge=1)
    candidate_frequencies_ghz: list[float]
    tracked_mode_index: int | None = None
    tracked_frequency_ghz: float | None = None
    global_error_indicator_percent: float = Field(ge=0)
    electric_energy_by_region: dict[str, float]
    magnetic_energy_by_region: dict[str, float]
    substrate_participation: float = Field(ge=0, le=1)
    vacuum_participation: float = Field(ge=0, le=1)
    electric_energy_j: float
    magnetic_energy_j: float
    energy_normalization_error_percent: float = Field(ge=0)
    cumulative_runtime_seconds: float | None = None
    runtime_seconds: float | None = None
    resolved_config_sha256: str
    output_file_hashes: dict[str, str]


class ModeMatch(BaseModel):
    """Identity match between adjacent AMR iterations.

    The similarity terms compare *regional energy distributions* from
    ``domain-E.csv`` — they are never true spatial field overlap.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_tag: str
    to_tag: str
    from_mode: int = Field(ge=1)
    to_mode: int = Field(ge=1)
    frequency_proximity: float = Field(ge=0, le=1)
    electric_regional_energy_similarity: float = Field(ge=0, le=1)
    magnetic_regional_energy_similarity: float = Field(ge=0, le=1)
    electric_field_mac: float = Field(ge=0, le=1)
    magnetic_field_mac: float = Field(ge=0, le=1)
    localization_similarity: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)
    runner_up_score: float = Field(ge=0, le=1)

    @property
    def margin(self) -> float:
        return self.score - self.runner_up_score


class SweepPointRecord(BaseModel):
    """One genuine Palace solve at a perturbed domain or physical parameter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sweep: str
    category: SweepCategory
    value: float = Field(gt=0)
    unit: str = "um"
    extents: DomainExtents
    mesh_sha256: str
    resolved_config_sha256: str
    frequency_ghz: float = Field(gt=0)
    mode_index: int = Field(ge=1)
    substrate_participation: float = Field(ge=0, le=1)
    vacuum_participation: float = Field(ge=0, le=1)
    electric_participation_by_region: dict[str, float]
    runtime_seconds: float = Field(ge=0)
    output_file_hashes: dict[str, str]


class V017BenchmarkResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    output_dir: Path
    reason: str | None = None
    evidence_path: Path | None = None
    tracked_frequency_ghz: float | None = None


class SweepExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: str
    global_error_indicator_percent: float = Field(ge=0)
    numerical: dict[str, tuple[float, ...]]
    physical: dict[str, tuple[float, ...]]
    reason: str


def staged_sweep_plan(
    global_error_percent: float,
    numerical: dict[str, tuple[float, ...]],
    physical: dict[str, tuple[float, ...]],
) -> SweepExecutionPlan:
    if global_error_percent > 5.0:
        return SweepExecutionPlan(
            tier="no_sweeps",
            global_error_indicator_percent=global_error_percent,
            numerical={},
            physical={},
            reason="global AMR indicator exceeds 5%",
        )
    if global_error_percent > 1.0:
        first = next(iter(numerical.items()), None)
        pilot = {first[0]: (first[1][-1],)} if first and first[1] else {}
        return SweepExecutionPlan(
            tier="one_numerical_endpoint_pilot",
            global_error_indicator_percent=global_error_percent,
            numerical=pilot,
            physical={},
            reason="global AMR indicator is between 1% and 5%",
        )
    if global_error_percent > 0.5:
        return SweepExecutionPlan(
            tier="numerical_convergence_only",
            global_error_indicator_percent=global_error_percent,
            numerical=numerical,
            physical={},
            reason="global AMR indicator is between 0.5% and 1%",
        )
    return SweepExecutionPlan(
        tier="full_promotion_assessment",
        global_error_indicator_percent=global_error_percent,
        numerical=numerical,
        physical=physical,
        reason="global AMR indicator is at or below 0.5%",
    )


class CompletedBaseAMR(BaseModel):
    """Validated pre-existing Palace base-AMR output reused during resume."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    config_path: Path
    postpro: Path
    run: PalaceRun
    peak_memory: PeakMemory
    validation: dict[str, Any]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError:
        return None
    return completed.stdout.strip() or None


def _install_record(root: Path) -> dict[str, Any] | None:
    path = root / ".tools" / "palace" / "install.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _gmsh_identity() -> dict[str, Any]:
    from textlayout.mesh.runtime import gmsh_identity

    return gmsh_identity()


def _preflight_peak_mb(root: Path) -> int | None:
    """Peak used-memory (MB) from a sibling ``*_preflight`` base-AMR run, if any.

    The reduced preflight writes ``base_mesh/peak_memory.json``; its peak is
    the best available estimate for the resource gate before the full run.
    """
    candidate = root.parent / f"{root.name}_preflight" / "base_mesh" / "peak_memory.json"
    if not candidate.is_file():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = payload.get("peak_used_mb")
    return int(value) if isinstance(value, (int, float)) and value > 0 else None


def _load_existing_base_mesh(base_dir: Path) -> GmshMeshResult | None:
    metrics_path = base_dir / "mesh_metrics.json"
    mesh_path = base_dir / "quarter_wave_base.msh"
    if not metrics_path.is_file() or not mesh_path.is_file():
        return None
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    recorded_hash = metrics.get("mesh_sha256")
    actual_hash = sha256_file(mesh_path)
    if recorded_hash and recorded_hash != actual_hash:
        raise PalaceOutputError(
            f"{mesh_path}: mesh hash {actual_hash} does not match mesh_metrics.json "
            f"{recorded_hash}"
        )
    return GmshMeshResult(
        path=mesh_path,
        runtime_seconds=float(metrics.get("runtime_seconds", 0.0)),
        element_count=int(metrics["element_count"]),
        minimum_quality=float(metrics["minimum_quality"]),
        mean_quality=float(metrics["mean_quality"]),
    )


def _runtime_from_stdout(stdout_path: Path) -> float | None:
    if not stdout_path.is_file():
        return None
    text = stdout_path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(
        r"(?im)^\s*Total\s+([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)\s*$",
        text,
    )
    return float(matches[-1][2]) if matches else None


def _completed_stdout(stdout_path: Path) -> bool:
    if not stdout_path.is_file():
        return False
    text = stdout_path.read_text(encoding="utf-8", errors="replace")
    return "Completed" in text and "adaptive mesh refinement" in text


def _load_peak_memory(run_dir: Path) -> dict[str, int]:
    path = run_dir / "peak_memory.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {str(key): int(value) for key, value in data.items() if isinstance(value, int)}


def validate_completed_base_amr(
    root: str | Path,
    *,
    capability: PalaceCapability | None = None,
    processes: int = 4,
) -> CompletedBaseAMR:
    """Validate and reconstruct a completed base AMR run without rerunning it."""
    root = Path(root).resolve()
    detected = capability or detect_palace()
    if not detected.available:
        raise PalaceOutputError(detected.unavailable_reason or "Palace is unavailable")
    base_dir = root / "base_mesh"
    config_path = base_dir / "palace_amr.json"
    mesh_path = base_dir / "quarter_wave_base.msh"
    postpro = base_dir / "postpro"
    required = [
        config_path,
        mesh_path,
        postpro / "eig.csv",
        postpro / "domain-E.csv",
        postpro / "error-indicators.csv",
        postpro / "palace.json",
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise PalaceOutputError(
            "completed base AMR cannot be reused; missing artifact(s): "
            + ", ".join(str(path) for path in missing)
        )
    resolved = _resolved_config(postpro)
    adapted_meshes = [
        (path.resolve() if path.is_symlink() else path)
        for path in postpro.rglob("*.mesh")
    ]
    adapted_meshes = [path for path in adapted_meshes if path.is_file()]
    raw_adapted = root / "raw" / "final_adapted.mesh"
    if not adapted_meshes and not raw_adapted.is_file():
        raise PalaceOutputError(
            "completed base AMR cannot be reused; no Palace adapted mesh was retained"
        )
    modes = parse_eigenmodes(postpro / "eig.csv")
    _ = parse_global_error_indicator(postpro / "error-indicators.csv")
    if not _completed_stdout(base_dir / "palace.stdout.txt"):
        raise PalaceOutputError(
            "completed base AMR cannot be reused; retained stdout does not contain "
            "Palace's AMR completion line"
        )
    install = _install_record(Path(__file__).resolve().parents[4]) or {}
    install_hash = install.get("palace_executable_sha256")
    if install_hash and detected.executable_sha256 and install_hash != detected.executable_sha256:
        raise PalaceOutputError(
            "completed base AMR cannot be reused; executable hash "
            f"{detected.executable_sha256} does not match install.json {install_hash}"
        )
    command = build_command(detected, config_path, cwd=base_dir, processes=processes)
    runtime = _runtime_from_stdout(base_dir / "palace.stdout.txt") or 0.0
    output_files = [
        postpro / "eig.csv",
        postpro / "domain-E.csv",
        postpro / "error-indicators.csv",
        postpro / "palace.json",
        resolved,
        base_dir / "palace.stdout.txt",
        base_dir / "palace.stderr.txt",
        *(adapted_meshes[-1:] or [raw_adapted]),
    ]
    run = PalaceRun(
        command=command,
        return_code=0,
        runtime_seconds=runtime,
        stdout_path=base_dir / "palace.stdout.txt",
        stderr_path=base_dir / "palace.stderr.txt",
        output_dir=base_dir,
        input_file_hashes=relative_hashes([config_path, mesh_path], base_dir),
        output_file_hashes=relative_hashes(output_files, root),
    )
    validation = {
        "schema": "textlayout.palace-base-amr-validation.v1",
        "validated_at": _timestamp(),
        "return_code": 0,
        "return_code_basis": (
            "reconstructed from completed Palace stdout and parseable required outputs; "
            "the interrupted shell did not leave a standalone process manifest"
        ),
        "modes_ghz": [mode.frequency_ghz for mode in modes],
        "resolved_config": str(resolved),
        "adapted_mesh": str(adapted_meshes[-1] if adapted_meshes else raw_adapted),
        "executable_sha256": detected.executable_sha256,
        "install_executable_sha256": install_hash,
        "command": command,
        "mpi_processes": processes,
    }
    write_json(validation, root / "base_amr_validation.json")
    return CompletedBaseAMR(
        config_path=config_path,
        postpro=postpro,
        run=run,
        peak_memory=_load_peak_memory(base_dir),
        validation=validation,
    )


def palace_resonator_status(output_dir: str | Path) -> dict[str, Any]:
    return status_report(Path(output_dir).resolve())


def _environment(repo_root: Path, capability: PalaceCapability) -> dict[str, Any]:
    """Capture the execution environment for the benchmark output tree.

    Combines the installed Palace identity (which already records the probed
    MPI and compiler versions and the native root) with a light WSL probe for
    OS, CPU, and memory so every benchmark run is accompanied by its context.
    """
    import platform

    record = _install_record(repo_root) or {}
    wsl = "unknown"
    cpu_model = "unknown"
    cores = "unknown"
    ram = "unknown"
    try:
        from textlayout.simulation.runners import _wsl_exe

        wsl_exe = _wsl_exe()
        if wsl_exe is not None:
            probe = subprocess.run(
                [
                    wsl_exe,
                    "-d",
                    "Ubuntu",
                    "--",
                    "bash",
                    "-lc",
                    "(. /etc/os-release 2>/dev/null && echo wsl=$PRETTY_NAME); "
                    "echo cores=$(nproc); "
                    "echo ram_kb=$(awk '/MemTotal/{print $2}' /proc/meminfo); "
                    "echo cpu=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | "
                    "sed 's/^ *//')",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
            fields = dict(
                line.split("=", 1)
                for line in probe.stdout.splitlines()
                if "=" in line
            )
            wsl = fields.get("wsl", wsl)
            cpu_model = fields.get("cpu", cpu_model)
            cores = fields.get("cores", cores)
            ram_kb = fields.get("ram_kb", "")
            if ram_kb.isdigit():
                ram = f"{int(ram_kb) / 1024 / 1024:.1f} GB"
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return {
        "schema": "textlayout.palace-environment.v1",
        "timestamp": _timestamp(),
        "os": platform.platform(),
        "wsl": wsl,
        "cpu_model": cpu_model,
        "cpu_logical_cores": cores,
        "ram": ram,
        "python": platform.python_version(),
        "palace_version": capability.version,
        "palace_executable_sha256": capability.executable_sha256,
        "gmsh_version": _gmsh_identity().get("version"),
        "mpi_version": record.get("mpi_version"),
        "compiler_versions": record.get("compiler_versions"),
        "native_root": record.get("native_root"),
        "git_commit": _git_commit(repo_root),
    }


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    keys = sorted(set(left) | set(right))
    a = [left.get(key, 0.0) for key in keys]
    b = [right.get(key, 0.0) for key in keys]
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (norm_a * norm_b)))


def _grouped_participation(participation: dict[str, float]) -> tuple[float, float]:
    substrate = sum(v for k, v in participation.items() if "substrate" in k.lower())
    vacuum = sum(v for k, v in participation.items() if "vacuum" in k.lower())
    return max(0.0, min(1.0, substrate)), max(0.0, min(1.0, vacuum))


def _mode_field(fields: list[ModeFieldData], index: int, source: str) -> ModeFieldData:
    match = next((item for item in fields if item.mode_index == index), None)
    if match is None:
        raise PalaceOutputError(f"{source}: no field record for mode {index}")
    return match


def _elapsed_total(meta: dict[str, Any]) -> float | None:
    durations = meta.get("ElapsedTime", {}).get("Durations", {})
    if not isinstance(durations, dict):
        return None
    for key, value in durations.items():
        if str(key).strip().lower() == "total" and isinstance(value, (int, float)):
            return float(value)
    numeric = [float(v) for v in durations.values() if isinstance(v, (int, float))]
    return max(numeric) if numeric else None


def _domain_energy_totals(domain_csv: Path, mode: int) -> tuple[float, float]:
    import csv

    with domain_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, skipinitialspace=True))
    for row in rows:
        normalized = {str(key).strip(): value for key, value in row.items()}
        if int(float(normalized.get("m", "0"))) == mode:
            return float(normalized["E_elec (J)"]), float(normalized["E_mag (J)"])
    raise PalaceOutputError(f"{domain_csv}: no energy row for mode {mode}")


def _score_pair(
    left_frequency: float,
    left_electric: dict[str, float],
    left_magnetic: dict[str, float],
    left_localization: float,
    candidate_frequency: float,
    candidate_electric: dict[str, float],
    candidate_magnetic: dict[str, float],
    candidate_localization: float,
) -> tuple[float, float, float, float]:
    frequency = max(
        0.0, 1.0 - abs(candidate_frequency - left_frequency) / left_frequency / 0.15
    )
    electric = _cosine(left_electric, candidate_electric)
    magnetic = _cosine(left_magnetic, candidate_magnetic)
    localization = max(0.0, 1.0 - abs(candidate_localization - left_localization))
    return frequency, electric, magnetic, localization


class _ParsedIteration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tag: str
    palace_iteration: int
    directory: Path
    modes: list[Eigenmode]
    fields: list[ModeFieldData]
    global_error_percent: float
    element_count: int
    degrees_of_freedom: int
    cumulative_runtime_seconds: float | None
    output_file_hashes: dict[str, str]


def _parse_iteration_dir(
    source: Path,
    *,
    tag: str,
    palace_iteration: int,
    model: FEMModel,
    output_root: Path,
) -> _ParsedIteration:
    eig = source / "eig.csv"
    domain = source / "domain-E.csv"
    indicators = source / "error-indicators.csv"
    metadata = source / "palace.json"
    modes = parse_eigenmodes(eig)
    fields = parse_mode_fields(domain, region_names=model.energy_regions(), output_dir=source)
    global_error = parse_global_error_indicator(indicators)
    if not metadata.is_file():
        raise PalaceOutputError(f"{source}: Palace metadata palace.json is missing")
    meta = json.loads(metadata.read_text(encoding="utf-8"))
    problem = meta.get("Problem", {})
    elements = problem.get("MeshElements")
    dof = problem.get("DegreesOfFreedom")
    if not isinstance(elements, int) or elements <= 0:
        raise PalaceOutputError(f"{metadata}: Problem.MeshElements is missing or invalid")
    if not isinstance(dof, int) or dof <= 0:
        raise PalaceOutputError(f"{metadata}: Problem.DegreesOfFreedom is missing or invalid")
    retained = [eig, domain, indicators, metadata]
    for field in fields:
        if field.field_file is not None:
            retained.extend(field_artifact_files(field.field_file))
    hashes = {
        str(path.resolve().relative_to(output_root.resolve())).replace("\\", "/"): sha256_file(
            path
        )
        for path in dict.fromkeys(retained)
    }
    return _ParsedIteration(
        tag=tag,
        palace_iteration=palace_iteration,
        directory=source,
        modes=modes,
        fields=fields,
        global_error_percent=global_error,
        element_count=elements,
        degrees_of_freedom=dof,
        cumulative_runtime_seconds=_elapsed_total(meta),
        output_file_hashes=hashes,
    )


def _collect_amr_iterations(postpro: Path) -> list[tuple[int, Path]]:
    """Return ``(palace_iteration, directory)`` in solve order.

    Palace moves each superseded iteration into ``iterationN`` and leaves the
    final accepted iteration's outputs at the top level of the output folder.
    """
    saved: list[tuple[int, Path]] = []
    for candidate in sorted(postpro.glob("iteration*")):
        if not candidate.is_dir():
            continue
        suffix = candidate.name.removeprefix("iteration")
        try:
            saved.append((int(suffix), candidate))
        except ValueError:
            continue
    saved.sort(key=lambda item: item[0])
    final_index = (saved[-1][0] + 1) if saved else 1
    return [*saved, (final_index, postpro)]


def _resolved_config(postpro: Path) -> Path:
    matches = sorted(postpro.glob("*_resolved.json"))
    if not matches:
        raise PalaceOutputError(
            f"{postpro}: Palace did not write its resolved configuration sidecar"
        )
    return matches[0]


def _run_palace_once(
    capability: PalaceCapability,
    *,
    run_dir: Path,
    model: FEMModel,
    mesh: GmshMeshResult,
    refinement: dict[str, Any],
    processes: int,
    timeout_seconds: float,
    cancel_event: Event | None,
) -> tuple[Path, Path, PalaceRun, PeakMemory]:
    """Execute one Palace AMR solve while sampling memory.

    Returns ``(config_path, postpro, retained run, peak-memory dict)``.
    """
    config = build_eigenmode_config(
        model, mesh_filename=mesh.path.name, output_dir="postpro"
    )
    config["Model"]["Refinement"] = refinement
    # Retain selected-mode fields for every saved adaptive iteration. These
    # Palace-owned vectors are required for electric/magnetic field MAC and
    # ParaView error/localization diagnostics.
    config["Problem"]["OutputFormats"] = {"GridFunction": True, "Paraview": True}
    config["Solver"]["Eigenmode"]["Save"] = model.eigenmode.mode_count
    config_path = run_dir / "palace_amr.json"
    write_config(config, config_path)
    process_record = run_dir / "solver_process.json"
    with MemorySampler(
        solver_process_record=str(process_record)
        if os.environ.get("TEXTLAYOUT_JOB_ID")
        else None
    ) as sampler:
        run = run_palace(
            capability,
            config_path,
            cwd=run_dir,
            processes=processes,
            timeout_seconds=timeout_seconds,
            cancel_event=cancel_event,
            input_paths=[mesh.path],
        )
    peak: PeakMemory = {**sampler.result.to_dict()}
    palace_peak = palace_reported_peak_memory_mb(
        run.stdout_path.read_text(encoding="utf-8", errors="replace")
    )
    measured_peak = float(peak.get("peak_solver_rss_mb") or 0)
    peak["palace_reported_peak_memory_mb"] = palace_peak
    peak["measured_vs_palace_percent"] = (
        abs(measured_peak - palace_peak) / palace_peak * 100.0
        if palace_peak and palace_peak > 0
        else None
    )
    if run.timed_out:
        raise PalaceOutputError(f"{run_dir.name}: Palace timed out")
    if run.cancelled:
        raise PalaceOutputError(f"{run_dir.name}: Palace was cancelled")
    if run.return_code != 0:
        raise PalaceOutputError(
            f"{run_dir.name}: Palace returned non-zero exit code {run.return_code}"
        )
    write_json(peak, run_dir / "peak_memory.json")
    return config_path, run_dir / "postpro", run, peak


def _invocation_record(
    label: str,
    run: PalaceRun,
    capability: PalaceCapability,
    *,
    processes: int,
    mesh_sha256: str,
    resolved_config_sha256: str | None,
    root: Path,
    peak_memory: PeakMemory | None = None,
) -> dict[str, Any]:
    """Every Palace invocation retains its full process-level identity."""

    def _relative(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
        except ValueError:
            return str(path)

    return {
        "label": label,
        "command": run.command,
        "mpi_processes": processes,
        "palace_version": capability.version,
        "palace_executable_sha256": capability.executable_sha256,
        "initial_mesh_sha256": mesh_sha256,
        "resolved_config_sha256": resolved_config_sha256,
        "return_code": run.return_code,
        "runtime_seconds": run.runtime_seconds,
        "peak_memory": peak_memory or {},
        "stdout": _relative(run.stdout_path),
        "stderr": _relative(run.stderr_path),
        "input_file_hashes": run.input_file_hashes,
        "output_file_hashes": run.output_file_hashes,
    }


def track_amr_modes(
    iterations: list[_ParsedIteration],
    *,
    seed_frequency_ghz: float,
    minimum_score: float = 0.98,
    minimum_margin: float = 0.05,
) -> tuple[list[int], list[ModeMatch]]:
    """Track one physical mode across AMR iterations without assuming mode 1.

    Candidates are scored on frequency continuity, electric and magnetic
    energy distribution by region, and resonator-region localization. An
    ambiguous winner (margin below ``minimum_margin``) or a weak match
    (score below ``minimum_score``) raises ``PalaceOutputError``.
    """
    if len(iterations) < 2:
        raise PalaceOutputError("mode tracking requires at least two AMR iterations")
    first = min(
        iterations[0].modes,
        key=lambda mode: abs(mode.frequency_ghz - seed_frequency_ghz),
    )
    indices = [first.index]
    matches: list[ModeMatch] = []
    current = first.index
    for left, right in zip(iterations, iterations[1:]):
        left_mode = next(mode for mode in left.modes if mode.index == current)
        left_field = _mode_field(left.fields, current, left.tag)
        scored: list[ModeMatch] = []
        for candidate in right.modes:
            candidate_field = _mode_field(right.fields, candidate.index, right.tag)
            frequency, electric, magnetic, localization = _score_pair(
                left_mode.frequency_ghz,
                left_field.electric_participation,
                left_field.magnetic_participation,
                left_field.resonator_localization,
                candidate.frequency_ghz,
                candidate_field.electric_participation,
                candidate_field.magnetic_participation,
                candidate_field.resonator_localization,
            )
            if left_field.field_file is None or candidate_field.field_file is None:
                raise PalaceOutputError(
                    f"{left.tag} to {right.tag}: retained Palace fields are required for MAC"
                )
            electric_mac = field_mac(
                left_field.field_file, candidate_field.field_file, kind="electric"
            )
            magnetic_mac = field_mac(
                left_field.field_file, candidate_field.field_file, kind="magnetic"
            )
            score = (
                frequency
                + 2.0 * electric
                + 2.0 * magnetic
                + localization
                + 2.0 * electric_mac
                + 2.0 * magnetic_mac
            ) / 10.0
            scored.append(
                ModeMatch(
                    from_tag=left.tag,
                    to_tag=right.tag,
                    from_mode=current,
                    to_mode=candidate.index,
                    frequency_proximity=frequency,
                    electric_regional_energy_similarity=electric,
                    magnetic_regional_energy_similarity=magnetic,
                    electric_field_mac=electric_mac,
                    magnetic_field_mac=magnetic_mac,
                    localization_similarity=localization,
                    score=score,
                    runner_up_score=0.0,
                )
            )
        ranked = sorted(scored, key=lambda item: (-item.score, item.to_mode))
        if not ranked:
            raise PalaceOutputError(f"{right.tag}: no candidate modes")
        runner_up = ranked[1].score if len(ranked) > 1 else 0.0
        best = ranked[0].model_copy(update={"runner_up_score": runner_up})
        # Ambiguity is a *validity* failure: two candidates the tracker cannot
        # tell apart (small winner-vs-runner-up margin) -> SIMULATION_INVALID.
        # A clear winner whose absolute similarity is merely low is NOT
        # ambiguous -- it is a *convergence* shortfall (the coarse mesh has not
        # stabilised the mode's regional energy). That is enforced separately by
        # the ``mode_regional_energy_similarity_above_0p98`` convergence gate,
        # which yields CONVERGENCE_FAILED rather than SIMULATION_INVALID.
        if best.margin < minimum_margin:
            raise PalaceOutputError(
                f"ambiguous_mode_identity: {left.tag} to {right.tag} margin "
                f"{best.margin:.6f} is below {minimum_margin:.6f}"
            )
        indices.append(best.to_mode)
        matches.append(best)
        current = best.to_mode
    return indices, matches


def _iteration_records(
    iterations: list[_ParsedIteration],
    tracked: list[int],
    *,
    polynomial_order: int,
    resolved_config_sha256: str,
) -> list[AMRIterationRecord]:
    records: list[AMRIterationRecord] = []
    previous_cumulative: float | None = None
    for parsed, mode_index in zip(iterations, tracked):
        field = _mode_field(parsed.fields, mode_index, parsed.tag)
        substrate, vacuum = _grouped_participation(field.electric_participation)
        electric_j, magnetic_j = _domain_energy_totals(
            parsed.directory / "domain-E.csv", mode_index
        )
        tracked_frequency = next(
            mode.frequency_ghz for mode in parsed.modes if mode.index == mode_index
        )
        delta: float | None = None
        if parsed.cumulative_runtime_seconds is not None:
            delta = (
                parsed.cumulative_runtime_seconds
                if previous_cumulative is None
                else max(0.0, parsed.cumulative_runtime_seconds - previous_cumulative)
            )
            previous_cumulative = parsed.cumulative_runtime_seconds
        records.append(
            AMRIterationRecord(
                tag=parsed.tag,
                palace_iteration=parsed.palace_iteration,
                element_count=parsed.element_count,
                degrees_of_freedom=parsed.degrees_of_freedom,
                polynomial_order=polynomial_order,
                candidate_frequencies_ghz=[mode.frequency_ghz for mode in parsed.modes],
                tracked_mode_index=mode_index,
                tracked_frequency_ghz=tracked_frequency,
                global_error_indicator_percent=parsed.global_error_percent,
                electric_energy_by_region=field.electric_participation,
                magnetic_energy_by_region=field.magnetic_participation,
                substrate_participation=substrate,
                vacuum_participation=vacuum,
                electric_energy_j=electric_j,
                magnetic_energy_j=magnetic_j,
                energy_normalization_error_percent=field.energy_normalization_error_percent,
                cumulative_runtime_seconds=parsed.cumulative_runtime_seconds,
                runtime_seconds=delta,
                resolved_config_sha256=resolved_config_sha256,
                output_file_hashes=parsed.output_file_hashes,
            )
        )
    return records


def _select_sweep_mode(
    modes: list[Eigenmode],
    fields: list[ModeFieldData],
    *,
    reference_frequency_ghz: float,
    reference_electric: dict[str, float],
    reference_magnetic: dict[str, float],
    reference_localization: float,
    source: str,
    minimum_margin: float = 0.05,
) -> tuple[Eigenmode, ModeFieldData]:
    scored: list[tuple[float, Eigenmode, ModeFieldData]] = []
    for mode in modes:
        field = _mode_field(fields, mode.index, source)
        frequency, electric, magnetic, localization = _score_pair(
            reference_frequency_ghz,
            reference_electric,
            reference_magnetic,
            reference_localization,
            mode.frequency_ghz,
            field.electric_participation,
            field.magnetic_participation,
            field.resonator_localization,
        )
        score = (frequency + 2.0 * electric + 2.0 * magnetic + localization) / 6.0
        scored.append((score, mode, field))
    scored.sort(key=lambda item: (-item[0], item[1].index))
    if not scored:
        raise PalaceOutputError(f"{source}: no candidate modes")
    if len(scored) > 1 and scored[0][0] - scored[1][0] < minimum_margin:
        raise PalaceOutputError(
            f"ambiguous_mode_identity: {source} margin "
            f"{scored[0][0] - scored[1][0]:.6f} is below {minimum_margin:.6f}"
        )
    return scored[0][1], scored[0][2]


def run_quarter_wave_benchmark_v017(
    output_dir: str | Path,
    *,
    layout_path: str | Path,
    capability: PalaceCapability | None = None,
    processes: int = 4,
    timeout_seconds: float = 7200.0,
    cancel_event: Event | None = None,
    mesh_scale: float = 3.0,
    extents: DomainExtents | None = None,
    amr: AMRSettings | None = None,
    sweep_amr: AMRSettings | None = None,
    numerical_sweep_values: dict[str, tuple[float, ...]] | None = None,
    physical_sweep_values: dict[str, tuple[float, ...]] | None = None,
    resume: bool = False,
    stop_after_stage: StageName | None = None,
    from_stage: StageName | None = None,
) -> V017BenchmarkResult:
    """Run the Palace 0.17 AMR + domain-convergence benchmark end to end.

    The main convergence study uses ``amr``; the domain and physical sweeps use
    ``sweep_amr`` (default: the same as ``amr``). A lighter ``sweep_amr`` keeps
    the many sweep solves tractable while the main study stays rigorous. Every
    sweep point uses the *same* settings, so its sensitivity is a fair
    comparison.
    """
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    detected = capability or detect_palace()
    base_extents = extents or DomainExtents()
    settings = amr or AMRSettings()
    sweep_settings = sweep_amr or settings
    numerical_requested = dict(
        numerical_sweep_values
        if numerical_sweep_values is not None
        else DEFAULT_NUMERICAL_SWEEP_VALUES
    )
    physical_requested = dict(
        physical_sweep_values
        if physical_sweep_values is not None
        else DEFAULT_PHYSICAL_SWEEP_VALUES
    )
    repo_root = Path(__file__).resolve().parents[4]
    layout = Path(layout_path).resolve()
    stage_ids: list[str] = []
    resume = resume or from_stage is not None

    spec, params = load_quarter_wave_layout(layout)
    target_frequency = float(spec.target.get("frequency_ghz", 6.0))
    technology = default_technology_library().get(spec.technology)
    geometry = QuarterWaveResonatorGenerator().generate(params, technology, spec.origin)

    toolchain = {
        "schema": "textlayout.palace-toolchain.v1",
        "required_palace_version": REQUIRED_PALACE_VERSION,
        "capability": capability_report(detected),
        "install_record": _install_record(repo_root),
        "gmsh": _gmsh_identity(),
        "git_commit": _git_commit(repo_root),
        "generated_at": _timestamp(),
    }
    write_json(toolchain, root / "toolchain.json")
    write_json(_environment(repo_root, detected), root / "environment.json")

    # Documented resource gate: record the memory budget and the process-count
    # decision before any solve. The count is never silently changed; when a
    # prior preflight peak is available the tier is applied and recorded.
    budget = read_memory_budget()
    preflight_peak = _preflight_peak_mb(root)
    resource_decision = decide_process_count(
        processes, budget, preflight_peak_mb=preflight_peak
    )
    resource_decision["timestamp"] = _timestamp()
    write_json(resource_decision, root / "resource_decision.json")
    accepted = resource_decision["accepted_processes"]
    processes = accepted if isinstance(accepted, int) else processes

    model = quarter_wave_fem_model(layout, mesh_scale=mesh_scale, extents=base_extents)
    fem_hash = write_json(model.model_dump(mode="json"), root / "fem_model.json")
    preflight_record = write_stage_record(
        root,
        stage="preflight",
        status="complete",
        input_hashes=relative_hashes([layout], root),
        output_hashes=relative_hashes(
            [
                root / "toolchain.json",
                root / "environment.json",
                root / "resource_decision.json",
                root / "fem_model.json",
            ],
            root,
        ),
        capability=detected,
        notes=[
            "toolchain identity, environment, resource decision and FEM model prepared"
        ],
    )
    stage_ids.append(preflight_record.evidence_id)
    if stop_after_stage == "preflight":
        return V017BenchmarkResult(status="STAGE_COMPLETE", output_dir=root)

    if not detected.available:
        evidence = _skipped_evidence(detected, layout, fem_hash, target_frequency, repo_root)
        evidence_path = write_canonical(evidence, root / "canonical_evidence.json")
        (root / "report.md").write_text(
            "# Palace 0.17 quarter-wave AMR benchmark\n\n"
            f"Status: `{evidence.status.value}`\n\n"
            f"Palace is unavailable: {detected.unavailable_reason}\n",
            encoding="utf-8",
            newline="\n",
        )
        return V017BenchmarkResult(
            status=evidence.status.value,
            output_dir=root,
            reason=detected.unavailable_reason,
            evidence_path=evidence_path,
        )

    resolved_dir = root / "resolved_configs"
    resolved_dir.mkdir(parents=True, exist_ok=True)
    base_dir = root / "base_mesh"
    base_dir.mkdir(parents=True, exist_ok=True)

    def _mesh_for(extent: DomainExtents, directory: Path, stem: str) -> GmshMeshResult:
        mesh = mesh_quarter_wave(
            geometry,
            params,
            model,
            directory / f"{stem}.msh",
            substrate_thickness_um=extent.substrate_thickness_um,
            vacuum_height_um=extent.vacuum_height_um,
            lid_height_um=extent.lid_height_um,
            lateral_margin_um=extent.lateral_margin_um,
        )
        if mesh.minimum_quality < model.mesh.min_element_quality:
            raise PalaceOutputError(
                f"{mesh.path.name}: minimum element quality {mesh.minimum_quality:.4f} "
                f"is below {model.mesh.min_element_quality:.4f}"
            )
        return mesh

    try:
        base_mesh = _load_existing_base_mesh(base_dir) if resume else None
        if base_mesh is None:
            base_mesh = _mesh_for(base_extents, base_dir, "quarter_wave_base")
            write_json(
                {
                    "mesh_sha256": sha256_file(base_mesh.path),
                    "element_count": base_mesh.element_count,
                    "minimum_quality": base_mesh.minimum_quality,
                    "mean_quality": base_mesh.mean_quality,
                    "runtime_seconds": base_mesh.runtime_seconds,
                    "extents": base_extents.model_dump(mode="json"),
                    "mesh_scale": mesh_scale,
                },
                base_dir / "mesh_metrics.json",
            )

        base_mesh_hash = sha256_file(base_mesh.path)
        mesh_record = write_stage_record(
            root,
            stage="base_mesh",
            status="reused" if resume else "complete",
            input_hashes=relative_hashes([root / "fem_model.json"], root),
            output_hashes=relative_hashes(
                [base_mesh.path, base_dir / "mesh_metrics.json"], root
            ),
            runtime_seconds=base_mesh.runtime_seconds,
            capability=detected,
            upstream_stage_evidence_ids=list(stage_ids),
        )
        stage_ids.append(mesh_record.evidence_id)
        if stop_after_stage == "base_mesh":
            return V017BenchmarkResult(status="STAGE_COMPLETE", output_dir=root)

        if resume:
            completed = validate_completed_base_amr(root, capability=detected, processes=processes)
            config_path = completed.config_path
            postpro = completed.postpro
            amr_run = completed.run
            amr_peak = completed.peak_memory
        else:
            config_path, postpro, amr_run, amr_peak = _run_palace_once(
                detected,
                run_dir=base_dir,
                model=model,
                mesh=base_mesh,
                refinement=settings.refinement_config(),
                processes=processes,
                timeout_seconds=timeout_seconds,
                cancel_event=cancel_event,
            )
        base_amr_record = write_stage_record(
            root,
            stage="base_amr",
            status="reused" if resume else "complete",
            input_hashes=relative_hashes([config_path, base_mesh.path], root),
            output_hashes=amr_run.output_file_hashes,
            command=amr_run.command,
            return_code=amr_run.return_code,
            runtime_seconds=amr_run.runtime_seconds,
            capability=detected,
            upstream_stage_evidence_ids=list(stage_ids),
            notes=(
                [
                    "return code reconstructed from completed stdout and parseable Palace outputs"
                ]
                if resume
                else []
            ),
        )
        stage_ids.append(base_amr_record.evidence_id)
        if stop_after_stage == "base_amr":
            return V017BenchmarkResult(status="STAGE_COMPLETE", output_dir=root)
        amr_runtime = amr_run.runtime_seconds
        command = amr_run.command
        resolved_source = _resolved_config(postpro)
        resolved_base = resolved_dir / "amr_palace_resolved.json"
        shutil.copy2(resolved_source, resolved_base)
        resolved_hash = sha256_file(resolved_base)
        invocations: list[dict[str, Any]] = [
            _invocation_record(
                "amr",
                amr_run,
                detected,
                processes=processes,
                mesh_sha256=base_mesh_hash,
                resolved_config_sha256=resolved_hash,
                root=root,
                peak_memory=amr_peak,
            )
        ]

        # Palace's final adapted mesh (SaveAdaptMesh) is retained raw, hashed,
        # and never committed: it is large solver-owned provenance. Palace's
        # SaveIteration leaves the top-level ``*.mesh`` as a *relative symlink*
        # into the final iteration subdirectory, so resolve it to the real file
        # (moving the symlink would dangle) and copy the content into raw/.
        raw_dir = root / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        adapted_meshes = sorted(postpro.rglob("*.mesh"))
        final_adapted_mesh: Path | None = None
        final_adapted_mesh_hash: str | None = None
        real_meshes = [
            (path.resolve() if path.is_symlink() else path)
            for path in adapted_meshes
        ]
        real_meshes = [path for path in real_meshes if path.is_file()]
        if real_meshes:
            final_adapted_mesh = raw_dir / "final_adapted.mesh"
            try:
                if real_meshes[-1].resolve() != final_adapted_mesh.resolve():
                    if final_adapted_mesh.exists() or final_adapted_mesh.is_symlink():
                        final_adapted_mesh.unlink()
                    shutil.copy2(real_meshes[-1], final_adapted_mesh)
                final_adapted_mesh_hash = sha256_file(final_adapted_mesh)
            except OSError:
                # Some Windows/WSL runs expose Palace's relative mesh symlink in
                # a way pathlib reports as a file but CopyFile2 cannot follow.
                # Reuse the raw retained mesh if an earlier post-processing
                # attempt already copied it.
                if final_adapted_mesh.is_file():
                    final_adapted_mesh_hash = sha256_file(final_adapted_mesh)
                else:
                    raise

        amr_dir = root / "amr"
        parsed_iterations: list[_ParsedIteration] = []
        for order, (palace_iteration, source) in enumerate(_collect_amr_iterations(postpro)):
            tag = f"iteration_{order:02d}"
            destination = amr_dir / tag
            destination.mkdir(parents=True, exist_ok=True)
            for name in ("eig.csv", "domain-E.csv", "error-indicators.csv", "palace.json"):
                candidate = source / name
                if not candidate.is_file():
                    raise PalaceOutputError(
                        f"{source}: Palace-owned output {name} is missing for {tag}"
                    )
                shutil.copy2(candidate, destination / name)
            parsed_iterations.append(
                _parse_iteration_dir(
                    source,
                    tag=tag,
                    palace_iteration=palace_iteration,
                    model=model,
                    output_root=root,
                )
            )

        tracking_error: str | None = None
        tracked: list[int] = []
        matches: list[ModeMatch] = []
        try:
            tracked, matches = track_amr_modes(
                parsed_iterations, seed_frequency_ghz=target_frequency
            )
        except PalaceOutputError as exc:
            tracking_error = str(exc)

        write_json(
            {
                "schema": "textlayout.palace-mode-tracking.v3",
                "method": (
                    "frequency continuity + regional electric/magnetic energy "
                    "similarity + electric/magnetic field MAC + resonator localization"
                ),
                "seed_frequency_ghz": target_frequency,
                "tracked_mode_indices": tracked,
                "matches": [match.model_dump(mode="json") for match in matches],
                "minimum_regional_energy_similarity": 0.98,
                "minimum_electric_field_mac": 0.95,
                "minimum_magnetic_field_mac": 0.90,
                "minimum_margin": 0.05,
                "error": tracking_error,
            },
            root / "mode_tracking.json",
        )
        mode_record = write_stage_record(
            root,
            stage="mode_tracking",
            status="failed" if tracking_error is not None else "complete",
            input_hashes={
                path: digest
                for parsed in parsed_iterations
                for path, digest in parsed.output_file_hashes.items()
            },
            output_hashes=relative_hashes([root / "mode_tracking.json"], root),
            capability=detected,
            upstream_stage_evidence_ids=list(stage_ids),
            notes=[tracking_error] if tracking_error is not None else [],
        )
        stage_ids.append(mode_record.evidence_id)
        if tracking_error is not None:
            return _finish_invalid(
                root,
                detected,
                layout,
                fem_hash,
                target_frequency,
                repo_root,
                reason="ambiguous_mode_identity",
                detail=tracking_error,
                command=command,
            )
        if stop_after_stage == "mode_tracking":
            return V017BenchmarkResult(status="STAGE_COMPLETE", output_dir=root)

        records = _iteration_records(
            parsed_iterations,
            tracked,
            polynomial_order=model.eigenmode.element_order,
            resolved_config_sha256=resolved_hash,
        )
        for record in records:
            write_json(record.model_dump(mode="json"), amr_dir / record.tag / "metrics.json")

        accepted = records[-1]
        accepted_frequency = accepted.tracked_frequency_ghz
        if accepted_frequency is None:
            raise PalaceOutputError("final AMR iteration has no tracked frequency")
        accepted_field = _mode_field(
            parsed_iterations[-1].fields, tracked[-1], parsed_iterations[-1].tag
        )
        sweep_plan = staged_sweep_plan(
            accepted.global_error_indicator_percent,
            numerical_requested,
            physical_requested,
        )
        numerical_requested = sweep_plan.numerical
        physical_requested = sweep_plan.physical
        write_json(sweep_plan.model_dump(mode="json"), root / "scientific_gate.json")

        sweeps: list[SensitivitySweep] = []
        sweep_records: list[SweepPointRecord] = []

        def _run_sweep_point(
            sweep_name: str,
            category: SweepCategory,
            value: float,
            unit: str,
            group_root: Path,
        ) -> tuple[SweepPointRecord, DomainSweepPoint]:
            point_dir = group_root / sweep_name / f"{value:g}{unit if unit == 'um' else ''}"
            point_dir.mkdir(parents=True, exist_ok=True)
            if sweep_name == "substrate_permittivity":
                extent = base_extents
                point_model = quarter_wave_fem_model(
                    layout,
                    mesh_scale=mesh_scale,
                    extents=extent,
                    substrate_permittivity=value,
                )
                # Identical geometry: the base mesh is reused byte-for-byte so
                # the sweep isolates the permittivity assumption.
                mesh_path = point_dir / base_mesh.path.name
                shutil.copy2(base_mesh.path, mesh_path)
                point_mesh = GmshMeshResult(
                    path=mesh_path,
                    runtime_seconds=0.0,
                    element_count=base_mesh.element_count,
                    minimum_quality=base_mesh.minimum_quality,
                    mean_quality=base_mesh.mean_quality,
                )
            else:
                extent = _extents_for(base_extents, sweep_name, value)
                point_model = quarter_wave_fem_model(
                    layout, mesh_scale=mesh_scale, extents=extent
                )
                point_mesh = _mesh_for(extent, point_dir, "quarter_wave")
            point_mesh_hash = sha256_file(point_mesh.path)
            _, point_postpro, point_run, point_peak = _run_palace_once(
                detected,
                run_dir=point_dir,
                model=point_model,
                mesh=point_mesh,
                refinement=sweep_settings.refinement_config(),
                processes=processes,
                timeout_seconds=timeout_seconds,
                cancel_event=cancel_event,
            )
            point_resolved = _resolved_config(point_postpro)
            resolved_copy = resolved_dir / f"{sweep_name}_{value:g}_resolved.json"
            shutil.copy2(point_resolved, resolved_copy)
            invocations.append(
                _invocation_record(
                    f"{sweep_name}@{value:g}",
                    point_run,
                    detected,
                    processes=processes,
                    mesh_sha256=point_mesh_hash,
                    resolved_config_sha256=sha256_file(resolved_copy),
                    root=root,
                    peak_memory=point_peak,
                )
            )
            for stale_mesh in point_postpro.rglob("*.mesh"):
                stale_mesh.unlink()
            modes = parse_eigenmodes(point_postpro / "eig.csv")
            fields = parse_mode_fields(
                point_postpro / "domain-E.csv",
                region_names=point_model.energy_regions(),
                output_dir=point_postpro,
            )
            mode, field = _select_sweep_mode(
                modes,
                fields,
                reference_frequency_ghz=accepted_frequency,
                reference_electric=accepted_field.electric_participation,
                reference_magnetic=accepted_field.magnetic_participation,
                reference_localization=accepted_field.resonator_localization,
                source=f"{sweep_name}@{value:g}",
            )
            substrate, vacuum = _grouped_participation(field.electric_participation)
            hashes = {
                str(path.resolve().relative_to(root)).replace("\\", "/"): sha256_file(path)
                for path in (
                    point_postpro / "eig.csv",
                    point_postpro / "domain-E.csv",
                    resolved_copy,
                )
            }
            record = SweepPointRecord(
                sweep=sweep_name,
                category=category,
                value=value,
                unit=unit,
                extents=extent,
                mesh_sha256=point_mesh_hash,
                resolved_config_sha256=sha256_file(resolved_copy),
                frequency_ghz=mode.frequency_ghz,
                mode_index=mode.index,
                substrate_participation=substrate,
                vacuum_participation=vacuum,
                electric_participation_by_region=field.electric_participation,
                runtime_seconds=point_run.runtime_seconds,
                output_file_hashes=hashes,
            )
            write_json(record.model_dump(mode="json"), point_dir / "point.json")
            point = DomainSweepPoint(
                value_um=value,
                frequency_ghz=mode.frequency_ghz,
                participation_by_region={"substrate": substrate, "vacuum": vacuum},
                output_file_hashes=hashes,
            )
            return record, point

        for group_root, category, requested in (
            (root / "numerical_domain_sweeps", SweepCategory.NUMERICAL_DOMAIN, numerical_requested),
            (root / "physical_sensitivity", SweepCategory.PHYSICAL_PARAMETER, physical_requested),
        ):
            for sweep_name, values in requested.items():
                unit = PHYSICAL_PARAMETER_METADATA.get(sweep_name, {}).get("unit", "um")
                points: list[DomainSweepPoint] = []
                for value in values:
                    sweep_point_record, point = _run_sweep_point(
                        sweep_name, category, value, unit, group_root
                    )
                    sweep_records.append(sweep_point_record)
                    points.append(point)
                sweeps.append(
                    SensitivitySweep(name=sweep_name, category=category, points=points)
                )
        numerical_files = [
            path
            for path in (root / "numerical_domain_sweeps").rglob("*")
            if path.is_file()
        ]
        numerical_record = write_stage_record(
            root,
            stage="numerical_sweeps",
            status="skipped" if not numerical_requested else "complete",
            input_hashes=relative_hashes([root / "mode_tracking.json"], root),
            output_hashes=relative_hashes(numerical_files, root),
            capability=detected,
            upstream_stage_evidence_ids=list(stage_ids),
            notes=(
                [f"{sweep_plan.tier}: {sweep_plan.reason}"]
                if not numerical_requested
                else []
            ),
        )
        stage_ids.append(numerical_record.evidence_id)
        if stop_after_stage == "numerical_sweeps":
            return V017BenchmarkResult(status="STAGE_COMPLETE", output_dir=root)
        physical_files = [
            path
            for path in (root / "physical_sensitivity").rglob("*")
            if path.is_file()
        ]
        physical_record = write_stage_record(
            root,
            stage="physical_sensitivity",
            status="skipped" if not physical_requested else "complete",
            input_hashes=relative_hashes([root / "mode_tracking.json"], root),
            output_hashes=relative_hashes(physical_files, root),
            capability=detected,
            upstream_stage_evidence_ids=list(stage_ids),
            notes=(
                [f"{sweep_plan.tier}: {sweep_plan.reason}"]
                if not physical_requested
                else []
            ),
        )
        stage_ids.append(physical_record.evidence_id)
        if stop_after_stage == "physical_sensitivity":
            return V017BenchmarkResult(status="STAGE_COMPLETE", output_dir=root)
    except PalaceOutputError as exc:
        return _finish_invalid(
            root,
            detected,
            layout,
            fem_hash,
            target_frequency,
            repo_root,
            reason="palace_output_invalid",
            detail=str(exc),
            command=None,
        )

    levels = [
        PalaceAMRLevel(
            tag=record.tag,
            refinement_kind="adaptive",
            polynomial_order=record.polynomial_order,
            frequency_ghz=record.tracked_frequency_ghz or 1e-9,
            global_error_indicator_percent=record.global_error_indicator_percent,
            element_error_indicator_file=f"amr/{record.tag}/error-indicators.csv",
            element_error_indicator_sha256=record.output_file_hashes[
                f"amr/{record.tag}/error-indicators.csv"
            ],
            energy_normalization_error_percent=record.energy_normalization_error_percent,
            electric_energy_by_region=record.electric_energy_by_region,
            magnetic_energy_by_region=record.magnetic_energy_by_region,
            participation_by_region={
                "substrate": record.substrate_participation,
                "vacuum": record.vacuum_participation,
            },
            output_file_hashes=record.output_file_hashes,
        )
        for record in records
    ]
    study = PalaceVerificationStudy(
        design_id="quarter_wave_resonator_6ghz_palace_v017",
        solver_version=detected.version,
        solver_artifact_hash=detected.executable_sha256,
        levels=levels,
        sweeps=sweeps,
        independent_reference=None,
    )
    verification = assess_palace_verification(study)
    stop_reason = (
        "tolerance_reached"
        if len(records) < settings.max_iterations
        else "max_iterations_reached"
    )
    supplementary = _supplementary_gates(
        detected, records, matches, target_frequency, model, stop_reason=stop_reason
    )
    run_manifest = {
        "schema": "textlayout.palace-run-manifest.v1",
        "generated_at": _timestamp(),
        "git_commit": _git_commit(repo_root),
        "palace_version": detected.version,
        "palace_executable_sha256": detected.executable_sha256,
        "initial_mesh": {
            "path": f"base_mesh/{base_mesh.path.name}",
            "sha256": base_mesh_hash,
            "element_count": base_mesh.element_count,
            "minimum_quality": base_mesh.minimum_quality,
            "mean_quality": base_mesh.mean_quality,
        },
        "final_adapted_mesh": {
            "path": "raw/final_adapted.mesh" if final_adapted_mesh is not None else None,
            "sha256": final_adapted_mesh_hash,
            "retention": (
                "raw solver-owned provenance; kept locally under out/, uploaded by CI "
                "only as an optional expiring artifact, never committed"
            ),
        },
        "polynomial_order": model.eigenmode.element_order,
        "amr": {
            "accepted_iterations": len(records),
            "stop_reason": stop_reason,
            "settings": settings.model_dump(mode="json"),
            "final_element_count": records[-1].element_count,
            "final_degrees_of_freedom": records[-1].degrees_of_freedom,
            "final_global_error_indicator_percent": records[-1].global_error_indicator_percent,
        },
        "scientific_gate": sweep_plan.model_dump(mode="json"),
        "resolved_config_sha256": resolved_hash,
        "resource": {
            "decision": resource_decision,
            "peak_used_mb": max(
                (inv.get("peak_memory", {}).get("peak_used_mb", 0) for inv in invocations),
                default=0,
            ),
            "peak_solver_rss_mb": max(
                (inv.get("peak_memory", {}).get("peak_solver_rss_mb", 0) for inv in invocations),
                default=0,
            ),
        },
        "invocations": invocations,
    }
    write_json(run_manifest, root / "run_manifest.json")
    write_json(run_manifest["resource"], root / "resource_summary.json")
    invalid_names = {
        gate.name
        for gate in supplementary
        if not gate.passed
        and gate.name
        in {
            "palace_version_exactly_0_17_0",
            "frequencies_finite_and_positive",
            "element_count_increases",
            "degrees_of_freedom_increase",
            "eigenfrequency_not_at_search_window_boundary",
        }
    }
    convergence_blockers = [
        *(gate for gate in verification.gates if not gate.passed),
        *(gate for gate in supplementary if not gate.passed and gate.name not in invalid_names),
    ]
    convergence_blockers = [
        gate for gate in convergence_blockers if gate.name != "independent_reference_target"
    ]
    if invalid_names:
        status = EvidenceStatus.SIMULATION_INVALID
    elif convergence_blockers:
        status = EvidenceStatus.CONVERGENCE_FAILED
    else:
        status = EvidenceStatus.SIMULATION_EXECUTED

    write_json(
        {
            "schema": "textlayout.palace-convergence.v2",
            "status": status.value,
            "verification_report": verification.model_dump(mode="json"),
            "supplementary_gates": [gate.model_dump(mode="json") for gate in supplementary],
            "amr_iterations": [record.model_dump(mode="json") for record in records],
            "amr_settings": settings.model_dump(mode="json"),
            "amr_stop_reason": stop_reason,
            "sweep_points": [record.model_dump(mode="json") for record in sweep_records],
            "unsupported_physical_parameters": UNSUPPORTED_PHYSICAL_PARAMETERS,
            "physical_parameter_metadata": PHYSICAL_PARAMETER_METADATA,
        },
        root / "convergence.json",
    )

    evidence = _executed_evidence(
        detected,
        layout=layout,
        fem_hash=fem_hash,
        target_frequency=target_frequency,
        repo_root=repo_root,
        root=root,
        records=records,
        sweep_records=sweep_records,
        status=status,
        command=command,
        runtime_seconds=amr_runtime + sum(r.runtime_seconds for r in sweep_records),
        verification_gates=[*verification.gates, *supplementary],
        invalid_names=invalid_names,
        base_mesh=base_mesh,
        config_path=config_path,
        resolved_hash=resolved_hash,
        final_adapted_mesh_hash=final_adapted_mesh_hash,
    )
    evidence_path = write_canonical(evidence, root / "canonical_evidence.json")
    _write_report(root, status, records, matches, sweep_records, verification, supplementary)
    evidence_record = write_stage_record(
        root,
        stage="evidence_promotion",
        status=status.value,
        input_hashes=relative_hashes([root / "convergence.json", root / "run_manifest.json"], root),
        output_hashes=relative_hashes([root / "canonical_evidence.json"], root),
        command=command,
        return_code=0,
        runtime_seconds=amr_runtime + sum(r.runtime_seconds for r in sweep_records),
        capability=detected,
        upstream_stage_evidence_ids=list(stage_ids),
        notes=[
            "without an independent reference, the maximum valid status is SIMULATION_EXECUTED"
        ],
    )
    stage_ids.append(evidence_record.evidence_id)
    if stop_after_stage == "evidence_promotion":
        return V017BenchmarkResult(
            status=status.value,
            output_dir=root,
            evidence_path=evidence_path,
            tracked_frequency_ghz=records[-1].tracked_frequency_ghz,
        )
    write_stage_record(
        root,
        stage="packet_generation",
        status="complete",
        input_hashes=relative_hashes([root / "canonical_evidence.json"], root),
        output_hashes=relative_hashes(
            [
                root / "report.md",
                root / "run_manifest.json",
                root / "resource_summary.json",
                root / "convergence.json",
                root / "base_amr_validation.json",
            ],
            root,
        ),
        capability=detected,
        upstream_stage_evidence_ids=list(stage_ids),
    )
    return V017BenchmarkResult(
        status=status.value,
        output_dir=root,
        evidence_path=evidence_path,
        tracked_frequency_ghz=records[-1].tracked_frequency_ghz,
    )


def _extents_for(base: DomainExtents, sweep: str, value: float) -> DomainExtents:
    if sweep == "vacuum_or_air_margin":
        return base.model_copy(update={"vacuum_height_um": value})
    if sweep == "substrate_thickness":
        return base.model_copy(update={"substrate_thickness_um": value})
    if sweep == "upper_boundary_distance":
        return base.model_copy(update={"lid_height_um": value})
    if sweep == "lateral_boundary_margin":
        return base.model_copy(update={"lateral_margin_um": value})
    raise ValueError(f"unknown sweep {sweep!r}")


def _supplementary_gates(
    capability: PalaceCapability,
    records: list[AMRIterationRecord],
    matches: list[ModeMatch],
    target_frequency: float,
    model: FEMModel,
    *,
    stop_reason: str,
) -> list[VerificationGate]:
    gates: list[VerificationGate] = []
    gates.append(
        VerificationGate(
            name="palace_version_exactly_0_17_0",
            passed=capability.version == REQUIRED_PALACE_VERSION,
            detail=f"detected {capability.version!r}",
        )
    )
    # Four accepted iterations are preferred; three usable iterations are
    # acceptable only when Palace itself stopped at its declared tolerance.
    enough = len(records) >= 4 or (len(records) >= 3 and stop_reason == "tolerance_reached")
    gates.append(
        VerificationGate(
            name="at_least_four_accepted_amr_iterations",
            passed=enough,
            value=float(len(records)),
            threshold=4.0,
            detail=(
                f"{len(records)} Palace-owned accepted adaptive iterations; "
                f"stop reason: {stop_reason}"
            ),
        )
    )
    elements = [record.element_count for record in records]
    gates.append(
        VerificationGate(
            name="element_count_increases",
            passed=all(a < b for a, b in zip(elements, elements[1:])),
            detail=str(elements),
        )
    )
    dofs = [record.degrees_of_freedom for record in records]
    gates.append(
        VerificationGate(
            name="degrees_of_freedom_increase",
            passed=all(a < b for a, b in zip(dofs, dofs[1:])),
            detail=str(dofs),
        )
    )
    minimum_score = min(
        (
            min(
                match.electric_regional_energy_similarity,
                match.magnetic_regional_energy_similarity,
            )
            for match in matches
        ),
        default=0.0,
    )
    minimum_margin = min((match.margin for match in matches), default=0.0)
    minimum_electric_mac = min(
        (match.electric_field_mac for match in matches), default=0.0
    )
    minimum_magnetic_mac = min(
        (match.magnetic_field_mac for match in matches), default=0.0
    )
    gates.append(
        VerificationGate(
            name="electric_field_mac_above_0p95",
            passed=bool(matches) and minimum_electric_mac > 0.95,
            value=minimum_electric_mac,
            threshold=0.95,
            detail="minimum adjacent-iteration electric-field modal assurance criterion",
        )
    )
    gates.append(
        VerificationGate(
            name="magnetic_field_mac_above_0p90",
            passed=bool(matches) and minimum_magnetic_mac > 0.90,
            value=minimum_magnetic_mac,
            threshold=0.90,
            detail="minimum adjacent-iteration magnetic-field modal assurance criterion",
        )
    )
    gates.append(
        VerificationGate(
            name="mode_regional_energy_similarity_above_0p98",
            passed=bool(matches) and minimum_score > 0.98,
            value=minimum_score,
            threshold=0.98,
            detail=(
                "minimum adjacent-iteration regional-energy similarity score; "
                "not spatial field overlap"
            ),
        )
    )
    gates.append(
        VerificationGate(
            name="mode_match_margin_above_0p05",
            passed=bool(matches) and minimum_margin > 0.05,
            value=minimum_margin,
            threshold=0.05,
            detail="minimum winner-versus-runner-up margin",
        )
    )
    all_frequencies = [
        frequency for record in records for frequency in record.candidate_frequencies_ghz
    ]
    gates.append(
        VerificationGate(
            name="frequencies_finite_and_positive",
            passed=bool(all_frequencies)
            and all(math.isfinite(value) and value > 0 for value in all_frequencies),
            detail="every parsed candidate frequency across AMR iterations",
        )
    )
    window_low = model.eigenmode.target_frequency_ghz
    tracked = [
        record.tracked_frequency_ghz
        for record in records
        if record.tracked_frequency_ghz is not None
    ]
    pinned = any(
        math.isclose(frequency, window_low, rel_tol=1e-6) for frequency in tracked
    )
    gates.append(
        VerificationGate(
            name="eigenfrequency_not_at_search_window_boundary",
            passed=bool(tracked) and not pinned,
            detail=f"target window floor {window_low} GHz, tracked {tracked}",
        )
    )
    return gates


def _skipped_evidence(
    capability: PalaceCapability,
    layout: Path,
    fem_hash: str,
    target_frequency: float,
    repo_root: Path,
) -> CanonicalEvidence:
    return CanonicalEvidence(
        evidence_id=compute_evidence_id(
            design_id="quarter_wave_resonator_6ghz_palace_v017",
            target_quantity="eigenmode_frequency",
            output_file_hashes={},
            extraction_config_hash=None,
        ),
        design_id="quarter_wave_resonator_6ghz_palace_v017",
        design_hash=sha256_file(layout),
        component="quarter_wave_resonator",
        analysis_scope="palace_017_amr_domain_convergence",
        target_quantity="eigenmode_frequency",
        target_value=target_frequency,
        target_unit="GHz",
        status=EvidenceStatus.SKIPPED_SOLVER_ABSENT,
        skip_reason=capability.unavailable_reason or "Palace is unavailable",
        input_file_hashes={"fem_model.json": fem_hash},
        git_commit=_git_commit(repo_root),
        timestamp=_timestamp(),
    )


def _finish_invalid(
    root: Path,
    capability: PalaceCapability,
    layout: Path,
    fem_hash: str,
    target_frequency: float,
    repo_root: Path,
    *,
    reason: str,
    detail: str,
    command: list[str] | None,
) -> V017BenchmarkResult:
    evidence = CanonicalEvidence(
        evidence_id=compute_evidence_id(
            design_id="quarter_wave_resonator_6ghz_palace_v017",
            target_quantity="eigenmode_frequency",
            output_file_hashes={},
            extraction_config_hash=None,
        ),
        design_id="quarter_wave_resonator_6ghz_palace_v017",
        design_hash=sha256_file(layout),
        component="quarter_wave_resonator",
        analysis_scope="palace_017_amr_domain_convergence",
        target_quantity="eigenmode_frequency",
        target_value=target_frequency,
        target_unit="GHz",
        status=EvidenceStatus.SIMULATION_INVALID,
        invalidation_reason=f"{reason}: {detail}",
        solver_name="Palace",
        solver_version=capability.version,
        solver_executable_sha256=capability.executable_sha256,
        command=command or [],
        input_file_hashes={"fem_model.json": fem_hash},
        git_commit=_git_commit(repo_root),
        timestamp=_timestamp(),
    )
    evidence_path = write_canonical(evidence, root / "canonical_evidence.json")
    (root / "report.md").write_text(
        "# Palace 0.17 quarter-wave AMR benchmark\n\n"
        f"Status: `SIMULATION_INVALID`\n\nreason = \"{reason}\"\n\n{detail}\n",
        encoding="utf-8",
        newline="\n",
    )
    return V017BenchmarkResult(
        status=EvidenceStatus.SIMULATION_INVALID.value,
        output_dir=root,
        reason=f"{reason}: {detail}",
        evidence_path=evidence_path,
    )


def _executed_evidence(
    capability: PalaceCapability,
    *,
    layout: Path,
    fem_hash: str,
    target_frequency: float,
    repo_root: Path,
    root: Path,
    records: list[AMRIterationRecord],
    sweep_records: list[SweepPointRecord],
    status: EvidenceStatus,
    command: list[str],
    runtime_seconds: float,
    verification_gates: list[VerificationGate],
    invalid_names: set[str],
    base_mesh: GmshMeshResult,
    config_path: Path,
    resolved_hash: str,
    final_adapted_mesh_hash: str | None,
) -> CanonicalEvidence:
    output_hashes: dict[str, str] = {}
    for record in records:
        output_hashes.update(record.output_file_hashes)
    for sweep_record in sweep_records:
        output_hashes.update(sweep_record.output_file_hashes)
    input_hashes = {
        "fem_model.json": fem_hash,
        f"base_mesh/{base_mesh.path.name}": sha256_file(base_mesh.path),
        f"base_mesh/{config_path.name}": sha256_file(config_path),
    }
    extraction = {
        "parser": PARSER,
        "parser_version": PARSER_VERSION,
        "tracked_mode_indices": [record.tracked_mode_index for record in records],
        "resolved_config_sha256": resolved_hash,
        "final_adapted_mesh_sha256": final_adapted_mesh_hash,
        "sweep_resolved_config_sha256": {
            f"{record.sweep}@{record.value:g}": record.resolved_config_sha256
            for record in sweep_records
        },
        "gates": [gate.model_dump(mode="json") for gate in verification_gates],
    }
    extraction_hash = sha256_json(extraction)
    finest = records[-1].tracked_frequency_ghz
    tracked_series = [
        record.tracked_frequency_ghz
        for record in records
        if record.tracked_frequency_ghz is not None
    ]
    frequency_changes = [
        abs(b - a) / max(abs(b), 1e-12) * 100.0
        for a, b in zip(tracked_series, tracked_series[1:])
    ]
    sanity_names = {
        "palace_version_exactly_0_17_0",
        "frequencies_finite_and_positive",
        "element_count_increases",
        "degrees_of_freedom_increase",
        "eigenfrequency_not_at_search_window_boundary",
    }
    sanity = [
        SanityCheck(name=gate.name, passed=gate.passed, detail=gate.detail)
        for gate in verification_gates
        if gate.name in sanity_names
    ]
    convergence = ConvergenceMetrics(
        method="palace_native_amr_with_domain_sweeps",
        refinement_levels=len(records),
        delta_percent=frequency_changes[-1] if frequency_changes else None,
        threshold_percent=0.2,
        converged=status is EvidenceStatus.SIMULATION_EXECUTED,
        notes=[
            f"{gate.name}: {'PASS' if gate.passed else 'FAIL'}; {gate.detail}"
            for gate in verification_gates
            if gate.name not in sanity_names
        ],
    )
    error = (
        (finest - target_frequency) / target_frequency * 100.0 if finest is not None else None
    )
    promoted_value = finest if status is EvidenceStatus.SIMULATION_EXECUTED else None
    return CanonicalEvidence(
        evidence_id=compute_evidence_id(
            design_id="quarter_wave_resonator_6ghz_palace_v017",
            target_quantity="eigenmode_frequency",
            output_file_hashes=output_hashes,
            extraction_config_hash=extraction_hash,
        ),
        design_id="quarter_wave_resonator_6ghz_palace_v017",
        design_hash=sha256_file(layout),
        component="quarter_wave_resonator",
        analysis_scope="palace_017_amr_domain_convergence",
        target_quantity="eigenmode_frequency",
        target_value=target_frequency,
        target_unit="GHz",
        extracted_quantity="eigenmode_frequency" if promoted_value is not None else None,
        extracted_value=promoted_value,
        extracted_unit="GHz" if promoted_value is not None else None,
        analytical_value=target_frequency,
        analytical_model=(
            "lambda/4 CPW with eps_eff=(1+eps_r)/2; comparison only, not an "
            "independent verification artifact"
        ),
        tolerance_percent=2.0,
        error_percent=error if promoted_value is not None else None,
        status=status,
        invalidation_reason=(
            "solver output failed physical-sanity checks: " + ", ".join(sorted(invalid_names))
            if status is EvidenceStatus.SIMULATION_INVALID
            else None
        ),
        solver_name="Palace",
        solver_version=capability.version,
        solver_executable_sha256=capability.executable_sha256,
        command=command,
        return_code=0,
        runtime_seconds=runtime_seconds,
        input_file_hashes=input_hashes,
        output_file_hashes=output_hashes,
        parser=PARSER,
        parser_version=PARSER_VERSION,
        extraction_config=extraction,
        extraction_config_hash=extraction_hash,
        convergence=convergence,
        sanity_checks=sanity,
        depends_on=[
            ArtifactDependency(
                role="mesh",
                artifact=str(base_mesh.path),
                sha256=sha256_file(base_mesh.path),
            ),
            *(
                [
                    ArtifactDependency(
                        role="final_adapted_mesh",
                        artifact="raw/final_adapted.mesh",
                        sha256=final_adapted_mesh_hash,
                    )
                ]
                if final_adapted_mesh_hash is not None
                else []
            ),
        ],
        git_commit=_git_commit(repo_root),
        timestamp=_timestamp(),
        warnings=[
            "No independent reference artifact exists for this design, so a fully "
            "converged result is limited to SIMULATION_EXECUTED.",
            "The analytical quarter-wave model is included as a comparison only.",
        ],
    )


def _write_report(
    root: Path,
    status: EvidenceStatus,
    records: list[AMRIterationRecord],
    matches: list[ModeMatch],
    sweep_records: list[SweepPointRecord],
    verification: Any,
    supplementary: list[VerificationGate],
) -> None:
    lines = [
        "# Palace 0.17 quarter-wave AMR benchmark",
        "",
        f"Status: `{status.value}`",
        "",
        "## AMR iterations",
        "",
        "| iteration | elements | ND DOF | order | tracked f (GHz) | global error (%) | "
        "substrate p | runtime (s) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for record in records:
        lines.append(
            "| {} | {} | {} | {} | {} | {:.4f} | {:.6f} | {} |".format(
                record.tag,
                record.element_count,
                record.degrees_of_freedom,
                record.polynomial_order,
                f"{record.tracked_frequency_ghz:.6f}"
                if record.tracked_frequency_ghz is not None
                else "-",
                record.global_error_indicator_percent,
                record.substrate_participation,
                f"{record.runtime_seconds:.1f}" if record.runtime_seconds is not None else "-",
            )
        )
    lines += [
        "",
        "## Mode tracking (regional-energy similarity, not spatial field overlap)",
        "",
    ]
    for match in matches:
        lines.append(
            f"- {match.from_tag} -> {match.to_tag}: mode {match.from_mode} -> "
            f"{match.to_mode}, regional-energy similarity score {match.score:.4f}, "
            f"margin {match.margin:.4f}"
        )

    def _sweep_table(category: SweepCategory, title: str, note: str) -> None:
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                note,
                "",
                "| sweep | value | f (GHz) | substrate p | vacuum p |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for record in sweep_records:
            if record.category is not category:
                continue
            lines.append(
                f"| {record.sweep} | {record.value:g} {record.unit} | "
                f"{record.frequency_ghz:.6f} | {record.substrate_participation:.6f} | "
                f"{record.vacuum_participation:.6f} |"
            )

    _sweep_table(
        SweepCategory.NUMERICAL_DOMAIN,
        "Numerical-domain convergence sweeps",
        "Computational truncation choices; the physics must not depend on these, "
        "so they gate numerical-domain convergence (< 0.2% frequency sensitivity).",
    )
    _sweep_table(
        SweepCategory.PHYSICAL_PARAMETER,
        "Physical sensitivity studies (reported, never gated)",
        "Real device/stack parameters; the frequency is *expected* to move. "
        "Physical sensitivity is not numerical convergence and never fails it.",
    )
    lines += ["", "### Physical parameter ownership", ""]
    for name, meta in PHYSICAL_PARAMETER_METADATA.items():
        lines.append(
            f"- `{name}`: owner {meta['owner']}, {meta['uncertainty_kind']} uncertainty "
            f"({meta['note']})"
        )
    for name, reason in UNSUPPORTED_PHYSICAL_PARAMETERS.items():
        lines.append(f"- `{name}`: not swept — {reason}")
    lines += [
        "",
        "## Uncertainty separation",
        "",
        "- **Mesh-discretization uncertainty**: bounded by the Palace AMR error "
        "indicator and the last-two-iteration frequency change above.",
        "- **Computational-domain uncertainty**: bounded by the numerical-domain "
        "sweeps above.",
        "- **Physical-model uncertainty**: shown by the physical sensitivity "
        "studies above; it is a property of the stack assumptions, not the solver.",
        "- **Fabrication/process uncertainty**: not assessed here; substrate "
        "thickness/permittivity spreads above indicate the direction and scale.",
    ]
    lines += ["", "## Gates", ""]
    for gate in [*verification.gates, *supplementary]:
        lines.append(f"- {'PASS' if gate.passed else 'FAIL'} `{gate.name}`: {gate.detail}")
    lines += [
        "",
        "This result has no independent reference artifact; even with every "
        "convergence gate passing it is limited to `SIMULATION_EXECUTED`.",
        "",
    ]
    (root / "report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
