"""JJ/SQUID physics, Monte Carlo yield, and CLI: math, determinism, honesty."""

from __future__ import annotations

import json
import math

import pytest

from textlayout.cli import main as cli_main
from textlayout.yield_model import (
    PHI0_WB,
    FrequencyTarget,
    JJProcessModel,
    JunctionGeometry,
    SquidGeometry,
    ec_ghz,
    ej_ghz,
    ic_ua,
    lc_resonance_ghz,
    lj_nh,
    run_jj_yield,
    run_qubit_array_yield,
    squid_ic_eff_ua,
    squid_lj_nh,
    transmon_f01_ghz,
)

REALISTIC_JC = 1.0  # uA/um^2
REALISTIC_AREA = 0.02  # um^2 -> Ic ~ 20 nA, LJ ~ 16 nH, f ~ 4.7 GHz @ 70 fF


class TestExactPhysics:
    def test_ic_equals_jc_times_area(self) -> None:
        assert ic_ua(2.0, 0.05) == pytest.approx(0.1)

    def test_ic_rejects_nonpositive_inputs(self) -> None:
        with pytest.raises(ValueError):
            ic_ua(0.0, 1.0)
        with pytest.raises(ValueError):
            ic_ua(1.0, -1.0)

    def test_lj_matches_phi0_over_2pi_ic(self) -> None:
        ic = 0.02  # uA
        expected_nh = PHI0_WB / (2.0 * math.pi * ic * 1e-6) * 1e9
        assert lj_nh(ic) == pytest.approx(expected_nh)

    def test_lc_resonance_matches_standard_formula(self) -> None:
        l_nh, c_pf = 16.0, 0.07
        expected_ghz = 1.0 / (2.0 * math.pi * math.sqrt(l_nh * 1e-9 * c_pf * 1e-12)) / 1e9
        assert lc_resonance_ghz(l_nh, c_pf) == pytest.approx(expected_ghz)

    def test_realistic_transmon_frequency_is_gigahertz_scale(self) -> None:
        ic = ic_ua(REALISTIC_JC, REALISTIC_AREA)
        lj = lj_nh(ic)
        f = lc_resonance_ghz(lj, 0.07)
        assert 1.0 < f < 10.0  # realistic transmon range

    def test_ej_ec_and_f01_are_internally_consistent(self) -> None:
        ic = ic_ua(REALISTIC_JC, REALISTIC_AREA)
        ej, ec = ej_ghz(ic), ec_ghz(70.0)
        f01 = transmon_f01_ghz(ic, 70.0)
        assert f01 == pytest.approx(math.sqrt(8.0 * ej * ec) - ec)


class TestSquidPhysics:
    def test_symmetric_squid_is_cosine(self) -> None:
        ic1 = ic2 = 10.0
        for flux in (0.0, 0.1, 0.25, 0.4):
            expected = (ic1 + ic2) * abs(math.cos(math.pi * flux))
            assert squid_ic_eff_ua(ic1, ic2, flux) == pytest.approx(expected)

    def test_asymmetric_squid_is_finite_at_half_flux(self) -> None:
        ic_eff = squid_ic_eff_ua(10.0, 8.0, 0.5)
        assert ic_eff == pytest.approx(2.0)  # |Ic1 - Ic2| at exact half flux
        assert squid_lj_nh(10.0, 8.0, 0.5) > 0

    def test_symmetric_squid_at_half_flux_diverges(self) -> None:
        with pytest.raises(ValueError):
            squid_lj_nh(10.0, 10.0, 0.5)

    def test_squid_geometry_schema_rejects_symmetric_half_flux(self) -> None:
        with pytest.raises(Exception):  # pydantic ValidationError wraps ValueError
            SquidGeometry(
                junction_1=JunctionGeometry(width_um=0.1, height_um=0.1),
                junction_2=JunctionGeometry(width_um=0.1, height_um=0.1),
                flux_bias_phi0=0.5,
            )

    def test_squid_geometry_schema_accepts_asymmetric_half_flux(self) -> None:
        squid = SquidGeometry(
            junction_1=JunctionGeometry(width_um=0.1, height_um=0.1),
            junction_2=JunctionGeometry(width_um=0.12, height_um=0.1),
            flux_bias_phi0=0.5,
        )
        assert squid.junction_1.area_um2 != squid.junction_2.area_um2


def _process(**overrides) -> JJProcessModel:
    defaults = dict(
        target_jc_ua_per_um2=REALISTIC_JC,
        wafer_jc_sigma_pct=5.0,
        local_jc_sigma_pct=3.0,
        cd_sigma_nm=5.0,
    )
    defaults.update(overrides)
    return JJProcessModel(**defaults)


def _junction() -> JunctionGeometry:
    return JunctionGeometry(width_um=0.1414, height_um=0.1414)  # area ~0.02 um^2


