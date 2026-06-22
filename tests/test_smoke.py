from __future__ import annotations

import json
import os
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from text_to_gds.adapters import resolve_josephsoncircuits_analysis_mode
from text_to_gds.drc import parse_drc_report
from text_to_gds.pcells import (
    cpw_quarter_wave_resonator,
    cpw_straight,
    dc_squid_pair,
    jj_ic_calibration_array,
    lumped_element_jpa_seed,
    manhattan_josephson_junction,
    meander_inductor,
    periodically_loaded_kit_unit_cell,
    photonic_crystal_stwpa,
    via_chain_monitor,
)
from text_to_gds.server import (
    compile_layout,
    export_3d_preview,
    export_cad_artifacts,
    export_hamiltonian_model,
    export_measurement_plan,
    export_openems_project,
    export_quantum_metal_bridge,
    export_rf_network,
    export_scientific_plot,
    extract_layout,
    list_pcells,
    list_research_integrations,
    list_simulators,
    plan_ljpa,
    run_parameter_sweep,
    run_process_drc,
    run_design_workflow,
    run_drc,
    run_gaydamachenko_jtwpa_benchmark,
    run_magic_extract,
    run_optimized_design_workflow,
    run_research_optimization,
    run_simulation,
    run_traveling_wave_paper_benchmark,
    run_validation_checklist,
)
from text_to_gds.simulation import (
    critical_current_ua,
    dc_squid_effective_critical_current_ua,
    josephson_inductance_ph,
)
from text_to_gds.ui import create_workbench_server


def test_manhattan_josephson_junction_writes_gds(tmp_path):
    component = manhattan_josephson_junction()
    output = tmp_path / "jj.gds"

    component.write_gds(output)

    assert output.exists()
    assert component.info["junction_area_um2"] == 0.22 * 0.22
    assert len(component.ports) == 4


def test_passive_pcells_expose_performance_parameters(tmp_path):
    cpw = cpw_straight(length=120, trace_width=8, gap=4, angle_deg=45)
    assert cpw.info["device_type"] == "cpw_straight"
    assert cpw.info["angle_deg"] == 45
    assert cpw.info["gap_um"] == 4
    assert len(cpw.ports) == 2

    inductor = meander_inductor(num_turns=4, segment_length=15, trace_width=1, pitch=3)
    assert inductor.info["device_type"] == "meander_inductor"
    assert inductor.info["electrical_length_um"] == 4 * 15 + 3 * 3

    output = tmp_path / "passive.gds"
    inductor.write_gds(output)
    assert output.exists()

    via_chain = via_chain_monitor()
    assert via_chain.info["device_type"] == "via_chain_monitor"
    assert via_chain.info["stage_count"] == 100
    assert via_chain.info["estimated_total_resistance_ohm"] < 50.0
    assert {port.name for port in via_chain.ports} == {"input", "output"}

    resonator = cpw_quarter_wave_resonator(target_frequency_ghz=6.0)
    assert resonator.info["device_type"] == "cpw_quarter_wave_resonator"
    assert resonator.info["electrical_length_um"] > 4_000
    assert resonator.info["gap_um"] == 6.0
    assert {port.name for port in resonator.ports} == {
        "feed_in",
        "feed_out",
        "resonator_open",
    }


def test_jj_ic_calibration_array_has_per_device_metadata(tmp_path):
    array = jj_ic_calibration_array()
    junctions = array.info["junctions"]
    assert array.info["active_region_um"] == [60.0, 12.0]
    assert len(junctions) == 16
    assert junctions[0]["expected_ic_ua"] == 0.08
    assert junctions[-1]["expected_ic_ua"] == 0.4
    output = tmp_path / "jj_calibration.gds"
    array.write_gds(output)
    assert output.exists()


