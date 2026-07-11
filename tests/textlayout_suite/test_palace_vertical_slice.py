"""Failure paths and convergence contract for the executable Palace slice."""

from __future__ import annotations

import math
import os
import stat
import sys
from pathlib import Path

import pytest

from textlayout.evidence import EvidenceStatus
from textlayout.evidence.canonical import sha256_file
from textlayout.fem.gmsh_physical import GmshMeshResult
from textlayout.solvers.palace.backend import DEFAULT_LAYOUT, PalaceBackend
from textlayout.solvers.palace.config import (
    build_eigenmode_config,
    quarter_wave_fem_model,
    write_config,
)
from textlayout.solvers.palace.evidence import assess_convergence, canonical_evidence
from textlayout.solvers.palace.models import (
    DomainSweepPoint,
    Eigenmode,
    MeshLevelResult,
    ModeFieldData,
    ModeMatchResult,
    PalaceCapability,
    PalaceOutputError,
)
from textlayout.solvers.palace.runner import run_palace


def _fake_palace(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_palace_impl.py"
    script.write_text(body, encoding="utf-8")
    if os.name == "nt":
        shim = tmp_path / "fake_palace.bat"
        shim.write_text(f'@echo off\n"{sys.executable}" "{script}" %*\n', encoding="ascii")
    else:
        shim = tmp_path / "fake_palace.sh"
        shim.write_text(f'#!/bin/sh\n"{sys.executable}" "{script}" "$@"\n', encoding="ascii")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    return shim


def _capability(executable: Path | None = None) -> PalaceCapability:
    return PalaceCapability(
        executable=str(executable) if executable else None,
        version="0.test",
        executable_sha256="a" * 64 if executable else None,
        unavailable_reason=None if executable else "Palace absent for test",
    )


def _level(
    root: Path,
    tag: str,
    *,
    length: float,
    elements: int,
    dof: int,
    frequency: float,
    global_error: float = 0.5,
) -> MeshLevelResult:
    level = root / tag
    postpro = level / "postpro"
    postpro.mkdir(parents=True)
    mesh = level / "mesh.msh"
    config = level / "palace.json"
    eig = postpro / "eig.csv"
    domain = postpro / "domain-E.csv"
    indicator = postpro / "error-indicators.csv"
    stdout = level / "palace.stdout.txt"
    stderr = level / "palace.stderr.txt"
    field = postpro / "mode.vtu"
    mesh.write_text("real mesh fixture", encoding="utf-8")
    config.write_text("{}\n", encoding="utf-8")
    eig.write_text(f"m,Re{{f}} (GHz)\n1,{frequency}\n", encoding="utf-8")
    domain.write_text("m,E_elec (J),E_mag (J)\n1,1,1\n", encoding="utf-8")
    indicator.write_text(f"Norm\n{global_error / 100}\n", encoding="utf-8")
    stdout.write_text(f"Nedelec DOF: {dof}\n", encoding="utf-8")
    stderr.write_text("none\n", encoding="utf-8")
    field.write_text("field fixture", encoding="utf-8")
    outputs = {
        str(path.relative_to(level)): sha256_file(path)
        for path in (eig, domain, indicator, field)
    }
    return MeshLevelResult(
        tag=tag,
        characteristic_length_um=length,
        local_characteristic_lengths_um={"cpw_gaps": length / 10},
        element_count=elements,
        degrees_of_freedom=dof,
        minimum_quality=0.2,
        mean_quality=0.8,
        mesh_path=mesh,
        mesh_sha256=sha256_file(mesh),
        mesh_runtime_seconds=1.0,
        solver_runtime_seconds=2.0,
        command=["palace", "-serial", "palace.json"],
        return_code=0,
        stdout_path=stdout,
        stderr_path=stderr,
        config_path=config,
        eig_path=eig,
        domain_energy_path=domain,
        error_indicator_path=indicator,
        modes=[Eigenmode(index=1, frequency_ghz=frequency)],
        mode_fields=[
            ModeFieldData(
                mode_index=1,
                electric_participation={"substrate_resonator": 0.8, "vacuum_outer": 0.2},
                magnetic_participation={"substrate_resonator": 0.6, "vacuum_outer": 0.4},
                resonator_localization=0.8,
                energy_normalization_error_percent=0.1,
                field_file=field,
            )
        ],
        global_error_indicator_percent=global_error,
        output_file_hashes=outputs,
    )


def _study(tmp_path: Path) -> tuple[list[MeshLevelResult], list[ModeMatchResult], list[DomainSweepPoint]]:
    levels = [
        _level(tmp_path, "A", length=40, elements=100, dof=200, frequency=6.03),
        _level(tmp_path, "B", length=30, elements=200, dof=400, frequency=6.01),
        _level(tmp_path, "C", length=20, elements=400, dof=800, frequency=6.0),
    ]
    matches = [
        ModeMatchResult(
            from_level=left.tag,
            to_level=right.tag,
            from_mode=1,
            to_mode=1,
            frequency_proximity=0.99,
            electric_field_overlap=0.99,
            magnetic_field_overlap=0.99,
            localization_similarity=0.99,
            score=0.99,
            runner_up_score=0.5,
        )
        for left, right in zip(levels, levels[1:])
    ]
    domains = [
        DomainSweepPoint(scale=scale, frequency_ghz=frequency, output_file_hashes={})
        for scale, frequency in ((0.85, 5.999), (1.0, 6.0), (1.15, 6.001))
    ]
    return levels, matches, domains


def _report(levels, matches, domains):
    return assess_convergence(
        levels,
        tracked_mode_indices=[1, 1, 1],
        matches=matches,
        domain_sweep=domains,
        search_window_ghz=(4.0, 8.0),
    )


def _evidence(tmp_path: Path, levels, report, **overrides):
    kwargs = {
        "design_id": "quarter_wave_test",
        "design_hash": "d" * 64,
        "geometry_hash": None,
        "fem_model_hash": "f" * 64,
        "capability": PalaceCapability(
            executable="palace", version="0.test", executable_sha256="a" * 64
        ),
        "levels": levels,
        "report": report,
        "output_root": tmp_path,
        "timestamp": "2026-07-11T00:00:00+00:00",
    }
    kwargs.update(overrides)
    return canonical_evidence(**kwargs)


def test_solver_absent_returns_skipped_solver_absent(tmp_path: Path) -> None:
    record = canonical_evidence(
        design_id="quarter_wave_test",
        design_hash="d" * 64,
        geometry_hash=None,
        fem_model_hash="f" * 64,
        capability=_capability(),
        levels=[],
        report=None,
        output_root=tmp_path,
    )
    assert record.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT
    assert record.extracted_value is None


def test_solver_timeout_is_retained(tmp_path: Path) -> None:
    shim = _fake_palace(tmp_path, "import time; time.sleep(10)")
    config = tmp_path / "palace.json"
    write_config({}, config)
    run = run_palace(_capability(shim), config, cwd=tmp_path, timeout_seconds=0.2)
    assert run.timed_out and not run.succeeded
    assert "timeout" in run.stderr_path.read_text(encoding="utf-8").lower()


def test_non_zero_return_code_is_not_success(tmp_path: Path) -> None:
    shim = _fake_palace(tmp_path, "import sys; sys.exit(7)")
    config = tmp_path / "palace.json"
    write_config({}, config)
    run = run_palace(_capability(shim), config, cwd=tmp_path)
    assert run.return_code == 7 and not run.succeeded


def test_missing_output_is_rejected(tmp_path: Path) -> None:
    shim = _fake_palace(tmp_path, "print('Palace completed without output')")
    model = quarter_wave_fem_model(DEFAULT_LAYOUT)
    mesh_path = tmp_path / "mesh.msh"
    mesh_path.write_text("mesh", encoding="utf-8")
    config = tmp_path / "palace.json"
    write_config(build_eigenmode_config(model, mesh_filename=mesh_path.name, output_dir="postpro"), config)
    backend = PalaceBackend(_capability(shim))
    run = backend.execute(config, cwd=tmp_path, mesh_path=mesh_path)
    mesh = GmshMeshResult(mesh_path, 1.0, 10, 0.2, 0.8)
    with pytest.raises(PalaceOutputError, match="missing Palace eigenvalue output"):
        backend.parse_level(tag="A", model=model, mesh=mesh, config_path=config, run=run)


def test_non_finite_frequency_is_simulation_invalid(tmp_path: Path) -> None:
    levels, matches, domains = _study(tmp_path)
    levels[-1] = levels[-1].model_copy(
        update={"modes": [Eigenmode(index=1, frequency_ghz=math.nan)]}
    )
    report = _report(levels, matches, domains)
    assert report.simulation_invalid
    assert "frequencies_finite_and_positive" in report.blockers


def test_boundary_pinned_eigenvalue_is_simulation_invalid(tmp_path: Path) -> None:
    levels, matches, domains = _study(tmp_path)
    levels[0] = levels[0].model_copy(update={"modes": [Eigenmode(index=1, frequency_ghz=4.0)]})
    report = _report(levels, matches, domains)
    assert report.simulation_invalid
    assert "eigenfrequency_not_at_search_window_boundary" in report.blockers


def test_unrefined_mesh_sequence_is_simulation_invalid(tmp_path: Path) -> None:
    levels, matches, domains = _study(tmp_path)
    levels[1] = levels[1].model_copy(update={"characteristic_length_um": 40.0})
    report = _report(levels, matches, domains)
    assert report.simulation_invalid
    assert "mesh_characteristic_length_strictly_refined" in report.blockers


def test_ambiguous_mode_identity_is_simulation_invalid(tmp_path: Path) -> None:
    levels, _, domains = _study(tmp_path)
    report = assess_convergence(
        levels,
        tracked_mode_indices=[],
        matches=[],
        domain_sweep=domains,
        search_window_ghz=(4.0, 8.0),
        tracking_error="ambiguous mode swap",
    )
    assert report.simulation_invalid
    assert "mode_identity_unambiguous" in report.blockers


def test_convergence_failure_withholds_frequency(tmp_path: Path) -> None:
    levels, matches, domains = _study(tmp_path)
    levels[-1] = levels[-1].model_copy(update={"global_error_indicator_percent": 2.0})
    report = _report(levels, matches, domains)
    record = _evidence(tmp_path, levels, report)
    assert record.status is EvidenceStatus.CONVERGENCE_FAILED
    assert record.extracted_value is None


def test_converged_off_target_is_simulation_executed(tmp_path: Path) -> None:
    levels, matches, domains = _study(tmp_path)
    record = _evidence(
        tmp_path,
        levels,
        _report(levels, matches, domains),
        target_frequency_ghz=5.0,
        target_method="independent fixture",
        independent_target_hash="b" * 64,
    )
    assert record.status is EvidenceStatus.SIMULATION_EXECUTED


def test_converged_on_target_with_independent_reference_is_verified(tmp_path: Path) -> None:
    levels, matches, domains = _study(tmp_path)
    record = _evidence(
        tmp_path,
        levels,
        _report(levels, matches, domains),
        target_frequency_ghz=6.0,
        target_method="independent fixture",
        independent_target_hash="b" * 64,
    )
    assert record.status is EvidenceStatus.PHYSICS_VERIFIED


def test_deterministic_input_generation(tmp_path: Path) -> None:
    model = quarter_wave_fem_model(DEFAULT_LAYOUT)
    config = build_eigenmode_config(model, mesh_filename="mesh.msh", output_dir="postpro")
    first = write_config(config, tmp_path / "first.json")
    second = write_config(dict(reversed(list(config.items()))), tmp_path / "second.json")
    assert first == second
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()


def test_modified_output_hash_is_detected(tmp_path: Path) -> None:
    levels, matches, domains = _study(tmp_path)
    record = _evidence(tmp_path, levels, _report(levels, matches, domains))
    assert record.verify_output_hashes(tmp_path) == []
    levels[-1].eig_path.write_text("m,Re{f} (GHz)\n1,9.9\n", encoding="utf-8")
    assert "output changed after evidence was written" in record.verify_output_hashes(tmp_path)[0]
