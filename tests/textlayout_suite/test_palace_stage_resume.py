"""Synthetic orchestration fixtures; no mesh, solver or physics certification."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from textlayout.fem.gmsh_physical import GmshMeshResult
from textlayout.simulation import resource_sampler
from textlayout.solvers.palace import benchmark_v017 as b
from textlayout.solvers.palace.backend import DEFAULT_LAYOUT
from textlayout.solvers.palace.models import PalaceBoundedAMRPolicy, PalaceCapability, PalaceRun


def synthetic_mesh(geometry, params, model, output_path, **kwargs):
    path = Path(output_path)
    path.write_text("SYNTHETIC CONTROL FLOW FIXTURE, NOT A MESH\n")
    return GmshMeshResult(path, 0, 1, 1, 1)


def synthetic_solve(capability, *, run_dir, **kwargs):
    postpro = run_dir / "postpro"
    postpro.mkdir()
    files = {
        "palace_amr.json": "{}",
        "palace.stdout.txt": "Completed adaptive mesh refinement\n",
        "palace.stderr.txt": "",
        "resource_summary.json": json.dumps(
            {
                "termination_reason": None,
                "orphan_processes_remaining": False,
            }
        ),
        "postpro/eig.csv": "m,Re{f} (GHz)\n1,5.0\n",
        "postpro/domain-E.csv": "synthetic domain fixture\n",
        "postpro/error-indicators.csv": "Norm\n0.001\n",
        "postpro/palace.json": "{}",
        "postpro/palace_resolved.json": "{}",
        "postpro/adapted.mesh": "synthetic adapted mesh fixture\n",
    }
    for name, value in files.items():
        (run_dir / name).write_text(value)
    config = run_dir / "palace_amr.json"
    run = PalaceRun(
        command=["synthetic-solver-not-executed"],
        return_code=0,
        runtime_seconds=0,
        stdout_path=run_dir / "palace.stdout.txt",
        stderr_path=run_dir / "palace.stderr.txt",
        output_dir=run_dir,
        output_file_hashes=b.relative_hashes([run_dir / name for name in files], run_dir.parent),
    )
    return config, postpro, run, {}


@pytest.fixture
def workflow(monkeypatch):
    # Explicit synthetic resource budget makes control-flow tests host-independent.
    def memory():
        return {"total_mb": 16384, "available_mb": 12288, "used_mb": 4096}

    monkeypatch.setattr(b, "read_memory_budget", memory)
    monkeypatch.setattr(resource_sampler, "read_memory_budget", memory)
    monkeypatch.setattr(
        resource_sampler.shutil, "disk_usage", lambda path: SimpleNamespace(free=100 * 1024**3)
    )
    monkeypatch.setattr(b, "mesh_quarter_wave", synthetic_mesh)
    monkeypatch.setattr(b, "_gmsh_identity", lambda: {"version": "synthetic"})
    monkeypatch.setattr(b, "_install_record", lambda root: None)
    solver = Mock(side_effect=synthetic_solve)
    monkeypatch.setattr(b, "_run_palace_once", solver)
    args = dict(
        layout_path=DEFAULT_LAYOUT,
        capability=PalaceCapability(
            executable="/synthetic/not-executed",
            version="0.17.0",
            executable_sha256="0" * 64,
        ),
        processes=1,
    )
    return args, solver


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("bounded", [False, True])
def test_mesh_then_amr_executes_once_and_completed_amr_is_reused(tmp_path, workflow, bounded):
    args, solver = workflow
    if bounded:
        args["amr"] = b.AMRSettings(
            bounded_policy=PalaceBoundedAMRPolicy(
                solved_states=2,
                max_rss_bytes=64 * 1024**2,
            )
        )
    first = b.run_quarter_wave_benchmark_v017(tmp_path, stop_after_stage="base_mesh", **args)
    assert first.status == "STAGE_COMPLETE", first.reason
    solver.assert_not_called()
    mesh = (tmp_path / "base_mesh/quarter_wave_base.msh").read_bytes()
    for index in range(2):
        result = b.run_quarter_wave_benchmark_v017(
            tmp_path,
            from_stage="base_amr",
            stop_after_stage="base_amr",
            **args,
        )
        assert result.status == "STAGE_COMPLETE", result.reason
        assert solver.call_count == 1
        record = json.loads((tmp_path / "stages/base_amr.json").read_text())
        assert record["status"] == ("complete" if index == 0 else "reused")
        assert (tmp_path / "base_mesh/quarter_wave_base.msh").read_bytes() == mesh


@pytest.mark.parametrize("change", ["mesh", "profile", "tool", "partial", "started", "missing"])
def test_resume_rejects_changed_or_partial_state_without_writing(tmp_path, workflow, change):
    args, solver = workflow
    b.run_quarter_wave_benchmark_v017(tmp_path, stop_after_stage="base_mesh", **args)
    if change == "mesh":
        (tmp_path / "base_mesh/quarter_wave_base.msh").write_text("changed")
    elif change == "profile":
        args["amr"] = b.AMRSettings(update_fraction=0.2)
    elif change == "tool":
        args["capability"] = args["capability"].model_copy(update={"executable_sha256": "1" * 64})
    elif change == "partial":
        (tmp_path / "base_mesh/palace.stdout.txt").write_text("incomplete")
    elif change == "started":
        b.write_stage_record(
            tmp_path, stage="base_amr", status="started", capability=args["capability"]
        )
    else:
        (tmp_path / "resume_profile.json").unlink()
    before = snapshot(tmp_path)
    result = b.run_quarter_wave_benchmark_v017(
        tmp_path,
        from_stage="base_amr",
        stop_after_stage="base_amr",
        **args,
    )
    assert result.status == "SIMULATION_INVALID"
    assert result.reason.startswith("resume rejected:")
    solver.assert_not_called()
    assert snapshot(tmp_path) == before


def test_interrupted_solver_is_not_launched_again(tmp_path, workflow):
    args, solver = workflow
    b.run_quarter_wave_benchmark_v017(tmp_path, stop_after_stage="base_mesh", **args)
    solver.side_effect = RuntimeError("synthetic interruption before output")
    result = b.run_quarter_wave_benchmark_v017(tmp_path, from_stage="base_amr", **args)
    assert result.status == "SIMULATION_INVALID"
    before = snapshot(tmp_path)
    second = b.run_quarter_wave_benchmark_v017(tmp_path, from_stage="base_amr", **args)
    assert second.status == "SIMULATION_INVALID"
    assert solver.call_count == 1
    assert snapshot(tmp_path) == before


def test_completed_output_corruption_is_rejected(tmp_path, workflow):
    args, solver = workflow
    b.run_quarter_wave_benchmark_v017(tmp_path, stop_after_stage="base_amr", **args)
    (tmp_path / "base_mesh/postpro/eig.csv").write_text("corrupted")
    before = snapshot(tmp_path)
    result = b.run_quarter_wave_benchmark_v017(tmp_path, from_stage="base_amr", **args)
    assert result.status == "SIMULATION_INVALID"
    assert solver.call_count == 1
    assert snapshot(tmp_path) == before


def test_completed_amr_still_requires_strict_solver_validation(tmp_path, workflow):
    args, solver = workflow
    b.run_quarter_wave_benchmark_v017(tmp_path, stop_after_stage="base_amr", **args)
    stdout = tmp_path / "base_mesh/palace.stdout.txt"
    stdout.write_text("solver did not complete")
    # Matching hashes cannot replace the solver completion contract.
    record_path = tmp_path / "stages/base_amr.json"
    record = json.loads(record_path.read_text())
    record["output_hashes"]["base_mesh/palace.stdout.txt"] = b.sha256_file(stdout)
    record_path.write_text(json.dumps(record))
    before = snapshot(tmp_path)
    result = b.run_quarter_wave_benchmark_v017(tmp_path, from_stage="base_amr", **args)
    assert result.status == "SIMULATION_INVALID"
    assert "completion line" in result.reason
    assert solver.call_count == 1
    assert snapshot(tmp_path) == before