class TestJJYieldMonteCarlo:
    def test_seeded_run_is_bit_for_bit_deterministic(self) -> None:
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=50)
        r1 = run_jj_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_samples=1000, seed=99,
        )
        r2 = run_jj_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_samples=1000, seed=99,
        )
        assert r1.yield_pct == r2.yield_pct
        assert r1.statistics == r2.statistics
        assert r1.worst_corners == r2.worst_corners

    def test_different_seeds_give_different_samples(self) -> None:
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=50)
        r1 = run_jj_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_samples=1000, seed=1,
        )
        r2 = run_jj_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_samples=1000, seed=2,
        )
        assert r1.statistics.mean_ghz != r2.statistics.mean_ghz

    def test_wider_jc_spread_widens_frequency_distribution(self) -> None:
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=1000)
        tight = run_jj_yield(
            process=_process(wafer_jc_sigma_pct=1.0, local_jc_sigma_pct=1.0, cd_sigma_nm=0.0),
            junction=_junction(), shunt_c_pf=0.07, target=target, n_samples=3000, seed=5,
        )
        loose = run_jj_yield(
            process=_process(wafer_jc_sigma_pct=10.0, local_jc_sigma_pct=10.0, cd_sigma_nm=0.0),
            junction=_junction(), shunt_c_pf=0.07, target=target, n_samples=3000, seed=5,
        )
        assert loose.statistics.sigma_mhz > tight.statistics.sigma_mhz

    def test_yield_and_confidence_interval_are_valid_percentages(self) -> None:
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=50)
        result = run_jj_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_samples=2000, seed=3,
        )
        assert 0.0 <= result.yield_pct <= 100.0
        low, high = result.yield_ci95_pct
        assert 0.0 <= low <= result.yield_pct <= high <= 100.0

    def test_worst_corners_bound_the_distribution(self) -> None:
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=50)
        result = run_jj_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_samples=1500, seed=11,
        )
        frequencies = [c.frequency_ghz for c in result.worst_corners]
        assert min(frequencies) == pytest.approx(result.statistics.min_ghz)
        assert max(frequencies) == pytest.approx(result.statistics.max_ghz)

    def test_synthetic_flag_reflects_calibration(self) -> None:
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=50)
        illustrative = run_jj_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_samples=200, seed=1,
        )
        assert illustrative.synthetic is True
        measured = run_jj_yield(
            process=_process(calibration="measured_on_process"), junction=_junction(),
            shunt_c_pf=0.07, target=target, n_samples=200, seed=1,
        )
        assert measured.synthetic is False

    def test_rejects_too_few_samples(self) -> None:
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=50)
        with pytest.raises(ValueError):
            run_jj_yield(
                process=_process(), junction=_junction(), shunt_c_pf=0.07,
                target=target, n_samples=10, seed=1,
            )


class TestQubitArrayYield:
    def test_deterministic_under_seed(self) -> None:
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=50)
        r1 = run_qubit_array_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_qubits=8, n_chips=300, seed=42,
        )
        r2 = run_qubit_array_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_qubits=8, n_chips=300, seed=42,
        )
        assert r1.chip_yield_pct == r2.chip_yield_pct
        assert r1.hit_rate == r2.hit_rate

    def test_chip_yield_at_most_per_qubit_hit_rate(self) -> None:
        """All-must-pass yield can never exceed the single-qubit hit rate."""
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=50)
        result = run_qubit_array_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_qubits=8, n_chips=500, seed=7,
        )
        assert result.chip_yield_pct <= result.hit_rate * 100.0 + 1e-6

    def test_forty_qubit_lattice_runs_and_reports_low_yield(self) -> None:
        """The headline result: independent per-qubit variation compounds badly."""
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=50)
        result = run_qubit_array_yield(
            process=_process(), junction=_junction(), shunt_c_pf=0.07,
            target=target, n_qubits=40, n_chips=300, seed=42,
        )
        assert result.n_qubits_per_chip == 40
        assert result.chip_yield_pct < result.hit_rate * 100.0
        assert result.chip_yield_pct <= 100.0

    def test_rejects_too_few_chips(self) -> None:
        target = FrequencyTarget(target_ghz=4.7, tolerance_mhz=50)
        with pytest.raises(ValueError):
            run_qubit_array_yield(
                process=_process(), junction=_junction(), shunt_c_pf=0.07,
                target=target, n_qubits=4, n_chips=10, seed=1,
            )


class TestYieldCLI:
    def test_cli_yield_jj(self, capsys) -> None:
        code = cli_main([
            "yield", "jj",
            "--jc", str(REALISTIC_JC), "--wafer-sigma-pct", "5", "--local-sigma-pct", "3",
            "--width-um", "0.1414", "--height-um", "0.1414",
            "--shunt-c-pf", "0.07", "--target-ghz", "4.7", "--tolerance-mhz", "50",
            "--n-samples", "500", "--seed", "1",
        ])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["analysis"] == "jj"
        assert 0.0 <= payload["yield_pct"] <= 100.0
        assert payload["synthetic"] is True

    def test_cli_yield_qubit_array(self, capsys) -> None:
        code = cli_main([
            "yield", "qubit-array",
            "--jc", str(REALISTIC_JC), "--wafer-sigma-pct", "5", "--local-sigma-pct", "3",
            "--width-um", "0.1414", "--height-um", "0.1414",
            "--shunt-c-pf", "0.07", "--target-ghz", "4.7", "--tolerance-mhz", "50",
            "--n-qubits", "40", "--n-chips", "300", "--seed", "42",
        ])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["n_qubits_per_chip"] == 40
        assert payload["chip_yield_pct"] is not None

    def test_cli_yield_jj_writes_evidence(self, tmp_path, capsys) -> None:
        out_dir = tmp_path / "evidence"
        code = cli_main([
            "yield", "jj",
            "--jc", str(REALISTIC_JC), "--wafer-sigma-pct", "5", "--local-sigma-pct", "3",
            "--width-um", "0.1414", "--height-um", "0.1414",
            "--shunt-c-pf", "0.07", "--target-ghz", "4.7", "--tolerance-mhz", "50",
            "--n-samples", "500", "--seed", "1", "--out", str(out_dir),
        ])
        assert code == 0
        assert (out_dir / "jj_yield_report.json").is_file()
        assert (out_dir / "jj_yield_report.md").is_file()