def test_lumped_element_jpa_seed_writes_gds(tmp_path):
    squid = dc_squid_pair()
    assert squid.info["device_type"] == "dc_squid_pair"
    assert squid.info["squid_junction_count"] == 2
    assert squid.info["junction_area_um2"] == 2 * 0.22 * 0.22

    component = lumped_element_jpa_seed(center_frequency_ghz=5.0, target_bandwidth_mhz=500.0)
    assert component.info["device_type"] == "lumped_element_jpa_seed"
    assert component.info["center_frequency_ghz"] == 5.0
    assert component.info["target_bandwidth_mhz"] == 500.0
    assert component.info["squid_enabled"] is True
    assert component.info["squid_junction_count"] == 2
    assert component.info["junction_area_um2"] == 2 * 0.22 * 0.22
    assert "cpw_trace_width_um" in component.info
    assert len(component.ports) == 6

    output = tmp_path / "ljpa_seed.gds"
    component.write_gds(output)
    assert output.exists()


def test_paper_referenced_traveling_wave_pcells(tmp_path):
    stwpa = photonic_crystal_stwpa(sample="A")
    assert stwpa.info["squid_count"] == 2160
    assert stwpa.info["junction_count"] == 4320
    assert stwpa.info["length_um"] == 7128.0
    assert {port.name for port in stwpa.ports} == {"rf_in", "rf_out"}
    stwpa.write_gds(tmp_path / "stwpa.gds")

    kit = periodically_loaded_kit_unit_cell()
    assert kit.info["region_count"] == 7
    assert kit.info["unit_cell_length_um"] == 2565.0
    kit.write_gds(tmp_path / "kit.gds")


def test_traveling_wave_paper_benchmark(monkeypatch, tmp_path):
    monkeypatch.setattr("text_to_gds.server.ARTIFACT_ROOT", tmp_path)
    result = run_traveling_wave_paper_benchmark()
    assert result["status"] == "passed"
    assert all(result["checks"].values())
    gaps = result["erickson_kit"]["band_gaps"]["gaps"][:9]
    assert max(gap["lower_relative_error"] for gap in gaps) < 0.01
    assert max(gap["width_relative_error"] for gap in gaps) < 0.05
    assert result["planat_stwpa"]["sample_a"]["relative_error"]["gap_center"] < 0.02
    assert (tmp_path / "traveling-wave-paper-parity.json").exists()
    assert (tmp_path / "traveling-wave-paper-parity.csv").exists()
    assert (tmp_path / "traveling-wave-paper-parity.png").exists()


def test_gaydamachenko_jtwpa_paper_benchmark(monkeypatch, tmp_path):
    monkeypatch.setattr("text_to_gds.server.ARTIFACT_ROOT", tmp_path)
    result = run_gaydamachenko_jtwpa_benchmark()
    assert result["status"] == "passed"
    assert all(result["checks"].values())
    assert result["stop_bands"][0]["upper_ghz"] < 12.48
    assert result["stop_bands"][1]["lower_ghz"] < 25.84 < result["stop_bands"][1]["upper_ghz"]
    assert result["comparison"]["coherence_length_relative_error"] < 0.15
    assert result["comparison"]["computed_gain_in_reported_band"]["minimum_db"] > 18.0
    assert (tmp_path / "gaydamachenko-3wm-jtwpa.json").exists()
    assert (tmp_path / "gaydamachenko-3wm-jtwpa.csv").exists()
    assert (tmp_path / "gaydamachenko-3wm-jtwpa.png").exists()


