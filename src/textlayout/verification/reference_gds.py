"""Independent mask-geometry comparison and open-source GDS round trips.

Zero XOR proves equivalence of the selected mask geometry. It does not prove
material properties, extracted circuit parameters, or fabrication readiness.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
from pathlib import Path
from typing import Any

import klayout.db as kdb


def _cell(layout: Any, name: str | None) -> Any:
    if name is not None:
        cell = layout.cell(name)
        if cell is None:
            raise ValueError(f"Cell {name!r} does not exist")
        return cell
    tops = layout.top_cells()
    if len(tops) != 1:
        raise ValueError(f"Select an explicit cell; found {len(tops)} top cells: "
                         f"{[cell.name for cell in tops]}")
    return tops[0]


def _labels(layout: Any, cell: Any) -> list[tuple[int, int, str]]:
    labels = []
    for layer in layout.layer_indexes():
        info = layout.get_info(layer)
        iterator = cell.begin_shapes_rec(layer)
        while not iterator.at_end():
            shape = iterator.shape()
            if shape.is_text():
                labels.append((info.layer, info.datatype,
                               shape.text.transformed(iterator.trans()).to_s()))
            iterator.next()
    return sorted(labels)


def compare_gds_geometry(
    reference: str | Path, candidate: str | Path, *,
    reference_cell: str | None = None, candidate_cell: str | None = None,
) -> dict[str, Any]:
    """Compare every layer in both files, including hierarchy and text positions."""
    source, output = Path(reference), Path(candidate)
    before, after = kdb.Layout(), kdb.Layout()
    before.read(str(source))
    after.read(str(output))
    original, exported = _cell(before, reference_cell), _cell(after, candidate_cell)
    result: dict[str, Any] = {
        "schema": "textlayout.reference-geometry.v1", "geometry_equivalent": False,
        "reference": str(source.resolve()), "candidate": str(output.resolve()),
        "reference_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "candidate_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "reference_cell": original.name, "candidate_cell": exported.name,
        "reference_dbu_um": before.dbu, "candidate_dbu_um": after.dbu,
        "scope": "Selected mask geometry and label content/placement only; no EM or process validation",
        "klayout_version": importlib.metadata.version("klayout"),
    }
    if before.dbu != after.dbu:
        result["error"] = "Database units differ; refusing a lossy implicit rescaling"
        return result
    keys = {(layout.get_info(i).layer, layout.get_info(i).datatype)
            for layout in (before, after) for i in layout.layer_indexes()}
    rows = []
    for layer, datatype in sorted(keys):
        indices = [layout.find_layer(layer, datatype) for layout in (before, after)]
        regions = [kdb.Region(cell.begin_shapes_rec(i)) if i is not None else kdb.Region()
                   for cell, i in zip((original, exported), indices, strict=True)]
        difference = regions[0] ^ regions[1]
        rows.append({"layer": layer, "datatype": datatype, "equal": difference.is_empty(),
                     "xor_area_um2": difference.area() * before.dbu**2,
                     "reference_area_um2": regions[0].area() * before.dbu**2,
                     "candidate_area_um2": regions[1].area() * after.dbu**2})
    result["layers"] = rows
    result["labels_equal"] = _labels(before, original) == _labels(after, exported)
    result["bbox_equal"] = original.bbox() == exported.bbox()
    result["reference_bbox_um"] = str(original.dbbox())
    result["candidate_bbox_um"] = str(exported.dbbox())
    result["geometry_equivalent"] = (bool(rows) and not original.bbox().empty()
                                      and all(r["equal"] for r in rows)
                                      and result["labels_equal"] and result["bbox_equal"])
    return result


def roundtrip_reference_gds(source: str | Path, output: str | Path, *,
                            cell: str | None = None) -> dict[str, Any]:
    """Import with gdsfactory, export, and compare independently with KLayout."""
    import gdsfactory as gf

    reference, candidate = Path(source).resolve(), Path(output).resolve()
    if reference == candidate:
        raise ValueError("The output must not overwrite the reference GDS")
    layout = kdb.Layout()
    layout.read(str(reference))
    selected = _cell(layout, cell).name
    candidate.parent.mkdir(parents=True, exist_ok=True)
    component = gf.import_gds(reference, cellname=selected)
    component.write_gds(candidate)
    result = compare_gds_geometry(reference, candidate, reference_cell=selected)
    result["gdsfactory_version"] = importlib.metadata.version("gdsfactory")
    return result
