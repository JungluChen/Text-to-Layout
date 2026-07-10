"""Multi-level mesh convergence, and the canonical evidence it earns.

A single eigenmode solve produces a number. It does not produce *knowledge* that
the number is a property of the device rather than of the discretisation. Only a
refinement study can distinguish the two, so this module refuses to emit
``SIMULATION_EXECUTED`` or ``PHYSICS_VERIFIED`` for a frequency that has not been
shown insensitive to the mesh.

The status a study earns, in the order the checks are applied:

``SKIPPED_SOLVER_ABSENT``
    The solver is not installed. Nothing ran; no value exists.
``SIMULATION_INVALID``
    The solver ran and its output failed a *physical* assertion -- a non-finite
    or non-positive frequency, an eigenvalue pinned to the edge of the search
    window (the solver returned its own guess), or a field that carries no
    normalised energy. These pass every *structural* check: a file exists, it
    parses, it yields a float. Only a physical assertion catches them.
``CONVERGENCE_FAILED``
    Every level is physically sane, but the frequency is still moving under
    refinement, or fewer than ``min_levels`` levels were run. The last value is
    recorded as a *withdrawn* claim in ``superseded`` -- never as an active one.
``SIMULATION_EXECUTED``
    Converged, but no design target was supplied to compare against.
``PHYSICS_VERIFIED``
    Converged *and* within tolerance of the design target.

This engine is solver-agnostic: it consumes :class:`MeshLevel` results. Palace is
the intended producer, but nothing here imports it, so the ladder is testable
without a 3-D FEM solver installed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
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

PARSER_VERSION = "1"
PARSER = "textlayout.simulation.mesh_convergence.assess"

#: A frequency this close to an eigen-search-window edge is the solver echoing
#: its own target back, not a resonance it found.
_WINDOW_EDGE_RELATIVE_TOLERANCE = 1e-6


@dataclass(frozen=True)
class SolverIdentity:
    """Who computed this, precisely enough to run it again."""

    name: str
    version: str | None = None
    executable_sha256: str | None = None
    container_digest: str | None = None
    command: list[str] = field(default_factory=list)

    @property
    def is_reproducible(self) -> bool:
        """Whether the exact binary can be identified from this record alone."""
        return bool(self.executable_sha256 or self.container_digest)


@dataclass(frozen=True)
class MeshLevel:
    """One solve at one mesh density.

    ``frequency_ghz`` is ``None`` when the level ran but produced no parseable
    value; that is a fact about the run, not a licence to drop the level.
    """

    characteristic_length_um: float
    frequency_ghz: float | None
    output_file: Path | None = None
    runtime_seconds: float | None = None
    #: Total field energy after normalisation. A correct eigenmode carries 1.0.
    energy_normalization: float | None = None


def _finite(value: float | None) -> bool:
    return value is not None and math.isfinite(value)


def _relative(path: Path, root: Path) -> str:
    """Record outputs relative to the run directory when possible, else by name."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def sanity_checks(
    levels: list[MeshLevel],
    *,
    eigen_window_ghz: tuple[float, float] | None = None,
    energy_tolerance: float = 1e-3,
) -> list[SanityCheck]:
    """Physical assertions about the raw solver output, each recorded by name.

    An empty list would be a silent gap, so every check is always reported --
    passing or failing.
    """
    checks: list[SanityCheck] = []

    missing = [level.characteristic_length_um for level in levels if level.frequency_ghz is None]
    checks.append(
        SanityCheck(
            name="every_level_produced_a_frequency",
            passed=not missing,
            detail=None if not missing else f"no frequency at lc={missing} um",
        )
    )

    non_finite = [
        level.characteristic_length_um
        for level in levels
        if level.frequency_ghz is not None and not math.isfinite(level.frequency_ghz)
    ]
    checks.append(
        SanityCheck(
            name="frequencies_finite",
            passed=not non_finite,
            detail=None if not non_finite else f"non-finite frequency at lc={non_finite} um",
        )
    )

    non_positive = [
        level.characteristic_length_um
        for level in levels
        if _finite(level.frequency_ghz) and level.frequency_ghz <= 0  # type: ignore[operator]
    ]
    checks.append(
        SanityCheck(
            name="frequencies_positive",
            passed=not non_positive,
            detail=None if not non_positive else f"non-positive frequency at lc={non_positive} um",
        )
    )

    lengths = [level.characteristic_length_um for level in levels]
    monotone = all(a > b for a, b in zip(lengths, lengths[1:]))
    checks.append(
        SanityCheck(
            name="mesh_is_strictly_refined",
            passed=monotone,
            detail=None if monotone else f"characteristic lengths not strictly decreasing: {lengths}",
        )
    )

    if eigen_window_ghz is not None:
        low, high = eigen_window_ghz
        pinned = [
            level.characteristic_length_um
            for level in levels
            if _finite(level.frequency_ghz)
            and (
                math.isclose(level.frequency_ghz, low, rel_tol=_WINDOW_EDGE_RELATIVE_TOLERANCE)  # type: ignore[arg-type]
                or math.isclose(level.frequency_ghz, high, rel_tol=_WINDOW_EDGE_RELATIVE_TOLERANCE)  # type: ignore[arg-type]
            )
        ]
        checks.append(
            SanityCheck(
                name="resonance_not_at_search_window_edge",
                passed=not pinned,
                detail=(
                    None
                    if not pinned
                    else f"eigenvalue pinned to window {eigen_window_ghz} GHz at lc={pinned} um"
                ),
            )
        )

    energies = [level.energy_normalization for level in levels if level.energy_normalization is not None]
    if energies:
        bad = [value for value in energies if not math.isfinite(value) or abs(value - 1.0) > energy_tolerance]
        checks.append(
            SanityCheck(
                name="field_energy_normalised",
                passed=not bad,
                detail=None if not bad else f"energy normalisation off unity: {bad}",
            )
        )

    return checks


