"""Tests for the physics compiler — target physics → solved geometry parameters.

The correct flow:
    prompt → target physics → solve parameters → generate geometry

NOT:
    prompt → rectangle → estimate physics

Every test verifies numerical formulas and checks that all outputs have lineage.
"""

from __future__ import annotations

import math

import pytest

from text_to_gds.physics_compiler import (
    C0_M_PER_S,
    ELECTRON_CHARGE_C,
    PHI0_WB,
    PLANCK_J_S,
    compile_physics,
    solve_cpw_resonator,
    solve_josephson_junction,
    solve_lc_capacitor,
    solve_transmon,
)


# ---------------------------------------------------------------------------
# CPW resonator
# ---------------------------------------------------------------------------

def test_cpw_resonator_quarter_wave_6ghz():
    """λ/4 CPW at 6 GHz with εeff=6.2 → length ≈ 5025 µm."""
    result = solve_cpw_resonator(target_frequency_ghz=6.0, effective_permittivity=6.2)
    assert result.status == "ok"

    lengths = {p.name: p.value for p in result.solved}
    expected = C0_M_PER_S * 1e6 / (4 * 6.0e9 * math.sqrt(6.2))
    assert lengths["electrical_length_um"] == pytest.approx(expected, rel=1e-4)


def test_cpw_resonator_half_wave_5ghz():
    """λ/2 CPW at 5 GHz (resonator_mode=2)."""
    result = solve_cpw_resonator(
        target_frequency_ghz=5.0,
        effective_permittivity=6.2,
        resonator_mode=2,
    )
    assert result.status == "ok"
    lengths = {p.name: p.value for p in result.solved}
    expected = C0_M_PER_S * 1e6 / (2 * 5.0e9 * math.sqrt(6.2))
    assert lengths["electrical_length_um"] == pytest.approx(expected, rel=1e-4)


def test_cpw_resonator_fails_on_negative_frequency():
    result = solve_cpw_resonator(target_frequency_ghz=-1.0)
    assert result.status == "failed"
    assert "positive" in result.reason.lower()


def test_cpw_resonator_all_outputs_have_lineage():
    result = solve_cpw_resonator(target_frequency_ghz=6.0)
    assert result.status == "ok"
    for param in result.solved:
        assert param.formula, f"Parameter {param.name} has no formula (lineage missing)"
        assert param.inputs, f"Parameter {param.name} has no inputs (lineage missing)"
        assert param.method_label in ("estimated", "extracted", "simulated", "measured")


def test_cpw_supercad_params_format():
    result = solve_cpw_resonator(target_frequency_ghz=6.0)
    params = result.as_supercad_params()
    assert "electrical_length_um" in params
    assert params["electrical_length_um"].endswith("um")


# ---------------------------------------------------------------------------
# Josephson junction
# ---------------------------------------------------------------------------

def test_jj_area_from_ic_and_jc():
    """Ic=1 µA, Jc=2 µA/µm² → area=0.5 µm²."""
    result = solve_josephson_junction(target_ic_ua=1.0, jc_ua_per_um2=2.0)
    assert result.status == "ok"
    vals = {p.name: p.value for p in result.solved}
    assert vals["junction_area_um2"] == pytest.approx(0.5, rel=1e-6)
    assert vals["junction_width_um"] == pytest.approx(math.sqrt(0.5), rel=1e-4)


def test_jj_lj_from_ic():
    """Lj = Phi0 / (2π Ic) for Ic=1 µA."""
    result = solve_josephson_junction(target_ic_ua=1.0, jc_ua_per_um2=2.0)
    assert result.status == "ok"
    vals = {p.name: p.value for p in result.solved}
    expected_lj_nh = PHI0_WB / (2.0 * math.pi * 1e-6) * 1e9
    assert vals["josephson_inductance_nh"] == pytest.approx(expected_lj_nh, rel=1e-4)


def test_jj_fails_below_drc_minimum():
    """Very small Ic → junction area below minimum → status=failed."""
    result = solve_josephson_junction(
        target_ic_ua=0.001,
        jc_ua_per_um2=100.0,
        min_dimension_um=0.10,
    )
    assert result.status == "failed"
    assert any("drc minimum" in e.lower() or "below" in e.lower() for e in result.errors)


def test_jj_all_outputs_have_lineage():
    result = solve_josephson_junction(target_ic_ua=1.0, jc_ua_per_um2=2.0)
    for param in result.solved:
        assert param.formula
        assert param.inputs


