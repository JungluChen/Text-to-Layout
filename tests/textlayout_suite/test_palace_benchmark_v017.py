"""Unit coverage for the Palace 0.17 AMR benchmark workflow (no solver needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from textlayout.solvers.palace.backend import DEFAULT_LAYOUT
from textlayout.solvers.palace.benchmark_v017 import (
    AMRSettings,
    _collect_amr_iterations,
    _extents_for,
    _ParsedIteration,
    run_quarter_wave_benchmark_v017,
    track_amr_modes,
)
from textlayout.solvers.palace.config import DomainExtents
from textlayout.solvers.palace.models import (
    Eigenmode,
    ModeFieldData,
    PalaceCapability,
    PalaceOutputError,
)
from textlayout.solvers.palace.stages import (
    palace_job_profile_from_payload,
    refresh_stage_job_profiles,
    write_stage_record,
)

ROOT = Path(__file__).resolve().parents[2]


def test_domain_extents_reject_lid_below_vacuum() -> None:
    with pytest.raises(ValueError):
        DomainExtents(vacuum_height_um=300.0, lid_height_um=200.0)


def test_extents_for_maps_each_required_sweep() -> None:
    base = DomainExtents()
    assert _extents_for(base, "vacuum_or_air_margin", 250.0).vacuum_height_um == 250.0
    assert _extents_for(base, "substrate_thickness", 275.0).substrate_thickness_um == 275.0
    assert _extents_for(base, "upper_boundary_distance", 500.0).lid_height_um == 500.0
    assert _extents_for(base, "lateral_boundary_margin", 80.0).lateral_margin_um == 80.0
    with pytest.raises(ValueError):
        _extents_for(base, "unknown", 1.0)


def test_sweep_defaults_are_split_by_category() -> None:
    from textlayout.solvers.palace.benchmark_v017 import (
        DEFAULT_NUMERICAL_SWEEP_VALUES,
        DEFAULT_PHYSICAL_SWEEP_VALUES,
        UNSUPPORTED_PHYSICAL_PARAMETERS,
    )

    assert set(DEFAULT_NUMERICAL_SWEEP_VALUES) == {
        "vacuum_or_air_margin",
        "upper_boundary_distance",
        "lateral_boundary_margin",
    }
    assert "substrate_thickness" in DEFAULT_PHYSICAL_SWEEP_VALUES
    assert "substrate_permittivity" in DEFAULT_PHYSICAL_SWEEP_VALUES
    # substrate thickness is a physical parameter and must never gate
    # numerical-domain convergence
    assert "substrate_thickness" not in DEFAULT_NUMERICAL_SWEEP_VALUES
    assert "metal_thickness" in UNSUPPORTED_PHYSICAL_PARAMETERS
    assert "kinetic_inductance" in UNSUPPORTED_PHYSICAL_PARAMETERS


def test_amr_settings_retain_the_adapted_mesh() -> None:
    refinement = AMRSettings().refinement_config()
    assert refinement["SaveAdaptIterations"] is True
    assert refinement["SaveAdaptMesh"] is True


def test_mode_match_uses_regional_energy_similarity_names() -> None:
    from textlayout.solvers.palace.benchmark_v017 import ModeMatch

    fields = set(ModeMatch.model_fields)
    assert "electric_regional_energy_similarity" in fields
    assert "magnetic_regional_energy_similarity" in fields
    assert "electric_field_overlap" not in fields
    assert "magnetic_field_overlap" not in fields


def test_amr_settings_project_native_palace_refinement_keys() -> None:
    refinement = AMRSettings(max_iterations=5).refinement_config()
    assert refinement["MaxIts"] == 5
    assert refinement["SaveAdaptIterations"] is True
    assert set(refinement) == {
        "Tol",
        "MaxIts",
        "UpdateFraction",
        "Nonconformal",
        "SaveAdaptIterations",
        "SaveAdaptMesh",
    }


def _iteration(
    tag: str,
    index: int,
    frequencies: dict[int, float],
    substrate: dict[int, float],
) -> _ParsedIteration:
    modes = [
        Eigenmode(index=mode, frequency_ghz=frequency)
        for mode, frequency in sorted(frequencies.items())
    ]
    fields = [
        ModeFieldData(
            mode_index=mode,
            electric_participation={
                "substrate_resonator": substrate[mode],
                "vacuum_resonator": 1.0 - substrate[mode],
            },
            magnetic_participation={
                "substrate_resonator": substrate[mode],
                "vacuum_resonator": 1.0 - substrate[mode],
            },
            resonator_localization=substrate[mode],
            energy_normalization_error_percent=0.01,
        )
        for mode in sorted(frequencies)
    ]
    return _ParsedIteration(
        tag=tag,
        palace_iteration=index,
        directory=Path("."),
        modes=modes,
        fields=fields,
        global_error_percent=0.1,
        element_count=1000 * index,
        degrees_of_freedom=5000 * index,
        cumulative_runtime_seconds=None,
        output_file_hashes={},
    )


def test_track_amr_modes_follows_the_physical_mode_not_the_index() -> None:
    # The resonator mode is index 2 on the first iteration and index 1 later:
    # tracking must follow the frequency/participation signature, not "mode 1".
    iterations = [
        _iteration("iteration_00", 1, {1: 9.0, 2: 6.01}, {1: 0.2, 2: 0.9}),
        _iteration("iteration_01", 2, {1: 6.005, 2: 9.1}, {1: 0.9, 2: 0.2}),
        _iteration("iteration_02", 3, {1: 6.002, 2: 9.2}, {1: 0.9, 2: 0.2}),
    ]
    tracked, matches = track_amr_modes(iterations, seed_frequency_ghz=6.0)
    assert tracked == [2, 1, 1]
    assert all(match.score > 0.98 for match in matches)
    assert all(match.margin > 0.05 for match in matches)


def test_track_amr_modes_raises_on_ambiguous_identity() -> None:
    # Two near-identical candidates: winner-vs-runner-up margin is ~0.
    iterations = [
        _iteration("iteration_00", 1, {1: 6.0}, {1: 0.9}),
        _iteration("iteration_01", 2, {1: 6.0005, 2: 6.0006}, {1: 0.9, 2: 0.9}),
    ]
    with pytest.raises(PalaceOutputError, match="ambiguous_mode_identity"):
        track_amr_modes(iterations, seed_frequency_ghz=6.0)


def test_collect_amr_iterations_orders_saved_then_final(tmp_path: Path) -> None:
    (tmp_path / "iteration1").mkdir()
    (tmp_path / "iteration2").mkdir()
    (tmp_path / "paraview").mkdir()
    ordered = _collect_amr_iterations(tmp_path)
    assert [item[0] for item in ordered] == [1, 2, 3]
    assert ordered[-1][1] == tmp_path
    assert ordered[0][1].name == "iteration1"


def test_absent_solver_produces_honest_skip(tmp_path: Path) -> None:
    absent = PalaceCapability(unavailable_reason="Palace was not found (test)")
    result = run_quarter_wave_benchmark_v017(
        tmp_path / "v017",
        layout_path=DEFAULT_LAYOUT,
        capability=absent,
    )
    assert result.status == "SKIPPED_SOLVER_ABSENT"
    evidence = json.loads(
        (tmp_path / "v017" / "canonical_evidence.json").read_text(encoding="utf-8")
    )
    assert evidence["status"] == "SKIPPED_SOLVER_ABSENT"
    assert evidence["skip_reason"] == "Palace was not found (test)"
    toolchain = json.loads((tmp_path / "v017" / "toolchain.json").read_text(encoding="utf-8"))
    assert toolchain["required_palace_version"] == "0.17.0"
    assert (tmp_path / "v017" / "fem_model.json").is_file()
    assert (tmp_path / "v017" / "report.md").is_file()


def test_status_reports_missing_stages_before_resume(tmp_path: Path) -> None:
    from textlayout.solvers.palace.benchmark_v017 import palace_resonator_status

    report = palace_resonator_status(tmp_path / "empty")
    assert report["stages"][0]["stage"] == "preflight"
    assert {stage["status"] for stage in report["stages"]} == {"missing"}
    assert report["orphan_processes"]["checked"] in {True, False}


def test_stage_record_can_reference_persistent_job_profile(tmp_path: Path) -> None:
    job_dir = tmp_path / "jobs" / "job-palace"
    job_dir.mkdir(parents=True)
    (job_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (job_dir / "environment.json").write_text("{}", encoding="utf-8")
    (job_dir / "stdout.txt").write_text("stdout", encoding="utf-8")
    (job_dir / "stderr.txt").write_text("stderr", encoding="utf-8")
    (job_dir / "heartbeat.json").write_text("{}", encoding="utf-8")
    (job_dir / "output_inventory.json").write_text("{}", encoding="utf-8")
    payload = {
        "job_id": "job-palace",
        "command": ["palace", "-serial", "palace_amr.json"],
        "cwd": str(tmp_path),
        "job_dir": str(job_dir),
        "stdout_path": str(job_dir / "stdout.txt"),
        "stderr_path": str(job_dir / "stderr.txt"),
        "pid": 123,
        "parent_pid": 12,
        "process_group_id": 123,
    }
    profile = palace_job_profile_from_payload(
        payload,
        upstream_stage_evidence_ids=["upstream"],
    )
    record = write_stage_record(
        tmp_path / "palace",
        stage="base_amr",
        status="complete",
        command=payload["command"],
        return_code=0,
        capability=PalaceCapability(
            executable="palace",
            version="0.17.0",
            executable_sha256="a" * 64,
            mpi_launcher="mpirun",
        ),
        job_profile=profile,
        upstream_stage_evidence_ids=["upstream"],
    )
    assert record.job_profile is not None
    assert record.job_profile.job_id == "job-palace"
    assert record.job_profile.launch_manifest_hash is not None
    assert record.job_profile.environment_manifest_hash is not None
    saved = json.loads(
        (tmp_path / "palace" / "stages" / "base_amr.json").read_text(encoding="utf-8")
    )
    assert saved["job_profile"]["job_id"] == "job-palace"
    assert saved["job_profile"]["solver_output_inventory_hash"] is not None

    (job_dir / "output_inventory.json").write_text('{"solver.out": "abc"}', encoding="utf-8")
    refreshed_profile = palace_job_profile_from_payload(payload)
    refreshed = refresh_stage_job_profiles(tmp_path / "palace", refreshed_profile)
    assert refreshed[0].job_profile is not None
    assert refreshed[0].job_profile.solver_output_inventory_hash is not None


def test_fem_model_gains_far_vacuum_volume_when_lid_is_above_vacuum() -> None:
    from textlayout.solvers.palace.config import quarter_wave_fem_model

    extents = DomainExtents(vacuum_height_um=300.0, lid_height_um=450.0)
    model = quarter_wave_fem_model(DEFAULT_LAYOUT, extents=extents)
    names = [volume.name for volume in model.volumes]
    assert names[-1] == "vacuum_far"
    assert model.volumes[-1].attribute == 5
    flat = quarter_wave_fem_model(
        DEFAULT_LAYOUT, extents=DomainExtents(vacuum_height_um=300.0, lid_height_um=300.0)
    )
    assert all(volume.name != "vacuum_far" for volume in flat.volumes)
