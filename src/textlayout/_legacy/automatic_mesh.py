"""Automatic solver input generation from physics_graph.json."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any


def _load_graph(graph: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(graph, dict):
        return graph
    return json.loads(Path(graph).read_text(encoding="utf-8"))


def _mesh_rules(graph: dict[str, Any]) -> list[dict[str, Any]]:
    rules = []
    for node in graph.get("nodes", []):
        ntype = node.get("type")
        if ntype == "josephson_junction":
            rules.append({"target": node["id"], "region": "JJ", "mesh_size_um": 0.02, "priority": "finest"})
        elif ntype == "transmission_line":
            gap = node.get("physics_parameters", {}).get("gap", {}).get("value")
            rules.append(
                {
                    "target": node["id"],
                    "region": "CPW gap",
                    "mesh_size_um": max(float(gap or 1.0) / 8.0, 0.05),
                    "priority": "high",
                }
            )
        elif ntype == "ground":
            rules.append({"target": node["id"], "region": "ground plane", "mesh_size_um": 10.0, "priority": "coarse"})
    return rules


def _write_openems(graph: dict[str, Any], out_dir: Path, rules: list[dict[str, Any]]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    geometry = out_dir / "geometry.xml"
    mesh = out_dir / "mesh.xml"
    ports = out_dir / "ports.xml"
    geometry_lines = ["<geometry source=\"physics_graph.json\">"]
    for node in graph.get("nodes", []):
        geom = node.get("geometry", {})
        geometry_lines.append(
            f"  <node id=\"{node['id']}\" type=\"{node['type']}\" "
            f"layer=\"{geom.get('layer_name', '')}\" bbox_um=\"{geom.get('bbox_um', '')}\"/>"
        )
    geometry_lines.append("</geometry>")
    geometry.write_text("\n".join(geometry_lines) + "\n", encoding="utf-8")

    mesh_lines = ["<mesh>"]
    for rule in rules:
        mesh_lines.append(
            f"  <refinement target=\"{rule['target']}\" region=\"{rule['region']}\" "
            f"size_um=\"{rule['mesh_size_um']}\" priority=\"{rule['priority']}\"/>"
        )
    mesh_lines.append("</mesh>")
    mesh.write_text("\n".join(mesh_lines) + "\n", encoding="utf-8")

    port_lines = ["<ports>"]
    for node in graph.get("nodes", []):
        if node.get("type") == "port":
            port_lines.append(
                f"  <port name=\"{node['name']}\" impedance_ohm=\"50\" "
                f"center_um=\"{node.get('geometry', {}).get('center_um', '')}\"/>"
            )
    port_lines.append("</ports>")
    ports.write_text("\n".join(port_lines) + "\n", encoding="utf-8")
    return {"geometry_xml": str(geometry), "mesh_xml": str(mesh), "ports_xml": str(ports)}


def _write_elmer(graph: dict[str, Any], out_dir: Path, rules: list[dict[str, Any]]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    geo = out_dir / "model.geo"
    msh = out_dir / "model.msh"
    sif = out_dir / "model.sif"
    geo.write_text(
        textwrap.dedent(
            """\
            // Text-to-GDS generated Elmer/Gmsh geometry stub from physics_graph.json.
            SetFactory("OpenCASCADE");
            Box(1) = {-250, -250, -30, 500, 500, 30};
            Physical Volume("substrate") = {1};
            """
        ),
        encoding="utf-8",
    )
    msh.write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n", encoding="utf-8")
    sif.write_text(
        "\n".join(
            [
                "Header",
                "  CHECK KEYWORDS Warn",
                "End",
                "Simulation",
                "  Coordinate System = Cartesian 3D",
                "  Simulation Type = Steady state",
                "End",
                "! Mesh rules: " + json.dumps(rules),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"geo": str(geo), "msh": str(msh), "sif": str(sif)}


def _write_palace(graph: dict[str, Any], out_dir: Path, rules: list[dict[str, Any]]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    config = out_dir / "palace.json"
    config.write_text(
        json.dumps(
            {
                "Problem": {"Type": "Driven", "Verbose": 2, "Output": "postpro"},
                "Model": {"Mesh": "model.msh", "L0": 1e-6},
                "Domains": {
                    "Materials": [
                        {"Attributes": [1], "Permittivity": 11.45, "LossTan": 1e-6},
                        {"Attributes": [2], "Permittivity": 1.0, "LossTan": 0.0},
                    ]
                },
                "Solver": {"Order": 2, "Device": "CPU", "Driven": {"MinFreq": 1.0, "MaxFreq": 12.0, "FreqStep": 0.01}},
                "Metadata": {"source_graph": graph.get("source_gds"), "mesh_rules": rules},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"config_json": str(config)}


def generate_solver_inputs_from_graph(
    graph: dict[str, Any] | str | Path,
    *,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Generate openEMS, Elmer, and Palace project inputs from physics graph."""
    graph_data = _load_graph(graph)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rules = _mesh_rules(graph_data)
    result = {
        "schema": "text-to-gds.automatic-mesh.v1",
        "status": "prepared",
        "source_graph_schema": graph_data.get("schema"),
        "mesh_refinement_rules": rules,
        "openems": _write_openems(graph_data, out / "openems", rules),
        "elmer": _write_elmer(graph_data, out / "elmer", rules),
        "palace": _write_palace(graph_data, out / "palace", rules),
        "model_validity": (
            "Generated solver inputs only. Any EM result still requires executing the "
            "solver and satisfying the solver execution contract."
        ),
    }
    report = out / "solver_inputs.json"
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report)
    return result
