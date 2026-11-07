"""Unit tests for Palace Atomic Checkpoint/Resume Engine and Modal Overlap Tracking."""

from __future__ import annotations

from pathlib import Path

import pytest

from textlayout.evidence.contract import EvidenceStatus
from textlayout.mesh.gmsh_pipeline import MeshControls, SubstrateStack, gmsh_available
from textlayout.models import Geometry, rectangle
from textlayout.simulation.backends.palace import (
    AMRIteration,
    AMRPolicy,
    read_manifest,
    run_eigenmode,
    validate_amr_convergence,
)
from textlayout.solvers.palace.models import Eigenmode, PalaceCapability

CPW = Geometry(
    "cpw",
    (
        rectangle("M1", -5.0, 0.0, 5.0, 100.0),
        rectangle("M1", -40.0, 0.0, -11.0, 100.0),
        rectangle("M1", 11.0, 0.0, 40.0, 100.0),
    ),
)
STACK = SubstrateStack(substrate_thickness_um=200.0, vacuum_height_um=200.0, lateral_margin_um=50.0)
COARSE = MeshControls(characteristic_length_um=80.0, metal_edge_length_um=10.0)


def _fake_palace_mock(tmp_path: Path, script_content: str) -> PalaceCapability:
    tmp_path.mkdir(parents=True, exist_ok=True)
    script = tmp_path / "fake_palace.py"
    script.write_text(script_content, encoding="utf-8")
    import os
    import stat
    import sys

    if os.name == "nt":
        shim = tmp_path / "palace_shim.bat"
        shim.write_text(f'@echo off\n"{sys.executable}" "{script}" %*\n', encoding="ascii")
    else:
        shim = tmp_path / "palace_shim.sh"
        shim.write_text(f'#!/bin/sh\n"{sys.executable}" "{script}" "$@"\n', encoding="ascii")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    return PalaceCapability(
        execution_kind="executable",
        executable=str(shim),
        version="0.17.0",
        executable_sha256="b" * 64,
    )


# ------------------------------------------------------------------ Priority 2: Checkpoint & Resume


@pytest.mark.skipif(not gmsh_available(), reason="gmsh required")
def test_checkpoint_state_machine_and_continuation(tmp_path: Path) -> None:
    # 1. First run: fail inside solver to simulate interruption during AMR
    failing_solver = _fake_palace_mock(
        tmp_path / "solver1",
        "import sys; sys.exit(1)",
    )
    run_dir = tmp_path / "run"
    first = run_eigenmode(CPW, STACK, run_dir, controls=COARSE, capability=failing_solver)
    assert first.status is EvidenceStatus.FAILED

    # Check manifest.json wrote INTERRUPTED state but preserved base_mesh
    manifest = read_manifest(run_dir / "manifest.json")
    assert manifest is not None
    assert manifest.state == "INTERRUPTED"
    assert "base_mesh" in manifest.completed_stages
    assert (run_dir / "model.msh").is_file()
    assert (run_dir / "mesh_manifest.json").is_file()
    msh_mtime = (run_dir / "model.msh").stat().st_mtime_ns

    # 2. Resume continuation: provide working solver
    working_solver = _fake_palace_mock(
        tmp_path / "solver2",
        "import pathlib\n"
        "p = pathlib.Path('postpro'); (p / 'iteration1').mkdir(parents=True)\n"
        "hdr = 'm,Re{f} (GHz),Im{f} (GHz),Q,Error (Bkwd.),Error (Abs.)\\n'\n"
        "(p / 'iteration1' / 'eig.csv').write_text(hdr + '1,5.0000,1e-6,1e6,0,0\\n')\n"
        "(p / 'eig.csv').write_text(hdr + '1,5.0002,1e-6,1e6,0,0\\n')\n"
        "(p / 'error-indicators.csv').write_text('Norm,Minimum,Maximum,Mean\\n0.005,0,0,0\\n')\n",
    )
    second = run_eigenmode(CPW, STACK, run_dir, controls=COARSE, capability=working_solver)
    assert second.status is EvidenceStatus.SIMULATION_EXECUTED
    assert second.audit_level == "NUMERICALLY_CONVERGED"

    # Verify model.msh was NOT re-meshed (continuation preserved the base_mesh checkpoint)
    assert (run_dir / "model.msh").stat().st_mtime_ns == msh_mtime

    # Verify manifest is now CONVERGED
    final_manifest = read_manifest(run_dir / "manifest.json")
    assert final_manifest is not None
    assert final_manifest.state == "CONVERGED"
    assert "base_mesh" in final_manifest.completed_stages
    assert "base_amr" in final_manifest.completed_stages

    # 3. Completed run is NEVER re-executed
    crash_solver = _fake_palace_mock(
        tmp_path / "solver3", "raise RuntimeError('should not be called')"
    )
    re_run = run_eigenmode(CPW, STACK, run_dir, controls=COARSE, capability=crash_solver)
    assert re_run.status is EvidenceStatus.SIMULATION_EXECUTED
    assert re_run.modes[0].frequency_ghz == pytest.approx(5.0002)


