"""FastHenry (inductance) and FastCap (capacitance) parasitic-extraction decks.

The classic MIT solvers extract conductor self/mutual inductance (FastHenry) and
the capacitance matrix (FastCap) from simple text decks. This module generates
runnable decks from the layout/process stack and executes the binaries when they
are on PATH (FastFieldSolvers ships Windows builds), skipping cleanly otherwise.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from textlayout._legacy.pyaedt_bridge import build_pyaedt_config


def fasthenry_available() -> bool:
    return shutil.which("fasthenry") is not None


def fastcap_available() -> bool:
    return shutil.which("fastcap") is not None


def _top_routing_layer(layer_mapping: dict[str, Any]) -> dict[str, Any]:
    return max(layer_mapping.values(), key=lambda spec: float(spec["elevation_um"]))


def _conductor_endpoints(stack: dict[str, Any]) -> tuple[list[float], list[float], float]:
    """Return (start_xy, end_xy, width_um) from RF ports, or the device diagonal."""
    ports = stack["ports"]["items"]
    if len(ports) >= 2:
        a, b = ports[0], ports[1]
        width = max(float(a.get("width", 10.0)), 1.0)
        return [float(a["center"][0]), float(a["center"][1])], [
            float(b["center"][0]),
            float(b["center"][1]),
        ], width
    bbox = stack["bbox_um"]
    return [bbox[0], 0.0], [bbox[2], 0.0], 10.0


def write_fasthenry_deck(
    *,
    inp_path: str | Path,
    start_xy: list[float],
    end_xy: list[float],
    width_um: float,
    height_um: float,
    elevation_um: float,
    conductivity_s_per_m: float = 5.8e7,
    freq_start_hz: float = 1e9,
    freq_stop_hz: float = 1e10,
    n_segments: int = 4,
) -> dict[str, Any]:
    """Write a FastHenry `.inp` deck for a conductor discretized into segments."""
    sigma_per_um = conductivity_s_per_m / 1e6  # 1/(Ohm*m) -> 1/(Ohm*um) for .units um
    lines = [
        "* Text-to-GDS FastHenry deck (conductor self-inductance)",
        ".units um",
        f".default sigma={sigma_per_um:.6g}",
        "",
    ]
    nodes = []
    for index in range(n_segments + 1):
        frac = index / n_segments
        x = start_xy[0] + frac * (end_xy[0] - start_xy[0])
        y = start_xy[1] + frac * (end_xy[1] - start_xy[1])
        node = f"N{index + 1}"
        nodes.append(node)
        lines.append(f"{node} x={x:.4f} y={y:.4f} z={elevation_um:.4f}")
    lines.append("")
    for index in range(n_segments):
        lines.append(
            f"E{index + 1} {nodes[index]} {nodes[index + 1]} "
            f"w={width_um:.4f} h={height_um:.4f} nwinc=5 nhinc=3"
        )
    lines += [
        "",
        f".external {nodes[0]} {nodes[-1]}",
        f".freq fmin={freq_start_hz:.6g} fmax={freq_stop_hz:.6g} ndec=1",
        ".end",
    ]
    inp = Path(inp_path)
    inp.parent.mkdir(parents=True, exist_ok=True)
    inp.write_text("\n".join(lines), encoding="utf-8")
    return {"inp_path": str(inp), "nodes": len(nodes), "segments": n_segments}


def _box_panels(name: str, box: list[float], z0: float, z1: float) -> str:
    """Six quadrilateral panels (a box) in FastCap quickif format."""
    x0, y0, x1, y1 = box
    corners = {
        "b": [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
        "t": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
        "s1": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        "s2": [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
        "s3": [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
        "s4": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
    }
    lines = [f"0 {name} conductor panels"]
    for quad in corners.values():
        coords = " ".join(f"{c:.4f}" for point in quad for c in point)
        lines.append(f"Q {name} {coords}")
    return "\n".join(lines) + "\n"


def write_fastcap_deck(
    *,
    lst_path: str | Path,
    conductors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write a FastCap list file plus one quickif panel file per conductor."""
    lst = Path(lst_path)
    lst.parent.mkdir(parents=True, exist_ok=True)
    list_lines = ["* Text-to-GDS FastCap list file"]
    for index, conductor in enumerate(conductors, start=1):
        name = conductor["name"]
        panel_file = lst.with_name(f"{lst.stem}_{name}.qui")
        panel_file.write_text(
            _box_panels(name, conductor["box"], conductor["z0"], conductor["z1"]),
            encoding="utf-8",
        )
        list_lines.append(f"C {panel_file.name} 1.0 0.0 0.0 0.0")
    lst.write_text("\n".join(list_lines) + "\n", encoding="utf-8")
    return {"lst_path": str(lst), "conductors": [c["name"] for c in conductors]}


