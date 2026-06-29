"""Create a 6 GHz JPA: GDS, four views + evidence view, signoff reports, real hooks.

Strictly single-frequency (6 GHz); never references the 2.1 GHz axion design.

Solver execution is honest:
  * JosephsonCircuits.jl runs directly when Julia is available -> EXECUTED with
    real result files; otherwise SKIPPED. Set TEXT_TO_GDS_SKIP_SOLVERS=1 to skip
    the attempt entirely.
  * FastCap2/Elmer (IDC capacitance) and openEMS (CPW S-params) write real input
    decks and only report EXECUTED if an output file exists on disk.

Outputs (workspace/artifacts/examples/create_6GHz_JPA/):
  jpa_6GHz.gds / .sidecar.json
  jpa_6GHz.mask_view.png / .layer_view.png / .net_view.png / .circuit_view.png / .evidence_view.png
  jpa_6GHz.drc.json / .lvs.json / .floating_metal.json / .layer_connectivity.json
  jpa_6GHz.pdk_rules.json / .lyp
  jpa_6GHz.solver_evidence.json  (+ JosephsonCircuits result/script/plot when EXECUTED)
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
        from text_to_gds.device_library import JPA
        from text_to_gds.device_views import render_device_views, render_evidence_view
        from text_to_gds.evidence import evidence_bundle, solver_evidence
        from text_to_gds.fabrication_signoff import run_fabrication_signoff
        from text_to_gds.signoff_extraction import (
            extract_capacitance,
            extract_jpa_dynamics,
            extract_sparameters,
        )
        from text_to_gds.verification.connectivity import extract_connectivity
    except ModuleNotFoundError as exc:
        _reexec_with_uv_if_needed(exc)

    out = ROOT / "workspace" / "artifacts" / "examples" / "create_6GHz_JPA"
    out.mkdir(parents=True, exist_ok=True)
    stem = "jpa_6GHz"
    freq_ghz, gain_db, bw_mhz = 6.0, 20.0, 200.0
    band = [freq_ghz - bw_mhz / 2000.0, freq_ghz + bw_mhz / 2000.0]
    label = "JPA 6 GHz"

    prompt = "Create 6GHz JPA with 50 ohm port"
    intent = synthesize_design_intent(
        prompt,
        inputs={
            "device": "JPA", "frequency_ghz": freq_ghz, "gain_db": gain_db,
            "bandwidth_mhz": bw_mhz, "target_impedance_ohm": 50.0, "jc_ua_per_um2": 2.0,
            "junction_count": 8, "wirebond_pads": True, "rf_ports": 2,
            "flux_line": True, "pump_mode": "flux",
        },
    )
    write_design_intent(intent, out / "design_intent.json")

    device = JPA(frequency_ghz=freq_ghz, impedance_ohm=50.0, target_gain_db=gain_db, bandwidth_mhz=bw_mhz)
    component = device.geometry()
    gds_path = out / f"{stem}.gds"
    component.write_gds(gds_path)

    connectivity = extract_connectivity(gds_path)
    extracted = device.extract()
    ports = device.ports()

    sidecar_path = out / f"{stem}.sidecar.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "schema": "text-to-gds.device-sidecar.v1", "device": "JPA",
                "frequency_ghz": freq_ghz, "gain_db": gain_db, "bandwidth_mhz": bw_mhz,
                "gds_path": str(gds_path), "synthesis": device._synthesis(),
                "extracted_parameters": extracted,
                "ports": {name: port.to_dict() for name, port in ports.items()},
                "device_topology": connectivity["device_topology"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    views = render_device_views(
        gds_path, out, stem, connectivity=connectivity, ports=ports,
        title=f"{freq_ghz:.0f} GHz JPA", annotations=None,
    )

    # --- fabrication signoff reports ----------------------------------------
    signoff = run_fabrication_signoff(gds_path, out, stem)

    # --- real solver-extraction hooks ---------------------------------------
    items: list[dict] = []
    if os.environ.get("TEXT_TO_GDS_SKIP_SOLVERS") == "1":
        for q in ("gain_db", "quantum_efficiency", "noise_temperature_k", "squeezing_db", "stability_margin"):
            items.append(solver_evidence(
                quantity=q, source_device=label, source_sidecar=sidecar_path,
                solver_name="JosephsonCircuits.jl", solver_status="SKIPPED",
                frequency_range_ghz=band, notes="solver run disabled (TEXT_TO_GDS_SKIP_SOLVERS=1)"))
    else:
        _report, jpa_items = extract_jpa_dynamics(device, out, stem, source_sidecar=sidecar_path, jc_ua_per_um2=2.0)
        items.extend(jpa_items)

    items.append(extract_capacitance(
        gds_path, out, f"{stem}_idc", device_label=label, source_sidecar=sidecar_path,
        quantity="idc_capacitance_f", conductor_layers=("M1", "M2"), eps_r=11.45))
    items.append(extract_sparameters(
        out, f"{stem}_cpw", device_label=label, source_sidecar=sidecar_path,
        cpw_width_um=10.0, cpw_gap_um=6.0, length_um=900.0, band_ghz=tuple(band), eps_r=11.45))

    bundle = evidence_bundle(device=label, source_sidecar=sidecar_path, items=items)
    evidence_path = out / f"{stem}.solver_evidence.json"
    evidence_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    views["evidence_view"] = str(out / f"{stem}.evidence_view.png")
    render_evidence_view(bundle, views["evidence_view"], f"{freq_ghz:.0f} GHz JPA")

    summary = {
        "schema": "text-to-gds.example.6ghz-jpa.v3",
        "prompt": prompt, "frequency_ghz": freq_ghz, "gds_path": str(gds_path),
        "sidecar_path": str(sidecar_path), "views": views,
        "signoff_reports": signoff["reports"], "signoff_statuses": signoff["statuses"],
        "solver_evidence_path": str(evidence_path),
        "lvs_status": connectivity["status"],
        "device_topology": connectivity["device_topology"],
        "extracted_parameters": extracted,
        "executed_quantities": bundle["executed_quantities"],
        "skipped_quantities": bundle["skipped_quantities"],
    }
    (out / f"{stem}.report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
