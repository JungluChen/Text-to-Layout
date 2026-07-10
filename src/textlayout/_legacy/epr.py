"""pyEPR-compatible HFSS handoff and field-energy participation analysis."""

from __future__ import annotations

import json
import math
from importlib.util import find_spec
from pathlib import Path
from typing import Any

PLANCK_J_S = 6.62607015e-34
REDUCED_FLUX_QUANTUM_WB = 2.067833848e-15 / (2.0 * math.pi)


def _field_energy_metrics(data: dict[str, Any]) -> dict[str, Any]:
    frequency_ghz = float(data["mode_frequency_ghz"])
    electric_energy = float(data["total_electric_energy_j"])
    magnetic_energy = float(data["total_magnetic_energy_j"])
    if min(frequency_ghz, electric_energy, magnetic_energy) <= 0.0:
        raise ValueError("Mode frequency and total field energies must be positive")
    junctions = []
    for junction in data.get("junctions", []):
        participation = float(junction["inductive_energy_j"]) / magnetic_energy
        lj_h = float(junction["lj_h"])
        ej_ghz = REDUCED_FLUX_QUANTUM_WB**2 / lj_h / PLANCK_J_S / 1e9
        junctions.append(
            {
                "name": junction["name"],
                "participation": participation,
                "lj_h": lj_h,
                "ej_ghz": ej_ghz,
            }
        )
    dielectrics = []
    loss_sum = 0.0
    for dielectric in data.get("dielectrics", []):
        participation = float(dielectric["electric_energy_j"]) / electric_energy
        loss_tangent = float(dielectric["loss_tangent"])
        loss = participation * loss_tangent
        loss_sum += loss
        dielectrics.append(
            {
                "name": dielectric["name"],
                "participation": participation,
                "loss_tangent": loss_tangent,
                "loss_contribution": loss,
            }
        )
    quality_factor = 1.0 / loss_sum if loss_sum > 0.0 else math.inf
    predicted_t1_s = quality_factor / (2.0 * math.pi * frequency_ghz * 1e9)
    anharmonicity_mhz = sum(
        junction["ej_ghz"] * 1e3 * junction["participation"] ** 2 / 2.0
        for junction in junctions
    )
    return {
        "mode_frequency_ghz": frequency_ghz,
        "junction_participation": junctions,
        "dielectric_participation": dielectrics,
        "dielectric_loss": loss_sum,
        "dielectric_quality_factor": quality_factor,
        "predicted_T1_s": predicted_t1_s,
        "predicted_T1_us": predicted_t1_s * 1e6,
        "first_order_anharmonicity_mhz": anharmonicity_mhz,
    }


def write_epr_analysis(
    sidecar: dict[str, Any],
    *,
    report_path: str | Path,
    script_path: str | Path,
    field_energy_path: str | Path | None = None,
    hfss_project_path: str | Path | None = None,
    hfss_project_name: str = "text_to_gds_device",
    hfss_design_name: str = "Eigenmode",
) -> dict[str, Any]:
    """Write a real pyEPR workflow and optionally evaluate exported field energies."""
    report_file, script_file = Path(report_path), Path(script_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.parent.mkdir(parents=True, exist_ok=True)
    info = sidecar.get("info", {})
    junction_count = int(info.get("squid_junction_count", 1 if info.get("junction_area_um2") else 0))
    junctions = []
    for index in range(max(junction_count, 1)):
        suffix = index + 1
        junctions.append(
            {
                "name": f"j{suffix}",
                "Lj_variable": f"Lj_{suffix}",
                "Cj_variable": f"Cj_{suffix}",
                "rect": f"rect_j{suffix}",
                "line": f"line_j{suffix}",
            }
        )
    project_path_literal = repr(str(Path(hfss_project_path))) if hfss_project_path else "None"
    junction_lines = "\n".join(
        f"pinfo.junctions[{j['name']!r}] = {{'Lj_variable': {j['Lj_variable']!r}, "
        f"'Cj_variable': {j['Cj_variable']!r}, 'rect': {j['rect']!r}, 'line': {j['line']!r}}}"
        for j in junctions
    )
    script_file.write_text(
        f'''# Generated pyEPR/HFSS analysis for Text-to-GDS.
import pyEPR as epr

project_path = {project_path_literal}
if project_path is None:
    raise SystemExit("Set hfss_project_path to an existing solved AEDT project")

pinfo = epr.ProjectInfo(
    project_path=project_path,
    project_name={hfss_project_name!r},
    design_name={hfss_design_name!r},
)
{junction_lines}
pinfo.validate_junction_info()
eprd = epr.DistributedAnalysis(pinfo)
eprd.do_EPR_analysis()
epra = epr.QuantumAnalysis(eprd.data_filename)
epra.analyze_all_variations(cos_trunc=8, fock_trunc=15)
print(eprd.data_filename)
print(epra.get_chis())
''',
        encoding="utf-8",
    )
    metrics = None
    status = "prepared"
    if field_energy_path is not None:
        field_data = json.loads(Path(field_energy_path).read_text(encoding="utf-8"))
        metrics = _field_energy_metrics(field_data)
        status = "executed_from_exported_field_energies"
    result = {
        "schema": "text-to-gds.epr-analysis.v1",
        "status": status,
        "backend": "pyEPR" if find_spec("pyEPR") is not None else "pyEPR_not_installed",
        "source_gds": sidecar.get("gds_path"),
        "hfss_project_path": str(hfss_project_path) if hfss_project_path else None,
        "junction_definitions": junctions,
        "metrics": metrics,
        "junction_participation": metrics["junction_participation"] if metrics else None,
        "dielectric_loss": metrics["dielectric_loss"] if metrics else None,
        "predicted_T1": metrics["predicted_T1_us"] if metrics else None,
        "script_path": str(script_file),
        "report_path": str(report_file),
        "validity": (
            "Metrics are computed from supplied field-energy exports. The generated script follows "
            "pyEPR ProjectInfo -> DistributedAnalysis -> QuantumAnalysis and requires solved HFSS fields."
        ),
    }
    report_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
