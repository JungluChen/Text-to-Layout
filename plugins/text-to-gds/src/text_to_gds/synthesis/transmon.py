"""Transmon parameter synthesis with scqubits-compatible quantities."""

from __future__ import annotations

import math
from typing import Any

from text_to_gds.extraction import ELECTRON_CHARGE_C, PHI0_WEBER, PLANCK_J_S


def synthesize_transmon(
    *,
    frequency_ghz: float,
    anharmonicity_mhz: float = -250.0,
    jc_ua_per_um2: float = 2.0,
) -> dict[str, Any]:
    if frequency_ghz <= 0.0 or jc_ua_per_um2 <= 0.0:
        raise ValueError("frequency_ghz and jc_ua_per_um2 must be positive")
    ec_ghz = abs(anharmonicity_mhz) / 1000.0
    if ec_ghz <= 0.0:
        raise ValueError("anharmonicity_mhz must be nonzero")
    ej_ghz = ((frequency_ghz + ec_ghz) ** 2) / (8.0 * ec_ghz)
    capacitance_f = ELECTRON_CHARGE_C**2 / (2.0 * PLANCK_J_S * ec_ghz * 1e9)
    ic_a = 2.0 * math.pi * (ej_ghz * 1e9 * PLANCK_J_S) / PHI0_WEBER
    junction_area_um2 = ic_a / (jc_ua_per_um2 * 1e-6)
    side_um = math.sqrt(max(junction_area_um2, 0.01))
    # Pre-layout feasibility gate: reject parameters that cannot produce a real
    # transmon before any GDS is written. EJ/EC < 20 leaves the charge-noise
    # regime; EJ/EC > 100 yields a flux-qubit-like double well with vanishing
    # anharmonicity. Both are non-physical for a tapeout-intended transmon.
    ej_over_ec = ej_ghz / ec_ghz
    if not 20.0 <= ej_over_ec <= 100.0:
        raise ValueError(
            f"EJ/EC = {ej_over_ec:.1f} is outside the transmon regime [20, 100]; "
            f"adjust frequency_ghz ({frequency_ghz}) / anharmonicity_mhz ({anharmonicity_mhz})"
        )
    if not 0.01 <= junction_area_um2 <= 10.0:
        raise ValueError(
            f"junction area {junction_area_um2:.4f} um^2 is unfabricable "
            f"(allowed 0.01-10 um^2 at Jc={jc_ua_per_um2} uA/um^2)"
        )
    validation: dict[str, Any] = {
        "tool": "scqubits",
        "status": "skipped",
        "reason": "scqubits validation not executed in synthesis function",
    }
    try:
        import scqubits as scq

        qubit = scq.Transmon(EJ=ej_ghz, EC=ec_ghz, ng=0.0, ncut=30)
        evals = qubit.eigenvals(evals_count=3)
        validation = {
            "tool": "scqubits",
            "status": "executed",
            "f01_ghz": float(evals[1] - evals[0]),
            "f12_ghz": float(evals[2] - evals[1]),
        }
    except Exception as exc:  # noqa: BLE001
        validation["reason"] = f"scqubits unavailable or failed: {exc}"
    return {
        "schema": "text-to-gds.synthesis.transmon.v1",
        "status": "ready",
        "frequency_ghz": frequency_ghz,
        "anharmonicity_mhz": anharmonicity_mhz,
        "ej_ghz": ej_ghz,
        "ec_ghz": ec_ghz,
        "ej_over_ec": ej_ghz / ec_ghz,
        "capacitance_f": capacitance_f,
        "capacitance_ff": capacitance_f * 1e15,
        "ic_a": ic_a,
        "ic_ua": ic_a * 1e6,
        "junction_area_um2": junction_area_um2,
        "junction_width_um": side_um,
        "junction_height_um": side_um,
        "scqubits_validation": validation,
        "lineage": {
            "EC": "EC approx |anharmonicity|",
            "EJ": "f01 approx sqrt(8*EJ*EC)-EC",
            "C": "EC = e^2/(2*C*h)",
            "Ic": "EJ = Phi0*Ic/(2*pi*h)",
            "area": "area = Ic/Jc",
        },
    }
