from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from textlayout.evidence.contract import EvidenceStatus
from textlayout.simulation.palace_verification import (
    DomainSweepPoint,
    IndependentReference,
    PalaceAMRLevel,
    PalaceVerificationStudy,
    SensitivitySweep,
    SweepCategory,
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


def _numerical_sweeps() -> list[SensitivitySweep]:
    return [
        SensitivitySweep(
            name=name,
            category=SweepCategory.NUMERICAL_DOMAIN,
            points=[
                DomainSweepPoint(
                    value_um=value,
                    frequency_ghz=frequency,
                    participation_by_region={"substrate": 0.9, "vacuum": 0.1},
                )
                for value, frequency in ((400, 6.0), (500, 6.0002), (700, 6.0004))
            ],
        )
        for name in (
            "vacuum_or_air_margin",
            "upper_boundary_distance",
            "lateral_boundary_margin",
        )
    ]


def _passing_study() -> PalaceVerificationStudy:
    levels = [_level("a", 6.001, 1.0), _level("b", 6.0005, 1.0001), _level("c", 6.0, 1.0002)]
    return PalaceVerificationStudy(
        design_id="passing",
        levels=levels,
        sweeps=_numerical_sweeps(),
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
        "all_numerical_domain_sweeps_complete",
        "independent_reference_target",
    }


def test_air_margin_sweep_alone_satisfies_its_numerical_gate() -> None:
    """A converged numerical-domain sweep passes; its per-sweep result says so."""
    report = assess_palace_verification(_passing_study())
    for result in report.numerical_domain_results:
        assert result.category is SweepCategory.NUMERICAL_DOMAIN
        assert result.passed is True
        assert result.frequency_sensitivity_percent is not None
        assert result.frequency_sensitivity_percent < 0.2


def test_physical_substrate_sensitivity_never_fails_numerical_convergence() -> None:
    """A 3% substrate-thickness frequency shift is physics, not divergence."""
    study = _passing_study()
    physical = SensitivitySweep(
        name="substrate_thickness",
        category=SweepCategory.PHYSICAL_PARAMETER,
        points=[
            DomainSweepPoint(
                value_um=value,
                frequency_ghz=frequency,
                participation_by_region={"substrate": 0.9, "vacuum": 0.1},
            )
            for value, frequency in ((250, 5.9), (300, 6.0), (350, 6.1))
        ],
    )
    report = assess_palace_verification(
        study.model_copy(update={"sweeps": [*study.sweeps, physical]})
    )
    assert report.status is EvidenceStatus.PHYSICS_VERIFIED
    assert "numerical_domain_frequency_sensitivity_percent" not in report.blockers
    named = {result.name: result for result in report.physical_sensitivity}
    assert named["substrate_thickness"].category is SweepCategory.PHYSICAL_PARAMETER
    assert named["substrate_thickness"].passed is None
    sensitivity = named["substrate_thickness"].frequency_sensitivity_percent
    assert sensitivity is not None and sensitivity > 2.0


def test_missing_numerical_domain_sweeps_still_block_convergence() -> None:
    study = _passing_study().model_copy(update={"sweeps": []})
    report = assess_palace_verification(study)
    assert "all_numerical_domain_sweeps_complete" in report.blockers
    assert "numerical_domain_frequency_sensitivity_percent" in report.blockers


def test_physical_sweep_never_satisfies_a_required_numerical_sweep() -> None:
    """Recategorising a required sweep as physical must not sneak it past the gate."""
    study = _passing_study()
    recategorised = [
        sweep.model_copy(update={"category": SweepCategory.PHYSICAL_PARAMETER})
        for sweep in study.sweeps
    ]
    report = assess_palace_verification(study.model_copy(update={"sweeps": recategorised}))
    assert "all_numerical_domain_sweeps_complete" in report.blockers


def test_similarity_gate_uses_regional_energy_terminology() -> None:
    report = assess_palace_verification(_passing_study())
    names = {gate.name for gate in report.gates}
    assert "regional_energy_mode_similarity" in names
    assert "electric_and_magnetic_mode_overlap" not in names
    gate = next(g for g in report.gates if g.name == "regional_energy_mode_similarity")
    assert "not spatial field overlap" in gate.detail


def test_committed_report_is_deterministically_current() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_palace_amr_benchmark.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
