"""OpenQ3D -- open-source capacitance/inductance extraction (Q3D analog).

Aggregates the open parasitic solvers behind one interface:

    capacitance -> Elmer (electrostatic FEM) and FastCap (BEM panels)
    inductance  -> FastHenry (partial-element)

plus an IDC capacitor auto-tune loop that adjusts finger geometry until the
target capacitance is met within tolerance. Every backend follows the standard
contract: it generates a runnable deck and executes only when its binary is on
PATH, reporting ``skipped`` otherwise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from text_to_gds.elmer_bridge import write_elmer_project
from text_to_gds.parasitics import export_fastcap, export_fasthenry
from text_to_gds.physics_extensions import optimize_idc_capacitor


class OpenQ3D:
    """Open-source Q3D-equivalent C/L matrix extraction."""

    def extract(
        self,
        gds_path: str | Path,
        *,
        output_stem: str | Path,
        sidecar_path: str | Path | None = None,
        process_path: str | Path | None = None,
        run: bool = False,
    ) -> dict[str, Any]:
        stem = Path(output_stem)
        elmer = write_elmer_project(
            gds_path,
            sif_path=stem.with_suffix(".sif"),
            report_path=stem.with_suffix(".elmer.report.json"),
            mesh_path=stem.with_suffix(".msh"),
            mesh_report_path=stem.with_suffix(".mesh.json"),
            sidecar_path=sidecar_path,
            process_path=process_path,
            run=run,
        )
        fastcap = export_fastcap(
            gds_path,
            lst_path=stem.with_suffix(".lst"),
            report_path=stem.with_suffix(".fastcap.json"),
            sidecar_path=sidecar_path,
            process_path=process_path,
            run=run,
        )
        fasthenry = export_fasthenry(
            gds_path,
            inp_path=stem.with_suffix(".inp"),
            report_path=stem.with_suffix(".fasthenry.json"),
            sidecar_path=sidecar_path,
            process_path=process_path,
            run=run,
        )
        c_matrix = elmer.get("capacitance_matrix_pf") or fastcap.get("capacitance_matrix_pf")
        return {
            "schema": "text-to-gds.open-q3d.v1",
            "backend": "OpenQ3D (Elmer + FastCap + FastHenry)",
            "source_gds": str(gds_path),
            "capacitance": {
                "matrix_pf": c_matrix,
                "elmer_status": elmer.get("status"),
                "fastcap_status": fastcap.get("status"),
            },
            "inductance": {
                "inductance_nh": fasthenry.get("inductance_nh"),
                "fasthenry_status": fasthenry.get("status"),
            },
            "coupling": {
                "source": "off-diagonal capacitance matrix terms",
                "available": c_matrix is not None,
            },
            "reports": {
                "elmer": elmer.get("report_path"),
                "fastcap": fastcap.get("report_path"),
                "fasthenry": fasthenry.get("report_path"),
            },
            "model_validity": (
                "Open-source Q3D analog. Capacitance from Elmer/FastCap, inductance from "
                "FastHenry. Review mesh/panel density and add a superconducting kinetic-"
                "inductance model before signoff."
            ),
        }


def tune_idc_capacitance(
    target_pf: float,
    *,
    epsilon_r: float = 11.45,
    min_feature_um: float = 0.2,
    tolerance_pct: float = 1.0,
) -> dict[str, Any]:
    """Auto-tune IDC finger geometry until capacitance meets ``target_pf``.

    Reuses the analytical IDC model surrogate. Returns the best geometry, the
    achieved value, the relative error, and whether it is within tolerance.
    """
    if target_pf <= 0.0:
        raise ValueError(f"target_pf must be positive, got {target_pf}")
    target_ff = float(target_pf) * 1000.0
    best = optimize_idc_capacitor(
        target_ff=target_ff, epsilon_r=epsilon_r, min_feature_um=min_feature_um
    )
    achieved_ff = float(best["capacitance_ff"])
    error_pct = abs(achieved_ff - target_ff) / target_ff * 100.0
    return {
        "schema": "text-to-gds.open-q3d-idc-tune.v1",
        "target_pf": float(target_pf),
        "achieved_pf": achieved_ff / 1000.0,
        "error_pct": round(error_pct, 4),
        "within_tolerance": error_pct <= tolerance_pct,
        "tolerance_pct": tolerance_pct,
        "geometry": {
            "finger_count": int(best["finger_count"]),
            "finger_length_um": float(best["finger_length_um"]),
            "finger_width_um": float(best["finger_width_um"]),
            "gap_um": float(best["gap_um"]),
        },
        "model_validity": "Analytical IDC surrogate; confirm with Elmer/FastCap before signoff.",
    }
