"""Mode identity, convergence gates, and existing CanonicalEvidence generation."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from textlayout.evidence.canonical import (
    ArtifactDependency,
    CanonicalEvidence,
    ConvergenceMetrics,
    SanityCheck,
    SupersededClaim,
    compute_evidence_id,
    sha256_file,
    sha256_json,
)
from textlayout.evidence.contract import EvidenceStatus
from textlayout.solvers.palace.models import (
    ConvergenceGate,
    ConvergenceReport,
    DomainSweepPoint,
    MeshLevelResult,
    ModeFieldData,
    ModeMatchResult,
    PalaceCapability,
    PalaceOutputError,
)
from textlayout.solvers.palace.parser import field_overlap

PARSER = "textlayout.solvers.palace.parser.parse_eigenmodes"
PARSER_VERSION = "1"


def _mode_field(level: MeshLevelResult, index: int) -> ModeFieldData:
    match = next((item for item in level.mode_fields if item.mode_index == index), None)
    if match is None:
        raise PalaceOutputError(f"level {level.tag}: no field record for mode {index}")
    return match


def _has_retained_field(level: MeshLevelResult, index: int) -> bool:
    return any(
        field.mode_index == index and field.field_file is not None
        for field in level.mode_fields
    )


def _pair_score(
    left_level: MeshLevelResult,
    left_index: int,
    right_level: MeshLevelResult,
    right_index: int,
    *,
    overlap: Callable[..., float],
) -> ModeMatchResult:
    left_mode = next(mode for mode in left_level.modes if mode.index == left_index)
    right_mode = next(mode for mode in right_level.modes if mode.index == right_index)
    left_field = _mode_field(left_level, left_index)
    right_field = _mode_field(right_level, right_index)
    if left_field.field_file is None or right_field.field_file is None:
        raise PalaceOutputError(
            f"levels {left_level.tag}/{right_level.tag}: Palace field files are required "
            "for electric and magnetic overlap"
        )
    frequency = max(
        0.0,
        1.0 - abs(right_mode.frequency_ghz - left_mode.frequency_ghz)
        / left_mode.frequency_ghz
        / 0.15,
    )
    electric = overlap(left_field.field_file, right_field.field_file, kind="electric")
    magnetic = overlap(left_field.field_file, right_field.field_file, kind="magnetic")
    localization = max(
        0.0,
        1.0 - abs(
            right_field.resonator_localization - left_field.resonator_localization
        ),
    )
    score = (frequency + 2.0 * electric + 2.0 * magnetic + localization) / 6.0
    return ModeMatchResult(
        from_level=left_level.tag,
        to_level=right_level.tag,
        from_mode=left_index,
        to_mode=right_index,
        frequency_proximity=frequency,
        electric_field_overlap=electric,
        magnetic_field_overlap=magnetic,
        localization_similarity=localization,
        score=score,
        runner_up_score=0.0,
    )


def track_modes(
    levels: list[MeshLevelResult],
    *,
    seed_frequency_ghz: float,
    overlap: Callable[..., float] = field_overlap,
    ambiguity_margin: float = 0.05,
) -> tuple[list[int], list[ModeMatchResult]]:
    """Track one mode using frequency, actual E/H fields, and localization."""
    if len(levels) < 2:
        raise ValueError("mode tracking requires at least two mesh levels")
    first_candidates = [
        mode for mode in levels[0].modes if _has_retained_field(levels[0], mode.index)
    ]
    if not first_candidates:
        raise PalaceOutputError(f"level {levels[0].tag}: no retained complex mode fields")
    first = min(
        first_candidates,
        key=lambda mode: abs(mode.frequency_ghz - seed_frequency_ghz),
    )
    indices = [first.index]
    matches: list[ModeMatchResult] = []
    current = first.index
    for left, right in zip(levels, levels[1:]):
        candidates = [
            _pair_score(left, current, right, candidate.index, overlap=overlap)
            for candidate in right.modes
            if _has_retained_field(right, candidate.index)
        ]
        ranked = sorted(candidates, key=lambda item: (-item.score, item.to_mode))
        if not ranked:
            raise PalaceOutputError(f"level {right.tag}: no candidate modes")
        runner_up = ranked[1].score if len(ranked) > 1 else 0.0
        best = ranked[0].model_copy(update={"runner_up_score": runner_up})
        if best.margin < ambiguity_margin:
            raise PalaceOutputError(
                f"ambiguous mode identity from {left.tag} to {right.tag}: modes "
                f"{best.to_mode} and {ranked[1].to_mode} differ by {best.margin:.6f}, "
                f"below the required margin {ambiguity_margin:.6f}"
            )
        indices.append(best.to_mode)
        matches.append(best)
        current = best.to_mode
    return indices, matches


def _relative_change(first: float, second: float) -> float:
    return abs(second - first) / max(abs(second), 1e-300) * 100.0


def _participation_change(
    left: ModeFieldData, right: ModeFieldData
) -> float | None:
    names = set(left.electric_participation) | set(right.electric_participation)
    changes = []
    for name in names:
        first = left.electric_participation.get(name, 0.0)
        second = right.electric_participation.get(name, 0.0)
        if max(abs(first), abs(second)) <= 1e-12:
            continue
        changes.append(abs(second - first) / max(abs(second), 1e-12) * 100.0)
    return max(changes) if changes else None


def assess_convergence(
    levels: list[MeshLevelResult],
    *,
    tracked_mode_indices: list[int],
    matches: list[ModeMatchResult],
    domain_sweep: list[DomainSweepPoint],
    search_window_ghz: tuple[float, float],
    tracking_error: str | None = None,
) -> ConvergenceReport:
    """Apply every required physical-sanity and convergence gate."""
    gates: list[ConvergenceGate] = []
    enough = len(levels) >= 3
    gates.append(
        ConvergenceGate(
            name="at_least_three_valid_mesh_levels",
            passed=enough,
            value=len(levels),
            threshold=3,
            detail="three parsed Palace solves are required",
        )
    )
    finite = bool(levels) and all(
        all(math.isfinite(mode.frequency_ghz) and mode.frequency_ghz > 0 for mode in level.modes)
        for level in levels
    )
    gates.append(
        ConvergenceGate(
            name="frequencies_finite_and_positive",
            passed=finite,
            detail="every parsed eigenfrequency must be finite and positive",
        )
    )
    lengths = [level.characteristic_length_um for level in levels]
    refined_lengths = all(left > right for left, right in zip(lengths, lengths[1:]))
    gates.append(
        ConvergenceGate(
            name="mesh_characteristic_length_strictly_refined",
            passed=refined_lengths,
            detail=str(lengths),
        )
    )
    elements = [level.element_count for level in levels]
    element_growth = all(left < right for left, right in zip(elements, elements[1:]))
    gates.append(
        ConvergenceGate(
            name="element_count_increases",
            passed=element_growth,
            detail=str(elements),
        )
    )
    dofs = [level.degrees_of_freedom for level in levels]
    dof_growth = all(left < right for left, right in zip(dofs, dofs[1:]))
    gates.append(
        ConvergenceGate(
            name="degrees_of_freedom_increase",
            passed=dof_growth,
            detail=str(dofs),
        )
    )

    tracking_complete = (
        tracking_error is None
        and len(tracked_mode_indices) == len(levels)
        and len(matches) == max(len(levels) - 1, 0)
    )
    gates.append(
        ConvergenceGate(
            name="mode_identity_unambiguous",
            passed=tracking_complete,
            detail=tracking_error or str(tracked_mode_indices),
        )
    )
    minimum_overlap = (
        min(
            min(match.electric_field_overlap, match.magnetic_field_overlap)
            for match in matches
        )
        if matches
        else None
    )
    gates.append(
        ConvergenceGate(
            name="electric_and_magnetic_field_overlap",
            passed=minimum_overlap is not None and minimum_overlap > 0.95,
            value=minimum_overlap,
            threshold=0.95,
            detail="minimum real field overlap across adjacent levels; strict > comparison",
        )
    )

    frequencies = [
        next(mode.frequency_ghz for mode in level.modes if mode.index == index)
        for level, index in zip(levels, tracked_mode_indices)
    ] if tracking_complete else []
    delta = _relative_change(frequencies[-2], frequencies[-1]) if len(frequencies) >= 2 else None
    gates.append(
        ConvergenceGate(
            name="finest_frequency_change_percent",
            passed=delta is not None and delta < 0.5,
            value=delta,
            threshold=0.5,
            detail="change across the two finest tracked modes",
        )
    )
    global_error = levels[-1].global_error_indicator_percent if levels else None
    gates.append(
        ConvergenceGate(
            name="palace_global_error_indicator_percent",
            passed=global_error is not None and global_error < 1.0,
            value=global_error,
            threshold=1.0,
            detail="final Palace error-indicators.csv Norm",
        )
    )
    domain_sensitivity = None
    if len(domain_sweep) >= 3:
        values = [point.frequency_ghz for point in domain_sweep]
        domain_sensitivity = (max(values) - min(values)) / (sum(values) / len(values)) * 100.0
    gates.append(
        ConvergenceGate(
            name="domain_size_frequency_sensitivity_percent",
            passed=domain_sensitivity is not None and domain_sensitivity < 0.2,
            value=domain_sensitivity,
            threshold=0.2,
            detail=f"{len(domain_sweep)} genuine domain-size solves",
        )
    )
    energy_error = None
    if levels and len(tracked_mode_indices) == len(levels):
        energy_error = max(
            _mode_field(level, mode_index).energy_normalization_error_percent
            for level, mode_index in zip(levels, tracked_mode_indices)
        )
    gates.append(
        ConvergenceGate(
            name="energy_normalization_error_percent",
            passed=energy_error is not None and energy_error < 0.5,
            value=energy_error,
            threshold=0.5,
            detail="maximum electric/magnetic energy-balance error",
        )
    )
    participation = None
    if len(levels) >= 2 and len(tracked_mode_indices) == len(levels):
        participation = _participation_change(
            _mode_field(levels[-2], tracked_mode_indices[-2]),
            _mode_field(levels[-1], tracked_mode_indices[-1]),
        )
    gates.append(
        ConvergenceGate(
            name="participation_change_percent",
            passed=participation is not None and participation < 5.0,
            value=participation,
            threshold=5.0,
            detail="worst regional electric participation change on the finest step",
        )
    )
    low, high = search_window_ghz
    boundary_pinned = any(
        math.isclose(frequency, low, rel_tol=1e-6)
        or math.isclose(frequency, high, rel_tol=1e-6)
        for frequency in frequencies
    )
    gates.append(
        ConvergenceGate(
            name="eigenfrequency_not_at_search_window_boundary",
            passed=bool(frequencies) and not boundary_pinned,
            detail=f"window={search_window_ghz}, frequencies={frequencies}",
        )
    )

    invalid_names = {
        "frequencies_finite_and_positive",
        "mesh_characteristic_length_strictly_refined",
        "element_count_increases",
        "degrees_of_freedom_increase",
        "mode_identity_unambiguous",
        "eigenfrequency_not_at_search_window_boundary",
    }
    invalid = [gate.name for gate in gates if gate.name in invalid_names and not gate.passed]
    return ConvergenceReport(
        gates=gates,
        tracked_mode_indices=tracked_mode_indices,
        matches=matches,
        finest_frequency_ghz=frequencies[-1] if frequencies else None,
        converged=not invalid and all(gate.passed for gate in gates),
        simulation_invalid=bool(invalid),
        invalidation_reason=(
            "solver output failed physical-sanity checks: " + ", ".join(invalid)
            if invalid
            else None
        ),
    )


def canonical_evidence(
    *,
    design_id: str,
    design_hash: str,
    geometry_hash: str | None,
    fem_model_hash: str,
    capability: PalaceCapability,
    levels: list[MeshLevelResult],
    report: ConvergenceReport | None,
    domain_sweep: list[DomainSweepPoint] | None = None,
    output_root: Path,
    target_frequency_ghz: float | None = None,
    target_tolerance_percent: float = 2.0,
    target_method: str | None = None,
    independent_target_hash: str | None = None,
    git_commit: str | None = None,
    timestamp: str | None = None,
) -> CanonicalEvidence:
    """Generate the repository's existing CanonicalEvidence, never a rival schema."""
    stamp = timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    target_quantity = "eigenmode_frequency"
    common = {
        "design_id": design_id,
        "design_hash": design_hash,
        "geometry_hash": geometry_hash,
        "component": "quarter_wave_resonator",
        "analysis_scope": "full_3d_eigenmode",
        "target_quantity": target_quantity,
        "target_value": target_frequency_ghz,
        "target_unit": "GHz" if target_frequency_ghz is not None else None,
        "tolerance_percent": target_tolerance_percent,
        "git_commit": git_commit,
        "timestamp": stamp,
    }
    if not capability.available:
        reason = capability.unavailable_reason or "Palace is unavailable"
        return CanonicalEvidence(
            evidence_id=compute_evidence_id(
                design_id=design_id,
                target_quantity=target_quantity,
                output_file_hashes={},
                extraction_config_hash=None,
            ),
            status=EvidenceStatus.SKIPPED_SOLVER_ABSENT,
            skip_reason=reason,
            **common,
        )
    if not levels or report is None:
        return CanonicalEvidence(
            evidence_id=compute_evidence_id(
                design_id=design_id,
                target_quantity=target_quantity,
                output_file_hashes={},
                extraction_config_hash=None,
            ),
            status=EvidenceStatus.FAILED,
            solver_name="Palace",
            solver_version=capability.version,
            solver_executable_sha256=capability.executable_sha256,
            container_digest=capability.container_digest,
            failure_reason="Palace did not produce a complete parsed mesh study",
            **common,
        )

    if independent_target_hash is not None and len(independent_target_hash) != 64:
        raise ValueError("independent_target_hash must be a 64-character SHA-256")
    output_hashes: dict[str, str] = {}
    input_hashes: dict[str, str] = {"fem_model.json": fem_model_hash}
    dependencies: list[ArtifactDependency] = []
    for level in levels:
        for path in (level.mesh_path, level.config_path):
            relative = str(path.resolve().relative_to(output_root.resolve()))
            input_hashes[relative] = sha256_file(path)
        dependencies.append(
            ArtifactDependency(role="mesh", artifact=str(level.mesh_path), sha256=level.mesh_sha256)
        )
        for relative, expected in level.output_file_hashes.items():
            path = level.eig_path.parent.parent / relative
            actual = sha256_file(path)
            if actual != expected:
                raise PalaceOutputError(
                    f"{path}: output changed after parsing ({expected} != {actual})"
                )
            output_hashes[str(path.resolve().relative_to(output_root.resolve()))] = actual
    for point in domain_sweep or []:
        for relative, expected in point.output_file_hashes.items():
            path = output_root / relative
            actual = sha256_file(path)
            if actual != expected:
                raise PalaceOutputError(
                    f"{path}: domain-sweep output changed after parsing ({expected} != {actual})"
                )
            output_hashes[relative] = actual
    if independent_target_hash is not None:
        dependencies.append(
            ArtifactDependency(
                role="independent_reference",
                artifact=target_method or "independent target",
                sha256=independent_target_hash,
            )
        )

    extraction = {
        "parser": PARSER,
        "parser_version": PARSER_VERSION,
        "tracked_mode_indices": report.tracked_mode_indices,
        "domain_scales": [point.scale for point in domain_sweep or []],
        "gates": [gate.model_dump(mode="json") for gate in report.gates],
    }
    extraction_hash = sha256_json(extraction)
    evidence_id = compute_evidence_id(
        design_id=design_id,
        target_quantity=target_quantity,
        output_file_hashes=output_hashes,
        extraction_config_hash=extraction_hash,
    )
    invalid_gate_names = {
        "frequencies_finite_and_positive",
        "mesh_characteristic_length_strictly_refined",
        "element_count_increases",
        "degrees_of_freedom_increase",
        "mode_identity_unambiguous",
        "eigenfrequency_not_at_search_window_boundary",
    }
    sanity = [
        SanityCheck(name=gate.name, passed=gate.passed, detail=gate.detail)
        for gate in report.gates
        if gate.name in invalid_gate_names
    ]
    delta_gate = next(
        gate for gate in report.gates if gate.name == "finest_frequency_change_percent"
    )
    convergence = ConvergenceMetrics(
        method="palace_mesh_mode_domain_convergence",
        refinement_levels=len(levels),
        delta_percent=float(delta_gate.value) if delta_gate.value is not None else None,
        threshold_percent=0.5,
        converged=report.converged,
        notes=[
            f"{gate.name}: {'PASS' if gate.passed else 'FAIL'}; {gate.detail}"
            for gate in report.gates
            if gate.name not in invalid_gate_names
        ],
    )
    solver_fields = {
        "solver_name": "Palace",
        "solver_version": capability.version,
        "solver_executable_sha256": capability.executable_sha256,
        "container_digest": capability.container_digest,
        "command": levels[-1].command,
        "return_code": levels[-1].return_code,
        "runtime_seconds": sum(level.solver_runtime_seconds for level in levels),
        "input_file_hashes": input_hashes,
        "output_file_hashes": output_hashes,
        "parser": PARSER,
        "parser_version": PARSER_VERSION,
        "extraction_config": extraction,
        "extraction_config_hash": extraction_hash,
        "depends_on": dependencies,
    }
    if report.simulation_invalid:
        return CanonicalEvidence(
            evidence_id=evidence_id,
            status=EvidenceStatus.SIMULATION_INVALID,
            invalidation_reason=report.invalidation_reason,
            sanity_checks=sanity,
            convergence=convergence,
            **solver_fields,
            **common,
        )
    finest = report.finest_frequency_ghz
    if finest is None:
        raise PalaceOutputError("convergence report has no finest frequency")
    if not report.converged:
        return CanonicalEvidence(
            evidence_id=evidence_id,
            status=EvidenceStatus.CONVERGENCE_FAILED,
            convergence=convergence,
            sanity_checks=sanity,
            superseded=SupersededClaim(
                status=EvidenceStatus.SIMULATION_EXECUTED.value,
                extracted_value=finest,
                extracted_unit="GHz",
                why_withdrawn="one or more required convergence gates failed",
            ),
            **solver_fields,
            **common,
        )
    error = (
        (finest - target_frequency_ghz) / target_frequency_ghz * 100.0
        if target_frequency_ghz is not None
        else None
    )
    verified = (
        error is not None
        and independent_target_hash is not None
        and abs(error) <= target_tolerance_percent
    )
    warnings = []
    if target_frequency_ghz is not None and independent_target_hash is None:
        warnings.append(
            "The declared target has no independent reference artifact hash; "
            "a converged result is limited to SIMULATION_EXECUTED."
        )
    return CanonicalEvidence(
        evidence_id=evidence_id,
        status=EvidenceStatus.PHYSICS_VERIFIED if verified else EvidenceStatus.SIMULATION_EXECUTED,
        extracted_quantity=target_quantity,
        extracted_value=finest,
        extracted_unit="GHz",
        analytical_value=target_frequency_ghz,
        analytical_model=target_method,
        error_percent=error,
        convergence=convergence,
        sanity_checks=sanity,
        warnings=warnings,
        **solver_fields,
        **common,
    )
