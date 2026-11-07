"""Headless AWS Palace eigenmode backend driven from a Gmsh mesh manifest.

Pipeline::

    Geometry + SubstrateStack --mesh_geometry--> MeshManifest
        --build_eigenmode_config--> palace.json
        --run_palace (if available)--> postpro/eig.csv, iteration*/eig.csv
        --parse + validate_amr_convergence--> PalaceEigenmodeResult

Status mapping (never fabricated):

* Gmsh absent -> ``SKIPPED_SOLVER_ABSENT`` (``.geo`` prepared only)
* mesh built, Palace absent -> ``SKIPPED_SOLVER_ABSENT`` with ``palace.json`` prepared
* ``execute=False`` -> ``SIMULATION_INPUT_PREPARED``
* Palace ran, non-zero exit or unparsable output -> ``FAILED``
* Palace ran, AMR did not meet the convergence gates -> ``CONVERGENCE_FAILED``
* Palace ran, gates met -> ``SIMULATION_EXECUTED`` with
  ``audit_level == "NUMERICALLY_CONVERGED"``

``PHYSICS_VERIFIED`` is deliberately out of scope here: it requires the
target comparison performed by :mod:`textlayout.evidence`.
"""

from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.contract import EvidenceStatus
from textlayout.mesh.gmsh_pipeline import (
    ENCLOSURE_ATTRIBUTE,
    METAL_ATTRIBUTE,
    SUBSTRATE_ATTRIBUTE,
    VACUUM_ATTRIBUTE,
    MeshControls,
    MeshManifest,
    SubstrateStack,
    mesh_geometry,
    write_manifest,
)
from textlayout.models import Geometry
from textlayout.solvers.palace.models import Eigenmode, PalaceCapability, PalaceOutputError

PALACE_EIGENMODE_SCHEMA = "textlayout.palace-eigenmode.v1"

AuditLevel = Literal["INPUT_PREPARED", "OUTPUT_PARSED", "NUMERICALLY_CONVERGED"]

PalaceExecutionState = Literal[
    "PENDING",
    "RUNNING_BASE",
    "RUNNING_AMR",
    "CONVERGED",
    "INTERRUPTED",
]


class PalaceManifest(BaseModel):
    """Atomic state-machine checkpoint manifest for Palace simulations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str = "textlayout.palace-manifest.v1"
    state: PalaceExecutionState
    stage: str
    completed_stages: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def write_manifest_atomic(manifest: PalaceManifest, path: Path) -> Path:
    """Atomically write the checkpoint manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def read_manifest(path: Path) -> PalaceManifest | None:
    """Read existing manifest if available and valid."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return PalaceManifest.model_validate(data)
    except Exception:
        return None


class AMRPolicy(BaseModel):
    """Bounded adaptive-mesh-refinement schedule and convergence gates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_iterations: int = Field(default=2, ge=0, description="Palace Refinement.MaxIts")
    indicator_tolerance_percent: float = Field(
        default=2.0, gt=0, description="Max final global error-indicator norm (percent)."
    )
    frequency_drift_tolerance_percent: float = Field(
        default=0.5, gt=0, description="Max |f_last - f_prev| / f_last (percent) per tracked mode."
    )
    max_dofs: int | None = Field(default=None, gt=0)
    save_iterations: bool = True

    def refinement_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "MaxIts": self.max_iterations,
            "Tol": self.indicator_tolerance_percent / 100.0,
            "SaveAdaptIterations": self.save_iterations,
        }
        if self.max_dofs is not None:
            config["MaxSize"] = self.max_dofs
        return config


class PalaceEigenmodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode_count: int = Field(default=2, ge=1, le=64)
    target_frequency_ghz: float = Field(default=4.0, gt=0)
    eigen_tolerance: float = Field(default=1e-8, gt=0)
    element_order: int = Field(default=1, ge=1, le=3)
    linear_tolerance: float = Field(default=1e-8, gt=0)
    linear_max_iterations: int = Field(default=400, ge=1)
    amr: AMRPolicy = Field(default_factory=AMRPolicy)
    processes: int = Field(default=1, ge=1)
    timeout_seconds: float = Field(default=1800.0, gt=0)
    paraview: bool = False


class AMRIteration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    output_dir: Path
    modes: list[Eigenmode]
    global_error_indicator_percent: float | None = None
    domain_energies: dict[int, dict[str, float]] = Field(default_factory=dict)