def test_mock_tool_chain_writes_sidecars(monkeypatch, tmp_path):
    monkeypatch.setattr("text_to_gds.server.ARTIFACT_ROOT", tmp_path)

    compiled = compile_layout(output_name="toolchain.gds")
    assert compiled["status"] == "compiled"
    assert (tmp_path / "toolchain.layout.png").exists()

    sidecar_path = tmp_path / "toolchain.sidecar.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["schema"] == "text-to-gds.sidecar.v0"
    assert sidecar["screenshot_path"] == compiled["screenshot_path"]
    assert sidecar["info"]["device_type"] == "manhattan_josephson_junction"
    assert sidecar["ports"][0]["layer"] == [3, 0]
    assert sidecar["labels"][0]["text"].startswith("JJ area")

    drc = run_drc(compiled["gds_path"])
    assert drc["status"] == "passed"
    assert drc["engine"] == "klayout_python_bbox"
    assert drc["checked_shapes"] == 3

    failing_drc = run_drc(compiled["gds_path"], min_width_um=0.3)
    assert failing_drc["status"] == "failed"
    assert failing_drc["violations"][0]["rule"] == "min_bbox_width"
    assert failing_drc["violations"][0]["layer"] == [4, 0]

    simulation = run_simulation(compiled["sidecar_path"], jc_ua_per_um2=2.0)
    assert simulation["critical_current_ua"] == sidecar["info"]["junction_area_um2"] * 2.0
    assert simulation["josephson_inductance_ph"] is not None
    assert simulation["physical_performance"]["ports"]["input"]["name"] == "bottom_west"
    assert simulation["plot"]["schema"] == "text-to-gds.simulation-plot.v0"
    assert simulation["scientific_plot"]["schema"] == "text-to-gds.scientific-plot.v0"
    assert (tmp_path / "toolchain.sidecar.simulation.png").exists()
    assert (tmp_path / "toolchain.sidecar.scientific.png").exists()
    assert (tmp_path / "toolchain.sidecar.scientific.svg").exists()
    assert (tmp_path / "toolchain.sidecar.scientific.csv").exists()

    plot = export_scientific_plot(simulation["result_path"], output_name="toolchain.review")
    assert plot["plot_type"] in {"line", "metric_summary"}
    assert (tmp_path / "toolchain.review.png").exists()

    extraction = extract_layout(compiled["sidecar_path"])
    assert extraction["schema"] == "text-to-gds.extraction-summary.v0"
    assert extraction["parameters"]["junction_area_um2"] == sidecar["info"]["junction_area_um2"]
    assert extraction["gds_shapes"]
    assert extraction["labels"][0]["layer"] == [10, 0]

    magic = run_magic_extract(
        compiled["gds_path"],
        output_name="toolchain.magic",
        magic_executable="definitely_missing_magic_for_test",
    )
    assert magic["status"] == "skipped"
    assert magic["adapter_result"]["adapter"] == "Magic VLSI"
    assert (tmp_path / "toolchain.magic.magic.tcl").exists()
    assert (tmp_path / "toolchain.magic.magic.json").exists()

    preview = export_3d_preview(compiled["gds_path"])
    assert preview["status"] == "previewed"
    assert (tmp_path / "toolchain.stack3d.html").exists()
    assert (tmp_path / "toolchain.stack3d.json").exists()

    cad = export_cad_artifacts(compiled["gds_path"])
    assert cad["schema"] == "text-to-gds.cad-export.v0"
    assert cad["shape_count"] == 3
    assert (tmp_path / "toolchain.layout.svg").exists()
    assert (tmp_path / "toolchain.layout.dxf").exists()
    assert (tmp_path / "toolchain.stack.stl").exists()
    assert (tmp_path / "toolchain.cad.json").exists()

    sweep = run_parameter_sweep(
        compiled["sidecar_path"],
        sweep_parameter="jc_ua_per_um2",
        start=1.0,
        stop=3.0,
        points=3,
    )
    assert sweep["schema"] == "text-to-gds.parameter-sweep.v0"
    assert [row["critical_current_ua"] for row in sweep["rows"]] == [0.0484, 0.0968, 0.1452]
    assert (tmp_path / "toolchain.sidecar.jc_ua_per_um2.sweep.png").exists()
    assert (tmp_path / "toolchain.sidecar.jc_ua_per_um2.sweep.csv").exists()

    josim = run_simulation(
        compiled["sidecar_path"],
        simulator="josim",
        jc_ua_per_um2=2.0,
        adapter_executable="definitely_missing_josim_for_test",
    )
    assert josim["adapter"] == "JoSIM"
    assert josim["adapter_status"] == "skipped"
    assert (tmp_path / "toolchain.sidecar.josim.cir").exists()

    ngspice = run_simulation(
        compiled["sidecar_path"],
        simulator="ngspice",
        jc_ua_per_um2=2.0,
        adapter_executable="definitely_missing_ngspice_for_test",
    )
    assert ngspice["adapter"] == "ngspice"
    assert ngspice["adapter_status"] == "skipped"
    assert (tmp_path / "toolchain.sidecar.ngspice.cir").exists()

    process_drc = run_process_drc(
        compiled["gds_path"],
        output_name="toolchain.process",
        klayout_executable="definitely_missing_klayout_for_test",
    )
    assert process_drc["engine"] == "klayout_python_process_rules"
    assert process_drc["status"] == "passed"
    assert process_drc["checked_shapes"] == 3
    assert "definitely_missing_klayout_for_test" in process_drc["warnings"][0]
    assert "KLayout Python process rules" in process_drc["warnings"][-1]
    assert process_drc["report_path"].endswith("toolchain.process.drc.json")

    workflow = run_design_workflow("Design a 5 Ghz LJPA with wilde bandwidth")
    assert workflow["schema"] == "text-to-gds.design-workflow.v0"
    assert workflow["pcell"] == "lumped_element_jpa_seed"
    assert workflow["plan"]["target"]["center_frequency_ghz"] == 5.0
    assert workflow["compile"]["gds_path"].endswith("ljpa_seed.gds")
    assert workflow["process_drc"]["report_path"].endswith("ljpa_seed.process.drc.json")
    assert workflow["cad"]["report_path"].endswith("ljpa_seed.cad.json")
    assert workflow["validation"]["report_path"].endswith("ljpa_seed.validation.json")
    assert (tmp_path / "ljpa_seed.workbench.html").exists()
    workbench_html = (tmp_path / "ljpa_seed.workbench.html").read_text(encoding="utf-8")
    assert "Text-to-GDS Workbench" in workbench_html
    assert "Simulation Metrics" in workbench_html
    assert "Simulation Plot" in workbench_html
    assert "Input/Output Ports" in workbench_html

    via_compiled = compile_layout(pcell="via_chain_monitor", output_name="via_chain.gds")
    via_sidecar = json.loads(Path(via_compiled["sidecar_path"]).read_text(encoding="utf-8"))
    assert via_sidecar["info"]["stage_count"] == 100
    assert [port["name"] for port in via_sidecar["ports"]] == ["input", "output"]
    via_simulation = run_simulation(via_compiled["sidecar_path"])
    assert via_simulation["physical_performance"]["analysis_type"] == "via_chain_resistance_estimate"
    assert via_simulation["physical_performance"]["estimated_total_resistance_ohm"] < 50.0

    jpa_flux = compile_layout(
        pcell="lumped_element_jpa_seed",
        output_name="flux_jpa.gds",
    )
    flux_simulation = run_simulation(
        jpa_flux["sidecar_path"],
        jc_ua_per_um2=2.0,
        target_frequency_ghz=5.0,
        target_bandwidth_mhz=500.0,
        flux_bias_phi0=0.25,
        squid_asymmetry=0.0,
        flux_period_current_ma=2.0,
    )
    expected_zero_flux_ic = 2 * 0.22 * 0.22 * 2.0
    assert round(flux_simulation["zero_flux_critical_current_ua"], 12) == round(
        expected_zero_flux_ic, 12
    )
    assert round(flux_simulation["critical_current_ua"], 12) == round(
        expected_zero_flux_ic * 0.5**0.5, 12
    )
    flux_tuning = flux_simulation["physical_performance"]["flux_tuning"]
    assert flux_tuning["schema"] == "text-to-gds.squid-flux-modulation.v0"
    assert flux_tuning["flux_period_current_ma"] == 2.0
    assert flux_tuning["operating_point"]["coil_current_ma"] == 0.5
    assert round(flux_tuning["operating_point"]["resonant_frequency_ghz"], 6) == round(
        5.0 * (0.5**0.5) ** 0.5,
        6,
    )

    validation = run_validation_checklist(
        gds_path=jpa_flux["gds_path"],
        sidecar_path=jpa_flux["sidecar_path"],
        drc_path=run_drc(jpa_flux["gds_path"])["report_path"],
        extraction_path=extract_layout(jpa_flux["sidecar_path"])["result_path"],
        simulation_path=flux_simulation["result_path"],
        cad_path=export_cad_artifacts(jpa_flux["gds_path"])["report_path"],
        output_name="flux_jpa.validation.json",
    )
    assert validation["schema"] == "text-to-gds.validation-roadmap.v0"
    assert validation["sections"]["layout_fabrication"][4]["name"] == "SQUID loop geometry verified"
    assert validation["sections"]["layout_fabrication"][4]["status"] == "pass"