# ------------------------------------------------------------------ Priority 4: Modal Overlap Tracking


def test_modal_overlap_tracking_resolves_mode_swapping_across_3_tiers(tmp_path: Path) -> None:
    # 3 mesh density tiers (iter 0, iter 1, iter 2)
    # Tier 0 (base): Mode 1 = 5.0 GHz (high substrate energy), Mode 2 = 5.8 GHz (high vacuum energy)
    # Tier 1 (adapt 1): Mode swapping happens!
    #   Mode 1 = 4.9 GHz (vacuum), Mode 2 = 5.002 GHz (substrate - this is our physical mode!)
    # Tier 2 (adapt 2):
    #   Mode 1 = 4.89 GHz (vacuum), Mode 2 = 5.003 GHz (substrate)

    dir0 = tmp_path / "tier0"
    dir1 = tmp_path / "tier1"
    dir2 = tmp_path / "tier2"
    for d in (dir0, dir1, dir2):
        d.mkdir()

    # Domain energies: Domain 1 = substrate, Domain 2 = vacuum
    it0 = AMRIteration(
        index=0,
        output_dir=dir0,
        modes=[
            Eigenmode(index=1, frequency_ghz=5.0),
            Eigenmode(index=2, frequency_ghz=5.8),
        ],
        global_error_indicator_percent=2.0,
        domain_energies={
            1: {"E_elec[1]": 0.95, "E_elec[2]": 0.05},
            2: {"E_elec[1]": 0.05, "E_elec[2]": 0.95},
        },
    )

    it1 = AMRIteration(
        index=1,
        output_dir=dir1,
        modes=[
            Eigenmode(index=1, frequency_ghz=4.9),  # vacuum mode swapped to index 1!
            Eigenmode(index=2, frequency_ghz=5.002),  # substrate physical mode swapped to index 2!
        ],
        global_error_indicator_percent=0.5,
        domain_energies={
            1: {"E_elec[1]": 0.05, "E_elec[2]": 0.95},  # vacuum
            2: {"E_elec[1]": 0.95, "E_elec[2]": 0.05},  # substrate
        },
    )

    it2 = AMRIteration(
        index=2,
        output_dir=dir2,
        modes=[
            Eigenmode(index=1, frequency_ghz=4.89),
            Eigenmode(index=2, frequency_ghz=5.003),
        ],
        global_error_indicator_percent=0.1,
        domain_energies={
            1: {"E_elec[1]": 0.05, "E_elec[2]": 0.95},
            2: {"E_elec[1]": 0.95, "E_elec[2]": 0.05},
        },
    )

    policy = AMRPolicy(indicator_tolerance_percent=1.0, frequency_drift_tolerance_percent=0.1)

    # Validate tracking: seed at 5.0 GHz
    conv = validate_amr_convergence([it0, it1, it2], policy, target_frequency_ghz=5.0)

    # Tracking must trace Mode 1 at tier 0 -> Mode 2 at tier 1 -> Mode 2 at tier 2
    assert conv.tracked_mode_indices == [1, 2, 2]
    assert conv.tracked_mode_frequencies_ghz == pytest.approx([5.0, 5.002, 5.003])
    # Overlap scores between stages must be near 1.0 because physical modes matched
    assert all(score > 0.9 for score in conv.modal_overlap_scores)

    # Drift on the tracked mode: |5.003 - 5.002| / 5.003 = 0.0199% < 0.1%
    assert conv.tracked_frequency_drift_percent is not None
    assert conv.tracked_frequency_drift_percent < 0.1
    assert conv.converged is True


def test_modal_overlap_tracking_rejects_unstable_eigenvalue(tmp_path: Path) -> None:
    dir0 = tmp_path / "tier0"
    dir1 = tmp_path / "tier1"
    dir0.mkdir()
    dir1.mkdir()

    it0 = AMRIteration(
        index=0,
        output_dir=dir0,
        modes=[Eigenmode(index=1, frequency_ghz=5.0)],
        global_error_indicator_percent=1.0,
    )
    it1 = AMRIteration(
        index=1,
        output_dir=dir1,
        modes=[Eigenmode(index=1, frequency_ghz=5.01)],  # 0.2% drift > 0.1% limit
        global_error_indicator_percent=0.1,
    )
    policy = AMRPolicy(indicator_tolerance_percent=1.0, frequency_drift_tolerance_percent=0.1)
    conv = validate_amr_convergence([it0, it1], policy, target_frequency_ghz=5.0)
    assert conv.converged is False
    assert "frequency drift" in conv.reason
