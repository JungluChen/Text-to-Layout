"""Fabrication signoff reports derived from real GDS geometry.

Produces the standard tape-out signoff artifact set:
  * DRC report         (min metal width + spacing via KLayout edge checks, JJ size)
  * LVS report         (geometry-extracted connectivity + device topology)
  * floating-metal report
  * layer-connectivity report
  * PDK rule summary
  * KLayout layer-properties file (.lyp)

Nothing here invents a value; every number comes from the polygons or the PDK.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import klayout.db as kdb

from textlayout._legacy.geometry.polygon import layer_regions
from textlayout._legacy.pdk.layers import PHYSICAL_LAYERS, layer_name
from textlayout._legacy.pdk.rules import DEFAULT_FABRICATION_RULES
from textlayout._legacy.verification.connectivity import extract_connectivity

# KLayout display colours per layer (matches the renderer palette).
_LYP_COLORS = {
    "M1": "#3f7fd0",
    "M2": "#34a853",
    "M3": "#9a6ce0",
    "JJ": "#f0c84b",
    "VIA12": "#ff8a3d",
    "VIA23": "#ff5d3d",
    "MARKER": "#9aa4b2",
    "PORT": "#cccccc",
    "UNDERCUT": "#888888",
    "KEEPOUT": "#cc4444",
}


def _dbu(path: str | Path) -> float:
    layout = kdb.Layout()
    layout.read(str(path))
    return layout.dbu


def signoff_drc(path: str | Path) -> dict[str, Any]:
    """Real DRC: KLayout width/space edge checks in microns, JJ sizing, via enclosure."""
    rules = DEFAULT_FABRICATION_RULES
    dbu = _dbu(path)
    regions = layer_regions(path)
    by_name = {layer_name(layer): item for layer, item in regions.items()}
    violations: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    min_w = max(int(round(rules.minimum_metal_width_um / dbu)), 1)
    min_s = max(int(round(rules.minimum_spacing_um / dbu)), 1)
    for name in ("M1", "M2", "M3"):
        item = by_name.get(name)
        if item is None:
            continue
        region = item.region
        w_viol = region.width_check(min_w).count()
        s_viol = region.space_check(min_s).count()
        checks.append({"layer": name, "min_width_um": rules.minimum_metal_width_um,
                       "min_spacing_um": rules.minimum_spacing_um,
                       "width_violations": int(w_viol), "spacing_violations": int(s_viol)})
        if w_viol:
            violations.append({"layer": name, "rule": "min_metal_width",
                               "limit_um": rules.minimum_metal_width_um, "count": int(w_viol)})
        if s_viol:
            violations.append({"layer": name, "rule": "min_spacing",
                               "limit_um": rules.minimum_spacing_um, "count": int(s_viol)})

    jj_item = by_name.get("JJ")
    jj_count = 0
    if jj_item is not None:
        for poly in jj_item.region.each_merged():
            jj_count += 1
            box = poly.bbox()
            w_um = (box.right - box.left) * dbu
            h_um = (box.top - box.bottom) * dbu
            if w_um < rules.minimum_jj_size_um or h_um < rules.minimum_jj_size_um:
                violations.append({"layer": "JJ", "rule": "min_jj_size",
                                   "limit_um": rules.minimum_jj_size_um,
                                   "measured_um": [round(w_um, 4), round(h_um, 4)]})
    checks.append({"layer": "JJ", "junction_count": jj_count, "min_size_um": rules.minimum_jj_size_um})

    # --- Via enclosure check: each VIA12/VIA23 polygon must be fully enclosed
    #     by the overlapping metal with at least via_enclosure_um clearance ---
    via_enc_dbu = max(int(round(rules.via_enclosure_um / dbu)), 1)
    for via_name, (metal_bot, metal_top) in [("VIA12", ("M1", "M2")), ("VIA23", ("M2", "M3"))]:
        via_item = by_name.get(via_name)
        if via_item is None:
            continue
        metal_bot_item = by_name.get(metal_bot)
        metal_top_item = by_name.get(metal_top)
        via_count = 0
        enclosure_violations = 0
        for via_poly in via_item.region.each_merged():
            via_count += 1
            box = via_poly.bbox()
            # Check enclosure: the via bounding box expanded by via_enclosure_um
            # must be fully contained within the metal region on both sides.
            # Use bbox corner points as a practical enclosure check.
            expanded_left = box.left - via_enc_dbu
            expanded_right = box.right + via_enc_dbu
            expanded_bottom = box.bottom - via_enc_dbu
            expanded_top = box.top + via_enc_dbu
            # A simple enclosure test: the via center and all 4 corners of the
            # expanded box must lie inside the metal region.
            test_points = [
                kdb.Point((box.left + box.right) // 2, (box.bottom + box.top) // 2),
                kdb.Point(expanded_left, expanded_bottom),
                kdb.Point(expanded_right, expanded_bottom),
                kdb.Point(expanded_left, expanded_top),
                kdb.Point(expanded_right, expanded_top),
            ]
            def _pts_inside(points: list[kdb.Point], region: kdb.Region) -> bool:
                """Check if all points lie inside the region (practical enclosure test)."""
                for pt in points:
                    # Create a 1-dbu box around the point and check intersection
                    tiny = kdb.Region(kdb.Box(pt, pt + kdb.Point(1, 1)))
                    if (tiny & region).is_empty():
                        return False
                return True

            bot_ok = _pts_inside(test_points, metal_bot_item.region) if metal_bot_item else False
            top_ok = _pts_inside(test_points, metal_top_item.region) if metal_top_item else False
            if not bot_ok or not top_ok:
                enclosure_violations += 1
        checks.append({"layer": via_name, "via_count": via_count,
                       "enclosure_limit_um": rules.via_enclosure_um,
                       "enclosure_violations": enclosure_violations})
        if enclosure_violations:
            violations.append({"layer": via_name, "rule": "via_enclosure",
                               "limit_um": rules.via_enclosure_um,
                               "count": enclosure_violations,
                               "severity": "warning"})

    # Hard failures are violations without a "warning" severity (or with severity "error")
    hard_failures = [v for v in violations if v.get("severity") != "warning"]
    return {
        "schema": "text-to-gds.signoff.drc.v1",
        "gds_path": str(path),
        "database_unit_um": dbu,
        "status": "passed" if not hard_failures else "failed",
        "violations": violations,
        "checks": checks,
        "rule_set": {
            "minimum_metal_width_um": rules.minimum_metal_width_um,
            "minimum_spacing_um": rules.minimum_spacing_um,
            "minimum_jj_size_um": rules.minimum_jj_size_um,
            "via_enclosure_um": rules.via_enclosure_um,
            "minimum_via_size_um": rules.minimum_via_size_um,
            "lithography_resolution_um": rules.lithography_resolution_um,
        },
    }


def signoff_lvs(path: str | Path) -> dict[str, Any]:
    conn = extract_connectivity(path)
    topo = conn["device_topology"]
    return {
        "schema": "text-to-gds.signoff.lvs.v1",
        "gds_path": str(path),
        "status": conn["status"],
        "metal_nodes": [n["id"] for n in conn["nodes"] if n["layer"] in {"M1", "M2", "M3"}],
        "junction_count": topo["junction_count"],
        "squid_count": topo["squid_count"],
        "shorted_junctions": topo["shorted_junctions"],
        "squids": topo["squids"],
        "floating_nodes": conn["floating_nodes"],
    }


def floating_metal_report(path: str | Path) -> dict[str, Any]:
    conn = extract_connectivity(path)
    floating = conn["floating_nodes"]
    nodes = {n["id"]: n for n in conn["nodes"]}
    # Compute area of each floating node in microns squared
    dbu = _dbu(path)
    floating_details = []
    for fid in floating:
        if fid not in nodes:
            continue
        node = nodes[fid]
        bbox = node["bbox"]
        area_um2 = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) * dbu * dbu
        floating_details.append({
            "id": fid,
            "layer": node["layer"],
            "bbox_dbu": bbox,
            "bbox_um": [round(c * dbu, 4) for c in bbox],
            "area_um2": round(area_um2, 6),
        })
    total_floating_area = sum(d["area_um2"] for d in floating_details)
    return {
        "schema": "text-to-gds.signoff.floating-metal.v1",
        "gds_path": str(path),
        "status": "passed" if not floating else "warning",
        "floating_count": len(floating),
        "total_floating_area_um2": round(total_floating_area, 6),
        "floating_nodes": floating_details,
    }


def layer_connectivity_report(path: str | Path) -> dict[str, Any]:
    conn = extract_connectivity(path)
    edges = conn["edges"]
    kinds: dict[str, int] = {}
    for e in edges:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    layer_counts: dict[str, int] = {}
    layer_areas: dict[str, float] = {}
    dbu = _dbu(path)
    for n in conn["nodes"]:
        layer_counts[n["layer"]] = layer_counts.get(n["layer"], 0) + 1
        bbox = n["bbox"]
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) * dbu * dbu
        layer_areas[n["layer"]] = layer_areas.get(n["layer"], 0.0) + area
    return {
        "schema": "text-to-gds.signoff.layer-connectivity.v1",
        "gds_path": str(path),
        "node_count_by_layer": layer_counts,
        "total_area_um2_by_layer": {k: round(v, 4) for k, v in layer_areas.items()},
        "edge_count_by_kind": kinds,
        "edges": edges,
    }


def pdk_rule_summary() -> dict[str, Any]:
    return {
        "schema": "text-to-gds.signoff.pdk-rules.v1",
        "rules": DEFAULT_FABRICATION_RULES.to_dict(),
        "layers": {name: spec.to_dict() for name, spec in PHYSICAL_LAYERS.items()},
    }


def write_klayout_lyp(path: str | Path) -> str:
    """Write a KLayout-compatible layer-properties (.lyp) XML file."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<layer-properties>"]
    for name, spec in PHYSICAL_LAYERS.items():
        color = _LYP_COLORS.get(name, "#aaaaaa")
        lines += [
            " <properties>",
            f"  <frame-color>{color}</frame-color>",
            f"  <fill-color>{color}</fill-color>",
            "  <frame-brightness>0</frame-brightness>",
            "  <fill-brightness>0</fill-brightness>",
            "  <dither-pattern>I5</dither-pattern>",
            "  <visible>true</visible>",
            "  <transparent>false</transparent>",
            "  <width>1</width>",
            "  <marked>false</marked>",
            f"  <name>{name} - {spec.role}</name>",
            f"  <source>{spec.layer[0]}/{spec.layer[1]}@1</source>",
            " </properties>",
        ]
    lines.append("</layer-properties>")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def run_fabrication_signoff(gds_path: str | Path, out_dir: str | Path, stem: str) -> dict[str, Any]:
    """Generate the full signoff artifact set and return their paths + statuses."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    reports = {
        "drc": (signoff_drc(gds_path), out / f"{stem}.drc.json"),
        "lvs": (signoff_lvs(gds_path), out / f"{stem}.lvs.json"),
        "floating_metal": (floating_metal_report(gds_path), out / f"{stem}.floating_metal.json"),
        "layer_connectivity": (layer_connectivity_report(gds_path), out / f"{stem}.layer_connectivity.json"),
        "pdk_rules": (pdk_rule_summary(), out / f"{stem}.pdk_rules.json"),
    }
    paths: dict[str, str] = {}
    statuses: dict[str, Any] = {}
    for key, (payload, dest) in reports.items():
        dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        paths[key] = str(dest)
        statuses[key] = payload.get("status")
    lyp_path = write_klayout_lyp(out / f"{stem}.lyp")
    paths["layer_properties_lyp"] = lyp_path
    return {
        "schema": "text-to-gds.signoff.bundle.v1",
        "gds_path": str(gds_path),
        "reports": paths,
        "statuses": statuses,
    }
