"""Open-source solver execution: graceful detection, parsing, and the
physics-verified gate. These run without any solver installed by exercising the
parsers on synthetic solver output and the missing-solver path directly.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import (
    SimulationResult,
    extract_resonance_from_touchstone,
    parse_fasthenry_inductance,
    prepare_spiral_fasthenry,
    run_fasthenry,
    run_openems,
    simulate_layout,
)

ROOT = Path(__file__).resolve().parents[2]


def _spiral_prepared(tmp_path: Path) -> SimulationResult:
    spec = LayoutSpec.model_validate(
        json.loads((ROOT / "examples/benchmarks/03_spiral_inductor/layout.json").read_text("utf-8"))
    )
    wf = build_default_workflow()
    built = wf.run(spec, formats=())
    return prepare_spiral_fasthenry(spec, built.geometry, wf.technology(spec.technology), tmp_path)


# --- Graceful missing-solver behaviour ---------------------------------------
def test_fasthenry_missing_is_graceful(tmp_path: Path) -> None:
    prepared = _spiral_prepared(tmp_path)
    result = run_fasthenry(prepared, executable="fasthenry-does-not-exist")
    assert result.status == "skipped"
    assert result.evidence_stage == "solver_missing"
    assert result.physics_verified is False
    assert "result" not in result.artifacts


def test_openems_missing_touchstone_is_graceful(tmp_path: Path) -> None:
    spec = LayoutSpec.model_validate(
        json.loads(
            (ROOT / "examples/benchmarks/04_quarter_wave_resonator/layout.json").read_text("utf-8")
        )
    )
    wf = build_default_workflow()
    built = wf.run(spec, formats=())
    result = simulate_layout(
        spec, built.geometry, wf.technology(spec.technology), tmp_path,
        solver="openems", execute=True,
    )
    # No Touchstone and no CSXCAD model generator yet -> honest non-result.
    assert result.physics_verified is False
    assert result.evidence_stage in {"solver_missing", "failed_gracefully"}


# --- Parsers on synthetic solver output --------------------------------------
def test_parse_fasthenry_inductance_from_synthetic_zc_mat() -> None:
    # 10 nH at 1 MHz -> reactance X = 2*pi*f*L = 0.06283 ohm.
    x = 2 * math.pi * 1e6 * 10e-9
    zc = f"Impedance matrix for frequency = 1e+06 1 x 1\n0.0123  {x:.8e}\n"
    inductance = parse_fasthenry_inductance(zc)
    assert inductance == pytest.approx(10e-9, rel=1e-6)


def test_extract_resonance_from_touchstone_notch(tmp_path: Path) -> None:
    # Synthetic 2-port S21 magnitude with a deep notch at 6 GHz.
    s2p = tmp_path / "resonator.s2p"
    lines = ["# GHz S MA R 50"]
    for i in range(41):
        f_ghz = 5.0 + i * 0.05  # 5.0 .. 7.0 GHz
        s21 = abs(f_ghz - 6.0) / 2.0 + 0.01  # minimum at 6 GHz
        lines.append(f"{f_ghz:.4f} 1.0 180 {s21:.4f} 0 {s21:.4f} 0 1.0 180")
    s2p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    resonance = extract_resonance_from_touchstone(s2p)
    assert resonance == pytest.approx(6.0, abs=0.05)


# --- Full execution path with a synthetic Touchstone (compared + verified) ----
def test_openems_post_processing_sets_physics_verified(tmp_path: Path) -> None:
    s2p = tmp_path / "model.s2p"
    lines = ["# GHz S MA R 50"]
    for i in range(41):
        f_ghz = 5.0 + i * 0.05
        s21 = abs(f_ghz - 6.0) / 2.0 + 0.01
        lines.append(f"{f_ghz:.4f} 1.0 180 {s21:.4f} 0 {s21:.4f} 0 1.0 180")
    s2p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    prepared = SimulationResult(
        status="input_files_prepared", solver="openEMS", readiness_level=2,
        reason="prepared", output_dir=tmp_path, artifacts={},
    )
    result = run_openems(prepared, target_frequency_ghz=6.0, touchstone=s2p)
    assert result.status == "executed"
    assert result.evidence_stage == "compared"
    assert result.extracted_quantities["resonance_frequency_ghz"] == pytest.approx(6.0, abs=0.05)
    assert result.target_comparison["within_tolerance"] is True
    assert result.physics_verified is True


def test_openems_off_target_is_not_physics_verified(tmp_path: Path) -> None:
    s2p = tmp_path / "model.s2p"
    lines = ["# GHz S MA R 50"]
    for i in range(41):
        f_ghz = 5.0 + i * 0.05
        s21 = abs(f_ghz - 5.2) / 2.0 + 0.01  # notch far from a 6 GHz target
        lines.append(f"{f_ghz:.4f} 1.0 180 {s21:.4f} 0 {s21:.4f} 0 1.0 180")
    s2p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    prepared = SimulationResult(
        status="input_files_prepared", solver="openEMS", readiness_level=2,
        reason="prepared", output_dir=tmp_path, artifacts={},
    )
    result = run_openems(prepared, target_frequency_ghz=6.0, touchstone=s2p)
    assert result.status == "executed"  # it ran and parsed
    assert result.target_comparison["within_tolerance"] is False
    assert result.physics_verified is False  # parsed but out of tolerance


# --- The physics-verified gate itself ----------------------------------------
def test_physics_verified_requires_execution_and_comparison() -> None:
    prepared = SimulationResult("input_files_prepared", "openEMS", 2, "prepared")
    assert prepared.physics_verified is False
    assert prepared.evidence_stage == "input_prepared"

    executed_no_compare = SimulationResult(
        "executed", "FasterCap", 3, "ran", extracted_quantities={"c": 1.0}
    )
    assert executed_no_compare.evidence_stage == "parsed"
    assert executed_no_compare.physics_verified is False  # no target comparison

    compared = SimulationResult(
        "executed", "FasterCap", 4, "ran",
        extracted_quantities={"c": 1.0},
        target_comparison={"within_tolerance": True},
    )
    assert compared.evidence_stage == "compared"
    assert compared.physics_verified is True
