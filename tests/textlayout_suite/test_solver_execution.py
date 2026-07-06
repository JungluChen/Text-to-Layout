"""Open-source solver execution: graceful detection, parsing, and the
physics-verified gate. These run without any solver installed by exercising the
parsers on synthetic solver output and the missing-solver path directly.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import pytest

from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import (
    SimulationResult,
    extract_resonance_from_touchstone,
    parse_josim_csv,
    parse_fasthenry_inductance,
    prepare_spiral_fasthenry,
    run_fasthenry,
    run_openems,
    run_josim,
    simulate_layout,
)
from textlayout.simulation.adapters import adapter_for

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "component",
    ["IDC", "CPW", "SpiralInductor", "QuarterWaveResonator", "SQUID"],
)
def test_registered_solver_adapters_share_four_method_shape(component: str) -> None:
    adapter = adapter_for(LayoutSpec(component=component, parameters={}))
    for method in (
        "available",
        "prepare",
        "run",
        "parse",
        "verify",
        "to_evidence",
    ):
        assert callable(getattr(adapter, method))


def _spiral_prepared(tmp_path: Path) -> SimulationResult:
    spec = LayoutSpec.model_validate(
        json.loads((ROOT / "examples/benchmarks/03_spiral_inductor/layout.json").read_text("utf-8"))
    )
    wf = build_default_workflow()
    built = wf.run(spec, formats=())
    return prepare_spiral_fasthenry(spec, built.geometry, wf.technology(spec.technology), tmp_path)


def _fake_executable(tmp_path: Path, name: str, body: list[str]) -> str:
    """Create a platform-native executable; the adapter still uses subprocess."""
    if sys.platform == "win32":
        path = tmp_path / f"{name}.bat"
        path.write_text("@echo off\n" + "\n".join(body) + "\n", encoding="ascii")
    else:
        path = tmp_path / name
        path.write_text("#!/bin/sh\nset -eu\n" + "\n".join(body) + "\n", encoding="ascii")
        os.chmod(path, 0o755)
    return str(path)


# --- Graceful missing-solver behaviour ---------------------------------------
def test_fasthenry_missing_is_graceful(tmp_path: Path) -> None:
    prepared = _spiral_prepared(tmp_path)
    result = run_fasthenry(prepared, executable="fasthenry-does-not-exist")
    assert result.status == "skipped"
    assert result.evidence_stage == "solver_missing"
    assert result.physics_verified is False
    assert "result" not in result.artifacts


def test_openems_missing_touchstone_is_graceful(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force solver absence regardless of what this machine has installed:
    # pointing the discovery env vars at a nonexistent path short-circuits
    # the PATH/.tools/WSL fallback. Without this, the test launches a real
    # multi-minute FDTD run on machines with a working openEMS stack.
    monkeypatch.setenv("TEXTLAYOUT_OPENEMS", str(tmp_path / "no-such-octave"))
    monkeypatch.setenv("TEXTLAYOUT_OPENEMS_CORE", str(tmp_path / "no-such-openems"))
    spec = LayoutSpec.model_validate(
        json.loads(
            (ROOT / "examples/benchmarks/04_quarter_wave_resonator/layout.json").read_text("utf-8")
        )
    )
    wf = build_default_workflow()
    built = wf.run(spec, formats=())
    result = simulate_layout(
        spec,
        built.geometry,
        wf.technology(spec.technology),
        tmp_path,
        solver="openems",
        execute=True,
    )
    # No solver available -> honest non-result, never a fabricated Touchstone.
    assert result.physics_verified is False
    assert result.evidence_stage in {"solver_missing", "failed_gracefully"}


def test_cpw_openems_driver_uses_native_cpw_ports(tmp_path: Path) -> None:
    spec = LayoutSpec.model_validate(
        json.loads((ROOT / "examples/benchmarks/02_cpw_50ohm/layout.json").read_text("utf-8"))
    )
    wf = build_default_workflow()
    built = wf.run(spec, formats=())
    prepared = simulate_layout(
        spec,
        built.geometry,
        wf.technology(spec.technology),
        tmp_path,
        solver="openems",
        execute=False,
    )
    driver = Path(prepared.artifacts["driver"]).read_text(encoding="utf-8")
    assert "AddCPWPort" in driver
    assert "RunOpenEMS" in driver


# --- Parsers on synthetic solver output --------------------------------------
def test_parse_fasthenry_inductance_from_synthetic_zc_mat() -> None:
    # 10 nH at 1 MHz -> reactance X = 2*pi*f*L = 0.06283 ohm.
    x = 2 * math.pi * 1e6 * 10e-9
    zc = f"Impedance matrix for frequency = 1e+06 1 x 1\n0.0123  {x:.8e}\n"
    inductance = parse_fasthenry_inductance(zc)
    assert inductance == pytest.approx(10e-9, rel=1e-6)


def test_fasthenry_present_uses_real_subprocess_and_parser(tmp_path: Path) -> None:
    x = 2 * math.pi * 1e6 * 3e-9
    if sys.platform == "win32":
        body = [
            "> Zc.mat echo Impedance matrix for frequency = 1e+06 1 x 1",
            f">> Zc.mat echo 0.01 {x:.12g}",
        ]
    else:
        body = [
            "printf '%s\\n' 'Impedance matrix for frequency = 1e+06 1 x 1' "
            f"'0.01 {x:.12g}' > Zc.mat"
        ]
    fake = _fake_executable(tmp_path, "fake_fasthenry", body)
    result = run_fasthenry(
        _spiral_prepared(tmp_path / "run"),
        executable=fake,
        target_inductance_h=3e-9,
    )
    assert result.status == "executed"
    assert result.physics_verified is True
    assert result.extracted_quantities["inductance_nh"] == pytest.approx(3.0, rel=1e-5)


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
        status="input_files_prepared",
        solver="openEMS",
        readiness_level=2,
        reason="prepared",
        output_dir=tmp_path,
        artifacts={},
    )
    result = run_openems(prepared, target_frequency_ghz=6.0, touchstone=s2p)
    assert result.status == "executed"
    assert result.evidence_stage == "compared"
    assert result.extracted_quantities["resonance_frequency_ghz"] == pytest.approx(6.0, abs=0.05)
    assert result.target_comparison["within_tolerance"] is True
    assert result.physics_verified is True


def test_openems_present_uses_real_subprocess_and_touchstone_parser(tmp_path: Path) -> None:
    spec = LayoutSpec.model_validate(
        json.loads(
            (ROOT / "examples/benchmarks/04_quarter_wave_resonator/layout.json").read_text("utf-8")
        )
    )
    wf = build_default_workflow()
    built = wf.run(spec, formats=())
    prepared = simulate_layout(
        spec,
        built.geometry,
        wf.technology(spec.technology),
        tmp_path / "run",
        solver="openems",
        execute=False,
    )
    driver = Path(prepared.artifacts["driver"]).read_text(encoding="utf-8")
    assert "RunOpenEMS" in driver
    assert "AddLumpedPort" in driver
    rows = ["# GHz S MA R 50"]
    for i in range(21):
        f_ghz = 5.5 + i * 0.05
        s21 = abs(f_ghz - 6.0) + 0.01
        rows.append(f"{f_ghz} 1 180 {s21} 0 {s21} 0 1 180")
    if sys.platform == "win32":
        body = [f"> openems_result.s2p echo {rows[0]}"] + [
            f">> openems_result.s2p echo {row}" for row in rows[1:]
        ]
    else:
        quoted = " ".join(repr(row) for row in rows)
        body = [f"printf '%s\\n' {quoted} > openems_result.s2p"]
    fake = _fake_executable(tmp_path, "fake_octave", body)
    result = run_openems(prepared, target_frequency_ghz=6.0, executable=fake)
    assert result.status == "executed"
    assert result.physics_verified is True
    assert result.extracted_quantities["resonance_frequency_ghz"] == pytest.approx(6.0)


def test_cpw_openems_present_subprocess_extracts_impedance(tmp_path: Path) -> None:
    spec = LayoutSpec.model_validate(
        json.loads((ROOT / "examples/benchmarks/02_cpw_50ohm/layout.json").read_text("utf-8"))
    )
    wf = build_default_workflow()
    built = wf.run(spec, formats=())
    prepared = simulate_layout(
        spec,
        built.geometry,
        wf.technology(spec.technology),
        tmp_path / "run",
        solver="openems",
        execute=False,
    )
    # Matched, reciprocal 50-ohm line with -45 degree transmission phase.
    rows = ["# GHz S RI R 50", "6 0 0 0.70710678 -0.70710678 0.70710678 -0.70710678 0 0"]
    if sys.platform == "win32":
        body = [f"> openems_result.s2p echo {rows[0]}", f">> openems_result.s2p echo {rows[1]}"]
    else:
        body = [f"printf '%s\\n' {repr(rows[0])} {repr(rows[1])} > openems_result.s2p"]
    fake = _fake_executable(tmp_path, "fake_cpw_octave", body)
    result = run_openems(prepared, target_frequency_ghz=6.0, executable=fake)
    assert result.status == "executed"
    assert result.physics_verified is True
    assert result.extracted_quantities["characteristic_impedance_ohm"] == pytest.approx(
        50.0, rel=1e-6
    )


def test_josim_csv_parser_and_present_subprocess(tmp_path: Path) -> None:
    from textlayout.simulation.josim import prepare_squid_josim

    spec = LayoutSpec(
        component="SQUID",
        parameters={
            "loop_inner_width_um": 20,
            "loop_inner_height_um": 20,
            "trace_width_um": 2,
            "junction_gap_um": 1,
            "junction_width_um": 1,
            "critical_current_ua": 10,
            "shunt_resistance_ohm": 8,
            "junction_capacitance_ff": 50,
        },
        target={"voltage_uv": 15},
    )
    wf = build_default_workflow()
    built = wf.run(spec, formats=())
    prepared = prepare_squid_josim(
        spec, built.geometry, wf.technology(spec.technology), tmp_path / "run"
    )
    rows = ['time,"V(TOP)","I(IBIAS)"', "0,0,0", "1e-9,10e-6,5e-6", "2e-9,20e-6,10e-6"]
    if sys.platform == "win32":
        body = [f"> squid_result.csv echo {rows[0]}"] + [
            f">> squid_result.csv echo {row}" for row in rows[1:]
        ]
    else:
        quoted = " ".join(repr(row) for row in rows)
        body = [f"printf '%s\\n' {quoted} > squid_result.csv"]
    fake = _fake_executable(tmp_path, "fake_josim", body)
    result = run_josim(prepared, executable=fake, target_voltage_uv=15)
    assert result.status == "executed"
    assert result.physics_verified is True
    assert parse_josim_csv(result.artifacts["result"])["mean_voltage_uv"] == pytest.approx(15)


def test_openems_off_target_is_not_physics_verified(tmp_path: Path) -> None:
    s2p = tmp_path / "model.s2p"
    lines = ["# GHz S MA R 50"]
    for i in range(41):
        f_ghz = 5.0 + i * 0.05
        s21 = abs(f_ghz - 5.2) / 2.0 + 0.01  # notch far from a 6 GHz target
        lines.append(f"{f_ghz:.4f} 1.0 180 {s21:.4f} 0 {s21:.4f} 0 1.0 180")
    s2p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    prepared = SimulationResult(
        status="input_files_prepared",
        solver="openEMS",
        readiness_level=2,
        reason="prepared",
        output_dir=tmp_path,
        artifacts={},
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
        "executed",
        "FasterCap",
        4,
        "ran",
        extracted_quantities={"c": 1.0},
        target_comparison={"within_tolerance": True},
    )
    assert compared.evidence_stage == "compared"
    assert compared.physics_verified is True
