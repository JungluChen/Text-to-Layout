"""End-to-end superconducting EDA compiler workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout._legacy.ai_scientist import diagnose_and_repair
from textlayout._legacy.automatic_mesh import generate_solver_inputs_from_graph
from textlayout._legacy.extraction import extract_physical_parameters, write_extraction
from textlayout._legacy.jpa_analysis import run_jpa_analysis
from textlayout._legacy.pcells import lumped_element_jpa_seed
from textlayout._legacy.physics_graph import extract_physics_graph, graph_to_josephsoncircuits_model


def _write_sidecar(component: Any, gds_path: Path, sidecar_path: Path) -> dict[str, Any]:
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
                "center": [float(v) for v in getattr(port, "center", (0.0, 0.0))],
                "width": float(getattr(port, "width", 0.0)),
                "orientation": getattr(port, "orientation", None),
                "layer": list(layer) if isinstance(layer, tuple) else layer,
            }
        )
    sidecar = {
        "schema": "text-to-gds.sidecar.v0",
        "pcell": "lumped_element_jpa_seed",
        "gds_path": str(gds_path),
        "ports": ports,
        "info": dict(component.info),
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    return sidecar


def _write_gain_map_placeholder(path: Path, analysis: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import h5py

        with h5py.File(path, "w") as handle:
            handle.attrs["schema"] = "text-to-gds.gain-map.v1"
            handle.attrs["status"] = str(analysis.get("status"))
            handle.attrs["source"] = str(analysis.get("report_path") or analysis.get("script_path"))
            if analysis.get("status") == "executed":
                sweep = analysis.get("sweep", {})
                for key in ("frequencies_ghz", "pump_fractions", "peak_gain_db", "center_gain_db"):
                    if key in sweep:
                        handle.create_dataset(key, data=sweep[key])
            else:
                handle.attrs["reason"] = "; ".join(analysis.get("warnings", [])) or analysis.get("reason", "solver not executed")
        return {"path": str(path), "status": "written"}
    except Exception as exc:  # noqa: BLE001
        path.write_text(
            json.dumps(
                {
                    "schema": "text-to-gds.gain-map.v1",
                    "status": "metadata_only",
                    "reason": f"h5py unavailable or failed: {exc}",
                    "analysis_status": analysis.get("status"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"path": str(path), "status": "metadata_json_fallback"}


def create_flux_tunable_jpa_for_axion_search(
    *,
    output_dir: str | Path,
    frequency_ghz: float = 2.1,
    gain_db: float = 20.0,
    bandwidth_mhz: float = 100.0,
    jc_ua_per_um2: float = 2.0,
) -> dict[str, Any]:
    """Run the final requested axion-search JPA compiler flow."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    component = lumped_element_jpa_seed(
        center_frequency_ghz=frequency_ghz,
        target_gain_db=gain_db,
        target_bandwidth_mhz=bandwidth_mhz,
        cpw_length=420.0,
        squid_count=4,
        shunt_capacitor_width_um=95.0,
        coupling_capacitor_length_um=50.0,
    )
    gds_path = out / "axion_flux_tunable_jpa.gds"
    sidecar_path = out / "axion_flux_tunable_jpa.sidecar.json"
    component.write_gds(str(gds_path))
    sidecar = _write_sidecar(component, gds_path, sidecar_path)

    extraction = extract_physical_parameters(
        gds_path,
        sidecar,
        jc_ua_per_um2=jc_ua_per_um2,
        capacitance_ff=float(component.info["shunt_capacitance_ff"]),
        target_frequency_ghz=frequency_ghz,
        frequency_tolerance=1.0,
    )
    extraction = write_extraction(extraction, out / "axion_flux_tunable_jpa.extraction.json")
    graph = extract_physics_graph(
        gds_path,
        sidecar,
        jc_ua_per_um2=jc_ua_per_um2,
        specific_capacitance_ff_per_um2=45.0,
        output_path=out / "physics_graph.json",
    )
    solver_inputs = generate_solver_inputs_from_graph(graph, output_dir=out / "solver_inputs")
    circuit_model = graph_to_josephsoncircuits_model(graph)
    (out / "josephsoncircuits_model.json").write_text(json.dumps(circuit_model, indent=2), encoding="utf-8")

    analysis = run_jpa_analysis(
        sidecar,
        script_path=out / "jpa_pump_sweep.jl",
        result_path=out / "jpa_pump_sweep.result.json",
        report_path=out / "jpa_analysis.json",
        plot_path=out / "jpa_analysis.png",
        jc_ua_per_um2=jc_ua_per_um2,
        target_frequency_ghz=frequency_ghz,
        target_bandwidth_mhz=bandwidth_mhz,
    )
    gain_map = _write_gain_map_placeholder(out / "gain_map.h5", analysis)
    extracted_lc = extraction.get("linear_circuit", {})
    actual_freq = extracted_lc.get("resonance_frequency_hz")
    diagnosis = diagnose_and_repair(
        {"frequency_ghz": frequency_ghz, "gain_db": gain_db, "bandwidth_mhz": bandwidth_mhz},
        {"frequency_ghz": float(actual_freq) / 1e9} if actual_freq else {},
        sidecar.get("info", {}),
        repair_gds_path=out / "axion_flux_tunable_jpa_repair.gds",
    )
    measurement_prediction = {
        "status": "pending_solver_execution",
        "reason": "Measurement prediction requires executed JosephsonCircuits and EM outputs.",
    }
    if analysis.get("status") == "executed":
        metrics = analysis.get("metrics", {})
        measurement_prediction = {
            "status": "predicted_from_solver",
            "center_frequency_ghz": frequency_ghz,
            "peak_gain_db": metrics.get("peak_gain_db"),
            "bandwidth_mhz": bandwidth_mhz,
            "noise_temperature_k": metrics.get("noise_temperature_k"),
        }

    result = {
        "schema": "text-to-gds.superconducting-eda-compiler.v1",
        "status": "prepared" if analysis.get("status") != "executed" else "executed",
        "prompt": "Create a flux tunable JPA for axion search: frequency 2.1 GHz, gain 20 dB, bandwidth 100 MHz",
        "outputs": {
            "gds": str(gds_path),
            "physics_graph": graph.get("result_path"),
            "extracted_lc": extracted_lc,
            "em_result": {
                "status": "input_files_prepared",
                "solver_inputs": solver_inputs["report_path"],
                "note": "Run openEMS/Elmer/Palace to create solver-owned EM numbers.",
            },
            "josephsoncircuits_gain": analysis,
            "gain_map_h5": gain_map,
            "measurement_prediction": measurement_prediction,
            "repair_suggestions": diagnosis,
        },
    }
    report = out / "axion_jpa_final.json"
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report)
    return result
