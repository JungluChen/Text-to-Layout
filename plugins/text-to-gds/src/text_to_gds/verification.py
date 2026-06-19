"""Layout extraction, LVS, design differencing, and wafer-mask generation."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

from text_to_gds.process import DEFAULT_PROCESS, ProcessStack


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, float):
        return round(value, 12)
    return value


def extract_equivalent_circuit(sidecar: dict[str, Any]) -> dict[str, Any]:
    """Extract a deterministic circuit graph from semantic layout metadata.

    The extractor uses explicit PCell metadata and ports. It does not infer
    connectivity through arbitrary unlabeled polygons; that limitation is
    reported rather than silently inventing nets.
    """
    info = sidecar.get("info", {}) if isinstance(sidecar.get("info"), dict) else {}
    pcell = str(sidecar.get("pcell", info.get("device_type", "unknown")))
    ports = sidecar.get("ports", []) if isinstance(sidecar.get("ports"), list) else []
    port_names = [str(port.get("name")) for port in ports if isinstance(port, dict)]
    nodes = sorted(set(port_names or ["0", "device"]))
    if "0" not in nodes:
        nodes.append("0")
    elements: list[dict[str, Any]] = []
    node_a = port_names[0] if port_names else "device"
    node_b = port_names[1] if len(port_names) > 1 else "0"
    area = float(info.get("junction_area_um2", 0.0) or 0.0)
    if area > 0.0 or "junction" in pcell or "jpa" in pcell or "squid" in pcell:
        junctions = int(info.get("junction_count", 2 if "squid" in pcell or "jpa" in pcell else 1))
        for index in range(junctions):
            elements.append(
                {
                    "name": f"BJJ{index + 1}",
                    "kind": "josephson_junction",
                    "nodes": [node_a, node_b],
                    "parameters": {"area_um2": area / max(junctions, 1)},
                }
            )
    length = float(info.get("length_um", info.get("trace_length_um", 0.0)) or 0.0)
    width = float(info.get("trace_width_um", info.get("width_um", 0.0)) or 0.0)
    if length > 0.0 and ("cpw" in pcell or "resonator" in pcell):
        elements.append(
            {
                "name": "TL1",
                "kind": "transmission_line",
                "nodes": [node_a, node_b],
                "parameters": {
                    "length_um": length,
                    "width_um": width,
                    "impedance_ohm": float(info.get("impedance_ohm", 50.0)),
                },
            }
        )
    if not elements:
        elements.append(
            {
                "name": "X1",
                "kind": pcell,
                "nodes": [node_a, node_b],
                "parameters": _canonical(info),
            }
        )
    return {
        "schema": "text-to-gds.extracted-circuit.v1",
        "source_pcell": pcell,
        "nodes": sorted(set(nodes)),
        "ports": port_names,
        "elements": elements,
        "extraction_basis": "semantic_pcell_metadata_and_named_ports",
        "polygon_connectivity_complete": False,
    }


def extract_circuit_from_gds(
    gds_path: str | Path, *, process: ProcessStack = DEFAULT_PROCESS
) -> dict[str, Any]:
    """Extract metal connectivity, vias, and JJ devices directly from GDS polygons."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    tops = layout.top_cells()
    if not tops:
        raise ValueError("GDS contains no top cell")
    conductor_names = [name for name in ("M1", "M2", "M3") if name in process.layers]
    via_pairs = {"VIA12": ("M1", "M2"), "VIA23": ("M2", "M3")}

    def polygons(layer_name: str) -> list[Any]:
        spec = process.layers.get(layer_name)
        if spec is None:
            return []
        index = layout.find_layer(*spec.layer)
        if index is None:
            return []
        region = kdb.Region()
        for top in tops:
            region.insert(top.begin_shapes_rec(index))
        region.merge()
        return list(region.each_merged())

    metal_polygons = {name: polygons(name) for name in conductor_names}
    keys = [(name, index) for name in conductor_names for index in range(len(metal_polygons[name]))]
    parent = {key: key for key in keys}

    def find(key: tuple[str, int]) -> tuple[str, int]:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a: tuple[str, int], b: tuple[str, int]) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    def intersects(first: Any, second: Any) -> bool:
        return not (kdb.Region(first) & kdb.Region(second)).is_empty()

    for via_name, (lower, upper) in via_pairs.items():
        if lower not in metal_polygons or upper not in metal_polygons:
            continue
        for via in polygons(via_name):
            lower_hits = [index for index, polygon in enumerate(metal_polygons[lower]) if intersects(via, polygon)]
            upper_hits = [index for index, polygon in enumerate(metal_polygons[upper]) if intersects(via, polygon)]
            for lower_index in lower_hits:
                for upper_index in upper_hits:
                    union((lower, lower_index), (upper, upper_index))

    roots = sorted({find(key) for key in keys})
    net_name = {root: f"N{index + 1}" for index, root in enumerate(roots)}
    elements = []
    unresolved = []
    if "JJ" in process.layers and "M1" in metal_polygons and "M2" in metal_polygons:
        dbu = layout.dbu
        for index, barrier in enumerate(polygons("JJ")):
            lower_hits = [item for item, polygon in enumerate(metal_polygons["M1"]) if intersects(barrier, polygon)]
            upper_hits = [item for item, polygon in enumerate(metal_polygons["M2"]) if intersects(barrier, polygon)]
            if not lower_hits or not upper_hits:
                unresolved.append({"junction": index + 1, "reason": "barrier does not overlap both M1 and M2"})
                continue
            area_um2 = float(barrier.area()) * dbu * dbu
            elements.append(
                {
                    "name": f"BJJ{index + 1}",
                    "kind": "josephson_junction",
                    "nodes": [net_name[find(("M1", lower_hits[0]))], net_name[find(("M2", upper_hits[0]))]],
                    "parameters": {"area_um2": area_um2},
                }
            )
    nets = []
    for root in roots:
        members = [list(key) for key in keys if find(key) == root]
        nets.append({"name": net_name[root], "members": members})
    return {
        "schema": "text-to-gds.extracted-circuit.v1",
        "source_gds": str(gds_path),
        "nodes": [net["name"] for net in nets],
        "ports": [],
        "nets": nets,
        "elements": elements,
        "unresolved_devices": unresolved,
        "extraction_basis": "klayout_polygon_connectivity_vias_and_junction_overlap",
        "polygon_connectivity_complete": not unresolved,
    }


