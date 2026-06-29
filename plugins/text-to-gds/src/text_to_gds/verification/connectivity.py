"""GDS-derived physical connectivity extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import klayout.db as kdb

from text_to_gds.geometry.polygon import layer_regions
from text_to_gds.pdk.layers import PHYSICAL_LAYERS, layer_name


CONDUCTIVE = {"M1", "M2", "M3", "VIA12", "VIA23"}
VIA_CONNECTIONS = {"VIA12": ("M1", "M2"), "VIA23": ("M2", "M3")}


def _polygons(region: kdb.Region) -> list[kdb.Polygon]:
    return list(region.each())


def _intersects(a: kdb.Polygon, b: kdb.Polygon) -> bool:
    return not (kdb.Region(a) & kdb.Region(b)).is_empty()


def extract_connectivity(path: str | Path) -> dict[str, Any]:
    regions = layer_regions(path)
    conductive_regions = {
        layer_name(layer): item.region.merged()
        for layer, item in regions.items()
        if layer_name(layer) in CONDUCTIVE
    }
    nodes: list[dict[str, Any]] = []
    polygons: dict[str, list[kdb.Polygon]] = {}
    for name, region in sorted(conductive_regions.items()):
        parts: list[kdb.Polygon] = []
        for index, poly in enumerate(region.each_merged()):
            node_id = f"{name}:{index}"
            box = poly.bbox()
            parts.append(poly)
            nodes.append(
                {
                    "id": node_id,
                    "layer": name,
                    "bbox": [box.left, box.bottom, box.right, box.top],
                    "area_database_units": float(poly.area()),
                }
            )
        polygons[name] = parts

    edges: list[dict[str, Any]] = []
    for via_name, connected_layers in VIA_CONNECTIONS.items():
        for via_index, via_poly in enumerate(polygons.get(via_name, [])):
            via_id = f"{via_name}:{via_index}"
            for metal in connected_layers:
                for metal_index, metal_poly in enumerate(polygons.get(metal, [])):
                    if _intersects(via_poly, metal_poly):
                        edges.append(
                            {
                                "source": via_id,
                                "target": f"{metal}:{metal_index}",
                                "kind": "via",
                                "via_layer": via_name,
                            }
                        )

    jj_region = regions.get(PHYSICAL_LAYERS["JJ"].layer)
    if jj_region:
        for jj_index, jj_poly in enumerate(_polygons(jj_region.region)):
            jj_box = jj_poly.bbox()
            touched = []
            for metal in ("M1", "M2", "M3"):
                for metal_index, metal_poly in enumerate(polygons.get(metal, [])):
                    if _intersects(jj_poly, metal_poly):
                        touched.append(f"{metal}:{metal_index}")
            for target in touched:
                edges.append({"source": f"JJ:{jj_index}", "target": target, "kind": "jj_overlap"})
            nodes.append(
                {
                    "id": f"JJ:{jj_index}",
                    "layer": "JJ",
                    "bbox": [jj_box.left, jj_box.bottom, jj_box.right, jj_box.top],
                    "area_database_units": float(jj_box.area()),
                }
            )

    port_region = regions.get(PHYSICAL_LAYERS["PORT"].layer)
    if port_region:
        for port_index, port_poly in enumerate(_polygons(port_region.region)):
            port_box = port_poly.bbox()
            port_id = f"PORT:{port_index}"
            nodes.append(
                {
                    "id": port_id,
                    "layer": "PORT",
                    "bbox": [port_box.left, port_box.bottom, port_box.right, port_box.top],
                    "area_database_units": float(port_box.area()),
                }
            )
            for metal in ("M1", "M2", "M3"):
                for metal_index, metal_poly in enumerate(polygons.get(metal, [])):
                    if _intersects(port_poly, metal_poly):
                        edges.append(
                            {
                                "source": port_id,
                                "target": f"{metal}:{metal_index}",
                                "kind": "port_marker",
                            }
                        )

    floating = [
        node["id"]
        for node in nodes
        if node["layer"] in {"M1", "M2", "M3"} and not any(node["id"] in (e["source"], e["target"]) for e in edges)
    ]
    topology = _device_topology(nodes, edges)
    status = "passed"
    if topology["shorted_junctions"]:
        status = "failed"
    elif floating:
        status = "warning"
    return {
        "schema": "text-to-gds.connectivity.v1",
        "gds_path": str(path),
        "nodes": nodes,
        "edges": edges,
        "floating_nodes": floating,
        "device_topology": topology,
        "status": status,
    }


def _device_topology(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    """Recognise junctions, SQUID loops, and shorts from the geometric graph.

    A Josephson junction is a JJ-layer polygon that overlaps two *distinct*
    merged metal islands (M-AlOx-M overlap). A junction that overlaps only one
    island is shorted (its two electrodes are the same conductor). A SQUID loop
    is two or more junctions bridging the *same* unordered pair of islands.
    """
    jj_ids = [node["id"] for node in nodes if node["layer"] == "JJ"]
    junctions: list[dict[str, Any]] = []
    for jj_id in jj_ids:
        islands = sorted(
            {
                edge["target"]
                for edge in edges
                if edge["kind"] == "jj_overlap" and edge["source"] == jj_id and edge["target"].split(":")[0] in {"M1", "M2", "M3"}
            }
        )
        junctions.append({"id": jj_id, "islands": islands, "is_junction": len(islands) >= 2})

    proper = [j for j in junctions if j["is_junction"]]
    shorted = [j["id"] for j in junctions if not j["is_junction"]]

    pair_to_jjs: dict[tuple[str, ...], list[str]] = {}
    for junction in proper:
        key = tuple(junction["islands"][:2])
        pair_to_jjs.setdefault(key, []).append(junction["id"])
    squids = [
        {"islands": list(pair), "junction_ids": sorted(jjs)}
        for pair, jjs in sorted(pair_to_jjs.items())
        if len(jjs) >= 2
    ]
    return {
        "junctions": junctions,
        "junction_count": len(proper),
        "squids": squids,
        "squid_count": len(squids),
        "shorted_junctions": shorted,
    }
