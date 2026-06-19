from __future__ import annotations

import json
from pathlib import Path

import pytest

from text_to_gds.process import DEFAULT_PROCESS
from text_to_gds.pyaedt_bridge import em_geometry_correction, write_pyaedt_project_bundle
from text_to_gds.pyaedt_benchmarks import run_pyaedt_benchmark_suite


ROOT = Path(__file__).resolve().parents[1]


def test_pyaedt_bundle_maps_process_and_generates_current_api_scripts(tmp_path):
    gds = tmp_path / "device.gds"
    gds.write_bytes(b"GDS fixture")
    sidecar = tmp_path / "device.sidecar.json"
    sidecar.write_text(
        json.dumps(
            {
                "gds_path": str(gds),
                "bbox_um": [[-100.0, -50.0], [100.0, 50.0]],
                "ports": [
                    {
                        "name": "rf_in",
                        "center": [-100.0, 0.0],
                        "width": 10.0,
                        "orientation": 180.0,
                    },
                    {
                        "name": "rf_out",
                        "center": [100.0, 0.0],
                        "width": 10.0,
                        "orientation": 0.0,
                    },
                ],
                "info": {"cpw_gap_um": 6.0},
                "process_stack": DEFAULT_PROCESS.to_dict(),
            }
        ),
        encoding="utf-8",
    )
    result = write_pyaedt_project_bundle(
        gds,
        config_path=tmp_path / "device.pyaedt.config.json",
        hfss_script_path=tmp_path / "device.hfss.py",
        q3d_script_path=tmp_path / "device.q3d.py",
        report_path=tmp_path / "device.pyaedt.json",
        hfss_project_path=tmp_path / "device.aedt",
        q3d_project_path=tmp_path / "device.q3d.aedt",
        sidecar_path=sidecar,
        process_path=ROOT / "process_database" / "generic_nb_3metal_sis_em.yaml",
    )

    assert result["status"] == "prepared"
    config = json.loads((tmp_path / "device.pyaedt.config.json").read_text(encoding="utf-8"))
    assert config["layer_mapping"]["3"]["name"] == "M1"
    assert config["layer_mapping"]["3"]["thickness_um"] == pytest.approx(0.18)
    assert config["substrate"]["relative_permittivity"] == pytest.approx(11.45)
    assert len(config["ports"]["items"]) == 2

    hfss_script = (tmp_path / "device.hfss.py").read_text(encoding="utf-8")
    q3d_script = (tmp_path / "device.q3d.py").read_text(encoding="utf-8")
    compile(hfss_script, "device.hfss.py", "exec")
    compile(q3d_script, "device.q3d.py", "exec")
    assert "app.import_gds_3d" in hfss_script
    assert ".modeler.import_gds_3d" not in hfss_script
    assert "create_linear_count_sweep" in hfss_script
    assert "export_touchstone" in hfss_script
    assert "create_fieldplot_volume" in hfss_script
    assert "Q3d" in q3d_script and "export_matrix_data" in q3d_script


def test_em_geometry_correction_is_a_first_order_optimizer_seed():
    correction = em_geometry_correction(
        target_frequency_ghz=6.0,
        extracted_frequency_ghz=5.95,
        extracted_impedance_ohm=48.0,
    )
    assert correction["frequency_error_percent"] == pytest.approx(-0.8333333333)
    assert correction["recommended_cpw_length_scale"] == pytest.approx(5.95 / 6.0)
    assert correction["recommended_cpw_gap_scale_seed"] > 1.0


def test_pyaedt_benchmarks_skip_missing_solver_data_and_compare_real_results(tmp_path):
    prepared = run_pyaedt_benchmark_suite(
        ROOT / "benchmarks" / "pyaedt",
        report_path=tmp_path / "prepared.json",
        results_root=tmp_path / "missing",
    )
    assert prepared["status"] == "prepared"
    assert prepared["counts"] == {"passed": 0, "failed": 0, "skipped": 3}

    results = tmp_path / "results"
    results.mkdir()
    (results / "07_hfss_resonator.result.json").write_text(
        json.dumps({"metrics": {"frequency_ghz": 5.95, "quality_factor": 21000}}),
        encoding="utf-8",
    )
    compared = run_pyaedt_benchmark_suite(
        ROOT / "benchmarks" / "pyaedt",
        report_path=tmp_path / "compared.json",
        results_root=results,
    )
    assert compared["counts"] == {"passed": 1, "failed": 0, "skipped": 2}
    frequency = compared["results"][0]["checks"][0]
    assert frequency["relative_error"] == pytest.approx(0.05 / 6.0)