def assess_convergence(
    levels: list[MeshLevel],
    *,
    threshold_percent: float,
    min_levels: int = 3,
) -> ConvergenceMetrics:
    """Change in the quantity across the two finest levels, against a declared bound."""
    if threshold_percent <= 0:
        raise ValueError(f"threshold_percent must be positive, got {threshold_percent!r}")
    if not levels:
        raise ValueError("a convergence assessment needs at least one mesh level")

    notes: list[str] = []
    usable = [level for level in levels if _finite(level.frequency_ghz)]
    delta: float | None = None
    converged = False

    if len(levels) < min_levels:
        notes.append(
            f"{len(levels)} mesh level(s) run; {min_levels} are required to evidence convergence"
        )
    elif len(usable) < 2:
        notes.append("fewer than two levels produced a finite frequency; no delta is computable")
    else:
        finest, next_finest = usable[-1], usable[-2]
        assert finest.frequency_ghz is not None and next_finest.frequency_ghz is not None
        delta = abs(finest.frequency_ghz - next_finest.frequency_ghz) / abs(finest.frequency_ghz) * 100.0
        converged = len(levels) >= min_levels and delta <= threshold_percent
        notes.append(
            f"|f({finest.characteristic_length_um} um) - f({next_finest.characteristic_length_um} um)|"
            f" / f = {delta:.4f}% against a declared bound of {threshold_percent:.4f}%"
        )

    return ConvergenceMetrics(
        method="mesh_refinement",
        refinement_levels=max(len(levels), 1),
        delta_percent=delta,
        threshold_percent=threshold_percent,
        converged=converged,
        notes=notes,
    )


def _error_percent(extracted: float, target: float) -> float:
    return (extracted - target) / target * 100.0


