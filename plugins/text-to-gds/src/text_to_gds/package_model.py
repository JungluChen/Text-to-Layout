"""Analytic chip-package parasitics: bondwire inductance and cavity modes.

These are first-order closed-form estimates (Grover bondwire inductance and the
rectangular-cavity resonance formula). They are design-screening tools, not a
full 3D package solve; treat the numbers as guidance until confirmed by HFSS or
measurement.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

MU0_H_PER_M = 4.0e-7 * math.pi
SPEED_OF_LIGHT_M_PER_S = 299792458.0


def bondwire_inductance_nh(
    length_um: float,
    diameter_um: float,
    *,
    count: int = 1,
    pitch_um: float | None = None,
) -> dict[str, Any]:
    """Grover straight-round-wire inductance, reduced for parallel bondwires.

    `L_single = (mu0 l / 2pi)(ln(2l/r) - 0.75)`. For `count` parallel wires with
    a pairwise mutual coupling derived from `pitch_um`, the effective inductance
    is `L_single (1 + k (count - 1)) / count`.
    """
    if length_um <= 0.0:
        raise ValueError(f"length_um must be positive, got {length_um}")
    if diameter_um <= 0.0:
        raise ValueError(f"diameter_um must be positive, got {diameter_um}")
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count}")
    if count > 1 and (pitch_um is None or pitch_um <= 0.0):
        raise ValueError("pitch_um must be positive when count > 1")

    length_m = length_um * 1e-6
    radius_m = (diameter_um / 2.0) * 1e-6
    single_h = (MU0_H_PER_M * length_m / (2.0 * math.pi)) * (
        math.log(2.0 * length_m / radius_m) - 0.75
    )

    coupling_k = 0.0
    mutual_h = 0.0
    if count > 1 and pitch_um:
        pitch_m = pitch_um * 1e-6
        mutual_h = (MU0_H_PER_M * length_m / (2.0 * math.pi)) * (
            math.log(2.0 * length_m / pitch_m) - 1.0 + pitch_m / length_m
        )
        coupling_k = min(max(mutual_h / single_h, 0.0), 0.99)
    effective_h = single_h * (1.0 + coupling_k * (count - 1)) / count
    return {
        "single_wire_nh": single_h * 1e9,
        "effective_nh": effective_h * 1e9,
        "mutual_coupling_k": coupling_k,
        "count": count,
        "length_um": length_um,
        "diameter_um": diameter_um,
        "pitch_um": pitch_um,
    }


def rectangular_cavity_modes_ghz(
    width_mm: float,
    length_mm: float,
    height_mm: float,
    *,
    epsilon_r: float = 1.0,
    max_modes: int = 5,
) -> list[dict[str, Any]]:
    """Lowest resonant modes of a closed rectangular package cavity.

    `f_mnl = (c / 2 sqrt(eps_r)) sqrt((m/a)^2 + (n/b)^2 + (l/d)^2)` with the box
    edges `a=width`, `b=height`, `d=length`. Modes with two zero indices do not
    exist and are skipped.
    """
    for name, value in (("width_mm", width_mm), ("length_mm", length_mm), ("height_mm", height_mm)):
        if value <= 0.0:
            raise ValueError(f"{name} must be positive, got {value}")
    if epsilon_r <= 0.0:
        raise ValueError(f"epsilon_r must be positive, got {epsilon_r}")

    a = width_mm * 1e-3
    b = height_mm * 1e-3
    d = length_mm * 1e-3
    prefactor = SPEED_OF_LIGHT_M_PER_S / (2.0 * math.sqrt(epsilon_r))
    modes: list[dict[str, Any]] = []
    for m in range(0, 3):
        for n in range(0, 3):
            for ell in range(0, 3):
                if (m == 0) + (n == 0) + (ell == 0) >= 2:
                    continue
                frequency_ghz = prefactor * math.sqrt(
                    (m / a) ** 2 + (n / b) ** 2 + (ell / d) ** 2
                ) / 1e9
                modes.append({"mode": [m, n, ell], "frequency_ghz": frequency_ghz})
    modes.sort(key=lambda item: item["frequency_ghz"])
    return modes[:max_modes]


def estimate_package_model(
    *,
    bondwire_length_um: float = 800.0,
    bondwire_diameter_um: float = 25.0,
    bondwire_count: int = 1,
    bondwire_pitch_um: float | None = None,
    package_width_mm: float = 6.0,
    package_length_mm: float = 6.0,
    package_height_mm: float = 3.0,
    package_epsilon_r: float = 1.0,
    operating_frequency_ghz: float = 6.0,
    coupling_capacitance_ff: float | None = None,
    mode_guard_band_ghz: float = 1.0,
) -> dict[str, Any]:
    """Estimate the chip -> wirebond -> PCB -> package -> connector parasitic chain."""
    if operating_frequency_ghz <= 0.0:
        raise ValueError(f"operating_frequency_ghz must be positive, got {operating_frequency_ghz}")

    bondwire = bondwire_inductance_nh(
        bondwire_length_um,
        bondwire_diameter_um,
        count=bondwire_count,
        pitch_um=bondwire_pitch_um,
    )
    effective_l_h = bondwire["effective_nh"] * 1e-9
    series_reactance_ohm = 2.0 * math.pi * operating_frequency_ghz * 1e9 * effective_l_h

    self_resonance_ghz = None
    if coupling_capacitance_ff is not None:
        if coupling_capacitance_ff <= 0.0:
            raise ValueError("coupling_capacitance_ff must be positive when provided")
        cap_f = coupling_capacitance_ff * 1e-15
        self_resonance_ghz = 1.0 / (2.0 * math.pi * math.sqrt(effective_l_h * cap_f)) / 1e9

    modes = rectangular_cavity_modes_ghz(
        package_width_mm,
        package_length_mm,
        package_height_mm,
        epsilon_r=package_epsilon_r,
    )
    lowest_mode_ghz = modes[0]["frequency_ghz"] if modes else None
    modes_near_band = [
        mode
        for mode in modes
        if abs(mode["frequency_ghz"] - operating_frequency_ghz) <= mode_guard_band_ghz
    ]
    warnings: list[str] = []
    if modes_near_band:
        warnings.append(
            f"{len(modes_near_band)} package mode(s) within {mode_guard_band_ghz} GHz of the "
            f"{operating_frequency_ghz} GHz operating band; package resonance can spoil the JPA."
        )
    if series_reactance_ohm > 25.0:
        warnings.append(
            f"Bondwire series reactance {series_reactance_ohm:.1f} ohm is comparable to 50 ohm; "
            "reduce bondwire length or parallel more wires."
        )

    return {
        "schema": "text-to-gds.package-model.v1",
        "operating_frequency_ghz": operating_frequency_ghz,
        "bondwire": bondwire,
        "bondwire_series_reactance_ohm": series_reactance_ohm,
        "bondwire_self_resonance_ghz": self_resonance_ghz,
        "package_modes_ghz": modes,
        "lowest_package_mode_ghz": lowest_mode_ghz,
        "modes_near_operating_band": modes_near_band,
        "chain": ["chip", "wirebond", "pcb", "package_cavity", "connector"],
        "warnings": warnings,
        "model_validity": (
            "Closed-form Grover bondwire inductance and rectangular-cavity modes. "
            "Confirm with HFSS package modelling or measured S-parameters before signoff."
        ),
    }


def _plot_package_model(model: dict[str, Any], plot_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    operating = model["operating_frequency_ghz"]
    effective_l_h = model["bondwire"]["effective_nh"] * 1e-9
    upper = max(operating * 2.0, (model["lowest_package_mode_ghz"] or operating) * 1.3, 12.0)
    freq = np.linspace(0.1, upper, 400)
    reactance = 2.0 * math.pi * freq * 1e9 * effective_l_h

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot(freq, reactance, label="bondwire |X_L| (ohm)")
    ax.axhline(50.0, color="gray", ls=":", lw=1, label="50 ohm")
    ax.axvline(operating, color="seagreen", ls="--", lw=1, label=f"operating {operating:g} GHz")
    for mode in model["package_modes_ghz"]:
        ax.axvline(mode["frequency_ghz"], color="crimson", ls="-", lw=0.8, alpha=0.6)
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("Series reactance (ohm)")
    ax.set_title(
        f"Package model: L={model['bondwire']['effective_nh']:.2f} nH, "
        f"lowest mode {model['lowest_package_mode_ghz']:.2f} GHz"
    )
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def write_package_model(
    *,
    report_path: str | Path,
    plot_path: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Compute the package model, write a JSON report and an impedance/mode plot."""
    model = estimate_package_model(**kwargs)
    try:
        _plot_package_model(model, Path(plot_path))
        model["plot_path"] = str(plot_path)
    except Exception as exc:  # pragma: no cover - plotting is best effort
        model["plot_error"] = str(exc)
    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(model, indent=2), encoding="utf-8")
    model["report_path"] = str(report_file)
    return model
