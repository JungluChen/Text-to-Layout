"""Create a 5 GHz transmon: GDS, views + evidence view, signoff reports, real hooks.

Honest solver execution:
  * scqubits computes the spectrum in-process and is written to a file -> EXECUTED.
  * FastCap2/Elmer (shunt capacitance) and openEMS (readout S-params) write real
    input decks and only report EXECUTED if an output file exists on disk.

Outputs (workspace/artifacts/examples/create_transmon/):
  transmon_5GHz.gds / .sidecar.json
  transmon_5GHz.mask_view.png / .layer_view.png / .net_view.png / .circuit_view.png / .evidence_view.png
  transmon_5GHz.drc.json / .lvs.json / .floating_metal.json / .layer_connectivity.json
  transmon_5GHz.pdk_rules.json / .lyp
  transmon_5GHz.scqubits.json / .solver_evidence.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _reexec_with_uv_if_needed(exc: ModuleNotFoundError) -> None:
    if os.environ.get("TEXT_TO_GDS_UV_REEXEC") == "1":
        raise exc
    env = dict(os.environ)
    env["TEXT_TO_GDS_UV_REEXEC"] = "1"
    cmd = ["py", "-3", "-m", "uv", "run", "--no-sync", "python", str(Path(__file__).resolve())]
    raise SystemExit(subprocess.call(cmd, cwd=ROOT, env=env))


def main() -> None:
    try:
        from text_to_gds.design_intent import synthesize_design_intent, write_design_intent
        from text_to_gds.device_library import Transmon
        from text_to_gds.device_views import render_device_views, render_evidence_view
        from text_to_gds.evidence import evidence_bundle, solver_evidence
        from text_to_gds.fabrication_signoff import run_fabrication_signoff
        from text_to_gds.signoff_extraction import extract_capacitance, extract_sparameters
        from text_to_gds.verification.connectivity import extract_connectivity
    except ModuleNotFoundError as exc:
        _reexec_with_uv_if_needed(exc)

    out = ROOT / "workspace" / "artifacts" / "examples" / "create_transmon"
    out.mkdir(parents=True, exist_ok=True)
    stem = "transmon_5GHz"
    freq_ghz = 5.0
    label = "transmon 5 GHz"

    prompt = "Create a 5 GHz transmon with -250 MHz anharmonicity"
    intent = synthesize_design_intent(
        prompt,
        inputs={
            "device": "transmon", "frequency_ghz": freq_ghz, "jc_ua_per_um2": 2.0,
            "junction_width_um": 0.12, "junction_height_um": 0.12, "capacitance_ff": 80.0,
            "package_clearance_um": 250.0, "wirebond_pads": True, "rf_ports": 1, "flux_line": True,
        },
    )
    write_design_intent(intent, out / "design_intent.json")

    device = Transmon(frequency_ghz=freq_ghz, anharmonicity_mhz=-250.0)
    component = device.geometry()
    gds_path = out / f"{stem}.gds"
    component.write_gds(gds_path)

    connectivity = extract_connectivity(gds_path)
    extracted = device.extract()
    ports = device.ports()
    plan = device._plan()

    sidecar_path = out / f"{stem}.sidecar.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "schema": "text-to-gds.device-sidecar.v1", "device": "transmon",
                "frequency_ghz": freq_ghz, "gds_path": str(gds_path),
                "synthesis": device._synthesis(), "extracted_parameters": extracted,
                "ports": {name: port.to_dict() for name, port in ports.items()},
                "device_topology": connectivity["device_topology"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    annotations = {
        f"coupling gap {plan['res_gap']:.1f} um": (plan["conn_w"] / 2.0 + 14.0, plan["conn_top"]),
        "SQUID (2 JJ)": (plan["loop_w"] + 20.0, 0.0),
    }
    views = render_device_views(
        gds_path, out, stem, connectivity=connectivity, ports=ports,
        title=f"{freq_ghz:.0f} GHz transmon", annotations=annotations,
    )

    # --- fabrication signoff reports ----------------------------------------
    signoff = run_fabrication_signoff(gds_path, out, stem)

    # --- scqubits spectrum (real solver, written to file) -------------------
    validation = device._synthesis()["scqubits_validation"]
    scq_path = out / f"{stem}.scqubits.json"
    scq_path.write_text(json.dumps(validation, indent=2), encoding="utf-8")
    scq_executed = validation.get("status") == "executed"
    band = [freq_ghz - 0.5, freq_ghz + 0.5]

    items = [
        solver_evidence(
            quantity="f01_ghz", source_device=label, source_sidecar=sidecar_path,
            solver_name="scqubits.Transmon",
            solver_status="EXECUTED" if scq_executed else "SKIPPED",
            input_file=sidecar_path, output_file=scq_path if scq_executed else None,
            frequency_range_ghz=band, value=validation.get("f01_ghz"), unit="GHz",
            notes=None if scq_executed else "scqubits not installed"),
        solver_evidence(
            quantity="anharmonicity_ghz", source_device=label, source_sidecar=sidecar_path,
            solver_name="scqubits.Transmon",
            solver_status="EXECUTED" if scq_executed else "SKIPPED",
            input_file=sidecar_path, output_file=scq_path if scq_executed else None,
            frequency_range_ghz=band, value=extracted.get("alpha_ghz"), unit="GHz",
            notes=None if scq_executed else "scqubits not installed"),
    ]
    # electrostatic shunt capacitance + readout S-parameters (real input decks)
    items.append(extract_capacitance(
        gds_path, out, f"{stem}_shunt", device_label=label, source_sidecar=sidecar_path,
        quantity="shunt_capacitance_f", conductor_layers=("M1", "M2"), eps_r=11.45))
    items.append(extract_sparameters(
        out, f"{stem}_readout", device_label=label, source_sidecar=sidecar_path,
        cpw_width_um=plan["res_w"], cpw_gap_um=plan["res_gap"],
        length_um=plan["meander_length"], band_ghz=(6.0, 7.0), eps_r=11.45))

    bundle = evidence_bundle(device=label, source_sidecar=sidecar_path, items=items)
    evidence_path = out / f"{stem}.solver_evidence.json"
    evidence_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    views["evidence_view"] = str(out / f"{stem}.evidence_view.png")
    render_evidence_view(bundle, views["evidence_view"], f"{freq_ghz:.0f} GHz transmon")

    summary = {
        "schema": "text-to-gds.example.transmon.v3",
        "prompt": prompt, "gds_path": str(gds_path), "sidecar_path": str(sidecar_path),
        "views": views, "signoff_reports": signoff["reports"], "signoff_statuses": signoff["statuses"],
        "scqubits_path": str(scq_path), "solver_evidence_path": str(evidence_path),
        "lvs_status": connectivity["status"], "device_topology": connectivity["device_topology"],
        "extracted_parameters": extracted,
        "executed_quantities": bundle["executed_quantities"],
        "skipped_quantities": bundle["skipped_quantities"],
    }
    (out / f"{stem}.report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