def _parse_spice(text: str) -> dict[str, Any]:
    elements = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("*", ".")):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        prefix = parts[0][0].upper()
        kind = {
            "R": "resistor",
            "L": "inductor",
            "C": "capacitor",
            "B": "josephson_junction",
            "J": "josephson_junction",
            "T": "transmission_line",
            "X": "subcircuit",
        }.get(prefix, "unknown")
        elements.append({"name": parts[0], "kind": kind, "nodes": parts[1:3]})
    return {"elements": elements}


def run_superconducting_lvs(
    extracted: dict[str, Any], schematic: dict[str, Any] | str | Path
) -> dict[str, Any]:
    """Compare extracted and schematic circuit topology by device kind and nets."""
    if isinstance(schematic, (str, Path)):
        path = Path(schematic)
        text = path.read_text(encoding="utf-8")
        schematic_data = json.loads(text) if path.suffix.lower() == ".json" else _parse_spice(text)
    else:
        schematic_data = schematic
    layout_elements = extracted.get("elements", [])
    schematic_elements = schematic_data.get("elements", [])

    def signature(element: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
        return str(element.get("kind", "unknown")), tuple(sorted(map(str, element.get("nodes", []))))

    layout_signatures = sorted(signature(element) for element in layout_elements)
    schematic_signatures = sorted(signature(element) for element in schematic_elements)
    missing = list(schematic_signatures)
    extra = []
    for item in layout_signatures:
        if item in missing:
            missing.remove(item)
        else:
            extra.append(item)
    return {
        "schema": "text-to-gds.lvs.v1",
        "passed": not missing and not extra,
        "layout_element_count": len(layout_elements),
        "schematic_element_count": len(schematic_elements),
        "missing_from_layout": [{"kind": kind, "nodes": list(nodes)} for kind, nodes in missing],
        "extra_in_layout": [{"kind": kind, "nodes": list(nodes)} for kind, nodes in extra],
        "comparison": "device_kind_and_undirected_net_topology",
    }


def generate_spice_netlist(circuit: dict[str, Any], *, subcircuit_name: str = "DEVICE") -> str:
    """Generate a portable SPICE/JoSIM starter netlist from an extracted graph."""
    ports = circuit.get("ports", []) or [node for node in circuit.get("nodes", []) if node != "0"]
    lines = ["* Generated from GDS semantic extraction", f".SUBCKT {subcircuit_name} {' '.join(ports)}"]
    for element in circuit.get("elements", []):
        name = str(element["name"])
        nodes = list(map(str, element.get("nodes", ["device", "0"])))[:2]
        params = element.get("parameters", {})
        kind = element.get("kind")
        if kind == "josephson_junction":
            area = float(params.get("area_um2", 0.05))
            lines.append(f"{name} {' '.join(nodes)} jjmod area={area:.12g}")
        elif kind == "transmission_line":
            z0 = float(params.get("impedance_ohm", 50.0))
            delay_ps = float(params.get("length_um", 100.0)) / 1.2e8 * 1e6
            lines.append(f"{name} {' '.join(nodes)} 0 0 Z0={z0:.12g} TD={delay_ps:.12g}p")
        elif kind == "resistor":
            lines.append(f"R{name.lstrip('R')} {' '.join(nodes)} {params.get('resistance_ohm', 50.0)}")
        elif kind == "inductor":
            lines.append(f"L{name.lstrip('L')} {' '.join(nodes)} {params.get('inductance_h', 1e-9)}")
        elif kind == "capacitor":
            lines.append(f"C{name.lstrip('C')} {' '.join(nodes)} {params.get('capacitance_f', 1e-12)}")
        else:
            lines.append(f"R{name.lstrip('X')} {' '.join(nodes)} 1e12")
    if any(element.get("kind") == "josephson_junction" for element in circuit.get("elements", [])):
        lines.append(".MODEL jjmod JJ(RTYPE=1 VG=2.8mV CAP=50fF RN=10)")
    lines.extend([f".ENDS {subcircuit_name}", ""])
    return "\n".join(lines)


def generate_josephsoncircuits_model(circuit: dict[str, Any]) -> str:
    """Generate executable Julia source describing the extracted circuit graph."""
    payload = json.dumps(_canonical(circuit), separators=(",", ":"))
    return f'''# Generated from text-to-gds extracted circuit
using JosephsonCircuits
using JSON3

circuit = JSON3.read(raw"""{payload}""")
println(JSON3.write(Dict(
    "schema" => "text-to-gds.josephsoncircuits-model.v1",
    "element_count" => length(circuit.elements),
    "status" => "model_loaded"
)))
'''


def design_fingerprint(design: dict[str, Any]) -> str:
    encoded = json.dumps(_canonical(design), separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {prefix: value}
    output: dict[str, Any] = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        output.update(_flatten(item, path))
    return output


def design_version_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Return parameter, performance, and structural metadata changes."""
    a, b = _flatten(before), _flatten(after)
    changed = {
        key: {"before": a.get(key), "after": b.get(key)}
        for key in sorted(set(a) | set(b))
        if a.get(key) != b.get(key)
    }
    return {
        "schema": "text-to-gds.design-diff.v1",
        "before": design_fingerprint(before),
        "after": design_fingerprint(after),
        "parameter_diff": {key: value for key, value in changed.items() if "performance" not in key},
        "performance_diff": {key: value for key, value in changed.items() if "performance" in key},
        "change_count": len(changed),
    }


def initialize_device_version_store(path: str | Path) -> Path:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS device_versions (
               commit_hash TEXT PRIMARY KEY, device_id TEXT NOT NULL,
               parent_hash TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
               message TEXT NOT NULL, design_json TEXT NOT NULL,
               gds_path TEXT, gds_hash TEXT)"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_device_versions_device ON device_versions(device_id, created_at)"
        )
    return database


def commit_device_version(
    path: str | Path,
    *,
    device_id: str,
    design: dict[str, Any],
    message: str,
    gds_path: str | Path | None = None,
    parent_hash: str | None = None,
) -> dict[str, Any]:
    database = initialize_device_version_store(path)
    design_json = json.dumps(_canonical(design), sort_keys=True, separators=(",", ":"))
    gds_hash = hashlib.sha256(Path(gds_path).read_bytes()).hexdigest() if gds_path else None
    content = json.dumps(
        {
            "device_id": device_id,
            "parent": parent_hash,
            "message": message,
            "design": json.loads(design_json),
            "gds_hash": gds_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    commit_hash = hashlib.sha256(content.encode()).hexdigest()
    with sqlite3.connect(database) as connection:
        if parent_hash is not None:
            parent = connection.execute(
                "SELECT device_id FROM device_versions WHERE commit_hash=?", (parent_hash,)
            ).fetchone()
            if parent is None or parent[0] != device_id:
                raise ValueError("Parent commit does not exist for this device")
        connection.execute(
            "INSERT OR IGNORE INTO device_versions VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)",
            (commit_hash, device_id, parent_hash, message, design_json, str(gds_path) if gds_path else None, gds_hash),
        )
    return {"commit_hash": commit_hash, "device_id": device_id, "parent_hash": parent_hash, "gds_hash": gds_hash, "database_path": str(database)}


def device_version_history(path: str | Path, device_id: str) -> list[dict[str, Any]]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            """SELECT commit_hash, parent_hash, created_at, message, design_json, gds_path, gds_hash
               FROM device_versions WHERE device_id=? ORDER BY created_at, rowid""",
            (device_id,),
        ).fetchall()
    return [{"commit_hash": row[0], "parent_hash": row[1], "created_at": row[2], "message": row[3], "design": json.loads(row[4]), "gds_path": row[5], "gds_hash": row[6]} for row in rows]


def chip_version_diff(
    before_design: dict[str, Any],
    after_design: dict[str, Any],
    *,
    before_gds: str | Path | None = None,
    after_gds: str | Path | None = None,
) -> dict[str, Any]:
    result = design_version_diff(before_design, after_design)
    result["geometry_diff"] = gds_visual_diff(before_gds, after_gds) if before_gds is not None and after_gds is not None else {"status": "not_provided"}
    result["schema"] = "text-to-gds.chip-version-diff.v1"
    return result


def gds_visual_diff(before_path: str | Path, after_path: str | Path) -> dict[str, Any]:
    """Compute exact per-layer XOR area between two GDS files using KLayout regions."""
    import klayout.db as kdb

    layouts = []
    for path in (before_path, after_path):
        layout = kdb.Layout()
        layout.read(str(path))
        layouts.append(layout)
    layer_keys = set()
    for layout in layouts:
        layer_keys.update((layout.get_info(index).layer, layout.get_info(index).datatype) for index in layout.layer_indices())
    per_layer = []
    total = 0.0
    for layer, datatype in sorted(layer_keys):
        regions = []
        for layout in layouts:
            index = layout.find_layer(layer, datatype)
            region = kdb.Region()
            if index is not None:
                for cell in layout.top_cells():
                    region.insert(cell.begin_shapes_rec(index))
            regions.append(region)
        xor = regions[0] ^ regions[1]
        dbu = layouts[0].dbu
        area = float(xor.area()) * dbu * dbu
        if area > 0.0:
            per_layer.append({"layer": [layer, datatype], "xor_area_um2": area})
            total += area
    return {
        "schema": "text-to-gds.gds-visual-diff.v1",
        "identical": total == 0.0,
        "xor_area_um2": total,
        "changed_layers": per_layer,
    }


def generate_wafer_mask(
    chip_gds: str | Path,
    output_gds: str | Path,
    *,
    wafer_diameter_mm: float = 50.8,
    chip_width_mm: float = 5.0,
    chip_height_mm: float = 5.0,
    dicing_lane_um: float = 100.0,
    edge_exclusion_mm: float = 2.0,
) -> dict[str, Any]:
    """Place complete chips inside a circular wafer and add lanes/alignment marks."""
    import klayout.db as kdb

    if min(wafer_diameter_mm, chip_width_mm, chip_height_mm) <= 0.0:
        raise ValueError("Wafer and chip dimensions must be positive")
    source = kdb.Layout()
    source.read(str(chip_gds))
    layout = kdb.Layout()
    layout.dbu = source.dbu
    chip_cell = layout.create_cell("CHIP")
    for source_top in source.top_cells():
        chip_cell.copy_tree(source_top)
    wafer = layout.create_cell("WAFER")
    lane_layer = layout.layer(100, 0)
    mark_layer = layout.layer(101, 0)
    radius_um = wafer_diameter_mm * 500.0 - edge_exclusion_mm * 1000.0
    pitch_x = chip_width_mm * 1000.0 + dicing_lane_um
    pitch_y = chip_height_mm * 1000.0 + dicing_lane_um
    nx, ny = int(radius_um // pitch_x), int(radius_um // pitch_y)
    placements = []
    dbu = layout.dbu
    for ix in range(-nx, nx + 1):
        for iy in range(-ny, ny + 1):
            x, y = ix * pitch_x, iy * pitch_y
            corner_radius = math.hypot(abs(x) + chip_width_mm * 500.0, abs(y) + chip_height_mm * 500.0)
            if corner_radius > radius_um:
                continue
            wafer.insert(kdb.CellInstArray(chip_cell.cell_index(), kdb.Trans(int(round(x / dbu)), int(round(y / dbu)))))
            placements.append({"row": iy, "column": ix, "center_um": [x, y]})
            half_w, half_h = chip_width_mm * 500.0, chip_height_mm * 500.0
            lane = dicing_lane_um / 2.0
            wafer.shapes(lane_layer).insert(kdb.DBox(x - half_w - lane, y - half_h, x - half_w + lane, y + half_h))
            wafer.shapes(lane_layer).insert(kdb.DBox(x - half_w, y - half_h - lane, x + half_w, y - half_h + lane))
    mark_size = 500.0
    for angle in range(0, 360, 90):
        x = 0.75 * radius_um * math.cos(math.radians(angle))
        y = 0.75 * radius_um * math.sin(math.radians(angle))
        wafer.shapes(mark_layer).insert(kdb.DBox(x - mark_size, y - 25, x + mark_size, y + 25))
        wafer.shapes(mark_layer).insert(kdb.DBox(x - 25, y - mark_size, x + 25, y + mark_size))
    output = Path(output_gds)
    output.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(output))
    return {
        "schema": "text-to-gds.wafer-mask.v1",
        "gds_path": str(output),
        "wafer_diameter_mm": wafer_diameter_mm,
        "chip_count": len(placements),
        "placements": placements,
        "dicing_lane_um": dicing_lane_um,
        "alignment_mark_count": 4,
    }
