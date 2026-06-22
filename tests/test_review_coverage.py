"""Direct coverage and golden-value regression tests added during the review.

These pin the small, deterministic numerical paths (ideal JJ, kinetic
inductance, nonlinear post-processing) against values recomputed from first
principles, and exercise the rendering/CAD/plot modules that were previously
only reached indirectly.
"""

from __future__ import annotations

import math

import pytest

from text_to_gds import nonlinear_extensions
from text_to_gds.cad_export import write_cad_artifacts
from text_to_gds.pcells import manhattan_josephson_junction
from text_to_gds.plots import write_simulation_plot
from text_to_gds.simulation import critical_current_ua, josephson_inductance_ph
from text_to_gds.superconductivity import sheet_kinetic_inductance_ph


# --- Golden-value physics regressions (computed independently of the module) ---

PHI0_WB = 2.067833848e-15
MU0_H_PER_M = 4.0 * math.pi * 1e-7


def test_ideal_junction_golden_values():
    # Default Manhattan JJ: 0.22um x 0.22um at Jc = 2.0 uA/um^2.
    ic_ua = critical_current_ua(0.22 * 0.22, 2.0)
    assert ic_ua == pytest.approx(0.0968, rel=0, abs=1e-12)

    lj_ph = josephson_inductance_ph(ic_ua)
    expected_lj_ph = PHI0_WB / (2.0 * math.pi * (ic_ua * 1e-6)) * 1e12
    assert lj_ph == pytest.approx(expected_lj_ph, rel=1e-9)
    assert lj_ph == pytest.approx(3399.855149, rel=1e-6)


def test_sheet_kinetic_inductance_golden():
    lambda_nm, thickness_nm = 100.0, 50.0
    value = sheet_kinetic_inductance_ph(lambda_nm, thickness_nm)
    lam, thickness = lambda_nm * 1e-9, thickness_nm * 1e-9
    expected = MU0_H_PER_M * lam / math.tanh(thickness / lam) * 1e12
    assert value == pytest.approx(expected, rel=1e-9)
    # Thicker films store less sheet kinetic inductance.
    assert sheet_kinetic_inductance_ph(lambda_nm, 200.0) < value


def test_sheet_kinetic_inductance_rejects_bad_input():
    with pytest.raises(ValueError):
        sheet_kinetic_inductance_ph(0.0, 50.0)
    with pytest.raises(ValueError):
        sheet_kinetic_inductance_ph(100.0, -1.0)


# --- nonlinear_extensions deterministic post-processing ---

def test_pump_leakage_golden():
    result = nonlinear_extensions.pump_leakage(
        pump_power_dbm=-40.0, isolation_db=20.0, filter_rejection_db=10.0
    )
    assert result["leaked_pump_power_dbm"] == pytest.approx(-70.0)
    assert result["total_rejection_db"] == pytest.approx(30.0)


def test_nonlinear_saturation_compresses_at_p1db():
    result = nonlinear_extensions.nonlinear_saturation(
        input_power_dbm=[-100.0, 0.0], small_signal_gain_db=20.0, p1db_dbm=0.0
    )
    small_signal, at_p1db = result["gain_db"]
    # Far below P1dB the gain is ~unchanged; at P1dB it has compressed ~3 dB.
    assert small_signal == pytest.approx(20.0, abs=1e-3)
    assert at_p1db == pytest.approx(20.0 - 10.0 * math.log10(2.0), abs=1e-6)


def test_gain_ripple_on_flat_band_is_zero():
    flat = nonlinear_extensions.gain_ripple_analysis([4.0, 5.0, 6.0], [20.0, 20.0, 20.0])
    assert flat["peak_to_peak_ripple_db"] == pytest.approx(0.0, abs=1e-9)
    assert flat["rms_ripple_db"] == pytest.approx(0.0, abs=1e-9)


# --- plots and cad_export rendering paths ---

def test_write_simulation_plot_summary(tmp_path):
    out = tmp_path / "sim.png"
    report = write_simulation_plot({"engine": "mock_jj", "critical_current_ua": 0.0968}, out)
    assert out.exists() and out.stat().st_size > 0
    assert report["plot_type"] in {"summary", "line"}


def test_write_cad_artifacts(tmp_path):
    gds = tmp_path / "jj.gds"
    manhattan_josephson_junction().write_gds(str(gds))
    report = write_cad_artifacts(
        gds,
        svg_path=tmp_path / "jj.svg",
        dxf_path=tmp_path / "jj.dxf",
        stl_path=tmp_path / "jj.stl",
        glb_path=tmp_path / "jj.glb",
        json_path=tmp_path / "jj.cad.json",
    )
    assert report["schema"] == "text-to-gds.cad-export.v0"
    assert (tmp_path / "jj.svg").exists()
    assert (tmp_path / "jj.dxf").exists()
    assert (tmp_path / "jj.stl").exists()
    assert report["shape_count"] >= 1