def test_external_simulator_fake_executables(monkeypatch, tmp_path):
    monkeypatch.setattr("text_to_gds.server.ARTIFACT_ROOT", tmp_path)
    compiled = compile_layout(output_name="adapter.gds")

    fake_josim = tmp_path / "fake_josim.py"
    fake_josim.write_text(
        "print('time voltage')\nprint('0 0')\nprint('1 2')\n",
        encoding="utf-8",
    )
    josim = run_simulation(
        compiled["sidecar_path"],
        simulator="josim",
        adapter_executable=str(fake_josim),
    )
    assert josim["adapter_status"] == "executed"
    assert josim["adapter_result"]["parsed_rows"] == [
        {"time": 0.0, "voltage": 0.0},
        {"time": 1.0, "voltage": 2.0},
    ]

    fake_ngspice = tmp_path / "fake_ngspice.py"
    fake_ngspice.write_text(
        "print('time v_in')\nprint('0 0')\nprint('1e-12 3.5')\n",
        encoding="utf-8",
    )
    ngspice = run_simulation(
        compiled["sidecar_path"],
        simulator="ngspice",
        adapter_executable=str(fake_ngspice),
    )
    assert ngspice["adapter_status"] == "executed"
    assert ngspice["adapter_result"]["parsed_rows"] == [
        {"time": 0.0, "v_in": 0.0},
        {"time": 1e-12, "v_in": 3.5},
    ]
    generated_ngspice = tmp_path / "adapter.sidecar.ngspice.cir"
    assert generated_ngspice.exists()
    generated_ngspice_text = generated_ngspice.read_text(encoding="utf-8")
    assert "Text-to-GDS generated ngspice JJ starter deck" in generated_ngspice_text
    assert ".tran" in generated_ngspice_text
    assert (tmp_path / "adapter.sidecar.ngspice.json").exists()

    fake_magic = tmp_path / "fake_magic.py"
    fake_magic.write_text(
        "import pathlib, sys\n"
        "script = pathlib.Path(sys.argv[-1])\n"
        "text = script.read_text(encoding='utf-8')\n"
        "print('magic ok')\n"
        "assert 'gds read' in text\n"
        "assert 'ext2spice' in text\n",
        encoding="utf-8",
    )
    magic = run_magic_extract(
        compiled["gds_path"],
        output_name="adapter.magic",
        magic_executable=str(fake_magic),
    )
    assert magic["status"] == "executed_with_warnings"
    assert magic["adapter_result"]["returncode"] == 0
    assert "Magic did not produce a SPICE netlist." in magic["adapter_result"]["warnings"]
    generated_magic = tmp_path / "adapter.magic.magic.tcl"
    assert generated_magic.exists()
    generated_magic_text = generated_magic.read_text(encoding="utf-8")
    assert "Text-to-GDS generated Magic extraction script" in generated_magic_text
    assert "ext2spice" in generated_magic_text

    fake_julia = tmp_path / "fake_julia.py"
    fake_julia.write_text(
        "import json, os\n"
        "result = os.environ['TEXT_TO_GDS_JC_RESULT']\n"
        "open(result, 'w', encoding='utf-8').write(json.dumps({'package_loaded': True}))\n"
        "print('josephsoncircuits ok')\n",
        encoding="utf-8",
    )
    jc = run_simulation(
        compiled["sidecar_path"],
        simulator="JosephsonCircuits.jl",
        adapter_executable=str(fake_julia),
        target_frequency_ghz=5.0,
        target_bandwidth_mhz=500.0,
    )
    assert jc["adapter_status"] == "executed"
    assert jc["adapter_result"]["result"] == {"package_loaded": True}
    assert jc["adapter_plan"]["analysis_mode"] == "single_port_reflection"
    generated_julia = tmp_path / "adapter.sidecar.josephsoncircuits.jl"
    assert generated_julia.exists()
    generated_text = generated_julia.read_text(encoding="utf-8")
    assert "hbsolve" in generated_text
    assert "single_port_reflection_harmonic_balance" in generated_text

    jpa = compile_layout(
        pcell="lumped_element_jpa_seed",
        parameters={
            "center_frequency_ghz": 5.0,
            "target_bandwidth_mhz": 500.0,
            "target_gain_db": 20.0,
        },
        output_name="jpa_adapter.gds",
    )
    jpa_sidecar = json.loads(Path(jpa["sidecar_path"]).read_text(encoding="utf-8"))
    assert resolve_josephsoncircuits_analysis_mode(jpa_sidecar) == "multiport_ljpa"

    jpa_jc = run_simulation(
        jpa["sidecar_path"],
        simulator="JosephsonCircuits.jl",
        adapter_executable=str(fake_julia),
        jc_ua_per_um2=2.0,
        target_frequency_ghz=5.0,
        target_bandwidth_mhz=500.0,
    )
    assert jpa_jc["adapter_status"] == "executed"
    assert jpa_jc["adapter_plan"]["analysis_mode"] == "multiport_ljpa"
    generated_multiport = tmp_path / "jpa_adapter.sidecar.josephsoncircuits.jl"
    generated_multiport_text = generated_multiport.read_text(encoding="utf-8")
    assert "multiport_ljpa_harmonic_balance" in generated_multiport_text
    assert "s21_db = s_db(2, 1)" in generated_multiport_text
    assert '\\"s_parameters_db\\"' in generated_multiport_text

    try:
        run_simulation(
            compiled["sidecar_path"],
            simulator="JosephsonCircuits.jl",
            adapter_executable=str(fake_julia),
            analysis_mode="multiport-ljpa",
        )
    except ValueError as error:
        assert "requires a lumped_element_jpa_seed sidecar" in str(error)
    else:
        raise AssertionError("expected multiport analysis to reject a standalone JJ sidecar")


