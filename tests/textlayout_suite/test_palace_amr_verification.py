from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from textlayout.evidence.contract import EvidenceStatus
from textlayout.simulation.palace_verification import (
    DomainSweep,
    DomainSweepPoint,
    IndependentReference,
    PalaceAMRLevel,
    PalaceVerificationStudy,
    assess_palace_verification,
    build_amr_config,
)

ROOT = Path(__file__).resolve().parents[2]
REPORT = (
    ROOT
    / "examples"
    / "solver_benchmarks"
    / "palace_cpw_quarter_wave"
    / "evidence"
    / "amr_verification.json"
)


def _level(tag: str, frequency: float, scale: float) -> PalaceAMRLevel:
    return PalaceAMRLevel(
        tag=tag,
        refinement_kind="adaptive",
        polynomial_order=2,
        frequency_ghz=frequency,
        global_error_indicator_percent=0.1,
        element_error_indicator_file=f"{tag}/indicator.gf",
        element_error_indicator_sha256=(tag.encode().hex() + "0" * 64)[:64],
        energy_normalization_error_percent=0.01,
        electric_energy_by_region={"substrate": 0.9 * scale, "vacuum": 0.1},
        magnetic_energy_by_region={"substrate": 0.5 * scale, "vacuum": 0.5},
        participation_by_region={"substrate": 0.9 * scale, "vacuum": 0.1},
        output_file_hashes={f"{tag}/eig.csv": "1" * 64},
    )


def _passing_study() -> PalaceVerificationStudy:
    levels = [_level("a", 6.001, 1.0), _level("b", 6.0005, 1.0001), _level("c", 6.0, 1.0002)]
    sweeps = [
        DomainSweep(
            name=name,
            points=[
                DomainSweepPoint(value_um=value, frequency_ghz=frequency)
                for value, frequency in ((400, 6.0), (500, 6.0002), (700, 6.0004))
            ],
        )
        for name in ("vacuum_domain", "substrate_thickness", "package_height", "lateral_boundary")
    ]
    return PalaceVerificationStudy(
        design_id="passing",
        levels=levels,
        sweeps=sweeps,
        independent_reference=IndependentReference(
            name="independent",
            method="independent solver",
            frequency_ghz=6.0,
            artifact_sha256="a" * 64,
        ),
    )


def test_amr_config_uses_palace_native_refinement_schema() -> None:
    config = build_amr_config(
        {"Problem": {"Type": "Eigenmode"}, "Model": {"Mesh": "cpw.msh"}, "Solver": {}},
        output="postpro_amr",
        polynomial_order=2,
    )
    assert config["Model"]["Refinement"] == {
        "Tol": 0.005,
        "MaxIts": 6,
        "UpdateFraction": 0.7,
        "Nonconformal": True,
        "SaveAdaptIterations": True,
        "SaveAdaptMesh": True,
    }
    assert config["Solver"]["Order"] == 2
    assert config["Problem"]["OutputFormats"]["GridFunction"] is True


def test_all_required_gates_can_promote_a_real_complete_study() -> None:
    report = assess_palace_verification(_passing_study())
    assert report.status is EvidenceStatus.PHYSICS_VERIFIED
    assert report.promoted_frequency_ghz == 6.0
    assert report.blockers == []


def test_missing_sweeps_and_amr_outputs_never_promote_existing_frequency() -> None:
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    assert payload["candidate_frequency_ghz"] == 5.709556059993
    assert payload["promoted_frequency_ghz"] is None
    assert payload["status"] == EvidenceStatus.SIMULATION_EXECUTED.value
    assert set(payload["blockers"]) >= {
        "palace_adaptive_mesh_refinement",
        "element_wise_error_indicators_recorded",
        "all_domain_sweeps_complete",
        "independent_reference_target",
    }


def test_committed_report_is_deterministically_current() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_palace_amr_benchmark.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
