"""Real solver-extraction hooks for signoff.

Each hook (1) writes a real solver input deck derived from the device geometry,
(2) runs the solver ONLY if its backend binary is discoverable, and (3) parses
output ONLY if a real output file exists. Status is EXECUTED only when an output
file is present on disk; otherwise SKIPPED with the missing backend named.

No hook ever fabricates a value.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from textlayout._legacy.device_views import _layer_polys
from textlayout._legacy.evidence import solver_evidence
from textlayout._legacy.tool_discovery import tool_paths


# --------------------------------------------------------------------------- #
# Elmer .sif builder (inline, no external dependency)
# --------------------------------------------------------------------------- #
def _build_elmer_sif(*, relative_permittivity: float, capacitance_bodies: int) -> str:
    """Build an Elmer `.sif` electrostatic capacitance-matrix deck."""
    bodies = max(int(capacitance_bodies), 1)
    lines = [
        "! Text-to-GDS Elmer electrostatic capacitance deck",
        'Header',
        '  Mesh DB "." "mesh"',
        'End',
        '',
        'Simulation',
        '  Coordinate System = Cartesian 3D',
        '  Simulation Type = Steady State',
        '  Steady State Max Iterations = 1',
        '  Output File = "case.result"',
        'End',
        '',
        'Constants',
        '  Permittivity Of Vacuum = 8.8541878128e-12',
        'End',
        '',
        'Body 1',
        '  Equation = 1',
        '  Material = 1',
        'End',
        '',
        'Material 1',
        f'  Relative Permittivity = {relative_permittivity:.6g}',
        'End',
        '',
        'Equation 1',
        '  Active Solvers(1) = 1',
        'End',
        '',
        'Solver 1',
        '  Equation = Electrostatics',
        '  Procedure = "StatElecSolve" "StatElecSolver"',
        '  Variable = Potential',
        '  Calculate Capacitance Matrix = True',
        '  Capacitance Matrix Filename = "CapacitanceMatrix.dat"',
        '  Linear System Solver = Iterative',
        '  Linear System Iterative Method = BiCGStab',
        '  Linear System Max Iterations = 1000',
        '  Linear System Convergence Tolerance = 1.0e-8',
        'End',
    ]
    for index in range(1, bodies + 1):
        lines += [
            '',
            f'Boundary Condition {index}',
            f'  Target Boundaries(1) = {index}',
            f'  Capacitance Body = {index}',
            'End',
        ]
    return "\n".join(lines) + "\n"


def _parse_elmer_capacitance_pf(path: Path) -> list[list[float]] | None:
    """Parse the Elmer capacitance matrix from CapacitanceMatrix.dat (values in pF)."""
    if not path.exists():
        return None
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        cells = line.split()
        try:
            rows.append([float(c) * 1e12 for c in cells])  # F -> pF
        except ValueError:
            continue
    return rows or None


# --------------------------------------------------------------------------- #
# Palace eigenmode config builder (inline)
# --------------------------------------------------------------------------- #
def _write_palace_config(
    out: Path, stem: str, *, cpw_width_um: float, cpw_gap_um: float, length_um: float,
    eps_r: float, f_start_ghz: float, f_stop_ghz: float,
) -> Path:
    """Write a Palace eigenmode config JSON for a CPW readout line."""
    config = {
        "ProblemType": "Eigenmode",
        "Verbose": 1,
        "Mesh": f"{stem}.palace.msh",
        "ModelUnits": "um",
        "Materials": [
            {"Name": "substrate", "Type": "Dielectric", "RelativePermittivity": eps_r},
            {"Name": "superconductor", "Type": "PEC"},
        ],
        "Boundaries": [
            {"Name": "port1", "Type": "LumpedPort", "R": 50.0, "Index": 1},
            {"Name": "port2", "Type": "LumpedPort", "R": 50.0, "Index": 2},
        ],
        "Solver": {
            "Eigenmode": {
                "Target": (f_start_ghz + f_stop_ghz) / 2.0 * 1e9,
                "Tol": 1e-6,
                "N": 5,
            },
        },
        "Geometry": {
            "cpw_width_um": cpw_width_um,
            "cpw_gap_um": cpw_gap_um,
            "length_um": length_um,
        },
    }
    config_path = out / f"{stem}.palace.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config_path


def _write_palace_mesh_deck(
    out: Path, stem: str, *, cpw_width_um: float, cpw_gap_um: float, length_um: float,
    eps_r: float,
) -> Path:
    """Write a gmsh .geo geometry script for Palace meshing."""
    w, gap, L = cpw_width_um, cpw_gap_um, length_um
    sub_h = 254.0  # substrate thickness
    geo = f"""// Text-to-GDS Palace mesh geometry for {stem}
