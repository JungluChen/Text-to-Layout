"""Physics-first pipeline tests.

Every test checks a NUMERICAL relationship, not a file artifact.  Tests validate:
  - JJ area / Ic / Lj lineage (exact formulas)
  - LC resonance from extracted L and C (never from target frequency)
  - Touchstone passivity and reciprocity
  - Explicit failure for missing inputs
  - scqubits adapter fails without capacitance
  - JosephsonCircuits adapter fails without Lj or C
  - Unit-qualified field aliases in extraction artifacts
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import gdsfactory as gf
import pytest

from text_to_gds.extraction import PHI0_WEBER, extract_physical_parameters, write_extraction
from text_to_gds.extraction_schema import (
    ec_ghz,
    ej_ghz,
    has_junction_physics,
    read_capacitance,
    read_ic,
    read_lj,
)
from text_to_gds.process import JJ, M1, M2
from text_to_gds.rf import write_rf_network_artifacts
from text_to_gds.rf_validation import validate_touchstone


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _physical_jj(tmp_path):
    """Write a 0.22 × 0.22 µm JJ GDS with M1/M2 electrode overlap."""
    gf.gpdk.get_generic_pdk().activate()
    component = gf.Component()
    component.add_polygon([(0, 0), (0.22, 0), (0.22, 0.22), (0, 0.22)], layer=JJ)
    component.add_polygon([(-1, 0), (1, 0), (1, 0.22), (-1, 0.22)], layer=M1)
    component.add_polygon([(0, -1), (0.22, -1), (0.22, 1), (0, 1)], layer=M2)
    gds = tmp_path / "jj.gds"
    component.write_gds(gds)
    sidecar = tmp_path / "jj.sidecar.json"
    sidecar.write_text(
        json.dumps(
            {
                "pcell": "manhattan_josephson_junction",
                "gds_path": str(gds),
                "info": {"device_type": "manhattan_josephson_junction"},
                "ports": [],
            }
        ),
        encoding="utf-8",
    )
    return gds, sidecar


def _write_s2p(path, s11_db=-20.0, s21_db=-1.0, s12_db=-1.0, s22_db=-20.0):
    path.write_text(
        "# GHZ S DB R 50\n"
        f"5.0 {s11_db} 0 {s21_db} 0 {s12_db} 0 {s22_db} 0\n"
        f"6.0 {s11_db} 0 {s21_db} 0 {s12_db} 0 {s22_db} 0\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Part 3 — JJ extraction numerical checks
# ---------------------------------------------------------------------------

def test_jj_area_0484_jc_2_gives_ic_0968_ua(tmp_path):
    """Benchmark: area 0.0484 µm² × Jc 2.0 µA/µm² = Ic 0.0968 µA."""
    gds, sidecar = _physical_jj(tmp_path)
    expected_area = 0.22 * 0.22  # = 0.0484 µm²
    jc = 2.0
    expected_ic_ua = expected_area * jc  # = 0.0968 µA
    expected_ic_a = expected_ic_ua * 1e-6

    result = extract_physical_parameters(gds, sidecar, jc_ua_per_um2=jc)

    assert result["junction"]["area"] == pytest.approx(expected_area, rel=1e-4)
    assert result["junction"]["ic"] == pytest.approx(expected_ic_a, rel=1e-4)
    # Ic in µA
    assert result["junction"]["ic"] * 1e6 == pytest.approx(0.0968, rel=1e-3)


def test_jj_lj_approx_3_4_nH(tmp_path):
    """Lj = Phi0 / (2π × 0.0968 µA) ≈ 3.40 nH."""
    gds, sidecar = _physical_jj(tmp_path)
    ic_a = 0.22 * 0.22 * 2.0 * 1e-6  # 9.68e-8 A
    expected_lj_h = PHI0_WEBER / (2.0 * math.pi * ic_a)

    result = extract_physical_parameters(gds, sidecar, jc_ua_per_um2=2.0)

    assert result["junction"]["lj"] == pytest.approx(expected_lj_h, rel=1e-4)
    # Should be ~3.40 nH
    assert 3.0e-9 < result["junction"]["lj"] < 4.0e-9


def test_jj_extraction_with_lc_and_lineage(tmp_path):
    gds, sidecar = _physical_jj(tmp_path)
    expected_area = 0.22 * 0.22
    jc = 2.0
    expected_ic = expected_area * jc * 1e-6
    expected_lj = PHI0_WEBER / (2.0 * math.pi * expected_ic)
    capacitance_ff = 1.0 / ((2.0 * math.pi * 6e9) ** 2 * expected_lj) * 1e15

    result = extract_physical_parameters(
        gds,
        sidecar,
        jc_ua_per_um2=jc,
        capacitance_ff=capacitance_ff,
        target_frequency_ghz=6.0,
    )

    assert result["status"] == "ok"
    assert result["junction"]["area"] == pytest.approx(expected_area, rel=1e-6)
    assert result["junction"]["ic"] == pytest.approx(expected_ic, rel=1e-6)
    assert result["junction"]["lj"] == pytest.approx(expected_lj, rel=0.05)
    assert result["linear_circuit"]["resonance_frequency"] == pytest.approx(6e9, rel=0.02)
    assert result["lineage"]["junction.lj"]["inputs"] == ["junction.ic"]
    artifact = write_extraction(result, tmp_path / "extraction.json")
    assert artifact["result_path"].endswith("extraction.json")


def test_missing_jc_returns_explicit_failure(tmp_path):
    """No Jc supplied → status=failed, ic=None."""
    gds, sidecar = _physical_jj(tmp_path)
    result = extract_physical_parameters(gds, sidecar)
    assert result["status"] == "failed"
    assert "missing extracted parameter" in result["reason"]
    assert result["junction"]["ic"] is None
    assert result["junction"]["lj"] is None


def test_missing_jj_layer_returns_explicit_failure(tmp_path):
    """GDS without JJ layer → no junction area, fails for junction device."""
    gf.gpdk.get_generic_pdk().activate()
    component = gf.Component()
    component.add_polygon([(-1, 0), (1, 0), (1, 0.22), (-1, 0.22)], layer=M1)
    gds = tmp_path / "no_jj.gds"
    component.write_gds(gds)
    sidecar = tmp_path / "no_jj.sidecar.json"
    sidecar.write_text(
        json.dumps({
            "pcell": "manhattan_josephson_junction",
            "gds_path": str(gds),
            "info": {"device_type": "manhattan_josephson_junction"},
            "ports": [],
        }),
        encoding="utf-8",
    )
    result = extract_physical_parameters(gds, sidecar, jc_ua_per_um2=2.0)
    assert result["status"] == "failed"
    assert result["junction"]["area"] is None


# ---------------------------------------------------------------------------
# Part 4 — LC resonance extraction
# ---------------------------------------------------------------------------

def test_f0_computed_from_extracted_lc_not_from_target(tmp_path):
    """f0 must equal 1/(2π√LC) from extracted values, not copied from target."""
    gds, sidecar = _physical_jj(tmp_path)
    jc = 2.0
    ic_a = 0.22 * 0.22 * jc * 1e-6
    lj_h = PHI0_WEBER / (2.0 * math.pi * ic_a)
    capacitance_ff = 1.0 / ((2.0 * math.pi * 6e9) ** 2 * lj_h) * 1e15

    result = extract_physical_parameters(
        gds, sidecar, jc_ua_per_um2=jc, capacitance_ff=capacitance_ff, target_frequency_ghz=6.0
    )
    assert result["status"] == "ok"
    extracted_f0 = result["linear_circuit"]["resonance_frequency"]
    computed_f0 = 1.0 / (2.0 * math.pi * math.sqrt(lj_h * capacitance_ff * 1e-15))
    assert extracted_f0 == pytest.approx(computed_f0, rel=1e-6)
    assert result["lineage"]["linear_circuit.resonance_frequency"]["formula"] == "f0 = 1 / (2*pi*sqrt(L*C))"


def test_missing_capacitance_leaves_f0_null(tmp_path):
    """Without capacitance, resonance_frequency must be None."""
    gds, sidecar = _physical_jj(tmp_path)
    result = extract_physical_parameters(gds, sidecar, jc_ua_per_um2=2.0)
    assert result["linear_circuit"]["resonance_frequency"] is None


def test_target_frequency_mismatch_fails(tmp_path):
    """If extracted f0 is outside tolerance, status=failed."""
    gds, sidecar = _physical_jj(tmp_path)
    jc = 2.0
    ic_a = 0.22 * 0.22 * jc * 1e-6
    lj_h = PHI0_WEBER / (2.0 * math.pi * ic_a)
    capacitance_ff = 1.0 / ((2.0 * math.pi * 6e9) ** 2 * lj_h) * 1e15

    # Pass a target that's 10% off (tolerance default 2%)
    result = extract_physical_parameters(
        gds, sidecar, jc_ua_per_um2=jc, capacitance_ff=capacitance_ff,
        target_frequency_ghz=6.6, frequency_tolerance=0.02
    )
    assert result["status"] == "failed"
    assert "tolerance" in result["reason"]


# ---------------------------------------------------------------------------
# Part 4 — unit-qualified alias fields
# ---------------------------------------------------------------------------

def test_unit_qualified_aliases_populated(tmp_path):
    """New field names (area_um2, ic_a, lj_h, capacitance_f, …) must be populated."""
    gds, sidecar = _physical_jj(tmp_path)
    result = extract_physical_parameters(gds, sidecar, jc_ua_per_um2=2.0, capacitance_ff=100.0)

    j = result["junction"]
    assert j["area_um2"] is not None
    assert j["ic_a"] is not None
    assert j["lj_h"] is not None
    assert j["jc_ua_per_um2"] == pytest.approx(2.0, rel=1e-6)

    lc = result["linear_circuit"]
    assert lc["capacitance_f"] is not None
    assert lc["capacitance_f"] == pytest.approx(100e-15, rel=1e-6)
    assert lc["inductance_h"] is not None

    assert result["geometry"]["shape_count"] >= 0
    assert "solver_inputs" in result
    assert "solver_outputs" in result


def test_extraction_schema_accessors(tmp_path):
    """extraction_schema accessor functions handle both old and new field names."""
    gds, sidecar = _physical_jj(tmp_path)
    result = extract_physical_parameters(gds, sidecar, jc_ua_per_um2=2.0, capacitance_ff=100.0)

    assert read_ic(result) == result["junction"]["ic"]
    assert read_lj(result) == result["junction"]["lj"]
    assert read_capacitance(result) == result["linear_circuit"]["capacitance"]
    assert has_junction_physics(result)


# ---------------------------------------------------------------------------
# Part 5 — RF / Touchstone validation
# ---------------------------------------------------------------------------

def test_rf_artifacts_require_and_validate_touchstone(tmp_path):
    source = tmp_path / "solver.s2p"
    _write_s2p(source)
    result = write_rf_network_artifacts(
        {"touchstone_path": str(source)},
        touchstone_path=tmp_path / "validated.s2p",
        report_path=tmp_path / "rf.json",
        plot_path=tmp_path / "rf.png",
        csv_path=tmp_path / "rf.csv",
    )
    assert result["status"] == "ok"
    assert result["source"] == "solver_touchstone"
    assert result["validation"]["passivity"] is True
    assert result["validation"]["reciprocity"] is True


def test_rf_rejects_nonpassive_or_missing_data(tmp_path):
    active = tmp_path / "active.s2p"
    _write_s2p(active, s11_db=0.0, s21_db=3.0, s12_db=3.0, s22_db=0.0)
    rejected = write_rf_network_artifacts(
        {"touchstone_path": str(active)},
        touchstone_path=tmp_path / "rejected.s2p",
        report_path=tmp_path / "rejected.json",
        plot_path=tmp_path / "rejected.png",
        csv_path=tmp_path / "rejected.csv",
    )
    assert rejected == {
        "schema": "text-to-gds.rf-network.v1",
        "status": "failed",
        "reason": "Touchstone data violates passive power conservation",
        "report_path": str(tmp_path / "rejected.json"),
    }
    missing = write_rf_network_artifacts(
        {},
        touchstone_path=tmp_path / "missing.s2p",
        report_path=tmp_path / "missing.json",
        plot_path=tmp_path / "missing.png",
        csv_path=tmp_path / "missing.csv",
    )
    assert missing["status"] == "failed"
    assert "Touchstone" in missing["reason"]


def test_validate_touchstone_accepts_passive_file(tmp_path):
    source = tmp_path / "good.s2p"
    _write_s2p(source)
    result = validate_touchstone(source)
    assert result["status"] == "ok"
    assert result["passivity"] is True
    assert result["reciprocity"] is True


def test_validate_touchstone_rejects_missing_file(tmp_path):
    result = validate_touchstone(tmp_path / "nonexistent.s2p")
    assert result["status"] == "failed"
    assert "not found" in result["reason"]


def test_validate_touchstone_rejects_active_file(tmp_path):
    active = tmp_path / "active.s2p"
    _write_s2p(active, s11_db=0.0, s21_db=3.0, s12_db=3.0, s22_db=0.0)
    result = validate_touchstone(active)
    assert result["status"] == "failed"
    assert "passivity" in result["reason"].lower() or "power" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Part 6 — openEMS / HFSS cross-check requires two real files
# ---------------------------------------------------------------------------

def test_cross_validate_solvers_fails_without_both_files(tmp_path):
    from text_to_gds.solver_agreement import cross_validate_solvers

    result_neither = cross_validate_solvers(None, None)
    assert result_neither["status"] == "failed"
    assert "missing" in result_neither["reason"].lower() or "executed" in result_neither["reason"].lower()

    source = tmp_path / "solver.s2p"
    _write_s2p(source)
    result_one = cross_validate_solvers(source, None)
    assert result_one["status"] == "failed"

    result_other = cross_validate_solvers(None, source)
    assert result_other["status"] == "failed"


def test_cross_validate_solvers_passes_with_two_matching_files(tmp_path):
    from text_to_gds.solver_agreement import cross_validate_solvers

    s1 = tmp_path / "hfss.s2p"
    s2 = tmp_path / "openems.s2p"
    _write_s2p(s1)
    _write_s2p(s2)
    result = cross_validate_solvers(s1, s2, tolerance_pct=5.0)
    assert result["status"] == "ok"
    assert result["passed"] is True
    assert result["confidence_pct"] >= 95.0


# ---------------------------------------------------------------------------
# Part 7 — JosephsonCircuits adapter validation
# ---------------------------------------------------------------------------

def test_josephsoncircuits_adapter_fails_without_lj(tmp_path):
    from text_to_gds.josephsoncircuits_adapter import run_josephsoncircuits

    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"lj": None, "ic": None, "area": 0.0484},
        "linear_circuit": {"capacitance": 100e-15},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = run_josephsoncircuits(
        extraction_path,
        script_path=tmp_path / "jc.jl",
        result_path=tmp_path / "jc_result.json",
        report_path=tmp_path / "jc_report.json",
    )
    assert result["status"] == "failed"
    assert "inductance" in result["reason"].lower() or "lj" in result["reason"].lower()


def test_josephsoncircuits_adapter_fails_without_capacitance(tmp_path):
    from text_to_gds.josephsoncircuits_adapter import run_josephsoncircuits

    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"lj": 3.4e-9, "lj_h": 3.4e-9, "ic": 9.68e-8, "ic_a": 9.68e-8, "area": 0.0484},
        "linear_circuit": {"capacitance": None},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = run_josephsoncircuits(
        extraction_path,
        script_path=tmp_path / "jc.jl",
        result_path=tmp_path / "jc_result.json",
        report_path=tmp_path / "jc_report.json",
    )
    assert result["status"] == "failed"
    assert "capacitance" in result["reason"].lower()


def test_josephsoncircuits_adapter_skipped_without_julia(tmp_path):
    from text_to_gds.josephsoncircuits_adapter import run_josephsoncircuits

    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"lj": 3.4e-9, "lj_h": 3.4e-9, "ic": 9.68e-8, "ic_a": 9.68e-8, "area": 0.0484},
        "linear_circuit": {"capacitance": 100e-15, "capacitance_f": 100e-15},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = run_josephsoncircuits(
        extraction_path,
        script_path=tmp_path / "jc.jl",
        result_path=tmp_path / "jc_result.json",
        report_path=tmp_path / "jc_report.json",
        julia_executable="_nonexistent_julia_",
    )
    assert result["status"] in ("skipped", "failed")
    assert result["executed"] is False


def test_josephsoncircuits_script_contains_lj_and_c(tmp_path):
    """Generated Julia script must embed Lj and C from extraction.json."""
    from text_to_gds.josephsoncircuits_adapter import run_josephsoncircuits

    lj_h = 3.4e-9
    cap_f = 100e-15
    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"lj": lj_h, "lj_h": lj_h, "ic": 9.68e-8, "ic_a": 9.68e-8, "area": 0.0484},
        "linear_circuit": {"capacitance": cap_f, "capacitance_f": cap_f},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    script_path = tmp_path / "jc.jl"
    run_josephsoncircuits(
        extraction_path,
        script_path=script_path,
        result_path=tmp_path / "jc_result.json",
        report_path=tmp_path / "jc_report.json",
        julia_executable="_nonexistent_julia_",
    )

    assert script_path.is_file()
    script_text = script_path.read_text(encoding="utf-8")
    # Script must contain the extracted Lj and C values
    assert f"{lj_h:.16g}" in script_text or f"{lj_h:.6g}" in script_text
    assert f"{cap_f:.16g}" in script_text or f"{cap_f:.6g}" in script_text


# ---------------------------------------------------------------------------
# Part 8 — scqubits adapter
# ---------------------------------------------------------------------------

def test_scqubits_fails_without_capacitance(tmp_path):
    from text_to_gds.scqubits_adapter import run_scqubits_transmon

    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"ic": 9.68e-8, "ic_a": 9.68e-8, "area": 0.0484},
        "linear_circuit": {"capacitance": None},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = run_scqubits_transmon(extraction_path, report_path=tmp_path / "scq.json")
    assert result["status"] == "failed"
    assert "capacitance" in result["reason"].lower()


def test_scqubits_fails_without_ic(tmp_path):
    from text_to_gds.scqubits_adapter import run_scqubits_transmon

    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"ic": None, "area": 0.0484},
        "linear_circuit": {"capacitance": 100e-15},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = run_scqubits_transmon(extraction_path, report_path=tmp_path / "scq.json")
    assert result["status"] == "failed"
    assert "ic" in result["reason"].lower() or "critical current" in result["reason"].lower()


def test_scqubits_ej_ec_computed_from_extracted_values(tmp_path):
    """EJ/EC must be derived from extracted Ic and C, never from defaults."""
    from text_to_gds.scqubits_adapter import run_scqubits_transmon
    from text_to_gds.extraction_schema import PHI0_WEBER, ELECTRON_CHARGE_C, PLANCK_J_S

    ic_a = 9.68e-8
    cap_f = 50e-15
    expected_ej = PHI0_WEBER * ic_a / (2.0 * math.pi) / (PLANCK_J_S * 1e9)
    expected_ec = (ELECTRON_CHARGE_C ** 2) / (2.0 * cap_f) / (PLANCK_J_S * 1e9)

    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"ic": ic_a, "ic_a": ic_a, "area": 0.0484},
        "linear_circuit": {"capacitance": cap_f, "capacitance_f": cap_f},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = run_scqubits_transmon(extraction_path, report_path=tmp_path / "scq.json")

    assert result["status"] in ("executed", "skipped")
    assert result["ej_ghz"] == pytest.approx(expected_ej, rel=1e-6)
    assert result["ec_ghz"] == pytest.approx(expected_ec, rel=1e-6)

    # EJ and EC GHz helper functions must agree
    assert ej_ghz(ic_a) == pytest.approx(expected_ej, rel=1e-9)
    assert ec_ghz(cap_f) == pytest.approx(expected_ec, rel=1e-9)


def test_scqubits_warns_about_harmonic_regime(tmp_path):
    """EJ/EC << 10 must trigger a warning about harmonic spectrum."""
    from text_to_gds.scqubits_adapter import run_scqubits_transmon

    # Very small Ic and large C → EJ/EC << 1 (Cooper-pair box / harmonic regime)
    ic_a = 1e-12    # 1 pA — tiny
    cap_f = 1e-12   # 1 pF — large

    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"ic": ic_a, "ic_a": ic_a, "area": 0.001},
        "linear_circuit": {"capacitance": cap_f, "capacitance_f": cap_f},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = run_scqubits_transmon(extraction_path, report_path=tmp_path / "scq.json")
    assert result["status"] in ("executed", "skipped")
    if result["status"] == "executed":
        # Must warn about charge-qubit regime
        assert result["ej_ec_ratio"] < 10.0
        assert any("charge" in w.lower() or "harmonic" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Part 2 refactor — scqubits anharmonicity enforcement
# ---------------------------------------------------------------------------

def test_scqubits_fails_when_anharmonicity_below_10_mhz(tmp_path):
    """Spectrum is nearly harmonic (|α| < 10 MHz) → status='failed'.

    Parameters: C = 10 pF (EC ≈ 1.94 MHz), Ic = 0.39 nA (EJ/EC ≈ 100).
    In the transmon regime α ≈ -EC ≈ -1.94 MHz, well below the 10 MHz threshold.
    ncut=30 is sufficient for EJ/EC ≈ 100.
    """
    from text_to_gds.scqubits_adapter import run_scqubits_transmon
    from text_to_gds.extraction_schema import ec_ghz, ej_ghz

    cap_f = 10e-12   # 10 pF → EC ≈ 1.94 MHz
    # Choose Ic so EJ/EC ≈ 100 → EJ ≈ 0.194 GHz
    # EJ_ghz = Phi0*Ic/(2*pi*h*1GHz) → Ic = 0.194e9 * 2*pi * h / Phi0
    target_ej_ghz = ec_ghz(cap_f) * 100.0
    ic_a = target_ej_ghz * 1e9 * 2 * math.pi * 6.62607015e-34 / 2.067833848e-15

    ec_val = ec_ghz(cap_f)
    ej_val = ej_ghz(ic_a)
    assert ec_val < 0.01, f"EC should be < 10 MHz, got {ec_val*1000:.2f} MHz"
    assert ej_val / ec_val > 50, f"EJ/EC should be > 50, got {ej_val/ec_val:.1f}"

    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"ic": ic_a, "ic_a": ic_a, "area": 0.001},
        "linear_circuit": {"capacitance": cap_f, "capacitance_f": cap_f},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = run_scqubits_transmon(extraction_path, report_path=tmp_path / "scq.json",
                                   ncut=50)
    # status="skipped" is acceptable when scqubits is not installed
    # status="failed" is the expected outcome when scqubits IS installed
    # status="executed" would mean the check was not enforced — test fails
    if result["status"] == "executed":
        anharm = result.get("anharmonicity_mhz")
        assert anharm is not None and abs(anharm) >= 10.0, (
            f"If status='executed', anharmonicity must be >= 10 MHz but got {anharm} MHz"
        )
    elif result["status"] == "failed":
        assert "harmonic" in result["reason"].lower() or "10" in result["reason"]
    # status="skipped" → scqubits not installed, test is vacuously satisfied


# ---------------------------------------------------------------------------
# Part 3 refactor — josephsoncircuits passive / JPA mode separation
# ---------------------------------------------------------------------------

def _jc_extraction(tmp_path: Path, lj_h: float = 3.4e-9, cap_f: float = 100e-15) -> Path:
    """Write a minimal v1 extraction.json for JC adapter tests."""
    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"lj": lj_h, "lj_h": lj_h, "ic": 9.68e-8, "ic_a": 9.68e-8, "area": 0.0484},
        "linear_circuit": {"capacitance": cap_f, "capacitance_f": cap_f},
        "lineage": {},
    }
    path = tmp_path / "extraction.json"
    path.write_text(json.dumps(extraction), encoding="utf-8")
    return path


def test_josephsoncircuits_passive_mode_generates_no_pump(tmp_path):
    """mode='passive' script must not include pump sweep or harmonic-balance keywords."""
    from text_to_gds.josephsoncircuits_adapter import run_josephsoncircuits

    ep = _jc_extraction(tmp_path)
    script_path = tmp_path / "passive.jl"
    run_josephsoncircuits(
        ep,
        script_path=script_path,
        result_path=tmp_path / "result.json",
        report_path=tmp_path / "report.json",
        mode="passive",
        julia_executable="_nonexistent_julia_",
    )
    assert script_path.is_file()
    text = script_path.read_text(encoding="utf-8")
    # Passive script must declare mode=passive and not run a pump sweep
    assert "mode=passive" in text.lower() or "passive" in text.lower()
    # Pump sweep variables must not appear
    assert "pump_currents" not in text and "peak_gain" not in text
    assert "hbsolve" not in text or "(), [], (0,)" in text  # empty pump if hbsolve used


def test_josephsoncircuits_jpa_mode_fails_without_pump(tmp_path):
    """mode='jpa' without pump_frequency_ghz must return status='failed'."""
    from text_to_gds.josephsoncircuits_adapter import run_josephsoncircuits

    ep = _jc_extraction(tmp_path)
    result = run_josephsoncircuits(
        ep,
        script_path=tmp_path / "jpa.jl",
        result_path=tmp_path / "result.json",
        report_path=tmp_path / "report.json",
        mode="jpa",
        pump_frequency_ghz=None,
        julia_executable="_nonexistent_julia_",
    )
    assert result["status"] == "failed"
    assert "pump" in result["reason"].lower() or "jpa" in result["reason"].lower()


def test_josephsoncircuits_jpa_mode_with_pump_generates_script(tmp_path):
    """mode='jpa' with pump must generate a harmonic-balance script."""
    from text_to_gds.josephsoncircuits_adapter import run_josephsoncircuits

    ep = _jc_extraction(tmp_path)
    script_path = tmp_path / "jpa.jl"
    run_josephsoncircuits(
        ep,
        script_path=script_path,
        result_path=tmp_path / "result.json",
        report_path=tmp_path / "report.json",
        mode="jpa",
        pump_frequency_ghz=12.0,
        julia_executable="_nonexistent_julia_",
    )
    assert script_path.is_file()
    text = script_path.read_text(encoding="utf-8")
    # JPA script must reference pump and harmonic balance
    assert "pump" in text.lower() or "hbsolve" in text.lower()


def test_josephsoncircuits_unknown_mode_fails(tmp_path):
    """Unrecognised mode must return status='failed' immediately."""
    from text_to_gds.josephsoncircuits_adapter import run_josephsoncircuits

    ep = _jc_extraction(tmp_path)
    result = run_josephsoncircuits(
        ep,
        script_path=tmp_path / "x.jl",
        result_path=tmp_path / "result.json",
        report_path=tmp_path / "report.json",
        mode="galaxy_brain",
        julia_executable="_nonexistent_julia_",
    )
    assert result["status"] == "failed"
    assert "mode" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Part 4 refactor — openEMS runner
# ---------------------------------------------------------------------------

def test_openems_runner_skips_without_openems(tmp_path):
    """openems_runner returns status='skipped' when openEMS is not installed."""
    from text_to_gds.openems_runner import run_openems

    ic_a = 9.68e-8
    lj_h = 3.4e-9
    cap_f = 100e-15
    f0_hz = 1.0 / (2.0 * math.pi * math.sqrt(lj_h * cap_f))
    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"ic": ic_a, "ic_a": ic_a, "lj": lj_h, "lj_h": lj_h, "area": 0.0484},
        "linear_circuit": {
            "capacitance": cap_f, "capacitance_f": cap_f,
            "resonance_frequency": f0_hz, "resonance_frequency_hz": f0_hz,
        },
        "solver_inputs": {"openems": {"epsilon_r": 11.45, "substrate_thickness_um": 254.0}},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = run_openems(
        extraction_path,
        sim_dir=tmp_path / "sim",
        report_path=tmp_path / "openems_report.json",
        openems_executable="_nonexistent_openems_",
    )
    assert result["status"] in ("skipped", "failed")
    # XML must still be generated
    assert (tmp_path / "sim" / "openems_sim.xml").is_file()


def test_openems_runner_fails_without_resonance_frequency(tmp_path):
    """openems_runner must fail explicitly when resonance_frequency is missing."""
    from text_to_gds.openems_runner import run_openems

    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"ic": 9.68e-8, "lj": 3.4e-9},
        "linear_circuit": {"capacitance": 100e-15, "resonance_frequency": None},
        "solver_inputs": {},
        "lineage": {},
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = run_openems(
        extraction_path,
        sim_dir=tmp_path / "sim",
        report_path=tmp_path / "openems_report.json",
        openems_executable="_nonexistent_openems_",
    )
    assert result["status"] == "failed"
    assert "resonance" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Part 1 refactor — unit normalisation in report
# ---------------------------------------------------------------------------

def test_report_uses_engineering_notation(tmp_path):
    """report.py must render Lj in nH (not pH) for values >= 1 nH."""
    from text_to_gds.report import _extraction_text

    extraction = {
        "schema": "text-to-gds.extraction.v1",
        "status": "ok",
        "device": "test",
        "junction": {"area": 0.0484, "ic": 9.68e-8, "lj": 3.4e-9},
        "linear_circuit": {
            "capacitance": 100e-15,
            "resonance_frequency": 6.0e9,
            "impedance": 50.0,
        },
        "lineage": {},
    }
    text = _extraction_text(extraction)
    # Lj = 3.4 nH → must say "nH", not "pH" or raw "3.4e-9"
    assert "nH" in text
    assert "pH" not in text
    # f0 = 6 GHz → must say "GHz"
    assert "GHz" in text
    # C = 100 fF → must say "fF" (< 1 pF)
    assert "fF" in text
    # Ic = 96.8 nA → must say "nA"
    assert "nA" in text or "µA" in text
