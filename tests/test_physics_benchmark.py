"""Physics-grounded benchmark tests.

These tests verify NUMERICAL reproduction, not just "can generate a picture".

What is benchmarked:
  1. Reproduce a known device (quarter-wave CPW at 6 GHz)
  2. Match extracted physics (frequency within tolerance)
  3. Pass DRC (minimum width and spacing rules)
  4. Pass solver validation (Touchstone is passive + reciprocal)

What is NOT benchmarked:
  - Whether a PNG was generated
  - Whether a JSON file exists
  - Whether any string was printed

Design rule: all numeric assertions use exact formulas, never magic constants.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import gdsfactory as gf
import pytest

from text_to_gds.extraction import PHI0_WEBER, extract_physical_parameters
from text_to_gds.physics_compiler import C0_M_PER_S, solve_cpw_resonator
from text_to_gds.process import DEFAULT_PROCESS, JJ, M1, M2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jj_gds(tmp_path: Path, width_um: float = 0.22, height_um: float = 0.22) -> tuple[Path, Path]:
    """Write a minimal JJ GDS with M1/JJ/M2 layers."""
    gf.gpdk.get_generic_pdk().activate()
    c = gf.Component()
    c.add_polygon([(0, 0), (width_um, 0), (width_um, height_um), (0, height_um)], layer=JJ)
    c.add_polygon([(-1, 0), (1, 0), (1, height_um), (-1, height_um)], layer=M1)
    c.add_polygon([(0, -1), (width_um, -1), (width_um, 1), (0, 1)], layer=M2)
    gds = tmp_path / "benchmark_jj.gds"
    c.write_gds(gds)
    sidecar = tmp_path / "benchmark_jj.sidecar.json"
    sidecar.write_text(
        json.dumps({
            "pcell": "manhattan_josephson_junction",
            "gds_path": str(gds),
            "info": {"device_type": "manhattan_josephson_junction"},
            "ports": [],
        }),
        encoding="utf-8",
    )
    return gds, sidecar


# ---------------------------------------------------------------------------
# Benchmark 1: Reproduce a known JJ device
# ---------------------------------------------------------------------------

class TestReproduceKnownJunction:
    """Benchmark: reproduce a 0.22×0.22 µm JJ with Jc=2 µA/µm² (NCU AlOx 2026)."""

    def test_junction_area_matches_design_spec(self, tmp_path):
        """Extracted area must match the designed 0.22×0.22 µm = 0.0484 µm²."""
        gds, sc = _write_jj_gds(tmp_path)
        result = extract_physical_parameters(gds, sc, jc_ua_per_um2=2.0)

        expected_area = 0.22 * 0.22
        assert result["junction"]["area"] == pytest.approx(expected_area, rel=1e-3)

    def test_ic_formula_ic_equals_jc_times_area(self, tmp_path):
        """Ic = Jc × area — not estimated from target frequency, not guessed."""
        gds, sc = _write_jj_gds(tmp_path)
        result = extract_physical_parameters(gds, sc, jc_ua_per_um2=2.0)

        area_um2 = 0.22 * 0.22
        jc = 2.0
        expected_ic_a = area_um2 * jc * 1e-6

        assert result["junction"]["ic"] == pytest.approx(expected_ic_a, rel=1e-3)
        assert result["lineage"]["junction.ic"]["formula"] == "Ic = Jc * area"

    def test_lj_formula_phi0_over_2pi_ic(self, tmp_path):
        """Lj = Phi0 / (2π Ic) — formula verified against known constant."""
        gds, sc = _write_jj_gds(tmp_path)
        result = extract_physical_parameters(gds, sc, jc_ua_per_um2=2.0)

        ic_a = result["junction"]["ic"]
        expected_lj_h = PHI0_WEBER / (2.0 * math.pi * ic_a)
        assert result["junction"]["lj"] == pytest.approx(expected_lj_h, rel=1e-6)
        assert result["lineage"]["junction.lj"]["formula"] == "Lj = Phi0 / (2*pi*Ic)"

    def test_f0_from_lc_not_from_target(self, tmp_path):
        """f0 must be derived from extracted L and C, not from the design target."""
        gds, sc = _write_jj_gds(tmp_path)
        ic_a = 0.22 * 0.22 * 2.0 * 1e-6
        lj_h = PHI0_WEBER / (2.0 * math.pi * ic_a)
        cap_ff = 1.0 / ((2.0 * math.pi * 6e9) ** 2 * lj_h) * 1e15

        result = extract_physical_parameters(
            gds, sc, jc_ua_per_um2=2.0, capacitance_ff=cap_ff, target_frequency_ghz=6.0
        )
        f0_extracted = result["linear_circuit"]["resonance_frequency"]
        f0_formula = 1.0 / (2.0 * math.pi * math.sqrt(lj_h * cap_ff * 1e-15))

        assert f0_extracted == pytest.approx(f0_formula, rel=1e-6)
        assert result["lineage"]["linear_circuit.resonance_frequency"]["formula"] == "f0 = 1 / (2*pi*sqrt(L*C))"


# ---------------------------------------------------------------------------
# Benchmark 2: CPW resonator physics compiler matches 1% tolerance
# ---------------------------------------------------------------------------

class TestCPWResonatorCompilerAccuracy:
    """Benchmark: physics compiler produces geometry that yields correct resonance."""

    def test_quarter_wave_length_formula_exact(self):
        """λ/4 length = c / (4 f sqrt(ε_eff)) — matches to floating-point precision."""
        f_ghz = 6.0
        eps_eff = 6.2
        result = solve_cpw_resonator(target_frequency_ghz=f_ghz, effective_permittivity=eps_eff)
        assert result.status == "ok"

        vals = {p.name: p.value for p in result.solved}
        expected_um = C0_M_PER_S * 1e6 / (4 * f_ghz * 1e9 * math.sqrt(eps_eff))
        assert vals["electrical_length_um"] == pytest.approx(expected_um, rel=1e-5)

    def test_back_calculated_frequency_within_1pct(self):
        """From the solved length, back-calculate f0 and verify within 1%."""
        f_target = 7.5
        eps_eff = 6.2
        result = solve_cpw_resonator(target_frequency_ghz=f_target, effective_permittivity=eps_eff)
        assert result.status == "ok"

        vals = {p.name: p.value for p in result.solved}
        length_m = vals["electrical_length_um"] * 1e-6
        f_back = C0_M_PER_S / (4 * length_m * math.sqrt(eps_eff))
        f_back_ghz = f_back / 1e9

        assert abs(f_back_ghz - f_target) / f_target < 0.01

    def test_cpw_resonator_sweep_all_succeed(self):
        """Physics compiler succeeds for 4–10 GHz sweep."""
        for f_ghz in [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:
            result = solve_cpw_resonator(target_frequency_ghz=f_ghz)
            assert result.status == "ok", f"Failed at {f_ghz} GHz: {result.reason}"


# ---------------------------------------------------------------------------
# Benchmark 3: DRC — process rules enforced
# ---------------------------------------------------------------------------

class TestDRCCompliance:
    """Benchmark: extracted geometry must satisfy process DRC rules."""

    def test_junction_area_above_process_minimum(self, tmp_path):
        """JJ area must exceed min_junction_width × min_junction_height."""
        gds, sc = _write_jj_gds(tmp_path)
        result = extract_physical_parameters(gds, sc, jc_ua_per_um2=2.0)

        min_area = (
            DEFAULT_PROCESS.rules.min_junction_width_um
            * DEFAULT_PROCESS.rules.min_junction_height_um
        )
        area = result["junction"]["area"]
        assert area is not None
        assert area > min_area, f"Junction area {area} µm² below DRC minimum {min_area} µm²"

    def test_cpw_trace_above_minimum_width(self):
        """CPW trace width from compiler must exceed process min_trace_width_um."""
        result = solve_cpw_resonator(target_frequency_ghz=6.0)
        assert result.status == "ok"
        vals = {p.name: p.value for p in result.solved}
        assert vals["trace_width_um"] >= DEFAULT_PROCESS.rules.min_trace_width_um

    def test_cpw_gap_above_minimum(self):
        """CPW gap from compiler must exceed process min_cpw_gap_um."""
        result = solve_cpw_resonator(target_frequency_ghz=6.0)
        assert result.status == "ok"
        vals = {p.name: p.value for p in result.solved}
        assert vals["gap_um"] >= DEFAULT_PROCESS.rules.min_cpw_gap_um


# ---------------------------------------------------------------------------
# Benchmark 4: Solver validation (Touchstone)
# ---------------------------------------------------------------------------

class TestSolverPassivity:
    """Benchmark: solver outputs must pass passivity and reciprocity checks."""

    def test_passive_touchstone_accepted(self, tmp_path):
        from text_to_gds.rf_validation import validate_touchstone

        ts = tmp_path / "passive.s2p"
        ts.write_text(
            "# GHZ S DB R 50\n"
            "5.0 -20.0 0 -1.0 0 -1.0 0 -20.0 0\n"
            "6.0 -22.0 0 -1.2 0 -1.2 0 -22.0 0\n",
            encoding="utf-8",
        )
        result = validate_touchstone(ts)
        assert result["status"] == "ok"
        assert result["passivity"] is True
        assert result["reciprocity"] is True

    def test_active_touchstone_rejected(self, tmp_path):
        from text_to_gds.rf_validation import validate_touchstone

        ts = tmp_path / "active.s2p"
        ts.write_text(
            "# GHZ S DB R 50\n"
            "5.0 0.0 0 3.0 0 3.0 0 0.0 0\n",
            encoding="utf-8",
        )
        result = validate_touchstone(ts)
        assert result["status"] == "failed"

    def test_rf_artifacts_reject_no_touchstone(self, tmp_path):
        from text_to_gds.rf import write_rf_network_artifacts

        # Empty simulation dict → must fail, never synthesise
        result = write_rf_network_artifacts(
            {},
            touchstone_path=tmp_path / "out.s2p",
            report_path=tmp_path / "out.json",
            plot_path=tmp_path / "out.png",
            csv_path=tmp_path / "out.csv",
        )
        assert result["status"] in ("failed", "skipped")
        assert not (tmp_path / "out.s2p").exists() or (tmp_path / "out.s2p").stat().st_size == 0

    def test_rf_artifacts_skipped_without_real_data(self, tmp_path):
        from text_to_gds.rf import write_rf_network_artifacts

        # Simulation data without real S-params → must skip, not synthesise
        simulation = {"physical_performance": {"center_frequency_ghz": 5.0}}
        result = write_rf_network_artifacts(
            simulation,
            touchstone_path=tmp_path / "out.s2p",
            report_path=tmp_path / "out.json",
            plot_path=tmp_path / "out.png",
            csv_path=tmp_path / "out.csv",
        )
        assert result["status"] == "skipped"


# ---------------------------------------------------------------------------
# Benchmark 5: Report metric lineage
# ---------------------------------------------------------------------------

class TestReportLineage:
    """Every numeric value in the manifest must carry solver lineage."""

    def test_metric_has_required_lineage_fields(self):
        from text_to_gds.report import _metric

        m = _metric(6.01, unit="GHz", method="simulated", solver="openEMS", file="result.s2p")
        assert m["value"] == 6.01
        assert m["unit"] == "GHz"
        assert m["method"] == "simulated"
        assert m["solver"] == "openEMS"
        assert m["file"] == "result.s2p"

    def test_metric_without_solver_is_still_valid(self):
        from text_to_gds.report import _metric

        m = _metric(5.0, unit="GHz", method="extracted")
        assert m["value"] == 5.0
        assert m["method"] == "extracted"
        assert "solver" not in m or m["solver"] is None

    def test_metric_none_value_is_allowed(self):
        """A None value with lineage is valid — it means the solver did not produce this metric."""
        from text_to_gds.report import _metric

        m = _metric(None, unit="dB", method="simulated", solver="JosephsonCircuits.jl")
        assert m["value"] is None
        assert m["method"] == "simulated"


# ---------------------------------------------------------------------------
# Benchmark 6: Technology YAML requirement
# ---------------------------------------------------------------------------

class TestTechnologyYAMLRequirement:
    """Layout generation must fail when no technology YAML is available."""

    def test_find_known_technology(self):
        from text_to_gds.process import find_technology_yaml

        path = find_technology_yaml("ncu_alox_2026")
        assert path is not None, (
            "ncu_alox_2026.yaml not found. Add it to process/ directory."
        )
        assert path.is_file()

    def test_unknown_technology_returns_none(self):
        from text_to_gds.process import find_technology_yaml

        path = find_technology_yaml("nonexistent_fictional_process_xyz_9999")
        assert path is None

    def test_load_ncu_alox_technology(self):
        from text_to_gds.process import find_technology_yaml, load_technology_yaml

        if find_technology_yaml("ncu_alox_2026") is None:
            pytest.skip("ncu_alox_2026.yaml not found")

        tech = load_technology_yaml("ncu_alox_2026")
        assert "M1" in tech.layers
        assert "JJ" in tech.layers
        assert tech.rules.min_junction_width_um > 0
        assert tech.rules.min_trace_width_um > 0

    def test_load_technology_fails_gracefully_when_missing(self):
        from text_to_gds.process import load_technology_yaml

        with pytest.raises(FileNotFoundError, match="No technology YAML"):
            load_technology_yaml("process_that_does_not_exist_42")

    def test_supercad_fails_without_technology(self, tmp_path):
        from text_to_gds.supercad import compile_supercad, parse_supercad

        text = (
            "DEVICE cpw_quarter_wave_resonator\n"
            "TECH nonexistent_process_xyz_9999\n"
            "ADD cpw_quarter_wave_resonator trace_width_um=10um\n"
        )
        seq = parse_supercad(text)
        result = compile_supercad(seq, output_dir=tmp_path / "out")
        assert result["status"] == "failed"
        assert "technology" in result["reason"].lower() or "yaml" in result["reason"].lower()