def test_registry_planner_and_adapter_metadata():
    pcells = list_pcells()
    assert "dc_squid_pair" in pcells["pcells"]
    assert "manhattan_josephson_junction" in pcells["pcells"]
    assert "cpw_straight" in pcells["pcells"]
    assert "cpw_quarter_wave_resonator" in pcells["pcells"]
    assert "jj_ic_calibration_array" in pcells["pcells"]
    assert "via_chain_monitor" in pcells["pcells"]

    plan = plan_ljpa("Design a 5 Ghz LJPA with wilde bandwidth")
    assert plan["target"]["center_frequency_ghz"] == 5.0
    assert plan["target"]["bandwidth_mhz"] == 500.0
    assert any("material" in question.lower() for question in plan["clarifying_questions"])
    assert "JosephsonCircuits.jl" in {
        adapter["name"] for adapter in plan["simulation_adapters"]
    }

    simulators = list_simulators()
    assert {adapter["name"] for adapter in simulators["adapters"]} == {
        "JosephsonCircuits.jl",
        "JoSIM",
        "Magic VLSI",
        "PySpice",
        "ngspice",
    }


def test_research_integrations_and_handoff_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr("text_to_gds.server.ARTIFACT_ROOT", tmp_path)
    compiled = compile_layout(
        pcell="lumped_element_jpa_seed",
        output_name="research_jpa.gds",
    )
    simulation = run_simulation(
        compiled["sidecar_path"],
        jc_ua_per_um2=2.0,
        target_frequency_ghz=5.0,
        target_bandwidth_mhz=500.0,
        flux_bias_phi0=0.25,
    )

    integrations = list_research_integrations()
    integration_ids = {item["id"] for item in integrations["integrations"]}
    assert {
        "gdsfactory",
        "josephsoncircuits",
        "scikit-rf",
        "openems",
        "optuna",
        "qiskit-metal",
        "scqubits",
        "qcodes",
    } <= integration_ids

    rf = export_rf_network(simulation["result_path"], output_name="research_jpa")
    assert rf["schema"] == "text-to-gds.rf-network.v0"
    assert rf["frequency_points"] > 2
    assert rf["peak_s21_gain_db"] is not None
    assert (tmp_path / "research_jpa.s2p").exists()
    assert (tmp_path / "research_jpa.rf.png").exists()
    assert (tmp_path / "research_jpa.rf.csv").exists()
    assert (tmp_path / "research_jpa.rf.json").exists()

    # run=False keeps the smoke test fast; the real FDTD path is covered by
    # tests/test_research_execution.py under TEXT_TO_GDS_RUN_EXTERNAL=1.
    openems = export_openems_project(
        compiled["sidecar_path"], output_name="research_jpa", run=False
    )
    assert openems["schema"] == "text-to-gds.openems-project.v0"
    assert openems["model"]["ports"]
    assert (tmp_path / "research_jpa.openems.py").exists()
    assert (tmp_path / "research_jpa.openems.json").exists()

    measurement = export_measurement_plan(
        compiled["sidecar_path"],
        simulation_path=simulation["result_path"],
        output_name="research_jpa",
    )
    assert measurement["schema"] == "text-to-gds.measurement-plan.v0"
    assert measurement["frequency_sweep"]["vna_ports"] == ["rf_in", "rf_out"]
    assert (tmp_path / "research_jpa.measurement.json").exists()
    assert (tmp_path / "research_jpa.qcodes.py").exists()

    hamiltonian = export_hamiltonian_model(
        compiled["sidecar_path"],
        output_name="research_jpa",
        jc_ua_per_um2=2.0,
        flux_bias_phi0=0.25,
    )
    assert hamiltonian["schema"] == "text-to-gds.hamiltonian-model.v0"
    assert hamiltonian["parameters"]["ej_ghz"] is not None
    assert hamiltonian["parameters"]["ec_ghz"] is not None
    assert (tmp_path / "research_jpa.hamiltonian.json").exists()
    assert (tmp_path / "research_jpa.scqubits.py").exists()

    qmetal = export_quantum_metal_bridge(compiled["sidecar_path"], output_name="research_jpa")
    assert qmetal["schema"] == "text-to-gds.quantum-metal-bridge.v0"
    assert qmetal["component"]["name"] == "lumped_element_jpa_seed"
    assert (tmp_path / "research_jpa.qmetal.json").exists()
    assert (tmp_path / "research_jpa.qmetal.py").exists()

    optimization = run_research_optimization(
        compiled["sidecar_path"],
        output_name="research_jpa",
        n_trials=4,
        target_frequency_ghz=5.0,
        target_gain_db=20.0,
        target_bandwidth_mhz=500.0,
        force_fallback=True,
    )
    assert optimization["schema"] == "text-to-gds.research-optimization.v0"
    assert optimization["engine"] == "fallback_grid"
    assert len(optimization["trials"]) == 4
    assert optimization["best"]["objective"] >= 0.0
    assert (tmp_path / "research_jpa.optuna.json").exists()
    assert (tmp_path / "research_jpa.optuna.csv").exists()
    assert (tmp_path / "research_jpa.optuna.png").exists()


