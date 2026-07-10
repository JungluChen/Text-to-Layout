"""CPW resonator synthesis."""

from __future__ import annotations

from typing import Any

from textlayout._legacy.cpw_physics import synthesize_cpw


def synthesize_resonator(
    *,
    frequency_ghz: float,
    impedance_ohm: float = 50.0,
    kind: str = "lambda/4",
    center_width_um: float = 10.0,
    gap_um: float = 6.0,
    ground_width_um: float = 500.0,
    epsilon_r: float = 11.45,
    substrate_thickness_um: float = 254.0,
) -> dict[str, Any]:
    cpw = synthesize_cpw(
        center_width_um=center_width_um,
        gap_um=gap_um,
        ground_width_um=ground_width_um,
        epsilon_r=epsilon_r,
        substrate_thickness_um=substrate_thickness_um,
        frequency_ghz=frequency_ghz,
        target_impedance_ohm=impedance_ohm,
        impedance_tolerance_ohm=10.0,
        substrate="high_resistivity_silicon",
    )
    factor = 1.0 if kind in {"lambda/4", "quarter_wave", "hanger"} else 2.0
    length_um = cpw["quarter_wave_length_um"] * factor
    return {
        "schema": "text-to-gds.synthesis.resonator.v1",
        "status": cpw["status"],
        "kind": kind,
        "frequency_ghz": frequency_ghz,
        "impedance_ohm": cpw["impedance_ohm"],
        "epsilon_eff": cpw["effective_permittivity"],
        "vp_m_per_s": cpw["phase_velocity_m_per_s"],
        "physical_length_um": length_um,
        "trace_width_um": center_width_um,
        "gap_um": gap_um,
        "lineage": cpw["lineage"],
    }
