"""Verification that each upstream library actually executes inside Text-to-GDS.

Fast, always-on checks cover the pure-Python libraries (scqubits, QCoDeS, Optuna,
scikit-rf). The slow external simulators (JosephsonCircuits.jl via Julia, openEMS via
FDTD) are gated behind TEXT_TO_GDS_RUN_EXTERNAL=1 so the default suite stays quick while
full verification remains available. qiskit-metal is allowed to skip cleanly because it
cannot be pip-installed on Windows/Python 3.12 (PySide2 constraint).
"""

from __future__ import annotations

import json
import os
from importlib.util import find_spec

import pytest

RUN_EXTERNAL = os.environ.get("TEXT_TO_GDS_RUN_EXTERNAL") == "1"


def _ljpa_sidecar() -> dict:
    return {
        "pcell": "lumped_element_jpa_seed",
        "gds_path": "verify.gds",
        "info": {
            "device_type": "lumped_element_jpa_seed",
            "junction_area_um2": 0.0484,
            "center_frequency_ghz": 5.0,
            "target_bandwidth_mhz": 500.0,
            "target_gain_db": 20.0,
            "cpw_trace_width_um": 10.0,
            "squid_enabled": True,
            "squid_junction_count": 2,
        },
        "ports": [{"name": "rf_in"}, {"name": "rf_out"}],
    }


@pytest.mark.skipif(find_spec("scqubits") is None, reason="scqubits not installed")
def test_scqubits_executes(tmp_path):
    from text_to_gds.research import write_hamiltonian_model

    model = write_hamiltonian_model(
        _ljpa_sidecar(),
        json_path=tmp_path / "h.json",
        script_path=tmp_path / "h.py",
        plot_path=tmp_path / "h.png",
        jc_ua_per_um2=200.0,
        flux_bias_phi0=0.1,
        squid_asymmetry=0.05,
    )
    execution = model["execution"]
    assert execution["status"] == "executed"
    assert execution["engine"].startswith("scqubits")
    assert len(execution["energy_levels_ghz"]) >= 4
    assert (tmp_path / "h.png").exists()


@pytest.mark.skipif(find_spec("qcodes") is None, reason="qcodes not installed")
def test_qcodes_executes(tmp_path):
    from text_to_gds.research import write_measurement_plan

    plan = write_measurement_plan(
        _ljpa_sidecar(),
        plan_path=tmp_path / "m.json",
        script_path=tmp_path / "m.py",
        db_path=tmp_path / "m.db",
        plot_path=tmp_path / "m.png",
        simulation={"physical_performance": {"center_frequency_ghz": 5.0, "bandwidth_3db_mhz": 420.0}},
    )
    execution = plan["execution"]
    assert execution["status"] == "executed"
    assert execution["run_id"] >= 1
    assert execution["guid"]
    assert (tmp_path / "m.db").exists()


@pytest.mark.skipif(find_spec("optuna") is None, reason="optuna not installed")
def test_optuna_executes(tmp_path):
    from text_to_gds.research import run_research_optimization

    result = run_research_optimization(
        _ljpa_sidecar(),
        json_path=tmp_path / "o.json",
        csv_path=tmp_path / "o.csv",
        plot_path=tmp_path / "o.png",
        n_trials=6,
    )
    assert result["engine"] == "optuna"
    assert len(result["trials"]) == 6


@pytest.mark.skipif(find_spec("skrf") is None, reason="scikit-rf not installed")
def test_scikit_rf_reads_touchstone(tmp_path):
    from text_to_gds.rf import write_rf_network_artifacts

    simulation = {
        "physical_performance": {
            "center_frequency_ghz": 5.0,
            "bandwidth_3db_mhz": 500.0,
            "estimated_peak_gain_db": 20.0,
        }
    }
    result = write_rf_network_artifacts(
        simulation,
        touchstone_path=tmp_path / "n.s2p",
        report_path=tmp_path / "n.json",
        plot_path=tmp_path / "n.png",
        csv_path=tmp_path / "n.csv",
    )
    skrf = result["scikit_rf"]
    assert skrf is not None
    assert skrf.get("available") is True
    assert skrf.get("nports") == 2


def test_qiskit_metal_executes_or_skips_cleanly(tmp_path):
    from text_to_gds.research import write_quantum_metal_bridge

    bridge = write_quantum_metal_bridge(
        _ljpa_sidecar(),
        json_path=tmp_path / "q.json",
        script_path=tmp_path / "q.py",
        gds_path=tmp_path / "q.gds",
    )
    status = bridge["execution"]["status"]
    assert status in {"executed", "skipped"}
    if status == "skipped":
        assert "reason" in bridge["execution"]


@pytest.mark.skipif(not RUN_EXTERNAL, reason="set TEXT_TO_GDS_RUN_EXTERNAL=1 to run the FDTD/Julia path")
def test_openems_executes(tmp_path):
    from text_to_gds.research import _find_openems_runtime, write_openems_project

    if _find_openems_runtime()[0] is None:
        pytest.skip("no local openEMS runtime")
    result = write_openems_project(
        _ljpa_sidecar(),
        script_path=tmp_path / "e.py",
        report_path=tmp_path / "e.json",
        result_path=tmp_path / "e.result.json",
        plot_path=tmp_path / "e.png",
        timeout_seconds=600,
    )
    assert result["status"] == "executed"
    execution = result["execution"]
    assert execution["effective_permittivity_midband"] > 1.0
    assert execution["insertion_loss_db_midband"] < 1.0


@pytest.mark.skipif(not RUN_EXTERNAL, reason="set TEXT_TO_GDS_RUN_EXTERNAL=1 to run the FDTD/Julia path")
def test_josephsoncircuits_jpa_executes(tmp_path):
    from text_to_gds.adapters import _command_prefix
    from text_to_gds.jpa_analysis import run_jpa_analysis

    if _command_prefix("julia") is None:
        pytest.skip("no local Julia/JosephsonCircuits runtime")
    report = run_jpa_analysis(
        _ljpa_sidecar(),
        script_path=tmp_path / "j.jl",
        result_path=tmp_path / "j.result.json",
        report_path=tmp_path / "j.json",
        plot_path=tmp_path / "j.png",
        jc_ua_per_um2=6.8,
        target_frequency_ghz=5.0,
        target_bandwidth_mhz=500.0,
        timeout_seconds=600,
    )
    assert report["status"] == "executed"
    metrics = report["metrics"]
    assert metrics["peak_gain_db"] > 5.0
    assert metrics["squeezing_db"] < 0.0
    assert metrics["oscillation_threshold_pump_fraction"] is not None
    assert json.loads((tmp_path / "j.result.json").read_text())["analysis_status"] == "executed"
