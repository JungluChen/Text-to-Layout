"""scqubits adapter that reads directly from extraction.json.

Rules enforced here:
  - Requires extracted Ic from junction (junction.ic_a or junction.ic).
  - Requires extracted C from linear_circuit (linear_circuit.capacitance_f or .capacitance).
  - Computes EJ = Phi0 * Ic / (2 * pi) and EC = e^2 / (2 * C) — never uses a default ratio.
  - Validates that the result is transmon-like (anharmonicity != 0, f12 != f01).
  - Returns status="failed" if Ic or C are missing.
  - Returns status="skipped" if scqubits is not installed.
  - Never assumes EJ/EC = 60 or any other default.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout._legacy.extraction_schema import (
    ec_ghz,
    ej_ghz,
    read_capacitance,
    read_ic,
)

SCHEMA = "text-to-gds.scqubits-adapter.v1"


def _failed(reason: str, report_path: Path) -> dict[str, Any]:
    result = {"schema": SCHEMA, "status": "failed", "reason": reason}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report_path)
    return result


def _write_spectrum_plot(
    evals: list[float],
    ej_ghz_val: float,
    ec_ghz_val: float,
    plot_path: Path,
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.8), constrained_layout=True)

    # Energy levels bar
    transitions = [(evals[i + 1] - evals[0]) for i in range(len(evals) - 1)]
    labels = [f"|{i}⟩→|{i+1}⟩" for i in range(len(transitions))]
    axes[0].barh(labels, transitions, color="#3866d6")
    axes[0].set_xlabel("transition energy (GHz)")
    axes[0].set_title("Transmon energy levels (scqubits)")
    axes[0].invert_yaxis()

    # Explicit f01 / f12 / anharmonicity panel
    f01 = evals[1] - evals[0] if len(evals) > 1 else 0.0
    f12 = evals[2] - evals[1] if len(evals) > 2 else 0.0
    anharm_mhz = (f12 - f01) * 1000.0
    info = (
        f"EJ  = {ej_ghz_val:.3f} GHz\n"
        f"EC  = {ec_ghz_val * 1000:.1f} MHz\n"
        f"EJ/EC = {ej_ghz_val / ec_ghz_val:.1f}\n"
        f"──────────────────\n"
        f"f01 = {f01:.4f} GHz\n"
        f"f12 = {f12:.4f} GHz\n"
        f"α   = {anharm_mhz:+.1f} MHz"
    )
    axes[1].text(0.08, 0.93, info, va="top", ha="left", family="monospace", fontsize=10,
                 transform=axes[1].transAxes,
                 bbox={"boxstyle": "round,pad=0.4", "facecolor": "#e8f4fd", "edgecolor": "#3866d6"})
    axes[1].axis("off")
    axes[1].set_title("f01 / f12 / α (anharmonicity)")

    fig.suptitle("scqubits Transmon spectrum (extraction-derived)", fontsize=13)
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def run_scqubits_transmon(
    extraction_path: str | Path,
    *,
    report_path: str | Path,
    plot_path: str | Path | None = None,
    n_evals: int = 6,
    ncut: int = 30,
    ng: float = 0.0,
) -> dict[str, Any]:
    """Compute transmon spectrum from extracted Ic and C using scqubits.

    Steps:
      1. Load extraction.json.
      2. Require Ic from junction and C from linear_circuit.
      3. Compute EJ = Phi0 * Ic / (2π), EC = e^2 / (2C).
      4. Run scqubits.Transmon if available.
      5. Validate transmon regime (f12 != f01, anharmonicity != 0).

    Returns status="failed" if Ic or C are missing.
    Returns status="skipped" if scqubits is not installed.
    Returns status="executed" with spectrum only after a real scqubits run.
    """
    report = Path(report_path)
    plot = Path(plot_path) if plot_path is not None else None

    try:
        extraction = json.loads(Path(extraction_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _failed(f"cannot read extraction.json: {e}", report)

    if extraction.get("schema") != "text-to-gds.extraction.v1":
        return _failed("extraction.json schema is not text-to-gds.extraction.v1", report)

    # --- require Ic ---
    ic_a = read_ic(extraction)
    if ic_a is None:
        return _failed(
            "scqubits requires extracted critical current (ic_a); "
            "run extract_layout with jc_ua_per_um2 to populate junction.ic",
            report,
        )

    # --- require C ---
    capacitance_f = read_capacitance(extraction)
    if capacitance_f is None:
        return _failed(
            "scqubits requires extracted capacitance; "
            "supply capacitance_ff to extract_layout",
            report,
        )

    # --- compute EJ and EC (never use defaults) ---
    ej_val = ej_ghz(ic_a)
    ec_val = ec_ghz(capacitance_f)
    ej_ec_ratio = ej_val / ec_val

    lineage = {
        "EJ": {
            "formula": "EJ = Phi0 * Ic / (2*pi)",
            "inputs": ["junction.ic_a", "PHI0_WEBER"],
            "unit": "GHz",
            "source_ic": extraction.get("lineage", {}).get("junction.ic", {}),
        },
        "EC": {
            "formula": "EC = e^2 / (2*C)",
            "inputs": ["linear_circuit.capacitance_f", "ELECTRON_CHARGE_C"],
            "unit": "GHz",
            "source_c": extraction.get("lineage", {}).get("linear_circuit.capacitance", {}),
        },
    }

    # --- try to import scqubits ---
    try:
        import scqubits  # type: ignore[import]
    except ImportError:
        payload: dict[str, Any] = {
            "schema": SCHEMA,
            "status": "skipped",
            "reason": "scqubits not installed (pip install scqubits or uv sync --extra quantum)",
            "ej_ghz": ej_val,
            "ec_ghz": ec_val,
            "ec_mhz": ec_val * 1000.0,
            "ej_ec_ratio": ej_ec_ratio,
            "lineage": lineage,
            "solver_inputs": {"EJ_GHz": ej_val, "EC_GHz": ec_val, "ng": ng, "ncut": ncut},
        }
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["report_path"] = str(report)
        return payload

    # --- run scqubits ---
    tmon = scqubits.Transmon(EJ=ej_val, EC=ec_val, ng=ng, ncut=ncut)
    evals_raw = tmon.eigenvals(evals_count=n_evals)
    evals = [float(e - evals_raw[0]) for e in evals_raw]   # shift ground to zero

    f01_ghz = evals[1] if len(evals) > 1 else None
    f12_ghz = evals[2] - evals[1] if len(evals) > 2 else None
    anharmonicity_mhz = ((f12_ghz - f01_ghz) * 1000.0) if (f01_ghz is not None and f12_ghz is not None) else None

    # --- enforce transmon-like anharmonicity ---
    if anharmonicity_mhz is not None and abs(anharmonicity_mhz) < 10.0:
        return _failed(
            f"spectrum is harmonic, not transmon: "
            f"|α| = {abs(anharmonicity_mhz):.3f} MHz < 10 MHz; "
            "increase Ic or reduce C to reach the transmon regime",
            report,
        )

    # --- warn about non-ideal operating points ---
    warnings: list[str] = []
    if ej_ec_ratio < 10.0:
        warnings.append(
            f"EJ/EC = {ej_ec_ratio:.1f} < 10: device is in charge-qubit regime, "
            "not transmon-like — charge dispersion is large"
        )
    if f01_ghz is not None and f12_ghz is not None and abs(f12_ghz - f01_ghz) < 1e-6:
        warnings.append("f12 ≈ f01: accidental degeneracy — check EJ/EC and extraction values")

    if plot is not None:
        _write_spectrum_plot(evals, ej_val, ec_val, plot)

    payload = {
        "schema": SCHEMA,
        "status": "executed",
        "engine": "scqubits.Transmon",
        "ej_ghz": ej_val,
        "ec_ghz": ec_val,
        "ec_mhz": ec_val * 1000.0,
        "ej_ec_ratio": ej_ec_ratio,
        "transmon_regime": ej_ec_ratio >= 10.0,
        "f01_ghz": f01_ghz,
        "f12_ghz": f12_ghz,
        "anharmonicity_mhz": anharmonicity_mhz,
        "energy_levels_ghz": evals,
        "warnings": warnings,
        "lineage": lineage,
        "solver_inputs": {"EJ_GHz": ej_val, "EC_GHz": ec_val, "ng": ng, "ncut": ncut},
        "plot_path": str(plot) if plot else None,
        "model_validity": (
            "EJ and EC derived from extracted Ic and C — never from default ratios. "
            "Spectrum from executed scqubits.Transmon. "
            "Anharmonicity = f12 - f01 (nonzero for transmon regime)."
        ),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["report_path"] = str(report)
    return payload
