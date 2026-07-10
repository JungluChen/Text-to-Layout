"""Superconducting-material model: kinetic inductance, participation, crowding.

Sheet kinetic inductance is derived either from the London penetration depth and
film thickness (`Ls = mu0 lambda coth(t/lambda)`) or from the normal-state sheet
resistance and Tc via Mattis-Bardeen (`Ls = hbar Rn / (pi Delta)`,
`Delta = 1.764 kB Tc`). The current-crowding profile uses the canonical thin-strip
edge distribution. These are analytic first-order models for design screening.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from textlayout._legacy.process import DEFAULT_PROCESS

MU0_H_PER_M = 4.0e-7 * math.pi
HBAR_J_S = 1.054571817e-34
BOLTZMANN_J_K = 1.380649e-23
BCS_GAP_FACTOR = 1.764


def superconducting_gap_j(tc_k: float) -> float:
    """BCS zero-temperature gap energy `Delta = 1.764 kB Tc` in joules."""
    if tc_k <= 0.0:
        raise ValueError(f"tc_k must be positive, got {tc_k}")
    return BCS_GAP_FACTOR * BOLTZMANN_J_K * tc_k


def sheet_kinetic_inductance_ph(lambda_l_nm: float, thickness_nm: float) -> float:
    """Sheet kinetic inductance (pH/square) from penetration depth and thickness."""
    if lambda_l_nm <= 0.0:
        raise ValueError(f"lambda_l_nm must be positive, got {lambda_l_nm}")
    if thickness_nm <= 0.0:
        raise ValueError(f"thickness_nm must be positive, got {thickness_nm}")
    lam = lambda_l_nm * 1e-9
    thickness = thickness_nm * 1e-9
    sheet_h = MU0_H_PER_M * lam * (1.0 / math.tanh(thickness / lam))
    return sheet_h * 1e12


def sheet_kinetic_inductance_from_rn_ph(rn_sheet_ohm: float, tc_k: float) -> float:
    """Sheet kinetic inductance (pH/square) from normal-state sheet resistance and Tc."""
    if rn_sheet_ohm <= 0.0:
        raise ValueError(f"rn_sheet_ohm must be positive, got {rn_sheet_ohm}")
    gap = superconducting_gap_j(tc_k)
    sheet_h = HBAR_J_S * rn_sheet_ohm / (math.pi * gap)
    return sheet_h * 1e12


def current_crowding_profile(points: int = 41) -> dict[str, list[float]]:
    """Normalized thin-strip current density `J(x) ~ 1/sqrt(1-(2x/w)^2)` across the width."""
    if points < 5:
        raise ValueError("points must be >= 5")
    positions: list[float] = []
    density: list[float] = []
    edge = 0.999
    for index in range(points):
        u = -edge + 2.0 * edge * index / (points - 1)
        positions.append(u)
        density.append(1.0 / math.sqrt(1.0 - u**2))
    mean = sum(density) / len(density)
    density = [value / mean for value in density]
    return {"normalized_position": positions, "normalized_current_density": density}


def _material_defaults(material: str) -> dict[str, Any]:
    spec = DEFAULT_PROCESS.materials.get(material)
    if spec is None:
        return {}
    return {
        "tc_k": spec.critical_temperature_k,
        "sheet_kinetic_inductance_ph_per_square": spec.kinetic_inductance_ph_per_square or None,
    }


def export_superconducting_material(
    *,
    material: str = "Nb",
    thickness_nm: float = 100.0,
    tc_k: float | None = None,
    lambda_l_nm: float | None = None,
    rn_sheet_ohm: float | None = None,
    trace_width_um: float | None = None,
    trace_length_um: float | None = None,
    geometric_inductance_ph: float | None = None,
    crowding_points: int = 41,
) -> dict[str, Any]:
    """Model a superconducting film: sheet Lk, total Lk, participation, crowding map."""
    defaults = _material_defaults(material)
    tc = tc_k if tc_k is not None else defaults.get("tc_k")

    method = None
    sheet_lk_ph: float | None = None
    if lambda_l_nm is not None:
        sheet_lk_ph = sheet_kinetic_inductance_ph(lambda_l_nm, thickness_nm)
        method = "london_penetration_depth"
    elif rn_sheet_ohm is not None and tc is not None:
        sheet_lk_ph = sheet_kinetic_inductance_from_rn_ph(rn_sheet_ohm, tc)
        method = "mattis_bardeen_rn_tc"
    elif defaults.get("sheet_kinetic_inductance_ph_per_square") is not None:
        sheet_lk_ph = float(defaults["sheet_kinetic_inductance_ph_per_square"])
        method = "process_material_default"
    else:
        raise ValueError(
            "Provide lambda_l_nm, or rn_sheet_ohm with tc_k, or a material with a "
            "process default sheet kinetic inductance."
        )

    result: dict[str, Any] = {
        "schema": "text-to-gds.superconducting-material.v1",
        "material": material,
        "thickness_nm": thickness_nm,
        "tc_k": tc,
        "superconducting_gap_uev": superconducting_gap_j(tc) / 1.602176634e-19 * 1e6 if tc else None,
        "lambda_l_nm": lambda_l_nm,
        "rn_sheet_ohm": rn_sheet_ohm,
        "sheet_kinetic_inductance_ph_per_square": sheet_lk_ph,
        "method": method,
        "current_crowding": current_crowding_profile(crowding_points),
    }

    squares = None
    total_lk_ph = None
    if trace_width_um is not None and trace_length_um is not None:
        if trace_width_um <= 0.0 or trace_length_um <= 0.0:
            raise ValueError("trace_width_um and trace_length_um must be positive")
        squares = trace_length_um / trace_width_um
        total_lk_ph = sheet_lk_ph * squares
    result["number_of_squares"] = squares
    result["total_kinetic_inductance_ph"] = total_lk_ph

    if geometric_inductance_ph is not None and total_lk_ph is not None:
        if geometric_inductance_ph < 0.0:
            raise ValueError("geometric_inductance_ph must be non-negative")
        total = total_lk_ph + geometric_inductance_ph
        result["geometric_inductance_ph"] = geometric_inductance_ph
        result["total_inductance_ph"] = total
        result["kinetic_inductance_participation"] = (
            total_lk_ph / total if total > 0.0 else None
        )
    else:
        result["kinetic_inductance_participation"] = None

    result["model_validity"] = (
        "Analytic sheet kinetic inductance and thin-strip current crowding. "
        "Participation needs a geometric inductance from EM extraction (openEMS/Q3D)."
    )
    return result


def _plot_material(model: dict[str, Any], plot_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    crowding = model["current_crowding"]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot(
        crowding["normalized_position"],
        crowding["normalized_current_density"],
        color="purple",
    )
    ax.fill_between(
        crowding["normalized_position"],
        crowding["normalized_current_density"],
        alpha=0.15,
        color="purple",
    )
    ax.set_xlabel("Normalized width position (2x/w)")
    ax.set_ylabel("Normalized current density")
    ax.set_title(
        f"{model['material']}: Lk={model['sheet_kinetic_inductance_ph_per_square']:.2f} pH/sq "
        f"({model['method']})"
    )
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def write_superconducting_material(
    *,
    report_path: str | Path,
    plot_path: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Compute the material model, write a JSON report and a crowding plot."""
    model = export_superconducting_material(**kwargs)
    try:
        _plot_material(model, Path(plot_path))
        model["plot_path"] = str(plot_path)
    except Exception as exc:  # pragma: no cover - plotting is best effort
        model["plot_error"] = str(exc)
    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(model, indent=2), encoding="utf-8")
    model["report_path"] = str(report_file)
    return model
