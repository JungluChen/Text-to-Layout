"""Physics graph intermediate representation extracted from layout artifacts.

The graph is the compiler IR between geometry extraction and circuit/solver
generation.  It is intentionally stricter than the older netlist graph: nodes
are physical devices or electromagnetic regions, edges are physical relations,
and every derived parameter carries a source and confidence.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from textlayout._legacy.cpw_physics import synthesize_cpw
from textlayout._legacy.extraction import PHI0_WEBER, PLANCK_J_S, _junction_overlap_area_um2, layer_bounding_boxes_from_gds
from textlayout._legacy.process import DEFAULT_PROCESS

NODE_TYPES = {
    "conductor",
    "capacitor",
    "inductor",
    "josephson_junction",
    "transmission_line",
    "port",
    "ground",
}

EDGE_TYPES = {
    "electrical_connection",
    "capacitive_coupling",
    "mutual_inductance",
    "microwave_port",
}


def _load_sidecar(sidecar: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if sidecar is None:
        return {}
    if isinstance(sidecar, dict):
        return sidecar
    return json.loads(Path(sidecar).read_text(encoding="utf-8"))


def _q(
    value: float,
    unit: str,
    *,
    formula: str,
    source: str,
    confidence: float,
    method_label: str = "extracted",
) -> dict[str, Any]:
    return {
        "value": float(value),
        "unit": unit,
        "formula": formula,
        "method": formula,
        "source": source,
        "confidence": float(confidence),
        "method_label": method_label,
    }


def _attach_file_path_to_parameters(graph: dict[str, Any], file_path: str) -> None:
    for node in graph.get("nodes", []):
        params = node.get("physics_parameters")
        if not isinstance(params, dict):
            continue
        for record in params.values():
            if isinstance(record, dict) and "value" in record:
                record.setdefault("file_path", file_path)
    for device in graph.get("devices", []):
        params = device.get("physics_parameters")
        if not isinstance(params, dict):
            continue
        for record in params.values():
            if isinstance(record, dict) and "value" in record:
                record.setdefault("file_path", file_path)


def _node(
    node_id: str,
    node_type: str,
    *,
    name: str,
    geometry: dict[str, Any] | None = None,
    physics_parameters: dict[str, Any] | None = None,
    confidence: float = 1.0,
) -> dict[str, Any]:
    if node_type not in NODE_TYPES:
        raise ValueError(f"Unsupported physics graph node type: {node_type}")
    return {
        "id": node_id,
        "name": name,
        "type": node_type,
        "geometry": geometry or {},
        "physics_parameters": physics_parameters or {},
        "confidence": float(confidence),
    }


def _edge(source: str, target: str, edge_type: str, **metadata: Any) -> dict[str, Any]:
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"Unsupported physics graph edge type: {edge_type}")
    return {
        "source": source,
        "target": target,
        "type": edge_type,
        "metadata": metadata,
    }


def _largest_box(boxes: list[dict[str, Any]], layer_name: str) -> dict[str, Any] | None:
    candidates = [box for box in boxes if box.get("layer_name") == layer_name]
    if not candidates:
        return None
    return max(candidates, key=lambda box: float(box.get("area_um2", 0.0)))


def _smallest_box(boxes: list[dict[str, Any]], layer_name: str) -> dict[str, Any] | None:
    candidates = [box for box in boxes if box.get("layer_name") == layer_name]
    if not candidates:
        return None
    return min(candidates, key=lambda box: float(box.get("area_um2", 0.0)))


def _boxes_connected(a: dict[str, Any], b: dict[str, Any], *, tolerance_um: float = 0.05) -> bool:
    ax0, ay0, ax1, ay1 = [float(v) for v in a["bbox_um"]]
    bx0, by0, bx1, by1 = [float(v) for v in b["bbox_um"]]
    return (
        ax0 <= bx1 + tolerance_um
        and ax1 + tolerance_um >= bx0
        and ay0 <= by1 + tolerance_um
        and ay1 + tolerance_um >= by0
    )


def _geometry_from_box(box: dict[str, Any]) -> dict[str, Any]:
    return {
        "layer": box.get("layer"),
        "layer_name": box.get("layer_name"),
        "material": box.get("material"),
        "bbox_um": box.get("bbox_um"),
        "width_um": box.get("width_um"),
        "height_um": box.get("height_um"),
        "area_um2": box.get("area_um2"),
    }


def _jj_parameters(
    area_um2: float,
    *,
    jc_ua_per_um2: float | None,
    specific_capacitance_ff_per_um2: float | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "area": _q(
            area_um2,
            "um^2",
            formula="area(JJ layout region)",
            source="GDS JJ layer",
            confidence=1.0,
        )
    }
    if jc_ua_per_um2 is not None:
        ic_a = area_um2 * float(jc_ua_per_um2) * 1e-6
        lj_h = PHI0_WEBER / (2.0 * math.pi * ic_a)
        ej_j = PHI0_WEBER * ic_a / (2.0 * math.pi)
        params.update(
            {
                "critical_current": _q(
                    ic_a,
                    "A",
                    formula="Ic = Jc * area",
                    source="GDS JJ area + process Jc",
                    confidence=0.98,
                    method_label="estimated",
                ),
                "josephson_inductance": _q(
                    lj_h,
                    "H",
                    formula="Lj = Phi0/(2*pi*Ic)",
                    source="GDS JJ area + process Jc",
                    confidence=0.98,
                    method_label="estimated",
                ),
                "josephson_energy": _q(
                    ej_j / PLANCK_J_S,
                    "Hz",
                    formula="Ej/h = Phi0*Ic/(2*pi*h)",
                    source="GDS JJ area + process Jc",
                    confidence=0.98,
                    method_label="estimated",
                ),
            }
        )
    if specific_capacitance_ff_per_um2 is not None:
        params["junction_capacitance"] = _q(
            area_um2 * float(specific_capacitance_ff_per_um2) * 1e-15,
            "F",
            formula="Cj = Cs * area",
            source="GDS JJ area + process specific capacitance",
            confidence=0.85,
            method_label="estimated",
        )
    return params


def _cpw_parameters(info: dict[str, Any]) -> dict[str, Any]:
    width = info.get("cpw_trace_width_um") or info.get("trace_width_um")
    gap = info.get("cpw_gap_um") or info.get("gap_um")
    length = info.get("cpw_length_um") or info.get("length_um") or info.get("electrical_length_um")
    if width is None or gap is None or length is None:
        return {}
    # Prefer precomputed values from the PCell sidecar. The PCell uses
    # cpw_conformal_mapping which treats effective_permittivity as ε_eff directly
    # (Z0 = 30π/√ε_eff × K'/K). synthesize_cpw treats its epsilon_r argument as
    # the substrate dielectric constant and applies (ε_r+1)/2 internally — so
    # passing ε_eff=6.2 to it as epsilon_r would yield ε_eff=(6.2+1)/2=3.6 (wrong).
    if info.get("z0_ohm") is not None and info.get("phase_velocity_m_per_s") is not None:
        z0 = float(info["z0_ohm"])
        vp = float(info["phase_velocity_m_per_s"])
        eps_eff = float(info.get("effective_permittivity", (299_792_458.0 / vp) ** 2))
        z0_source = "layout sidecar (PCell conformal mapping)"
        eps_src = "layout sidecar (CPW ε_eff)"
        confidence_z0 = 0.92
    else:
        eps = float(info.get("effective_permittivity", 6.2))
        cpw = synthesize_cpw(
            center_width_um=float(width),
            gap_um=float(gap),
            ground_width_um=float(info.get("ground_width_um", 500.0)),
            epsilon_r=eps,
            substrate_thickness_um=float(info.get("substrate_thickness_um", 254.0)),
            frequency_ghz=float(info.get("center_frequency_ghz", info.get("target_frequency_ghz", 6.0))),
            target_impedance_ohm=float(info.get("target_impedance_ohm", 50.0)),
            impedance_tolerance_ohm=float(info.get("impedance_tolerance_ohm", 50.0)),
        )
        z0 = float(cpw["impedance_ohm"])
        vp = float(cpw["phase_velocity_m_per_s"])
        eps_eff = float(cpw["effective_permittivity"])
        z0_source = "extracted width/gap + process"
        eps_src = "finite substrate CPW model"
        confidence_z0 = 0.86
    return {
        "width": _q(float(width), "um", formula="sidecar CPW trace width", source="layout sidecar", confidence=0.95),
        "gap": _q(float(gap), "um", formula="sidecar CPW gap", source="layout sidecar", confidence=0.95),
        "length": _q(float(length), "um", formula="sidecar CPW path length", source="layout sidecar", confidence=0.85),
        "z0": _q(z0, "ohm", formula="Z0 = sqrt(L'/C')", source=z0_source, confidence=confidence_z0, method_label="estimated"),
        "epsilon_eff": _q(eps_eff, "1", formula="epsilon_eff from PCell or finite-substrate model", source=eps_src, confidence=0.85, method_label="estimated"),
        "phase_velocity": _q(vp, "m/s", formula="vp = c/sqrt(epsilon_eff)", source="CPW model", confidence=0.86, method_label="estimated"),
        "capacitance_per_length": _q(1.0 / (z0 * vp), "F/m", formula="C' = 1/(Z0*vp)", source="CPW model", confidence=0.82, method_label="estimated"),
        "inductance_per_length": _q(z0 / vp, "H/m", formula="L' = Z0/vp", source="CPW model", confidence=0.82, method_label="estimated"),
    }


def _idc_parameters(info: dict[str, Any]) -> dict[str, Any]:
    fingers = info.get("finger_count") or info.get("idc_finger_count")
    length = info.get("finger_length_um") or info.get("idc_finger_length_um")
    gap = info.get("finger_gap_um") or info.get("idc_gap_um") or info.get("gap_um")
    if fingers is None or length is None or gap is None:
        return {}
    eps0 = 8.8541878128e-12
    eps_eff = float(info.get("effective_permittivity", 6.2))
    width_um = float(info.get("finger_width_um", max(float(gap), 1.0)))
    overlap_area_m2 = max(int(fingers) - 1, 1) * float(length) * width_um * 1e-12
    capacitance_f = eps0 * eps_eff * overlap_area_m2 / (float(gap) * 1e-6)
    return {
        "finger_count": _q(float(fingers), "count", formula="sidecar IDC finger count", source="layout sidecar", confidence=0.95),
        "finger_length": _q(float(length), "um", formula="sidecar IDC finger length", source="layout sidecar", confidence=0.95),
        "gap": _q(float(gap), "um", formula="sidecar IDC gap", source="layout sidecar", confidence=0.95),
        "capacitance": _q(capacitance_f, "F", formula="C = eps0*eps_eff*(N-1)*length*width/gap", source="extracted IDC geometry", confidence=0.7, method_label="estimated"),
    }


def extract_physics_graph(
    gds_path: str | Path,
    sidecar: dict[str, Any] | str | Path | None = None,
    *,
    jc_ua_per_um2: float | None = None,
    specific_capacitance_ff_per_um2: float | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Extract ``physics_graph.json`` from GDS polygons, layer stack, and ports."""
    gds = Path(gds_path)
    sidecar_data = _load_sidecar(sidecar)
    info = sidecar_data.get("info") if isinstance(sidecar_data.get("info"), dict) else {}
    boxes = layer_bounding_boxes_from_gds(gds)
    ports = sidecar_data.get("ports") if isinstance(sidecar_data.get("ports"), list) else []

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    devices: list[dict[str, Any]] = []

    for index, port in enumerate(ports):
        node_id = f"port:{port.get('name', index)}"
        nodes.append(
            _node(
                node_id,
                "port",
                name=str(port.get("name", f"port_{index}")),
                geometry={"center_um": port.get("center"), "width_um": port.get("width"), "layer": port.get("layer")},
            )
        )

    for layer_name in sorted({str(box["layer_name"]) for box in boxes}):
        layer_boxes = [box for box in boxes if box.get("layer_name") == layer_name]
        area = sum(float(box["area_um2"]) for box in layer_boxes)
        largest = _largest_box(layer_boxes, layer_name) or layer_boxes[0]
        node_type = "ground" if layer_name.upper() in {"M1", "GND", "GROUND"} else "conductor"
        nodes.append(
            _node(
                f"layer:{layer_name}",
                node_type,
                name=layer_name,
                geometry={**_geometry_from_box(largest), "total_area_um2": area, "shape_count": len(layer_boxes)},
                confidence=0.9,
            )
        )

    jj_box = _smallest_box(boxes, "JJ")
    if jj_box is not None:
        jj_overlap_area_um2 = _junction_overlap_area_um2(gds)
        params = _jj_parameters(
            float(jj_overlap_area_um2),
            jc_ua_per_um2=jc_ua_per_um2,
            specific_capacitance_ff_per_um2=specific_capacitance_ff_per_um2,
        )
        jj_geometry = _geometry_from_box(jj_box)
        jj_geometry["area_um2"] = jj_overlap_area_um2
        jj_geometry["area_source"] = "area(M1 intersect M2 within JJ process window)"
        jj_node = _node(
            "device:jj0",
            "josephson_junction",
            name="JJ0",
            geometry=jj_geometry,
            physics_parameters=params,
            confidence=0.98 if jc_ua_per_um2 is not None else 0.75,
        )
        nodes.append(jj_node)
        devices.append(jj_node)
        for layer_name in ("M1", "M2"):
            electrode = _smallest_box(boxes, layer_name)
            if electrode and _boxes_connected(jj_box, electrode, tolerance_um=0.2):
                edges.append(_edge(f"layer:{layer_name}", "device:jj0", "electrical_connection", recognition="JJ overlap"))

    cpw_params = _cpw_parameters(info)
    if cpw_params:
        signal = _largest_box(boxes, "M3") or _largest_box(boxes, "M2")
        cpw_node = _node(
            "device:cpw0",
            "transmission_line",
            name="CPW0",
            geometry=_geometry_from_box(signal) if signal else {"source": "sidecar"},
            physics_parameters=cpw_params,
            confidence=0.86,
        )
        nodes.append(cpw_node)
        devices.append(cpw_node)
        if "layer:M1" in {node["id"] for node in nodes}:
            edges.append(_edge("device:cpw0", "layer:M1", "capacitive_coupling", recognition="CPW gap to ground plane"))
        for port in ports:
            if str(port.get("name", "")).lower().startswith(("rf", "in", "out", "p")):
                edges.append(_edge(f"port:{port.get('name')}", "device:cpw0", "microwave_port", impedance_ohm=50.0))

    idc_params = _idc_parameters(info)
    if idc_params:
        cap_node = _node(
            "device:idc0",
            "capacitor",
            name="IDC0",
            geometry={"source": "sidecar IDC geometry"},
            physics_parameters=idc_params,
            confidence=0.78,
        )
        nodes.append(cap_node)
        devices.append(cap_node)

    if info.get("inductor_turns") or info.get("inductor_segment_length_um"):
        length = float(info.get("inductor_turns", 1)) * float(info.get("inductor_segment_length_um", 1.0))
        ind_node = _node(
            "device:inductor0",
            "inductor",
            name="L0",
            geometry={"length_um": length, "turns": info.get("inductor_turns")},
            physics_parameters={"length": _q(length, "um", formula="turns * segment_length", source="layout sidecar", confidence=0.8)},
            confidence=0.8,
        )
        nodes.append(ind_node)
        devices.append(ind_node)

    # Polygon connectivity pass for same/adjacent conductor layers.
    conductor_boxes = [box for box in boxes if str(box.get("layer_name", "")).startswith("M")]
    for left_index, left in enumerate(conductor_boxes):
        for right in conductor_boxes[left_index + 1 :]:
            if left.get("layer_name") != right.get("layer_name") and _boxes_connected(left, right):
                edges.append(
                    _edge(
                        f"layer:{left['layer_name']}",
                        f"layer:{right['layer_name']}",
                        "electrical_connection",
                        recognition="polygon connectivity",
                    )
                )

    graph = {
        "schema": "text-to-gds.physics-graph.v1",
        "status": "ok" if nodes else "failed",
        "source_gds": str(gds),
        "source_sidecar": str(sidecar) if isinstance(sidecar, (str, Path)) else None,
        "source_of_truth": "physics_graph.json",
        "node_types": sorted(NODE_TYPES),
        "edge_types": sorted(EDGE_TYPES),
        "nodes": nodes,
        "edges": edges,
        "devices": [
            {
                "name": device["name"],
                "type": device["type"],
                "geometry": device["geometry"],
                "physics_parameters": device["physics_parameters"],
                "confidence": device["confidence"],
            }
            for device in devices
        ],
        "extraction_methods": {
            "polygon_connectivity": True,
            "layer_stack": DEFAULT_PROCESS.to_dict(),
            "port_detection": bool(ports),
            "jj_overlap_recognition": jj_box is not None,
            "cpw_mode_detection": bool(cpw_params),
        },
        "warnings": [] if nodes else ["no physics nodes extracted from GDS"],
    }
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        _attach_file_path_to_parameters(graph, str(out))
        out.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        graph["result_path"] = str(out)
    else:
        _attach_file_path_to_parameters(graph, str(gds))
    return graph


def graph_to_josephsoncircuits_model(graph: dict[str, Any]) -> dict[str, Any]:
    """Build a circuit model list from physics graph device nodes."""
    circuit = []
    for device in graph.get("devices", []):
        dtype = device.get("type")
        params = device.get("physics_parameters", {})
        if dtype == "josephson_junction":
            circuit.append({"type": "Josephson junction", "name": device["name"], "parameters": params})
        elif dtype == "capacitor":
            circuit.append({"type": "capacitor", "name": device["name"], "parameters": params})
        elif dtype == "inductor":
            circuit.append({"type": "inductor", "name": device["name"], "parameters": params})
        elif dtype == "transmission_line":
            circuit.append({"type": "resonator", "name": device["name"], "parameters": params})
    for node in graph.get("nodes", []):
        if node.get("type") == "port":
            circuit.append({"type": "port", "name": node["name"], "parameters": node.get("geometry", {})})
    return {
        "schema": "text-to-gds.josephsoncircuits-model.v1",
        "source_graph_schema": graph.get("schema"),
        "circuit": circuit,
        "ready_for_solver": any(item["type"] == "Josephson junction" for item in circuit)
        and any(item["type"] in {"capacitor", "resonator"} for item in circuit),
    }