class AMRConvergence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    converged: bool
    iterations: list[AMRIteration]
    final_error_indicator_percent: float | None = None
    max_frequency_drift_percent: float | None = None
    indicator_tolerance_percent: float
    frequency_drift_tolerance_percent: float
    reason: str
    tracked_mode_indices: list[int] = Field(default_factory=list)
    tracked_mode_frequencies_ghz: list[float] = Field(default_factory=list)
    modal_overlap_scores: list[float] = Field(default_factory=list)
    tracked_frequency_drift_percent: float | None = None


class PalaceEigenmodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str = Field(default=PALACE_EIGENMODE_SCHEMA, alias="schema")
    status: EvidenceStatus
    audit_level: AuditLevel
    reason: str | None = None
    output_dir: Path
    mesh_manifest_path: Path | None = None
    config_path: Path | None = None
    eig_path: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    command: list[str] = Field(default_factory=list)
    return_code: int | None = None
    solver_runtime_seconds: float | None = None
    capability: PalaceCapability | None = None
    modes: list[Eigenmode] = Field(default_factory=list)
    amr: AMRConvergence | None = None

    @property
    def executed(self) -> bool:
        return self.status in {
            EvidenceStatus.SIMULATION_EXECUTED,
            EvidenceStatus.CONVERGENCE_FAILED,
        }


def build_eigenmode_config(
    manifest: MeshManifest, request: PalaceEigenmodeRequest, *, output_subdir: str = "postpro"
) -> dict[str, Any]:
    """Palace JSON for an eigenmode solve on a :func:`mesh_geometry` mesh."""
    if manifest.mesh_path is None:
        raise ValueError("mesh manifest carries no mesh_path; cannot build a Palace config")
    stack = manifest.stack
    attrs = manifest.attributes
    materials: list[dict[str, Any]] = [
        {
            "Attributes": [attrs.get("substrate", SUBSTRATE_ATTRIBUTE)],
            "Permittivity": stack.epsilon_r,
        },
        {"Attributes": [attrs.get("vacuum", VACUUM_ATTRIBUTE)], "Permittivity": 1.0},
    ]
    if stack.loss_tangent > 0:
        materials[0]["LossTan"] = stack.loss_tangent
    config: dict[str, Any] = {
        "Problem": {
            "Type": "Eigenmode",
            "Verbose": 2,
            "Output": output_subdir,
            "OutputFormats": {"GridFunction": False, "Paraview": request.paraview},
        },
        "Model": {
            "Mesh": manifest.mesh_path.name,
            "L0": manifest.length_unit_m,
            "Refinement": request.amr.refinement_config(),
        },
        "Domains": {
            "Materials": materials,
            "Postprocessing": {
                "Energy": [
                    {"Index": 1, "Attributes": [attrs.get("substrate", SUBSTRATE_ATTRIBUTE)]},
                    {"Index": 2, "Attributes": [attrs.get("vacuum", VACUUM_ATTRIBUTE)]},
                ]
            },
        },
        "Boundaries": {
            "PEC": {
                "Attributes": sorted(
                    {
                        attrs.get("metal", METAL_ATTRIBUTE),
                        attrs.get("enclosure", ENCLOSURE_ATTRIBUTE),
                    }
                )
            }
        },
        "Solver": {
            "Order": request.element_order,
            "Device": "CPU",
            "Eigenmode": {
                "N": request.mode_count,
                "Tol": request.eigen_tolerance,
                "Target": request.target_frequency_ghz,
                "Save": request.mode_count if request.paraview else 0,
            },
            "Linear": {
                "Type": "Default",
                "KSPType": "GMRES",
                "Tol": request.linear_tolerance,
                "MaxIts": request.linear_max_iterations,
            },
        },
    }
    return config


def write_config(config: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


_ITERATION_DIR = re.compile(r"^iteration_?(\d+)$", re.IGNORECASE)


def _parse_iteration_domain_energies(output_dir: Path) -> dict[int, dict[str, float]]:
    domain_csv = output_dir / "domain-E.csv"
    if not domain_csv.is_file():
        return {}
    try:
        with domain_csv.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle, skipinitialspace=True))
        results: dict[int, dict[str, float]] = {}
        for row in rows:
            m_idx = int(float(row.get("m", 0)))
            results[m_idx] = {k: float(v) for k, v in row.items() if k != "m" and v}
        return results
    except Exception:
        return {}