# ---------------------------------------------------------------------------
# LC resonator capacitor
# ---------------------------------------------------------------------------

def test_lc_capacitor_from_frequency_and_inductance():
    """C = 1/(2πf)² / L for f=6 GHz, L=3.4 nH."""
    result = solve_lc_capacitor(target_frequency_ghz=6.0, inductance_nh=3.4)
    assert result.status == "ok"
    vals = {p.name: p.value for p in result.solved}
    expected_c_f = 1.0 / ((2.0 * math.pi * 6e9) ** 2 * 3.4e-9)
    assert vals["capacitance_ff"] == pytest.approx(expected_c_f * 1e15, rel=1e-4)


def test_lc_capacitor_fails_on_zero_inductance():
    result = solve_lc_capacitor(target_frequency_ghz=6.0, inductance_nh=0.0)
    assert result.status == "failed"


# ---------------------------------------------------------------------------
# Transmon solver
# ---------------------------------------------------------------------------

def test_transmon_ec_equals_anharmonicity():
    """In transmon regime, EC should equal the target anharmonicity."""
    anharmonicity_mhz = 200.0
    result = solve_transmon(
        target_qubit_frequency_ghz=5.0,
        target_anharmonicity_mhz=anharmonicity_mhz,
    )
    assert result.status == "ok"
    vals = {p.name: p.value for p in result.solved}
    assert vals["ec_ghz"] == pytest.approx(anharmonicity_mhz / 1000.0, rel=1e-6)


def test_transmon_ej_formula():
    """EJ = (f01 + EC)² / (8 EC)."""
    f01 = 5.0
    alpha_mhz = 200.0
    ec = alpha_mhz / 1000.0
    expected_ej = (f01 + ec) ** 2 / (8.0 * ec)

    result = solve_transmon(target_qubit_frequency_ghz=f01, target_anharmonicity_mhz=alpha_mhz)
    assert result.status == "ok"
    vals = {p.name: p.value for p in result.solved}
    assert vals["ej_ghz"] == pytest.approx(expected_ej, rel=1e-4)


def test_transmon_ic_from_ej():
    """Ic = EJ × 2π h / Phi0."""
    f01 = 5.0
    alpha_mhz = 200.0
    ec = alpha_mhz / 1000.0
    ej = (f01 + ec) ** 2 / (8.0 * ec)
    expected_ic_a = ej * 1e9 * 2.0 * math.pi * PLANCK_J_S / PHI0_WB

    result = solve_transmon(target_qubit_frequency_ghz=f01, target_anharmonicity_mhz=alpha_mhz)
    assert result.status == "ok"
    vals = {p.name: p.value for p in result.solved}
    assert vals["ic_ua"] == pytest.approx(expected_ic_a * 1e6, rel=1e-4)


def test_transmon_capacitance_from_ec():
    """C = e² / (2 EC h)."""
    ec_ghz = 0.2
    expected_c_f = (ELECTRON_CHARGE_C ** 2) / (2.0 * ec_ghz * 1e9 * PLANCK_J_S)

    result = solve_transmon(target_qubit_frequency_ghz=5.0, target_anharmonicity_mhz=200.0)
    assert result.status == "ok"
    vals = {p.name: p.value for p in result.solved}
    assert vals["capacitance_ff"] == pytest.approx(expected_c_f * 1e15, rel=1e-4)


def test_transmon_fails_on_zero_frequency():
    result = solve_transmon(target_qubit_frequency_ghz=0.0, target_anharmonicity_mhz=200.0)
    assert result.status == "failed"


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def test_compile_physics_dispatcher_cpw():
    result = compile_physics("cpw_resonator", {"target_frequency_ghz": 6.0})
    assert result.status == "ok"
    assert result.device == "cpw_resonator"


def test_compile_physics_dispatcher_jj():
    result = compile_physics(
        "josephson_junction",
        {"target_ic_ua": 1.0},
        process_params={"jc_ua_per_um2": 2.0},
    )
    assert result.status == "ok"


def test_compile_physics_dispatcher_unknown():
    result = compile_physics("ufo_antenna", {"target_frequency_ghz": 6.0})
    assert result.status == "failed"
    assert "unknown device" in result.reason.lower()


def test_compile_physics_no_fake_defaults():
    """compile_physics must not return fake geometry when inputs are missing."""
    result = compile_physics("josephson_junction", {})
    assert result.status == "failed"