def mesh_convergence_evidence(
    *,
    design_id: str,
    design_hash: str,
    component: str,
    analysis_scope: str,
    levels: list[MeshLevel],
    solver: SolverIdentity | None,
    solver_absent_reason: str | None = None,
    target_frequency_ghz: float | None = None,
    tolerance_percent: float = 2.0,
    threshold_percent: float = 1.0,
    min_levels: int = 3,
    eigen_window_ghz: tuple[float, float] | None = None,
    geometry_hash: str | None = None,
    input_file_hashes: dict[str, str] | None = None,
    depends_on: list[ArtifactDependency] | None = None,
    git_commit: str | None = None,
    environment_hash: str | None = None,
    timestamp: str | None = None,
    output_root: Path | None = None,
) -> CanonicalEvidence:
    """Walk the status ladder and emit exactly the claim the evidence supports."""
    if solver is not None and not levels:
        # Not a physics outcome: a solver was named but nothing was run. Refusing
        # here keeps the ladder below from having to invent a status for it.
        raise ValueError("a solver-backed convergence study needs at least one mesh level")
    stamp = timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    target_quantity = "eigenmode_frequency"
    common = {
        "design_id": design_id,
        "design_hash": design_hash,
        "geometry_hash": geometry_hash,
        "component": component,
        "analysis_scope": analysis_scope,
        "target_quantity": target_quantity,
        "target_value": target_frequency_ghz,
        "target_unit": "GHz" if target_frequency_ghz is not None else None,
        "tolerance_percent": tolerance_percent,
        "input_file_hashes": dict(input_file_hashes or {}),
        "depends_on": list(depends_on or []),
        "git_commit": git_commit,
        "environment_hash": environment_hash,
        "timestamp": stamp,
    }

    if solver is None:
        reason = solver_absent_reason or "the eigenmode solver is not installed"
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

    extraction_config = {
        "parser": PARSER,
        "parser_version": PARSER_VERSION,
        "min_levels": min_levels,
        "threshold_percent": threshold_percent,
        "eigen_window_ghz": list(eigen_window_ghz) if eigen_window_ghz else None,
        "characteristic_lengths_um": [level.characteristic_length_um for level in levels],
    }
    extraction_config_hash = sha256_json(extraction_config)

    root = output_root or Path(".")
    output_file_hashes = {
        _relative(level.output_file, root): sha256_file(level.output_file)
        for level in levels
        if level.output_file is not None and level.output_file.is_file()
    }

    evidence_id = compute_evidence_id(
        design_id=design_id,
        target_quantity=target_quantity,
        output_file_hashes=output_file_hashes,
        extraction_config_hash=extraction_config_hash,
    )
    provenance_gaps = [] if solver.is_reproducible else ["solver_executable_hash_unrecorded"]
    runtime = sum(level.runtime_seconds or 0.0 for level in levels) or None
    solver_fields = {
        "solver_name": solver.name,
        "solver_version": solver.version,
        "solver_executable_sha256": solver.executable_sha256,
        "container_digest": solver.container_digest,
        "command": list(solver.command),
        "runtime_seconds": runtime,
        "parser": PARSER,
        "parser_version": PARSER_VERSION,
        "extraction_config": extraction_config,
        "extraction_config_hash": extraction_config_hash,
        "provenance_gaps": provenance_gaps,
    }

    checks = sanity_checks(levels, eigen_window_ghz=eigen_window_ghz)
    failed = [check.name for check in checks if not check.passed]
    if failed:
        return CanonicalEvidence(
            evidence_id=evidence_id,
            status=EvidenceStatus.SIMULATION_INVALID,
            invalidation_reason=(
                "solver output failed physical-sanity checks: " + ", ".join(sorted(failed))
            ),
            sanity_checks=checks,
            output_file_hashes=output_file_hashes,
            **solver_fields,
            **common,
        )

    convergence = assess_convergence(
        levels, threshold_percent=threshold_percent, min_levels=min_levels
    )
    finest = levels[-1].frequency_ghz
    assert finest is not None  # guaranteed: every_level_produced_a_frequency passed

    if not convergence.converged:
        return CanonicalEvidence(
            evidence_id=evidence_id,
            status=EvidenceStatus.CONVERGENCE_FAILED,
            convergence=convergence,
            sanity_checks=checks,
            output_file_hashes=output_file_hashes,
            superseded=SupersededClaim(
                status=EvidenceStatus.SIMULATION_EXECUTED.value,
                extracted_value=finest,
                extracted_unit="GHz",
                why_withdrawn=(
                    "the frequency is still moving under mesh refinement; "
                    + "; ".join(convergence.notes)
                ),
            ),
            **solver_fields,
            **common,
        )

    error = _error_percent(finest, target_frequency_ghz) if target_frequency_ghz else None
    verified = error is not None and abs(error) <= tolerance_percent
    return CanonicalEvidence(
        evidence_id=evidence_id,
        status=EvidenceStatus.PHYSICS_VERIFIED if verified else EvidenceStatus.SIMULATION_EXECUTED,
        extracted_quantity=target_quantity,
        extracted_value=finest,
        extracted_unit="GHz",
        error_percent=error,
        convergence=convergence,
        sanity_checks=checks,
        output_file_hashes=output_file_hashes,
        **solver_fields,
        **common,
    )