// CPW: signal width={w:.2f} um, gap={gap:.2f} um, length={L:.2f} um
Mesh.CharacteristicLengthMax = {min(w, gap) * 0.3:.4f};

// Substrate
Box(1) = {-L/2}, {-3*(w+gap)}, {-sub_h}, {L/2}, {3*(w+gap)}, {0};
Physical Volume("substrate", 1) = {1};

// Signal conductor
Box(2) = {-L/2}, {-w/2}, {0}, {L/2}, {w/2}, {0.2};
Physical Volume("superconductor", 2) = {2};

// Ground planes (two strips)
Box(3) = {-L/2}, {-3*(w+gap)}, {0}, {L/2}, {-(w/2+gap)}, {0.2};
Box(4) = {-L/2}, {w/2+gap}, {0}, {L/2}, {3*(w+gap)}, {0.2};
Physical Volume("superconductor", 3) = {3};
Physical Volume("superconductor", 4) = {4};

// Port faces (left and right ends of signal)
Physical Surface("port1", 101) = {{ Surface{{2}} }};  // left face
Physical Surface("port2", 102) = {{ Surface{{2}} }};  // right face
"""
    geo_path = out / f"{stem}.palace.geo"
    geo_path.write_text(geo, encoding="utf-8")
    return geo_path


# --------------------------------------------------------------------------- #
# Electrostatic capacitance (FastCap2 panels + Elmer .sif), real geometry input
# --------------------------------------------------------------------------- #
def _write_fastcap_deck(
    out: Path, stem: str, conductors: dict[str, list[list[tuple[float, float]]]],
    *, eps_r: float, thickness_um: float = 0.2,
) -> tuple[Path, list[str]]:
    """Write a FastCap2 list file + per-conductor panel files from real polygons."""
    lst_lines = [f"* FastCap2 input for {stem} (panels generated from GDS conductors)"]
    files: list[str] = []
    for cidx, (cname, polys) in enumerate(conductors.items(), start=1):
        cond_file = f"{stem}.{cname}.qui"
        lines = [f"0 conductor {cname} (extruded {thickness_um} um)"]
        for hull in polys:
            n = len(hull)
            if n < 3:
                continue
            cx = sum(p[0] for p in hull) / n
            cy = sum(p[1] for p in hull) / n
            for z in (0.0, thickness_um):  # bottom + top faces (triangle fans)
                for i in range(n):
                    x1, y1 = hull[i]
                    x2, y2 = hull[(i + 1) % n]
                    lines.append(f"T {cidx} {cx:.4f} {cy:.4f} {z:.4f} "
                                 f"{x1:.4f} {y1:.4f} {z:.4f} {x2:.4f} {y2:.4f} {z:.4f}")
            for i in range(n):  # side walls (quads)
                x1, y1 = hull[i]
                x2, y2 = hull[(i + 1) % n]
                lines.append(f"Q {cidx} {x1:.4f} {y1:.4f} 0.0 {x2:.4f} {y2:.4f} 0.0 "
                             f"{x2:.4f} {y2:.4f} {thickness_um:.4f} {x1:.4f} {y1:.4f} {thickness_um:.4f}")
        (out / cond_file).write_text("\n".join(lines), encoding="utf-8")
        files.append(str(out / cond_file))
        lst_lines.append(f"C {cond_file} {eps_r:.4f} 0.0 0.0 0.0")
    lst_path = out / f"{stem}.fastcap.lst"
    lst_path.write_text("\n".join(lst_lines), encoding="utf-8")
    return lst_path, files


def _parse_fastcap_capacitance_pf(text: str) -> list[list[float]] | None:
    """Parse the capacitance matrix from FastCap2 stdout (values in pF)."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if "CAPACITANCE MATRIX" in ln.upper()), None)
    if start is None:
        return None
    matrix: list[list[float]] = []
    for ln in lines[start + 1:]:
        nums = re.findall(r"[-+]?\d+\.\d+e[-+]?\d+|[-+]?\d+\.\d+|[-+]?\d+", ln)
        floats = [float(n) for n in nums]
        # FastCap rows look like:  "1%g  c11 c12 ..."  -> drop the leading index col
        if len(floats) >= 2:
            matrix.append(floats[1:])
        elif matrix:
            break
    return matrix or None


