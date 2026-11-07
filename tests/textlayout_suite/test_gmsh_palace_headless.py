"""Gmsh pipeline and headless Palace backend: honest statuses when solvers are absent."""

from __future__ import annotations

import builtins
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from textlayout.evidence.contract import EvidenceStatus
from textlayout.mesh.gmsh_pipeline import (
    MeshControls,
    MeshManifest,
    SubstrateStack,
    gmsh_available,
    mesh_geometry,
    write_geo_script,
)
from textlayout.models import Geometry, rectangle
from textlayout.simulation.backends.palace import (
    AMRIteration,
    AMRPolicy,
    PalaceEigenmodeRequest,
    build_eigenmode_config,
    collect_amr_iterations,
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


@pytest.fixture
def no_gmsh(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "gmsh" or name.startswith("gmsh."):
            raise ImportError("gmsh hidden for test")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "gmsh", raising=False)


def _absent() -> PalaceCapability:
    return PalaceCapability(unavailable_reason="Palace absent for test")


def _fake_palace(tmp_path: Path, body: str) -> PalaceCapability:
    tmp_path.mkdir(parents=True, exist_ok=True)
    script = tmp_path / "fake_palace_impl.py"
    script.write_text(body, encoding="utf-8")
    if os.name == "nt":
        shim = tmp_path / "fake_palace.bat"
        shim.write_text(f'@echo off\n"{sys.executable}" "{script}" %*\n', encoding="ascii")
    else:
        shim = tmp_path / "fake_palace.sh"
        shim.write_text(f'#!/bin/sh\n"{sys.executable}" "{script}" "$@"\n', encoding="ascii")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    return PalaceCapability(
        execution_kind="executable",
        executable=str(shim),
        version="0.test",
        executable_sha256="a" * 64,
    )


def _eig(path: Path, freqs: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["m,Re{f} (GHz),Im{f} (GHz),Q,Error (Bkwd.),Error (Abs.)"]
    for i, f in enumerate(freqs, start=1):
        lines.append(f"{i},{f},1e-6,1e6,1e-16,1e-10")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _indicator(path: Path, norm: float) -> None:
    path.write_text(f"Norm,Minimum,Maximum,Mean\n{norm},0,0,0\n", encoding="utf-8")


# ------------------------------------------------------------------ Gmsh pipeline


def test_mesh_pipeline_without_gmsh_prepares_geo_and_reports_absence(
    tmp_path: Path, no_gmsh: None
) -> None:
    manifest = mesh_geometry(CPW, STACK, tmp_path / "model.msh", controls=COARSE)
    assert manifest.status == "SKIPPED_SOLVER_ABSENT"
    assert manifest.mesh_path is None and not manifest.mesh_available
    assert manifest.geo_path is not None and manifest.geo_path.is_file()
    geo = manifest.geo_path.read_text(encoding="utf-8")
    assert 'SetFactory("OpenCASCADE")' in geo and 'Physical Surface("metal", 10)' in geo
    assert manifest.metal_polygon_count == 3
    assert manifest.attributes == {
        "substrate": 1,
        "vacuum": 2,
        "metal": 10,
        "enclosure": 11,
        "interface": 20,
    }


def test_mesh_pipeline_filters_metal_layers_and_rejects_empty_geometry(tmp_path: Path) -> None:
    stack = STACK.model_copy(update={"metal_layers": ("M2",)})
    geo = write_geo_script(CPW, stack, COARSE, tmp_path / "x.geo")
    assert "Plane Surface" not in geo.read_text(encoding="utf-8")
    manifest = mesh_geometry(Geometry("empty", ()), STACK, tmp_path / "empty.msh")
    assert manifest.status == "FAILED" and "no polygons" in (manifest.reason or "")


def test_mesh_controls_validation() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        MeshControls(characteristic_length_um=10.0, metal_edge_length_um=20.0)
    refined = COARSE.refined(2.0)
    assert refined.characteristic_length_um == 40.0 and refined.metal_edge_length_um == 5.0
    with pytest.raises(ValueError, match="at least 10%"):
        SubstrateStack(substrate_thickness_um=500.0, vacuum_height_um=10.0)


@pytest.mark.skipif(not gmsh_available(), reason="gmsh SDK not installed (install the `fem` extra)")
def test_mesh_pipeline_with_gmsh_is_deterministic_and_labelled(tmp_path: Path) -> None:
    first = mesh_geometry(CPW, STACK, tmp_path / "a.msh", controls=COARSE)
    second = mesh_geometry(CPW, STACK, tmp_path / "b.msh", controls=COARSE)
    assert first.status == second.status == "MESH_GENERATED"
    assert first.mesh_sha256 == second.mesh_sha256
    assert first.element_count and first.element_count > 0
    assert first.minimum_quality is not None and 0.0 < first.minimum_quality <= 1.0
    text = first.mesh_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    for name in ('"substrate"', '"vacuum"', '"metal"', '"enclosure"', '"interface"'):
        assert name in text


# -------------------------------------------------------------- Palace backend


def test_eigenmode_config_uses_manifest_attributes(tmp_path: Path) -> None:
    mesh = tmp_path / "m.msh"
    mesh.write_text("mesh", encoding="utf-8")
    manifest = MeshManifest(status="MESH_GENERATED", mesh_path=mesh, stack=STACK, controls=COARSE)
    config = build_eigenmode_config(
        manifest, PalaceEigenmodeRequest(mode_count=3, target_frequency_ghz=5.0)
    )
    assert config["Model"]["Mesh"] == "m.msh" and config["Model"]["L0"] == 1e-6
    assert config["Boundaries"]["PEC"]["Attributes"] == [10, 11]
    assert config["Domains"]["Materials"][0]["Permittivity"] == STACK.epsilon_r
    assert config["Solver"]["Eigenmode"] == {"N": 3, "Tol": 1e-8, "Target": 5.0, "Save": 0}
    assert config["Model"]["Refinement"]["MaxIts"] == 2
    with pytest.raises(ValueError, match="no mesh_path"):
        build_eigenmode_config(
            MeshManifest(status="SKIPPED_SOLVER_ABSENT", stack=STACK, controls=COARSE),
            PalaceEigenmodeRequest(),
        )


def test_amr_convergence_gates() -> None:
    policy = AMRPolicy(indicator_tolerance_percent=2.0, frequency_drift_tolerance_percent=0.5)

    def it(index: int, f: float, norm: float | None) -> AMRIteration:
        return AMRIteration(
            index=index,
            output_dir=Path("."),
            modes=[Eigenmode(index=1, frequency_ghz=f)],
            global_error_indicator_percent=norm,
        )

    assert validate_amr_convergence([], policy).converged is False
    single = validate_amr_convergence([it(0, 5.0, 1.0)], policy)
    assert single.converged is False and "single solved state" in single.reason
    good = validate_amr_convergence([it(0, 5.00, 5.0), it(1, 5.01, 1.0)], policy)
    assert good.converged is True
    assert good.max_frequency_drift_percent == pytest.approx(0.01 / 5.01 * 100.0)
    drift = validate_amr_convergence([it(0, 5.0, 5.0), it(1, 5.2, 1.0)], policy)
    assert drift.converged is False and "frequency drift" in drift.reason
    noisy = validate_amr_convergence([it(0, 5.0, 5.0), it(1, 5.001, 3.0)], policy)
    assert noisy.converged is False and "error indicator" in noisy.reason
    missing = validate_amr_convergence([it(0, 5.0, None), it(1, 5.001, None)], policy)
    assert missing.converged is False and "indicator missing" in missing.reason


def test_collect_amr_iterations_orders_subdirectories_then_final(tmp_path: Path) -> None:
    postpro = tmp_path / "postpro"
    _eig(postpro / "iteration2" / "eig.csv", [5.02])
    _eig(postpro / "iteration_1" / "eig.csv", [5.1])
    _eig(postpro / "eig.csv", [5.021])
    _indicator(postpro / "error-indicators.csv", 0.005)
    iterations = collect_amr_iterations(postpro)
    assert [i.modes[0].frequency_ghz for i in iterations] == [5.1, 5.02, 5.021]
    assert iterations[-1].global_error_indicator_percent == pytest.approx(0.5)
    assert collect_amr_iterations(tmp_path / "nowhere") == []


def test_run_eigenmode_without_gmsh_is_skipped_solver_absent(tmp_path: Path, no_gmsh: None) -> None:
    result = run_eigenmode(CPW, STACK, tmp_path, controls=COARSE, capability=_absent())
    assert result.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT
    assert result.audit_level == "INPUT_PREPARED"
    assert result.config_path is None and result.modes == []
    payload = json.loads((tmp_path / "palace_eigenmode.json").read_text(encoding="utf-8"))
    assert payload["status"] == "SKIPPED_SOLVER_ABSENT"
    assert payload["schema"] == "textlayout.palace-eigenmode.v1"


@pytest.mark.skipif(not gmsh_available(), reason="gmsh SDK not installed (install the `fem` extra)")
def test_run_eigenmode_with_mesh_but_no_palace_prepares_input(tmp_path: Path) -> None:
    result = run_eigenmode(CPW, STACK, tmp_path, controls=COARSE, capability=_absent())
    assert result.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT
    assert result.config_path is not None and result.config_path.is_file()
    assert "Palace absent" in (result.reason or "")
    prepared = run_eigenmode(
        CPW,
        STACK,
        tmp_path / "prep",
        controls=COARSE,
        capability=_fake_palace(tmp_path, "pass"),
        execute=False,
    )
    assert prepared.status is EvidenceStatus.SIMULATION_INPUT_PREPARED


@pytest.mark.skipif(not gmsh_available(), reason="gmsh SDK not installed (install the `fem` extra)")
def test_run_eigenmode_parses_converged_and_failed_fake_runs(tmp_path: Path) -> None:
    converged = _fake_palace(
        tmp_path / "ok",
        "import pathlib\n"
        "p = pathlib.Path('postpro'); (p / 'iteration1').mkdir(parents=True)\n"
        "hdr = 'm,Re{f} (GHz),Im{f} (GHz),Q,Error (Bkwd.),Error (Abs.)\\n'\n"
        "(p / 'iteration1' / 'eig.csv').write_text(hdr + '1,5.00,1e-6,1e6,0,0\\n')\n"
        "(p / 'eig.csv').write_text(hdr + '1,5.01,1e-6,1e6,0,0\\n')\n"
        "(p / 'error-indicators.csv').write_text('Norm,Minimum,Maximum,Mean\\n0.005,0,0,0\\n')\n",
    )
    result = run_eigenmode(CPW, STACK, tmp_path / "ok", controls=COARSE, capability=converged)
    assert result.status is EvidenceStatus.SIMULATION_EXECUTED
    assert result.audit_level == "NUMERICALLY_CONVERGED"
    assert result.modes[0].frequency_ghz == pytest.approx(5.01)
    assert result.amr is not None and result.amr.converged

    exploded = _fake_palace(tmp_path / "bad", "import sys; sys.exit(3)")
    failed = run_eigenmode(CPW, STACK, tmp_path / "bad", controls=COARSE, capability=exploded)
    assert failed.status is EvidenceStatus.FAILED and failed.return_code == 3

    silent = _fake_palace(tmp_path / "silent", "print('done')")
    empty = run_eigenmode(CPW, STACK, tmp_path / "silent", controls=COARSE, capability=silent)
    assert empty.status is EvidenceStatus.FAILED and "no eig.csv" in (empty.reason or "")

    single = _fake_palace(
        tmp_path / "single",
        "import pathlib\np = pathlib.Path('postpro'); p.mkdir()\n"
        "(p / 'eig.csv').write_text('m,Re{f} (GHz)\\n1,5.0\\n')\n",
    )
    unconverged = run_eigenmode(CPW, STACK, tmp_path / "single", controls=COARSE, capability=single)
    assert unconverged.status is EvidenceStatus.CONVERGENCE_FAILED
    assert unconverged.audit_level == "OUTPUT_PARSED"
