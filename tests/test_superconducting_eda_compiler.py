from __future__ import annotations

import csv
import json
from pathlib import Path

from text_to_gds.automatic_mesh import generate_solver_inputs_from_graph
from text_to_gds.inverse_design import inverse_design_jpa
from text_to_gds.measurement_comparison import compare_measurement_to_simulation
from text_to_gds.pcells import lumped_element_jpa_seed
from text_to_gds.pdk import load_pdk
from text_to_gds.physics_graph import extract_physics_graph, graph_to_josephsoncircuits_model
from text_to_gds.solver_contract import solver_quantity, validate_solver_execution
from text_to_gds.superconducting_eda_compiler import create_flux_tunable_jpa_for_axion_search


ROOT = Path(__file__).resolve().parents[1]


def _jpa_sidecar(tmp_path: Path) -> tuple[Path, dict]:
    component = lumped_element_jpa_seed(center_frequency_ghz=2.1, target_bandwidth_mhz=100.0)
    gds = tmp_path / "jpa.gds"
    component.write_gds(str(gds))
    ports = []
    try:
        port_items = component.ports.items()
    except AttributeError:
        port_items = [(port.name, port) for port in component.get_ports_list()]
    for name, port in port_items:
        layer = getattr(port, "layer", None)
        layer_info = getattr(port, "layer_info", None)
        if layer is None and layer_info is not None:
            layer = (int(layer_info.layer), int(layer_info.datatype))
        ports.append(
            {
                "name": name,
                "center": [float(v) for v in port.center],
                "width": float(port.width),
                "layer": list(layer) if isinstance(layer, tuple) else layer,
            }
        )
    return gds, {"pcell": "lumped_element_jpa_seed", "gds_path": str(gds), "info": dict(component.info), "ports": ports}


def test_physics_graph_extracts_devices_and_jc_model(tmp_path):
    gds, sidecar = _jpa_sidecar(tmp_path)
    graph = extract_physics_graph(
        gds,
        sidecar,
        jc_ua_per_um2=2.0,
        specific_capacitance_ff_per_um2=45.0,
        output_path=tmp_path / "physics_graph.json",
    )
    assert graph["schema"] == "text-to-gds.physics-graph.v1"
    assert (tmp_path / "physics_graph.json").exists()
    node_types = {node["type"] for node in graph["nodes"]}
    assert {"josephson_junction", "transmission_line", "port", "ground"} <= node_types
    edge_types = {edge["type"] for edge in graph["edges"]}
    assert "microwave_port" in edge_types
    assert graph["extraction_methods"]["jj_overlap_recognition"] is True
    model = graph_to_josephsoncircuits_model(graph)
    assert model["ready_for_solver"] is True
    assert {"Josephson junction", "resonator", "port"} <= {item["type"] for item in model["circuit"]}


def test_automatic_mesh_writes_solver_inputs(tmp_path):
    gds, sidecar = _jpa_sidecar(tmp_path)
    graph = extract_physics_graph(gds, sidecar, jc_ua_per_um2=2.0)
    result = generate_solver_inputs_from_graph(graph, output_dir=tmp_path / "solver_inputs")
    assert result["status"] == "prepared"
    assert Path(result["openems"]["geometry_xml"]).exists()
    assert Path(result["openems"]["mesh_xml"]).exists()
    assert Path(result["elmer"]["geo"]).exists()
    assert Path(result["palace"]["config_json"]).exists()
    priorities = {rule["priority"] for rule in result["mesh_refinement_rules"]}
    assert {"finest", "high", "coarse"} <= priorities


def test_solver_contract_rejects_non_solver_and_accepts_real_files(tmp_path):
    input_file = tmp_path / "in.xml"
    output_file = tmp_path / "out.s2p"
    input_file.write_text("<xml/>", encoding="utf-8")
    output_file.write_text("# Hz S RI R 50\n", encoding="utf-8")
    bad = validate_solver_execution(
        {
            "solver": "scipy",
            "version": "1",
            "input_file": str(input_file),
            "output_file": str(output_file),
            "mesh_size": 1,
            "runtime": 1,
            "convergence": {"status": "ok"},
        }
    )
    assert bad["passed"] is False
    good = solver_quantity(
        1.0,
        "GHz",
        quantity="frequency",
        provenance={
            "solver": "openEMS",
            "version": "0.0.36",
            "input_file": str(input_file),
            "output_file": str(output_file),
            "mesh_size": 1000,
            "runtime": 2.5,
            "convergence": {"status": "ok"},
        },
    )
    assert good["status"] == "ok"


def test_inverse_design_regenerates_gds_for_each_candidate(tmp_path):
    result = inverse_design_jpa(
        "I need 6 GHz JPA, 20 dB gain, 200 MHz bandwidth",
        output_dir=tmp_path / "inverse",
        iterations=3,
    )
    assert result["candidate_count"] == 3
    for candidate in result["history"]:
        assert Path(candidate["gds_path"]).exists()
        assert Path(candidate["physics_graph_path"]).exists()
        assert candidate["solver_status"] == "not_run"


def test_measurement_comparison_outputs_process_correction(tmp_path):
    csv_path = tmp_path / "measurement.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["frequency_ghz", "gain_db"])
        writer.writeheader()
        for freq, gain in [(5.8, 10.0), (5.9, 18.0), (6.0, 20.0), (6.1, 17.0), (6.2, 9.0)]:
            writer.writerow({"frequency_ghz": freq, "gain_db": gain})
    sim = {"measurement_prediction": {"center_frequency_ghz": 6.2, "peak_gain_db": 19.0, "bandwidth_3db_mhz": 120.0}}
    result = compare_measurement_to_simulation(
        csv_path,
        sim,
        report_path=tmp_path / "comparison.json",
        fit_kind="jpa_gain",
    )
    assert result["schema"] == "text-to-gds.measurement-comparison.v1"
    assert "effective_epsilon_scale" in result["process_correction"]


def test_aluminum_jj_pdk_loads():
    pdk = load_pdk(ROOT / "process" / "aluminum_jj.yaml")
    assert pdk.process_id == "aluminum_jj"
    assert pdk.layers["JJ"].critical_current_density_ua_per_um2 == 2.0
    assert pdk.materials["Al"].penetration_depth_nm == 50.0


def test_final_axion_search_jpa_outputs_required_bundle(tmp_path):
    result = create_flux_tunable_jpa_for_axion_search(output_dir=tmp_path / "axion")
    outputs = result["outputs"]
    assert Path(outputs["gds"]).exists()
    assert Path(outputs["physics_graph"]).exists()
    assert outputs["extracted_lc"]
    assert Path(outputs["em_result"]["solver_inputs"]).exists()
    assert outputs["josephsoncircuits_gain"]["script_path"].endswith(".jl")
    assert Path(outputs["gain_map_h5"]["path"]).exists()
    assert outputs["measurement_prediction"]["status"] in {"pending_solver_execution", "predicted_from_solver"}
    assert outputs["repair_suggestions"]["reason"] is not None
    report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    assert report["schema"] == "text-to-gds.superconducting-eda-compiler.v1"