def collect_amr_iterations(postpro_dir: Path) -> list[AMRIteration]:
    """Parse ``postpro/iteration*/eig.csv`` (in order) followed by the final ``postpro/eig.csv``."""
    from textlayout.solvers.palace.parser import parse_eigenmodes, parse_global_error_indicator

    iterations: list[AMRIteration] = []
    candidates: list[tuple[int, Path]] = []
    if postpro_dir.is_dir():
        for child in postpro_dir.iterdir():
            match = _ITERATION_DIR.match(child.name)
            if match and child.is_dir():
                candidates.append((int(match.group(1)), child))
    for index, directory in sorted(candidates):
        eig = directory / "eig.csv"
        if not eig.is_file():
            continue
        indicator = directory / "error-indicators.csv"
        iterations.append(
            AMRIteration(
                index=index,
                output_dir=directory,
                modes=parse_eigenmodes(eig),
                global_error_indicator_percent=(
                    parse_global_error_indicator(indicator) if indicator.is_file() else None
                ),
                domain_energies=_parse_iteration_domain_energies(directory),
            )
        )
    final_eig = postpro_dir / "eig.csv"
    if final_eig.is_file():
        final_indicator = postpro_dir / "error-indicators.csv"
        iterations.append(
            AMRIteration(
                index=(iterations[-1].index + 1) if iterations else 0,
                output_dir=postpro_dir,
                modes=parse_eigenmodes(final_eig),
                global_error_indicator_percent=(
                    parse_global_error_indicator(final_indicator)
                    if final_indicator.is_file()
                    else None
                ),
                domain_energies=_parse_iteration_domain_energies(postpro_dir),
            )
        )
    return iterations


def compute_modal_overlap(
    prev_iter: AMRIteration,
    curr_iter: AMRIteration,
    prev_mode: Eigenmode,
    curr_mode: Eigenmode,
) -> float:
    """Compute modal overlap heuristic using field dot products or domain energy vectors."""
    from textlayout.solvers.palace.parser import _field_file, field_overlap

    prev_field = _field_file(prev_iter.output_dir, prev_mode.index)
    curr_field = _field_file(curr_iter.output_dir, curr_mode.index)
    if prev_field is not None and curr_field is not None:
        try:
            return float(field_overlap(prev_field, curr_field, kind="electric"))
        except Exception:
            pass

    prev_vec = prev_iter.domain_energies.get(prev_mode.index)
    curr_vec = curr_iter.domain_energies.get(curr_mode.index)
    if prev_vec and curr_vec:
        common_keys = sorted(set(prev_vec.keys()) & set(curr_vec.keys()))
        if common_keys:
            v1 = [prev_vec[k] for k in common_keys]
            v2 = [curr_vec[k] for k in common_keys]
            dot = sum(a * b for a, b in zip(v1, v2, strict=False))
            norm1 = math.sqrt(sum(a * a for a in v1))
            norm2 = math.sqrt(sum(b * b for b in v2))
            if norm1 > 0 and norm2 > 0:
                return max(0.0, min(1.0, dot / (norm1 * norm2)))

    df = abs(curr_mode.frequency_ghz - prev_mode.frequency_ghz)
    ref_f = max(prev_mode.frequency_ghz, 1e-6)
    return max(0.0, 1.0 - (df / (ref_f * 0.2)))