def test_optimized_design_workflow_and_live_ui(monkeypatch, tmp_path):
    monkeypatch.setattr("text_to_gds.server.ARTIFACT_ROOT", tmp_path)
    optimized = run_optimized_design_workflow(
        "Design a 6 Ghz LJPA with 700 MHz bandwidth",
        output_name="optimized.gds",
        max_iterations=3,
    )
    assert optimized["status"] == "optimized_with_local_surrogate"
    assert optimized["optimization"]["final_parameters"]["cpw_length"] != 210.0
    assert (tmp_path / "optimized.workbench.html").exists()

    httpd = create_workbench_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{httpd.server_port}"
        with urllib.request.urlopen(base_url, timeout=10) as response:
            html = response.read().decode("utf-8")
        assert "Text-to-GDS Live Workbench" in html

        payload = json.dumps(
            {
                "prompt": "Design a 5 Ghz LJPA with wilde bandwidth",
                "output_name": "ui_seed.gds",
                "optimize": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url}/api/design-workflow",
            data=payload,
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            api_result = json.loads(response.read().decode("utf-8"))
        assert api_result["status"] == "optimized_with_local_surrogate"
        assert (tmp_path / "ui_seed.workbench.html").exists()

        plot_path = api_result["simulation"]["plot_path"]
        artifact_url = f"{base_url}/api/artifact?path={urllib.parse.quote(plot_path, safe='')}"
        with urllib.request.urlopen(artifact_url, timeout=10) as response:
            plot_bytes = response.read()
            content_type = response.headers.get("content-type", "")
        assert content_type.startswith("image/png")
        assert plot_bytes.startswith(b"\x89PNG")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_parse_lyrdb_report(tmp_path):
    lyrdb = tmp_path / "sample.lyrdb"
    lyrdb.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<report-database>
  <categories>
    <category id="c1"><name>M1_min_width</name><description>M1 width below limit</description></category>
  </categories>
  <cells>
    <cell id="cell1"><name>TOP</name></cell>
  </cells>
  <items>
    <item>
      <category>c1</category>
      <cell>cell1</cell>
      <values><value><box>-1,-2;3,4</box></value></values>
    </item>
  </items>
</report-database>
""",
        encoding="utf-8",
    )

    violations = parse_drc_report(lyrdb)
    assert violations == [
        {
            "rule": "M1_min_width",
            "message": "M1 width below limit",
            "severity": "error",
            "cell": "TOP",
            "bbox_um": [-1.0, -2.0, 3.0, 4.0],
            "geometry": ["-1,-2;3,4"],
        }
    ]


def test_mcp_stdio_protocol_lists_and_calls_tools(tmp_path):
    async def run_client() -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env = {
            **os.environ,
            "TEXT_TO_GDS_WORKSPACE": str(tmp_path / "workspace"),
        }
        params = StdioServerParameters(
            command=sys.executable,
            args=["src/text_to_gds/server.py"],
            cwd=repo_root,
            env=env,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                assert {
                    "compile_layout",
                    "run_process_drc",
                    "run_magic_extract",
                    "plan_ljpa",
                    "run_design_workflow",
                    "export_cad_artifacts",
                    "export_scientific_plot",
                    "run_parameter_sweep",
                    "run_validation_checklist",
                    "list_research_integrations",
                    "export_rf_network",
                    "export_openems_project",
                    "export_measurement_plan",
                    "export_hamiltonian_model",
                    "export_quantum_metal_bridge",
                    "run_research_optimization",
                } <= names

                result = await session.call_tool(
                    "plan_ljpa",
                    {"prompt": "Design a 5 Ghz LJPA with wilde bandwidth"},
                )
                payload = json.loads(result.content[0].text)
                assert payload["target"]["center_frequency_ghz"] == 5.0
                assert payload["target"]["bandwidth_mhz"] == 500.0

    anyio.run(run_client)


def test_ideal_josephson_simulation_units():
    ic_ua = critical_current_ua(junction_area_um2=0.0484, jc_ua_per_um2=2.0)
    assert ic_ua == 0.0968

    lj_ph = josephson_inductance_ph(ic_ua)
    assert lj_ph is not None
    assert round(lj_ph, 6) == 3399.855149

    squid_zero_flux = dc_squid_effective_critical_current_ua(
        0.2,
        flux_bias_phi0=0.0,
        squid_asymmetry=0.0,
    )
    squid_half_flux = dc_squid_effective_critical_current_ua(
        0.2,
        flux_bias_phi0=0.5,
        squid_asymmetry=0.0,
    )
    squid_asymmetric_half_flux = dc_squid_effective_critical_current_ua(
        0.2,
        flux_bias_phi0=0.5,
        squid_asymmetry=0.1,
    )
    assert squid_zero_flux == 0.2
    assert round(squid_half_flux, 12) == 0.0
    assert round(squid_asymmetric_half_flux, 12) == 0.02


def test_ideal_josephson_simulation_rejects_invalid_jc():
    try:
        critical_current_ua(junction_area_um2=0.0484, jc_ua_per_um2=0.0)
    except ValueError as error:
        assert "jc_ua_per_um2 must be positive" in str(error)
    else:
        raise AssertionError("expected ValueError")