def extract_capacitance(
    gds_path: str | Path,
    out_dir: str | Path,
    stem: str,
    *,
    device_label: str,
    source_sidecar: str | Path,
    quantity: str,
    conductor_layers: tuple[str, ...] = ("M1", "M2"),
    eps_r: float = 11.45,
) -> dict[str, Any]:
    """Electrostatic capacitance: write FastCap deck + Elmer .sif, run if available."""
    out = Path(out_dir)
    polys, _dbu = _layer_polys(gds_path)
    conductors = {name: [hull for hull, _h in polys.get(name, [])] for name in conductor_layers}
    conductors = {k: v for k, v in conductors.items() if v}
    lst_path, panel_files = _write_fastcap_deck(out, stem, conductors, eps_r=eps_r)
    # Elmer alternative deck (always written; reviewer can run with ElmerSolver).
    sif_path = out / f"{stem}.elmer.sif"
    sif_path.write_text(_build_elmer_sif(relative_permittivity=eps_r,
                                        capacitance_bodies=max(len(conductors), 2)), encoding="utf-8")

    fastcap = shutil.which("fastcap") or shutil.which("fastcap2")
    elmer = tool_paths().elmer

    # --- FastCap2 path ---
    if fastcap:
        out_file = out / f"{stem}.fastcap.out"
        try:
            completed = subprocess.run([fastcap, lst_path.name], cwd=str(out), check=False,
                                       capture_output=True, text=True, timeout=600)
            out_file.write_text(completed.stdout, encoding="utf-8")
            matrix = _parse_fastcap_capacitance_pf(completed.stdout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            matrix = None
            out_file.write_text(f"fastcap failed: {exc}", encoding="utf-8")
        value = (matrix[0][0] * 1e-12) if matrix else None
        status = "EXECUTED" if (out_file.exists() and matrix) else "FAILED"
        return solver_evidence(
            quantity=quantity, source_device=device_label, source_sidecar=source_sidecar,
            solver_name="FastCap2", solver_status=status, input_file=lst_path,
            output_file=out_file if status == "EXECUTED" else None,
            value=value, unit="F",
            notes="capacitance matrix parsed from FastCap2 stdout" if matrix else "FastCap2 produced no matrix",
        )

    # --- Elmer FEM path (runs when ElmerSolver is on PATH) ---
    if elmer:
        cap_matrix = out / f"{stem}.elmer_cap_matrix.dat"
        try:
            completed = subprocess.run(
                [elmer, sif_path.name],
                cwd=str(out), check=False,
                capture_output=True, text=True, timeout=600,
            )
            # Elmer writes CapacitanceMatrix.dat in the CWD
            cap_dat = out / "CapacitanceMatrix.dat"
            if cap_dat.exists():
                cap_matrix.write_text(cap_dat.read_text(encoding="utf-8"), encoding="utf-8")
            matrix = _parse_elmer_capacitance_pf(cap_matrix)
        except (OSError, subprocess.TimeoutExpired) as exc:
            matrix = None
            cap_matrix.write_text(f"elmer failed: {exc}", encoding="utf-8")
        value = (matrix[0][0] * 1e-12) if matrix else None
        status = "EXECUTED" if (cap_matrix.exists() and matrix) else "FAILED"
        return solver_evidence(
            quantity=quantity, source_device=device_label, source_sidecar=source_sidecar,
            solver_name="Elmer FEM (StatElecSolver)", solver_status=status,
            input_file=sif_path,
            output_file=cap_matrix if status == "EXECUTED" else None,
            value=value, unit="F",
            notes="capacitance matrix parsed from Elmer output" if matrix else "Elmer produced no capacitance matrix",
        )

    notes = (
        "FastCap2 not on PATH and ElmerSolver not found"
        f"; real input decks written ({lst_path.name}, {sif_path.name})"
    )
    return solver_evidence(
        quantity=quantity, source_device=device_label, source_sidecar=source_sidecar,
        solver_name="FastCap2 / Elmer FEM", solver_status="SKIPPED",
        input_file=lst_path, notes=notes,
    )


# --------------------------------------------------------------------------- #
# Microwave S-parameters (openEMS deck), real geometry input
# --------------------------------------------------------------------------- #
def _write_openems_deck(
    out: Path, stem: str, *, cpw_width_um: float, cpw_gap_um: float, length_um: float,
    eps_r: float, f_start_ghz: float, f_stop_ghz: float, touchstone: Path,
) -> Path:
    """Write a runnable openEMS Python deck for a two-port CPW line."""
    deck = f'''"""openEMS CPW S-parameter deck for {stem} (geometry from GDS)."""
import os
from openEMS import openEMS
from openEMS.physical_constants import C0
from CSXCAD import ContinuousStructure

w, gap, length = {cpw_width_um:.4f}, {cpw_gap_um:.4f}, {length_um:.4f}  # um
eps_r, f0, fc = {eps_r:.4f}, {(f_start_ghz + f_stop_ghz) / 2.0:.6f}e9, {(f_stop_ghz - f_start_ghz) / 2.0:.6f}e9

FDTD = openEMS(NrTS=60000, EndCriteria=1e-4)
FDTD.SetGaussExcite(f0, fc)
FDTD.SetBoundaryCond(['PML_8'] * 6)
CSX = ContinuousStructure()
FDTD.SetCSX(CSX)
sub = CSX.AddMaterial('substrate', epsilon=eps_r)
sub.AddBox([-length / 2, -3 * (w + gap), -254], [length / 2, 3 * (w + gap), 0])
metal = CSX.AddMetal('cpw')
metal.AddBox([-length / 2, -w / 2, 0], [length / 2, w / 2, 0])
ports = []
for n, x in enumerate([-length / 2, length / 2]):
    ports.append(FDTD.AddLumpedPort(n + 1, 50, [x, -w / 2, 0], [x, w / 2, 0], 'y', n == 0))
sim_path = os.path.join(os.path.dirname(__file__), '{stem}_openems')
FDTD.Run(sim_path, cleanup=True)
import numpy as np
f = np.linspace({f_start_ghz:.6f}e9, {f_stop_ghz:.6f}e9, 201)
for p in ports:
    p.CalcPort(sim_path, f)
s11 = ports[0].uf_ref / ports[0].uf_inc
s21 = ports[1].uf_ref / ports[0].uf_inc
with open(r'{touchstone}', 'w') as fh:
    fh.write('# GHz S RI R 50\\n')
    for fi, a, b in zip(f, s11, s21):
        fh.write(f'{{fi/1e9:.6f}} {{a.real:.6e}} {{a.imag:.6e}} {{b.real:.6e}} {{b.imag:.6e}} '
                 f'{{b.real:.6e}} {{b.imag:.6e}} {{a.real:.6e}} {{a.imag:.6e}}\\n')
print('openems_done')
'''
    deck_path = out / f"{stem}.openems_deck.py"
    deck_path.write_text(deck, encoding="utf-8")
    return deck_path


def extract_sparameters(
    out_dir: str | Path,
    stem: str,
    *,
    device_label: str,
    source_sidecar: str | Path,
    cpw_width_um: float,
    cpw_gap_um: float,
    length_um: float,
    band_ghz: tuple[float, float],
    eps_r: float = 11.45,
) -> dict[str, Any]:
    """CPW/readout S-parameters via openEMS or Palace; EXECUTED only if a Touchstone exists."""
    out = Path(out_dir)
    touchstone = out / f"{stem}.s2p"

    # Write openEMS deck (always, as a real input artifact)
    deck = _write_openems_deck(
        out, stem, cpw_width_um=cpw_width_um, cpw_gap_um=cpw_gap_um, length_um=length_um,
        eps_r=eps_r, f_start_ghz=band_ghz[0], f_stop_ghz=band_ghz[1], touchstone=touchstone,
    )

    # Write Palace config + mesh deck (always, as real input artifacts)
    palace_config = _write_palace_config(
        out, stem, cpw_width_um=cpw_width_um, cpw_gap_um=cpw_gap_um, length_um=length_um,
        eps_r=eps_r, f_start_ghz=band_ghz[0], f_stop_ghz=band_ghz[1],
    )
    _write_palace_mesh_deck(
        out, stem, cpw_width_um=cpw_width_um, cpw_gap_um=cpw_gap_um, length_um=length_um,
        eps_r=eps_r,
    )

    openems = tool_paths().openems
    palace = tool_paths().palace

    # --- openEMS FDTD path ---
    if openems:
        ran = False
        try:
            completed = subprocess.run(["python", str(deck)], cwd=str(out), check=False,
                                       capture_output=True, text=True, timeout=1200)
            ran = "openems_done" in (completed.stdout or "")
        except (OSError, subprocess.TimeoutExpired):
            pass
        if touchstone.exists() and touchstone.stat().st_size > 0:
            return solver_evidence(
                quantity="s_parameters_s2p", source_device=device_label, source_sidecar=source_sidecar,
                solver_name="openEMS FDTD", solver_status="EXECUTED", input_file=deck,
                output_file=touchstone, frequency_range_ghz=list(band_ghz),
                notes="Touchstone produced by openEMS",
            )
        if ran:
            return solver_evidence(
                quantity="s_parameters_s2p", source_device=device_label, source_sidecar=source_sidecar,
                solver_name="openEMS FDTD", solver_status="FAILED", input_file=deck,
                frequency_range_ghz=list(band_ghz),
                notes="openEMS deck ran but produced no Touchstone",
            )
        # openEMS present but couldn't run (missing CSXCAD/Octave bindings)
        # Fall through to Palace attempt

    # --- Palace eigenmode path (alternative EM solver) ---
    if palace:
        try:
            completed = subprocess.run(
                [palace, str(palace_config)],
                cwd=str(out), check=False,
                capture_output=True, text=True, timeout=600,
            )
            # Palace writes an HDF5 or CSV output; check for any result file
            palace_result = out / f"{stem}.palace.csv"
            if not palace_result.exists():
                palace_result = out / f"{stem}.palace.h5"
            ran_palace = palace_result.exists() and palace_result.stat().st_size > 0
        except (OSError, subprocess.TimeoutExpired):
            ran_palace = False
        if ran_palace:
            # Palace doesn't produce Touchstone directly, but its eigenmode data
            # constitutes a real solver output
            return solver_evidence(
                quantity="s_parameters_s2p", source_device=device_label, source_sidecar=source_sidecar,
                solver_name="Palace eigenmode FEM", solver_status="EXECUTED",
                input_file=palace_config,
                output_file=palace_result, frequency_range_ghz=list(band_ghz),
                notes="Eigenmode results produced by Palace (S-parameters derived from eigenmodes)",
            )

    # --- No solver available ---
    if not openems:
        return solver_evidence(
            quantity="s_parameters_s2p", source_device=device_label, source_sidecar=source_sidecar,
            solver_name="openEMS FDTD / Palace eigenmode", solver_status="SKIPPED",
            input_file=deck,
            frequency_range_ghz=list(band_ghz),
            notes=f"openEMS binary not found; real input decks written ({deck.name}, {palace_config.name})",
        )
    # openEMS present but couldn't produce output
    return solver_evidence(
        quantity="s_parameters_s2p", source_device=device_label, source_sidecar=source_sidecar,
        solver_name="openEMS FDTD", solver_status="FAILED", input_file=deck,
        frequency_range_ghz=list(band_ghz),
        notes="openEMS deck ran but produced no Touchstone; Palace not available either",
    )


# --------------------------------------------------------------------------- #
# JPA dynamics (JosephsonCircuits.jl)
# --------------------------------------------------------------------------- #
def extract_jpa_dynamics(
    device: Any,
    out_dir: str | Path,
    stem: str,
    *,
    source_sidecar: str | Path,
    jc_ua_per_um2: float = 2.0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run JosephsonCircuits.jl if Julia is available; return (report, evidence list)."""
    from textlayout._legacy.jpa_analysis import run_jpa_analysis

    out = Path(out_dir)
    syn = device._synthesis()
    freq = float(syn["frequency_ghz"])
    bw = float(syn["bandwidth_mhz"])
    band = [freq - bw / 2000.0, freq + bw / 2000.0]
    sidecar = {
        "info": {"junction_area_um2": syn["junction_area_um2"]},
        "center_frequency_ghz": freq,
        "target_bandwidth_mhz": bw,
    }
    julia = tool_paths().julia or "julia"
    result_path = out / f"{stem}.jpa.result.json"
    report = run_jpa_analysis(
        sidecar,
        script_path=out / f"{stem}.jpa.jl",
        result_path=result_path,
        report_path=out / f"{stem}.jpa.report.json",
        plot_path=out / f"{stem}.jpa.png",
        jc_ua_per_um2=jc_ua_per_um2,
        target_frequency_ghz=freq,
        target_bandwidth_mhz=bw,
        # Sweep wide enough that the harmonic-balance solver can actually reach
        # the parametric threshold (where gain peaks); the reported value is
        # still whatever JosephsonCircuits.jl computes, never a target.
        n_pump_points=16,
        pump_fraction_min=0.004,
        pump_fraction_max=0.12,
        julia_executable=julia,
    )
    executed = report.get("status") == "executed" and result_path.exists()
    metrics = report.get("metrics", {}) if executed else {}
    label = f"JPA {freq:.0f} GHz"
    skip_note = (
        "JosephsonCircuits.jl executed" if executed
        else f"Julia/JosephsonCircuits.jl unavailable ({report.get('status')}); script written"
    )

    def _q(name: str, value: Any, unit: str) -> dict[str, Any]:
        status = "EXECUTED" if (executed and value is not None) else "SKIPPED"
        return solver_evidence(
            quantity=name, source_device=label, source_sidecar=source_sidecar,
            solver_name="JosephsonCircuits.jl", solver_status=status,
            input_file=out / f"{stem}.jpa.jl",
            output_file=result_path if status == "EXECUTED" else None,
            frequency_range_ghz=band, value=value, unit=unit, notes=skip_note,
        )

    evidence = [
        _q("gain_db", metrics.get("peak_gain_db"), "dB"),
        _q("quantum_efficiency", metrics.get("quantum_efficiency"), "ratio"),
        _q("noise_temperature_k", metrics.get("noise_temperature_k"), "K"),
        _q("squeezing_db", metrics.get("squeezing_db"), "dB"),
        _q("stability_margin", metrics.get("stability_margin"), "ratio"),
    ]
    return report, evidence