def validate_amr_convergence(
    iterations: list[AMRIteration],
    policy: AMRPolicy,
    target_frequency_ghz: float = 4.0,
) -> AMRConvergence:
    """Apply the AMR gates with modal overlap tracking across refinement tiers."""
    base: dict[str, Any] = {
        "iterations": iterations,
        "indicator_tolerance_percent": policy.indicator_tolerance_percent,
        "frequency_drift_tolerance_percent": policy.frequency_drift_tolerance_percent,
    }
    if not iterations:
        return AMRConvergence(converged=False, reason="no eigenmode output parsed", **base)
    final = iterations[-1]
    indicator = final.global_error_indicator_percent
    if len(iterations) < 2:
        return AMRConvergence(
            converged=False,
            final_error_indicator_percent=indicator,
            reason="single solved state; refinement convergence cannot be demonstrated",
            **base,
        )

    # Track target physical mode across successive mesh density tiers
    tracked_indices: list[int] = []
    tracked_frequencies: list[float] = []
    overlap_scores: list[float] = []

    first_iter = iterations[0]
    if not first_iter.modes:
        return AMRConvergence(converged=False, reason="no modes in initial iteration", **base)
    first_mode = min(
        first_iter.modes,
        key=lambda m: abs(m.frequency_ghz - target_frequency_ghz),
    )
    tracked_indices.append(first_mode.index)
    tracked_frequencies.append(first_mode.frequency_ghz)

    for k in range(1, len(iterations)):
        prev_it = iterations[k - 1]
        curr_it = iterations[k]
        prev_mode_idx = tracked_indices[-1]
        prev_m = next((m for m in prev_it.modes if m.index == prev_mode_idx), prev_it.modes[0])

        candidates = []
        for cand in curr_it.modes:
            overlap = compute_modal_overlap(prev_it, curr_it, prev_m, cand)
            freq_score = max(
                0.0,
                1.0
                - abs(cand.frequency_ghz - prev_m.frequency_ghz)
                / (max(prev_m.frequency_ghz, 1e-6) * 0.2),
            )
            composite_score = 0.7 * overlap + 0.3 * freq_score
            candidates.append((composite_score, overlap, cand))

        candidates.sort(key=lambda c: (-c[0], c[2].index))
        best_score, best_overlap, best_mode = candidates[0]
        tracked_indices.append(best_mode.index)
        tracked_frequencies.append(best_mode.frequency_ghz)
        overlap_scores.append(best_overlap)

    # Tracked frequency drift
    prev_freq = tracked_frequencies[-2]
    final_freq = tracked_frequencies[-1]
    tracked_drift = (
        abs(final_freq - prev_freq) / final_freq * 100.0 if final_freq > 0 else 0.0
    )

    all_drifts: list[float] = []
    for last_mode, prev_mode in zip(final.modes, iterations[-2].modes, strict=False):
        if last_mode.frequency_ghz > 0:
            all_drifts.append(
                abs(last_mode.frequency_ghz - prev_mode.frequency_ghz)
                / last_mode.frequency_ghz
                * 100.0
            )
    max_drift = max(all_drifts) if all_drifts else tracked_drift

    failures: list[str] = []
    if indicator is None:
        failures.append("final global error indicator missing")
    elif indicator > policy.indicator_tolerance_percent:
        failures.append(f"error indicator {indicator:.3f}% > {policy.indicator_tolerance_percent}%")

    if tracked_drift > policy.frequency_drift_tolerance_percent:
        failures.append(
            f"frequency drift {tracked_drift:.4f}% > {policy.frequency_drift_tolerance_percent}%"
        )

    return AMRConvergence(
        converged=not failures,
        final_error_indicator_percent=indicator,
        max_frequency_drift_percent=max_drift,
        tracked_mode_indices=tracked_indices,
        tracked_mode_frequencies_ghz=tracked_frequencies,
        modal_overlap_scores=overlap_scores,
        tracked_frequency_drift_percent=tracked_drift,
        reason="; ".join(failures) if failures else "indicator and frequency-drift gates passed",
        **base,
    )


