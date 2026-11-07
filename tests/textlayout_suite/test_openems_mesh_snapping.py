"""Verification of openEMS Port Mesh Snapping & Zero-Signal Rectification."""

from __future__ import annotations

import math
from pathlib import Path


from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation.mesh_snapping import (
    MeshSnappingGuard,
    PortTerminal,
    validate_port_energy,
)
from textlayout.simulation.open_source import prepare_cpw_openems


def test_collapsed_port_mesh_root_cause_diagnosis() -> None:
    # Diagnostic scenario: port terminal coordinates falling on the same Yee cell / line
    # e.g., low = 5.0, high = 5.0 or mesh lines having only 1 line in [5.0, 11.0]
    guard = MeshSnappingGuard(min_distinct_lines=3)
    collapsed_mesh = {"y": [0.0, 5.0, 20.0, 50.0]}
    terminals = [PortTerminal(port_index=1, terminal_low=5.0, terminal_high=11.0, axis="y")]

    # Before snapping, only 5.0 is in [5.0, 11.0] -> distinct lines count is 1 < 3
    assert not guard.verify_gap_span(collapsed_mesh["y"], 5.0, 11.0)

    # Snapping guard rectifies this by inserting distinct lines
    res = guard.snap(collapsed_mesh, terminals)
    assert res.passed is True
    assert res.any_lines_inserted is True
    assert guard.verify_gap_span(collapsed_mesh["y"], 5.0, 11.0)
    assert len([y for y in collapsed_mesh["y"] if 5.0 <= y <= 11.0]) >= 3


def test_validate_port_energy_rejects_zero_or_nan() -> None:
    # 1. Zero energy injected
    zero_err = validate_port_energy(port_energies={1: 0.0, 2: 0.0})
    assert len(zero_err) > 0
    assert any("collapsed" in msg for msg in zero_err)

    # 2. Non-finite S-parameters
    nan_err = validate_port_energy(
        port_energies={1: 1e-6},
        s_parameters={"s11": [complex(float("nan"), 0.0)]},
    )
    assert len(nan_err) > 0
    assert any("non-finite" in msg for msg in nan_err)

    # 3. Valid non-zero energy and finite S-parameters
    valid_err = validate_port_energy(
        port_energies={1: 1.25e-6, 2: 1.20e-6},
        s_parameters={
            "s11": [complex(0.01, -0.02), complex(0.015, -0.025)],
            "s21": [complex(0.99, -0.1), complex(0.98, -0.15)],
        },
    )
    assert len(valid_err) == 0


def test_standard_50ohm_cpw_openems_mesh_snapping(tmp_path: Path) -> None:
    # Standard 50-ohm CPW through line: w = 10 um, gap = 6 um, length = 1000 um
    spec = LayoutSpec(
        component="CPW",
        parameters={
            "length_um": 1000.0,
            "center_width_um": 10.0,
            "gap_um": 6.0,
            "ground_width_um": 100.0,
        },
        target={"frequency_ghz": 5.0},
    )
    workflow = build_default_workflow()
    layout_res = workflow.run(spec, formats=())
    assert layout_res.report.passed

    tech = workflow.technology(spec.technology)

    out_dir = tmp_path / "openems_cpw"
    res = prepare_cpw_openems(spec, layout_res.geometry, tech, out_dir)
    assert res.status == "input_files_prepared"

    driver_path = Path(res.artifacts["driver"])
    assert driver_path.is_file()
    octave_script = driver_path.read_text(encoding="utf-8")

    # Assert driver contains excitation gap snapping lines
    # gap is from width/2 = 5 to width/2 + gap = 11
    # Check that mesh.y explicitly includes the required gap subdivision lines
    assert "5" in octave_script
    assert "11" in octave_script
    assert "unique(sort([mesh.y" in octave_script

    # Synthetic verification of port response on standard 50-ohm line
    # 401 frequency points from f_start to f_stop
    freq_count = 401
    f_start = 5.0e9 / 4.0
    f_stop = 2.0 * 5.0e9
    freqs = [f_start + i * (f_stop - f_start) / (freq_count - 1) for i in range(freq_count)]

    # Ideal / physical simulated S-parameters for 50-ohm matched line:
    # S11 ~ -30 to -40 dB (|S11| << 1, non-zero), S21 has unit magnitude with transmission phase delay
    v_p = 3e8 / math.sqrt((11.7 + 1.0) / 2.0)
    length_m = 1000.0 * 1e-6
    s11_sim = [
        complex(
            0.005 * math.cos(2 * math.pi * f * length_m / v_p),
            0.005 * math.sin(2 * math.pi * f * length_m / v_p),
        )
        for f in freqs
    ]
    s21_sim = [
        complex(
            0.999 * math.cos(-2 * math.pi * f * length_m / v_p),
            0.999 * math.sin(-2 * math.pi * f * length_m / v_p),
        )
        for f in freqs
    ]

    port_energies = {1: 2.5e-12, 2: 2.48e-12}  # non-zero injected port energy
    s_params = {"s11": s11_sim, "s21": s21_sim}

    # Verify no non-finite or zero samples across all 401 points
    failures = validate_port_energy(port_energies=port_energies, s_parameters=s_params)
    assert len(failures) == 0
    for name, vals in s_params.items():
        assert len(vals) == 401
        assert all(math.isfinite(v.real) and math.isfinite(v.imag) for v in vals)
        assert all(not (v.real == 0.0 and v.imag == 0.0) for v in vals)
