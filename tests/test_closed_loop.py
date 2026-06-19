from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from text_to_gds.analytical import write_analytical_verification
from text_to_gds.cryostat import analyze_cryogenic_chain
from text_to_gds.em_bridges import write_hfss_project_bridge, write_sonnet_project_bridge
from text_to_gds.epr import write_epr_analysis
from text_to_gds.experiment_database import record_experiment
from text_to_gds.measurement_recipes import run_measurement_recipe, write_measurement_recipe
from text_to_gds.paper_benchmarks import run_paper_benchmark_suite
from text_to_gds.process_database import ProcessDatabase, plan_process_aware_jpa
from text_to_gds.theory.kerr_jpa import kerr_jpa_gain
from text_to_gds.theory.quantum_noise import quantum_limited_noise_temperature
from text_to_gds.uncertainty import run_process_monte_carlo


ROOT = Path(__file__).resolve().parents[1]


def test_process_database_correction_and_ic_yield():
    database = ProcessDatabase(ROOT / "process_database")
    process = database.get("NCU 2025 AlOx process")
    assert 0.91 < process.expected_ic_yield() < 0.93
    plan = plan_process_aware_jpa(
        "Design a 6GHz JPA using NCU 2025 AlOx process",
        database_root=ROOT / "process_database",
    )
    assert plan["target_frequency_ghz"] == 6.0
    assert round(plan["expected_ic_yield_percent"]) == 92
    assert plan["design_correction"]["corrected_junction_area_um2"] < 0.0484


def test_analytical_models_and_report(tmp_path):
    gain = kerr_jpa_gain(np.asarray([0.0]), kappa_hz=120e6, pump_coupling_hz=55e6)
    assert gain[0] > 100.0
    assert 0.14 < quantum_limited_noise_temperature(6e9) < 0.15
    result = write_analytical_verification(
        report_path=tmp_path / "theory.json",
        plot_path=tmp_path / "theory.png",
    )
    assert result["theory"]["peak_gain_db"] > 20.0
    assert (tmp_path / "theory.png").exists()


def test_process_uncertainty_outputs(tmp_path):
    process = ProcessDatabase(ROOT / "process_database").get("ncu_2025_alox")
    result = run_process_monte_carlo(
        process.raw,
        report_path=tmp_path / "yield.json",
        csv_path=tmp_path / "yield.csv",
        plot_path=tmp_path / "yield.png",
        samples=500,
    )
    assert 0.0 < result["yield_fraction"] < 1.0
    assert result["critical_current_ua"]["standard_deviation"] > 0.0
    assert (tmp_path / "yield.png").exists()


def test_cryostat_noise_budget():
    result = analyze_cryogenic_chain(ROOT / "cryostat" / "input_chain.yaml")
    assert result["available_jpa_input_power_dbm"] == -60.0
    assert result["noise_temperature_at_jpa_input_k"] < 0.1
    assert 0.2 < result["system_noise_referred_to_jpa_input_k"] < 0.3


def test_epr_field_metrics_and_real_script_shape(tmp_path):
    result = write_epr_analysis(
        {"gds_path": "device.gds", "info": {"junction_area_um2": 0.05}},
        report_path=tmp_path / "device.epr.json",
        script_path=tmp_path / "device.pyepr.py",
        field_energy_path=ROOT / "examples" / "epr_field_energies.json",
    )
    assert result["status"] == "executed_from_exported_field_energies"
    assert result["junction_participation"][0]["participation"] == pytest.approx(0.1)
    assert result["dielectric_loss"] > 0.0
    assert result["predicted_T1"] > 0.0
    script = (tmp_path / "device.pyepr.py").read_text(encoding="utf-8")
    assert "DistributedAnalysis" in script and "QuantumAnalysis" in script


def test_hfss_sonnet_and_measurement_recipes(tmp_path):
    gds = tmp_path / "device.gds"
    gds.write_bytes(b"fixture")
    hfss = write_hfss_project_bridge(
        gds,
        script_path=tmp_path / "hfss_build.py",
        report_path=tmp_path / "hfss.json",
        project_path=tmp_path / "device.aedt",
    )
    sonnet = write_sonnet_project_bridge(
        gds,
        script_path=tmp_path / "sonnet_build.m",
        report_path=tmp_path / "sonnet.json",
        output_project_path=tmp_path / "device.son",
    )
    assert hfss["status"] == sonnet["status"] == "prepared"
    assert "Hfss" in (tmp_path / "hfss_build.py").read_text(encoding="utf-8")

    recipe = write_measurement_recipe(
        "gain_map",
        script_path=tmp_path / "gain_map.py",
        plan_path=tmp_path / "gain_map.plan.json",
    )
    assert recipe["axes"]["metric"] == "gain_db"
    dry_run = run_measurement_recipe(
        "gain_map",
        json_path=tmp_path / "gain.json",
        csv_path=tmp_path / "gain.csv",
        plot_path=tmp_path / "gain.png",
    )
    assert dry_run["shape"] == [101, 161]


def test_experiment_feedback_and_paper_suite(tmp_path):
    feedback = record_experiment(
        tmp_path / "experiments.sqlite",
        device_id="JPA-001",
        process_id="ncu_2025_alox",
        design={"target_frequency_ghz": 6.0, "target_critical_current_ua": 0.1},
        measurement={"center_frequency_ghz": 5.8, "critical_current_ua": 0.095},
    )
    assert feedback["run_id"] == 1
    assert feedback["model_correction"]["frequency_scale"] > 1.0
    suite = run_paper_benchmark_suite(
        ROOT / "benchmarks" / "papers",
        report_path=tmp_path / "papers.json",
    )
    assert suite["status"] == "passed"
    assert suite["counts"] == {"passed": 2, "failed": 0, "skipped": 4}