def write_result(result: PalaceEigenmodeResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.model_dump(mode="json", by_alias=True), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def run_eigenmode(
    geometry: Geometry,
    stack: SubstrateStack,
    output_dir: str | Path,
    *,
    request: PalaceEigenmodeRequest | None = None,
    controls: MeshControls | None = None,
    capability: PalaceCapability | None = None,
    execute: bool = True,
) -> PalaceEigenmodeResult:
    """Mesh, configure, (optionally) run and parse one Palace eigenmode problem.

    Missing Gmsh or Palace never raises; it yields ``SKIPPED_SOLVER_ABSENT``.
    Uses an atomic checkpoint manifest to guarantee reproducible continuation.
    """
    request = request or PalaceEigenmodeRequest()
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest_file = out / "manifest.json"

    # Priority 2: Check for completed runs -- never re-execute completed runs!
    prior_manifest = read_manifest(manifest_file)
    if prior_manifest is not None and prior_manifest.state == "CONVERGED":
        eigen_res_file = out / "palace_eigenmode.json"
        if eigen_res_file.is_file():
            try:
                return PalaceEigenmodeResult.model_validate_json(
                    eigen_res_file.read_text(encoding="utf-8")
                )
            except Exception:
                pass

    # Checkpoint continuation: check if base_mesh is already complete
    base_mesh_reused = False
    manifest_path: Path | None = None
    manifest: MeshManifest | None = None

    if (
        prior_manifest is not None
        and "base_mesh" in prior_manifest.completed_stages
        and (out / "model.msh").is_file()
        and (out / "mesh_manifest.json").is_file()
    ):
        try:
            manifest_data = json.loads((out / "mesh_manifest.json").read_text(encoding="utf-8"))
            manifest = MeshManifest.model_validate(manifest_data)
            manifest_path = out / "mesh_manifest.json"
            base_mesh_reused = True
        except Exception:
            manifest = None

    if not base_mesh_reused or manifest is None:
        write_manifest_atomic(
            PalaceManifest(state="PENDING", stage="pending"),
            manifest_file,
        )
        write_manifest_atomic(
            PalaceManifest(state="RUNNING_BASE", stage="base_mesh"),
            manifest_file,
        )
        manifest = mesh_geometry(geometry, stack, out / "model.msh", controls=controls)
        manifest_path = write_manifest(manifest, out / "mesh_manifest.json")
        if not manifest.mesh_available:
            status = (
                EvidenceStatus.SKIPPED_SOLVER_ABSENT
                if manifest.status == "SKIPPED_SOLVER_ABSENT"
                else EvidenceStatus.FAILED
            )
            write_manifest_atomic(
                PalaceManifest(
                    state="INTERRUPTED",
                    stage="base_mesh",
                    error=manifest.reason,
                    artifacts={"mesh_manifest": str(manifest_path)},
                ),
                manifest_file,
            )
            result = PalaceEigenmodeResult(
                status=status,
                audit_level="INPUT_PREPARED",
                reason=manifest.reason,
                output_dir=out,
                mesh_manifest_path=manifest_path,
            )
            write_result(result, out / "palace_eigenmode.json")
            return result

    artifacts: dict[str, str] = {
        "mesh": str(out / "model.msh"),
        "mesh_manifest": str(manifest_path),
    }
    write_manifest_atomic(
        PalaceManifest(
            state="RUNNING_AMR",
            stage="base_amr",
            completed_stages=["base_mesh"],
            artifacts=artifacts,
        ),
        manifest_file,
    )

    config_path = write_config(build_eigenmode_config(manifest, request), out / "palace.json")
    artifacts["config"] = str(config_path)

    if capability is None:
        from textlayout.solvers.palace.capability import detect_palace

        capability = detect_palace()

    if not capability.available:
        write_manifest_atomic(
            PalaceManifest(
                state="INTERRUPTED",
                stage="base_amr",
                completed_stages=["base_mesh"],
                artifacts=artifacts,
                error=capability.unavailable_reason or "Palace not found",
            ),
            manifest_file,
        )
        result = PalaceEigenmodeResult(
            status=EvidenceStatus.SKIPPED_SOLVER_ABSENT,
            audit_level="INPUT_PREPARED",
            reason=capability.unavailable_reason or "Palace not found",
            output_dir=out,
            mesh_manifest_path=manifest_path,
            config_path=config_path,
            capability=capability,
        )
        write_result(result, out / "palace_eigenmode.json")
        return result

    if not execute:
        write_manifest_atomic(
            PalaceManifest(
                state="PENDING",
                stage="base_amr",
                completed_stages=["base_mesh"],
                artifacts=artifacts,
                error="execute=False",
            ),
            manifest_file,
        )
        result = PalaceEigenmodeResult(
            status=EvidenceStatus.SIMULATION_INPUT_PREPARED,
            audit_level="INPUT_PREPARED",
            reason="execute=False; Palace input prepared but not run",
            output_dir=out,
            mesh_manifest_path=manifest_path,
            config_path=config_path,
            capability=capability,
        )
        write_result(result, out / "palace_eigenmode.json")
        return result

    from textlayout.solvers.palace.runner import run_palace

    try:
        run = run_palace(
            capability,
            config_path,
            cwd=out,
            processes=request.processes,
            timeout_seconds=request.timeout_seconds,
            input_paths=[config_path, manifest.mesh_path] if manifest.mesh_path else [config_path],
        )
    except Exception as exc:
        write_manifest_atomic(
            PalaceManifest(
                state="INTERRUPTED",
                stage="base_amr",
                completed_stages=["base_mesh"],
                artifacts=artifacts,
                error=f"Palace execution raised: {exc}",
            ),
            manifest_file,
        )
        result = PalaceEigenmodeResult(
            status=EvidenceStatus.FAILED,
            audit_level="INPUT_PREPARED",
            reason=f"Palace execution raised: {exc}",
            output_dir=out,
            mesh_manifest_path=manifest_path,
            config_path=config_path,
            capability=capability,
        )
        write_result(result, out / "palace_eigenmode.json")
        return result

    common: dict[str, Any] = {
        "output_dir": out,
        "mesh_manifest_path": manifest_path,
        "config_path": config_path,
        "stdout_path": run.stdout_path,
        "stderr_path": run.stderr_path,
        "command": run.command,
        "return_code": run.return_code,
        "solver_runtime_seconds": run.runtime_seconds,
        "capability": capability,
    }
    if run.stdout_path:
        artifacts["stdout"] = str(run.stdout_path)
    if run.stderr_path:
        artifacts["stderr"] = str(run.stderr_path)

    postpro = out / "postpro"
    if not run.succeeded:
        write_manifest_atomic(
            PalaceManifest(
                state="INTERRUPTED",
                stage="base_amr",
                completed_stages=["base_mesh"],
                artifacts=artifacts,
                error=run.termination_reason or f"Palace exited with {run.return_code}",
            ),
            manifest_file,
        )
        result = PalaceEigenmodeResult(
            status=EvidenceStatus.FAILED,
            audit_level="INPUT_PREPARED",
            reason=run.termination_reason or f"Palace exited with {run.return_code}",
            **common,
        )
        write_result(result, out / "palace_eigenmode.json")
        return result

    try:
        iterations = collect_amr_iterations(postpro)
    except PalaceOutputError as exc:
        write_manifest_atomic(
            PalaceManifest(
                state="INTERRUPTED",
                stage="base_amr",
                completed_stages=["base_mesh"],
                artifacts=artifacts,
                error=str(exc),
            ),
            manifest_file,
        )
        result = PalaceEigenmodeResult(
            status=EvidenceStatus.FAILED, audit_level="INPUT_PREPARED", reason=str(exc), **common
        )
        write_result(result, out / "palace_eigenmode.json")
        return result

    if not iterations:
        write_manifest_atomic(
            PalaceManifest(
                state="INTERRUPTED",
                stage="base_amr",
                completed_stages=["base_mesh"],
                artifacts=artifacts,
                error=f"Palace exited 0 but wrote no eig.csv under {postpro}",
            ),
            manifest_file,
        )
        result = PalaceEigenmodeResult(
            status=EvidenceStatus.FAILED,
            audit_level="INPUT_PREPARED",
            reason=f"Palace exited 0 but wrote no eig.csv under {postpro}",
            **common,
        )
        write_result(result, out / "palace_eigenmode.json")
        return result

    convergence = validate_amr_convergence(
        iterations, request.amr, target_frequency_ghz=request.target_frequency_ghz
    )
    final = iterations[-1]

    if convergence.converged:
        write_manifest_atomic(
            PalaceManifest(
                state="CONVERGED",
                stage="completed",
                completed_stages=["base_mesh", "base_amr"],
                artifacts=artifacts,
            ),
            manifest_file,
        )
    else:
        write_manifest_atomic(
            PalaceManifest(
                state="INTERRUPTED",
                stage="base_amr",
                completed_stages=["base_mesh"],
                artifacts=artifacts,
                error=convergence.reason,
            ),
            manifest_file,
        )

    result = PalaceEigenmodeResult(
        status=(
            EvidenceStatus.SIMULATION_EXECUTED
            if convergence.converged
            else EvidenceStatus.CONVERGENCE_FAILED
        ),
        audit_level="NUMERICALLY_CONVERGED" if convergence.converged else "OUTPUT_PARSED",
        reason=convergence.reason,
        eig_path=final.output_dir / "eig.csv",
        modes=final.modes,
        amr=convergence,
        **common,
    )
    write_result(result, out / "palace_eigenmode.json")
    return result


__all__ = [
    "PALACE_EIGENMODE_SCHEMA",
    "AMRConvergence",
    "AMRIteration",
    "AMRPolicy",
    "PalaceEigenmodeRequest",
    "PalaceEigenmodeResult",
    "PalaceExecutionState",
    "PalaceManifest",
    "build_eigenmode_config",
    "collect_amr_iterations",
    "compute_modal_overlap",
    "read_manifest",
    "run_eigenmode",
    "validate_amr_convergence",
    "write_config",
    "write_manifest_atomic",
    "write_result",
]
