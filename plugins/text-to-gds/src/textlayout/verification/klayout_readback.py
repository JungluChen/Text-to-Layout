"""Independent KLayout readback verification of every exported GDS.

The exporter (gdsfactory) and the verifier (KLayout) are different code bases
on purpose: the readback proves the *file on disk* — the artifact a mask shop
would receive — contains what the Geometry IR promised, rather than trusting
the writer's own bookkeeping.

Checks: top cell exists, bounding box is non-empty and matches the IR within
tolerance, every expected layer is present, per-layer polygon counts match,
and the database unit is sane (a unit mistake shows up as a ~1000× bbox error).
Results are written to ``klayout_readback.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textlayout.models import Geometry, Technology

READBACK_SCHEMA = "textlayout.klayout-readback.v1"

_BBOX_TOLERANCE_UM = 0.01  # GDS grid snap: 1 nm dbu, generous 10 nm slack


@dataclass(slots=True)
class ReadbackCheck:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass(slots=True)
class ReadbackResult:
    gds_path: str
    checks: list[ReadbackCheck] = field(default_factory=list)
    top_cell: str | None = None
    dbu_um: float | None = None
    bbox_um: dict[str, float] | None = None
    layers: dict[str, int] = field(default_factory=dict)
    polygon_count: int = 0
    label_count: int = 0

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": READBACK_SCHEMA,
            "status": "pass" if self.passed else "fail",
            "gds_path": self.gds_path,
            "top_cell": self.top_cell,
            "dbu_um": self.dbu_um,
            "bbox_um": self.bbox_um,
            "layers": dict(self.layers),
            "polygon_count": self.polygon_count,
            "label_count": self.label_count,
            "checks": [check.to_dict() for check in self.checks],
        }


def read_back_gds(
    gds_path: str | Path,
    geometry: Geometry | None = None,
    technology: Technology | None = None,
) -> ReadbackResult:
    """Load ``gds_path`` with the KLayout API and verify it against the IR."""
    import klayout.db as kdb

    result = ReadbackResult(gds_path=str(gds_path))
    path = Path(gds_path)
    if not path.is_file() or path.stat().st_size == 0:
        result.checks.append(ReadbackCheck("gds_file_exists", False, f"missing or empty: {path}"))
        return result
    result.checks.append(ReadbackCheck("gds_file_exists", True, str(path)))

    layout = kdb.Layout()
    try:
        layout.read(str(path))
    except Exception as exc:  # noqa: BLE001 - a corrupt GDS must fail, not crash
        result.checks.append(ReadbackCheck("gds_readable", False, f"KLayout read failed: {exc}"))
        return result
    result.checks.append(ReadbackCheck("gds_readable", True, ""))

    result.dbu_um = float(layout.dbu)
    dbu_ok = 1e-5 <= layout.dbu <= 0.01
    result.checks.append(
        ReadbackCheck(
            "database_unit_sane",
            dbu_ok,
            f"dbu = {layout.dbu} um" + ("" if dbu_ok else " (expected ~0.001 um)"),
        )
    )

    tops = layout.top_cells()
    if not tops:
        result.checks.append(ReadbackCheck("top_cell_exists", False, "no top cell"))
        return result
    top = tops[0]
    result.top_cell = top.name
    result.checks.append(
        ReadbackCheck(
            "top_cell_exists",
            len(tops) == 1,
            top.name if len(tops) == 1 else f"{len(tops)} top cells: {[c.name for c in tops]}",
        )
    )

    bbox = top.dbbox()
    empty = bbox.empty()
    if not empty:
        result.bbox_um = {
            "width": round(bbox.width(), 6),
            "height": round(bbox.height(), 6),
        }
    result.checks.append(
        ReadbackCheck(
            "bbox_non_empty",
            not empty,
            "" if empty else f"{bbox.width():.4f} x {bbox.height():.4f} um",
        )
    )

    polygon_count = 0
    label_count = 0
    layer_polygons: dict[str, int] = {}
    index_by_key: dict[str, int] = {}
    for layer_index in layout.layer_indexes():
        info = layout.get_info(layer_index)
        key = f"{info.layer}/{info.datatype}"
        index_by_key[key] = layer_index
        count = 0
        for cell in layout.each_cell():
            shapes = cell.shapes(layer_index)
            for shape in shapes.each():
                if shape.is_text():
                    label_count += 1
                elif shape.is_polygon() or shape.is_box() or shape.is_path():
                    count += 1
        if count:
            layer_polygons[key] = layer_polygons.get(key, 0) + count
            polygon_count += count
    result.layers = layer_polygons
    result.polygon_count = polygon_count
    result.label_count = label_count
    result.checks.append(
        ReadbackCheck(
            "polygon_count_positive", polygon_count > 0, f"{polygon_count} polygons read back"
        )
    )

    if geometry is not None and technology is not None:
        expected: dict[str, int] = {}
        unknown_layers: set[str] = set()
        for polygon in geometry.polygons:
            if not technology.has_layer(polygon.layer):
                # Never mirror an exporter fallback here: an IR layer the
                # technology does not know is a verification failure, not a
                # remapping to layer 0/0.
                unknown_layers.add(polygon.layer)
                continue
            layer_info = technology.layer(polygon.layer)
            key = f"{layer_info.gds_layer}/{layer_info.gds_datatype}"
            expected[key] = expected.get(key, 0) + 1
        if unknown_layers:
            result.checks.append(
                ReadbackCheck(
                    "ir_layers_known_to_technology",
                    False,
                    f"IR layers not in technology {technology.name!r}: {sorted(unknown_layers)}",
                )
            )
        missing = sorted(set(expected) - set(layer_polygons))
        result.checks.append(
            ReadbackCheck(
                "expected_layers_present",
                not missing,
                "all expected layers found" if not missing else f"missing layers: {missing}",
            )
        )
        mismatched = {
            key: (expected[key], layer_polygons.get(key, 0))
            for key in expected
            if layer_polygons.get(key, 0) != expected[key]
        }
        result.checks.append(
            ReadbackCheck(
                "per_layer_polygon_counts_match",
                not mismatched,
                "IR and GDS polygon counts agree"
                if not mismatched
                else f"(expected, found) per layer: {mismatched}",
            )
        )
        # Polygon-exact minimum-width DRC on the file itself. Parameter checks
        # validate the *inputs*; this measures the *drawn* geometry with
        # KLayout's width_check, so a generator bug producing a sub-rule
        # feature fails readback even when its parameters looked legal.
        width_failures: list[str] = []
        checked_width_layers = 0
        for layer_name in sorted({polygon.layer for polygon in geometry.polygons}):
            if not technology.has_layer(layer_name):
                continue
            min_width_um = technology.min_width_for(layer_name)
            if min_width_um <= 0.0:
                continue
            layer_info = technology.layer(layer_name)
            checked_index = index_by_key.get(f"{layer_info.gds_layer}/{layer_info.gds_datatype}")
            if checked_index is None:
                continue  # absence is reported by expected_layers_present
            region = kdb.Region(top.begin_shapes_rec(checked_index))
            region.merge()
            limit_dbu = int(round(min_width_um / layout.dbu))
            markers = sum(1 for _ in region.width_check(limit_dbu).each())
            checked_width_layers += 1
            if markers:
                width_failures.append(
                    f"{layer_name}: {markers} drawn feature(s) narrower than {min_width_um} um"
                )
        if checked_width_layers:
            result.checks.append(
                ReadbackCheck(
                    "drawn_min_width",
                    not width_failures,
                    f"{checked_width_layers} layer(s) width-checked"
                    if not width_failures
                    else "; ".join(width_failures),
                )
            )

        if not geometry.is_empty and not empty:
            ir_bbox = geometry.bbox()
            width_ok = abs(ir_bbox.width - bbox.width()) <= _BBOX_TOLERANCE_UM
            height_ok = abs(ir_bbox.height - bbox.height()) <= _BBOX_TOLERANCE_UM
            result.checks.append(
                ReadbackCheck(
                    "bbox_matches_ir",
                    width_ok and height_ok,
                    f"IR {ir_bbox.width:.4f}x{ir_bbox.height:.4f} um vs "
                    f"GDS {bbox.width():.4f}x{bbox.height():.4f} um",
                )
            )
        expected_ports = len(geometry.ports)
        if expected_ports:
            result.checks.append(
                ReadbackCheck(
                    "ports_declared",
                    True,
                    f"{expected_ports} port(s) declared in the IR/sidecar; GDS text "
                    f"labels found: {label_count}",
                )
            )

    return result


def write_readback_json(result: ReadbackResult, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return out