def _parse_fasthenry_inductance_nh(output_dir: Path) -> float | None:
    mat = output_dir / "Zc.mat"
    if not mat.exists():
        return None
    text = mat.read_text(encoding="utf-8", errors="ignore")
    # Impedance row is "Re + Im j"; L = Im / (2 pi f). Fall back to first complex pair.
    numbers = re.findall(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?", text)
    freqs = re.findall(r"Frequency\s*=\s*([-+0-9.eE]+)", text)
    if len(numbers) >= 2 and freqs:
        try:
            imag = float(numbers[1])
            freq = float(freqs[0])
            return imag / (2.0 * 3.141592653589793 * freq) * 1e9
        except (ValueError, ZeroDivisionError):
            return None
    return None


def _parse_fastcap_matrix_pf(stdout: str) -> list[list[float]] | None:
    rows: list[list[float]] = []
    for line in stdout.splitlines():
        cells = re.findall(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?", line)
        if len(cells) >= 2 and ("%" in line or "Cond" in line or "capacitance" in line.lower()):
            try:
                rows.append([float(c) for c in cells])
            except ValueError:
                continue
    return rows or None


def export_fasthenry(
    gds_path: str | Path,
    *,
    inp_path: str | Path,
    report_path: str | Path,
    sidecar_path: str | Path | None = None,
    process_path: str | Path | None = None,
    run: bool = True,
) -> dict[str, Any]:
    """Generate (and optionally run) a FastHenry inductance extraction."""
    stack = build_pyaedt_config(
        gds_path, outputs={}, sidecar_path=sidecar_path, process_path=process_path
    )
    top = _top_routing_layer(stack["layer_mapping"])
    start_xy, end_xy, width = _conductor_endpoints(stack)
    deck = write_fasthenry_deck(
        inp_path=inp_path,
        start_xy=start_xy,
        end_xy=end_xy,
        width_um=width,
        height_um=float(top["thickness_um"]),
        elevation_um=float(top["elevation_um"]),
    )
    result: dict[str, Any] = {
        "schema": "text-to-gds.fasthenry.v1",
        "backend": "FastHenry",
        "status": "prepared",
        "source_gds": str(gds_path),
        "deck": deck,
        "expected_results": ["inductance_nh", "resistance_ohm"],
        "model_validity": (
            "Normal-metal conductor model; superconducting kinetic inductance needs the "
            "lambda/sheet model from export_superconducting_material."
        ),
    }
    if run:
        if not fasthenry_available():
            result["status"] = "skipped"
            result["warnings"] = ["fasthenry not on PATH; install FastFieldSolvers FastHenry."]
        else:
            inp = Path(inp_path)
            completed = subprocess.run(
                ["fasthenry", inp.name],
                check=False,
                capture_output=True,
                text=True,
                cwd=str(inp.parent),
            )
            result["returncode"] = completed.returncode
            inductance = _parse_fasthenry_inductance_nh(inp.parent)
            if inductance is not None:
                result["inductance_nh"] = inductance
            result["status"] = "executed" if completed.returncode == 0 else "failed"
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report_path)
    return result


def export_fastcap(
    gds_path: str | Path,
    *,
    lst_path: str | Path,
    report_path: str | Path,
    sidecar_path: str | Path | None = None,
    process_path: str | Path | None = None,
    run: bool = True,
) -> dict[str, Any]:
    """Generate (and optionally run) a FastCap capacitance-matrix extraction."""
    from textlayout._legacy.meshing import _layer_footprints

    stack = build_pyaedt_config(
        gds_path, outputs={}, sidecar_path=sidecar_path, process_path=process_path
    )
    footprints = _layer_footprints(gds_path)
    conductors = []
    for number, box in footprints.items():
        spec = stack["layer_mapping"].get(number)
        if spec is None:
            continue
        z0 = float(spec["elevation_um"])
        conductors.append(
            {
                "name": spec["name"],
                "box": box,
                "z0": z0,
                "z1": z0 + float(spec["thickness_um"]),
            }
        )
    conductors = sorted(
        conductors,
        key=lambda c: (c["box"][2] - c["box"][0]) * (c["box"][3] - c["box"][1]),
        reverse=True,
    )[:3]
    deck = write_fastcap_deck(lst_path=lst_path, conductors=conductors)
    result: dict[str, Any] = {
        "schema": "text-to-gds.fastcap.v1",
        "backend": "FastCap",
        "status": "prepared",
        "source_gds": str(gds_path),
        "deck": deck,
        "expected_results": ["capacitance_matrix_pf"],
        "model_validity": (
            "Conductor surfaces meshed as box panels in vacuum; add the substrate "
            "dielectric and finer panels before capacitance signoff."
        ),
    }
    if run:
        if not fastcap_available():
            result["status"] = "skipped"
            result["warnings"] = ["fastcap not on PATH; install FastFieldSolvers FastCap."]
        else:
            lst = Path(lst_path)
            completed = subprocess.run(
                ["fastcap", lst.name],
                check=False,
                capture_output=True,
                text=True,
                cwd=str(lst.parent),
            )
            result["returncode"] = completed.returncode
            matrix = _parse_fastcap_matrix_pf(completed.stdout)
            if matrix is not None:
                result["capacitance_matrix_pf"] = matrix
            result["status"] = "executed" if completed.returncode == 0 else "failed"
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report_path)
    return result
