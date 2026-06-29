"""True GDS geometry extraction engine — Phase 1.

Reads a GDS file with KLayout's Python API, extracts polygons per layer,
detects device types (CPW, JJ, IDC, SQUID, transmission line), and computes
device-specific geometry parameters.  Output is geometry_extraction.json with
full provenance on every measurement.

Device detection rules (based on default Nb/AlOx process layers):
  JJ    — polygons on layer (4,0) [JJ] overlapping layer (3,0) [M1]
  CPW   — M1 polygon with aspect ratio >= 5 and width in [1, 30] µm range
  IDC   — cluster of ≥4 parallel M1 fingers with similar width and spacing
  SQUID — exactly two JJ regions sharing a common M1 loop
  via   — via layer polygon, area < threshold
  TLine — long M1 polygon (length > 200 µm) with controlled width

All measurements are labelled method="extracted", source="klayout.db".
LLM-generated values are never written here.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ─── Layer definitions (must match process.py DEFAULT_LAYERS) ──────────────────
_LAYER_M1 = (3, 0)
_LAYER_JJ = (4, 0)
_LAYER_M2 = (5, 0)
_LAYER_VIA = (6, 0)
_LAYER_SUB = (1, 0)

_SCHEMA = "text-to-gds.geometry-extraction.v1"

# ─── Geometry helpers ──────────────────────────────────────────────────────────

@dataclass
class PolygonRecord:
    layer: tuple[int, int]
    cell: str
    bbox_um: list[float]          # [x_min, y_min, x_max, y_max]
    width_um: float
    height_um: float
    area_um2: float
    aspect_ratio: float           # max(w,h)/min(w,h)
    perimeter_um: float
    vertices: list[list[float]]   # polygon vertices in µm


@dataclass
class DetectedDevice:
    device_type: str              # "cpw" | "jj" | "idc" | "squid" | "via" | "tline" | "metal"
    parameters: dict[str, Any]
    polygons: list[int]           # indices into polygon list
    confidence: float


@dataclass
class GeometryExtraction:
    schema: str
    gds_path: str
    polygons: list[PolygonRecord]
    devices: list[DetectedDevice]
    layer_summary: dict[str, Any]
    extraction_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "gds_path": self.gds_path,
            "polygon_count": len(self.polygons),
            "device_count": len(self.devices),
            "layer_summary": self.layer_summary,
            "devices": [
                {
                    "device_type": d.device_type,
                    "parameters": d.parameters,
                    "polygon_indices": d.polygons,
                    "confidence": d.confidence,
                }
                for d in self.devices
            ],
            "polygons": [
                {
                    "index": i,
                    "layer": list(p.layer),
                    "cell": p.cell,
                    "bbox_um": p.bbox_um,
                    "width_um": round(p.width_um, 4),
                    "height_um": round(p.height_um, 4),
                    "area_um2": round(p.area_um2, 6),
                    "aspect_ratio": round(p.aspect_ratio, 3),
                    "perimeter_um": round(p.perimeter_um, 4),
                }
                for i, p in enumerate(self.polygons)
            ],
            "extraction_notes": self.extraction_notes,
            "provenance": {
                "method": "extracted",
                "source": "klayout.db",
                "tool": "KLayout Python API",
            },
        }


# ─── Main extraction function ──────────────────────────────────────────────────

def extract_geometry(
    gds_path: str | Path,
    *,
    top_cell: str | None = None,
    flatten: bool = True,
) -> GeometryExtraction:
    """Extract all polygon geometry from a GDS file and detect device types.

    Parameters
    ----------
    gds_path:
        Path to the .gds or .gds2 file.
    top_cell:
        If given, use this cell as the top; otherwise use the library top cell.
    flatten:
        If True, flatten the cell hierarchy before extraction (default: True).

    Returns
    -------
    GeometryExtraction
        Full extraction result with all polygons and detected devices.

    Raises
    ------
    FileNotFoundError
        If the GDS file does not exist.
    ImportError
        If klayout is not installed.
    """
    gds_path = Path(gds_path)
    if not gds_path.exists():
        raise FileNotFoundError(f"GDS file not found: {gds_path}")

    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    dbu = float(layout.dbu)

    if top_cell is not None:
        cell = layout.cell(top_cell)
        if cell is None:
            raise ValueError(f"Cell '{top_cell}' not found in layout")
    else:
        cell = layout.top_cell()
        if cell is None:
            if layout.cells() > 0:
                cell = next(iter(layout.each_cell()))
            else:
                raise ValueError("Layout has no cells")

    notes: list[str] = []

    if flatten:
        cell.flatten(True)
        notes.append("hierarchy flattened for extraction")

    polygons: list[PolygonRecord] = []
    layer_counts: dict[str, int] = {}

    for layer_index in layout.layer_indices():
        info = layout.get_info(layer_index)
        layer = (int(info.layer), int(info.datatype))
        layer_key = f"L{layer[0]}D{layer[1]}"

        for shape in cell.shapes(layer_index).each():
            poly_dbu: kdb.Polygon | None = None
            if shape.is_polygon():
                poly_dbu = shape.polygon
            elif shape.is_box():
                poly_dbu = kdb.Polygon(shape.box)
            elif shape.is_path():
                poly_dbu = shape.path.polygon()
            else:
                continue

            if poly_dbu is None:
                continue

            bbox = poly_dbu.bbox()
            w = abs(bbox.width()) * dbu
            h = abs(bbox.height()) * dbu
            if w < 1e-6 or h < 1e-6:
                continue

            area = poly_dbu.area() * (dbu ** 2)
            if area < 1e-9:
                continue

            vertices = [
                [pt.x * dbu, pt.y * dbu]
                for pt in poly_dbu.each_point_hull()
            ]
            n = len(vertices)
            perimeter = sum(
                math.hypot(
                    vertices[(i + 1) % n][0] - vertices[i][0],
                    vertices[(i + 1) % n][1] - vertices[i][1],
                )
                for i in range(n)
            )

            rec = PolygonRecord(
                layer=layer,
                cell=cell.name,
                bbox_um=[
                    float(bbox.left) * dbu,
                    float(bbox.bottom) * dbu,
                    float(bbox.right) * dbu,
                    float(bbox.top) * dbu,
                ],
                width_um=w,
                height_um=h,
                area_um2=area,
                aspect_ratio=max(w, h) / max(min(w, h), 1e-9),
                perimeter_um=perimeter,
                vertices=vertices,
            )
            polygons.append(rec)
            layer_counts[layer_key] = layer_counts.get(layer_key, 0) + 1

    notes.append(f"extracted {len(polygons)} polygons from {len(layer_counts)} active layers")

    devices = _detect_devices(polygons, notes)

    layer_summary: dict[str, Any] = {}
    for layer_index in layout.layer_indices():
        info = layout.get_info(layer_index)
        layer = (int(info.layer), int(info.datatype))
        key = f"L{layer[0]}D{layer[1]}"
        count = layer_counts.get(key, 0)
        if count > 0:
            layer_summary[key] = {
                "layer": layer[0],
                "datatype": layer[1],
                "polygon_count": count,
            }

    return GeometryExtraction(
        schema=_SCHEMA,
        gds_path=str(gds_path),
        polygons=polygons,
        devices=devices,
        layer_summary=layer_summary,
        extraction_notes=notes,
    )


# ─── Device detection ──────────────────────────────────────────────────────────

def _detect_devices(
    polygons: list[PolygonRecord],
    notes: list[str],
) -> list[DetectedDevice]:
    devices: list[DetectedDevice] = []
    used: set[int] = set()

    m1_indices = [i for i, p in enumerate(polygons) if p.layer == _LAYER_M1]
    m2_indices = [i for i, p in enumerate(polygons) if p.layer == _LAYER_M2]
    jj_indices = [i for i, p in enumerate(polygons) if p.layer == _LAYER_JJ]
    via_indices = [i for i, p in enumerate(polygons) if p.layer == _LAYER_VIA]

    # --- Josephson junctions: JJ layer polygons ---
    jj_devices = _detect_josephson_junctions(polygons, jj_indices, m1_indices, m2_indices)
    for dev in jj_devices:
        devices.append(dev)
        used.update(dev.polygons)

    # --- SQUIDs: pairs of JJ near a common M1 loop ---
    squid_devices = _detect_squids(polygons, jj_devices)
    for dev in squid_devices:
        devices.append(dev)

    # --- CPW: long, narrow M1 polygons ---
    cpw_devices = _detect_cpw(polygons, m1_indices, used)
    for dev in cpw_devices:
        devices.append(dev)
        used.update(dev.polygons)

    # --- IDC: cluster of parallel M1 fingers ---
    idc_devices = _detect_idc(polygons, m1_indices, used)
    for dev in idc_devices:
        devices.append(dev)
        used.update(dev.polygons)

    # --- Transmission lines: very long M1 polygons ---
    tline_devices = _detect_tlines(polygons, m1_indices, used)
    for dev in tline_devices:
        devices.append(dev)
        used.update(dev.polygons)

    # --- Vias ---
    for i in via_indices:
        p = polygons[i]
        devices.append(DetectedDevice(
            device_type="via",
            parameters={
                "area_um2": round(p.area_um2, 4),
                "width_um": round(p.width_um, 4),
                "height_um": round(p.height_um, 4),
                "layer": list(p.layer),
                "provenance": {"method": "extracted", "source": "klayout.db"},
            },
            polygons=[i],
            confidence=0.9,
        ))
        used.add(i)

    n_unclassified = len([i for i in m1_indices if i not in used])
    if n_unclassified:
        notes.append(f"{n_unclassified} M1 polygons not classified into a device type")

    notes.append(f"detected {len(devices)} devices total")
    return devices


def _detect_josephson_junctions(
    polygons: list[PolygonRecord],
    jj_indices: list[int],
    m1_indices: list[int],
    m2_indices: list[int],
) -> list[DetectedDevice]:
    """Detect JJs from bottom-Al/top-Al overlap near the JJ process marker."""
    devices: list[DetectedDevice] = []
    for ji in jj_indices:
        jj = polygons[ji]
        width_um = min(jj.width_um, jj.height_um)
        height_um = max(jj.width_um, jj.height_um)

        overlapping_m1 = []
        for mi in m1_indices:
            if _bboxes_overlap(jj.bbox_um, polygons[mi].bbox_um):
                overlapping_m1.append(mi)
        overlapping_m2 = []
        for mi in m2_indices:
            if _bboxes_overlap(jj.bbox_um, polygons[mi].bbox_um):
                overlapping_m2.append(mi)

        area = 0.0
        for bottom_i in overlapping_m1:
            for top_i in overlapping_m2:
                area += _bbox_intersection_area(polygons[bottom_i].bbox_um, polygons[top_i].bbox_um)

        devices.append(DetectedDevice(
            device_type="jj",
            parameters={
                "junction_area_um2": round(area, 5),
                "bridge_width_um": round(width_um, 4),
                "bridge_height_um": round(height_um, 4),
                "bottom_electrode_count": len(overlapping_m1),
                "top_electrode_count": len(overlapping_m2),
                "layer": list(jj.layer),
                "provenance": {
                    "method": "extracted",
                    "source": "klayout.db",
                    "note": "area = M1/M2 polygon overlap; JJ marker geometry is not counted",
                },
            },
            polygons=[ji] + overlapping_m1 + overlapping_m2,
            confidence=0.95 if area > 0.0 else 0.25,
        ))
    return devices


def _detect_squids(
    polygons: list[PolygonRecord],
    jj_devices: list[DetectedDevice],
) -> list[DetectedDevice]:
    """Detect SQUIDs: two JJ devices whose bounding boxes are within 30 µm of each other."""
    squids: list[DetectedDevice] = []
    n = len(jj_devices)
    paired: set[int] = set()
    for i in range(n):
        if i in paired:
            continue
        for j in range(i + 1, n):
            if j in paired:
                continue
            jj1 = jj_devices[i]
            jj2 = jj_devices[j]
            p1_idx = jj1.polygons[0]
            p2_idx = jj2.polygons[0]
            p1 = polygons[p1_idx]
            p2 = polygons[p2_idx]
            dist = _bbox_centroid_distance(p1.bbox_um, p2.bbox_um)
            if dist <= 30.0:
                a1 = jj1.parameters["junction_area_um2"]
                a2 = jj2.parameters["junction_area_um2"]
                squids.append(DetectedDevice(
                    device_type="squid",
                    parameters={
                        "junction_1_area_um2": a1,
                        "junction_2_area_um2": a2,
                        "junction_separation_um": round(dist, 3),
                        "area_asymmetry": round(abs(a1 - a2) / max(a1, a2, 1e-12), 4),
                        "provenance": {
                            "method": "extracted",
                            "source": "klayout.db",
                            "note": "SQUID loop inductance requires EM solver",
                        },
                    },
                    polygons=jj1.polygons + jj2.polygons,
                    confidence=0.80,
                ))
                paired.add(i)
                paired.add(j)
    return squids


def _detect_cpw(
    polygons: list[PolygonRecord],
    m1_indices: list[int],
    used: set[int],
) -> list[DetectedDevice]:
    """Detect CPW segments: M1 polygons with aspect ratio >= 5 and width in [1, 25] µm."""
    devices: list[DetectedDevice] = []
    for i in m1_indices:
        if i in used:
            continue
        p = polygons[i]
        if p.aspect_ratio < 5.0:
            continue
        width = min(p.width_um, p.height_um)
        length = max(p.width_um, p.height_um)
        if not (0.5 <= width <= 30.0):
            continue

        devices.append(DetectedDevice(
            device_type="cpw",
            parameters={
                "center_width_um": round(width, 4),
                "length_um": round(length, 4),
                "aspect_ratio": round(p.aspect_ratio, 2),
                "layer": list(p.layer),
                "note": "gap_um requires adjacent ground polygon analysis",
                "provenance": {
                    "method": "extracted",
                    "source": "klayout.db",
                    "note": "Z0 and epsilon_eff require cpw_physics.synthesize_cpw()",
                },
            },
            polygons=[i],
            confidence=0.75,
        ))
    return devices


def _detect_idc(
    polygons: list[PolygonRecord],
    m1_indices: list[int],
    used: set[int],
) -> list[DetectedDevice]:
    """Detect IDC: ≥4 parallel M1 polygons with similar width and regular spacing."""
    candidates = [
        i for i in m1_indices
        if i not in used
        and polygons[i].aspect_ratio >= 3.0
        and polygons[i].width_um <= 10.0
    ]
    if len(candidates) < 4:
        return []

    widths = [min(polygons[i].width_um, polygons[i].height_um) for i in candidates]
    median_width = sorted(widths)[len(widths) // 2]

    fingers = [
        i for i, w in zip(candidates, widths)
        if abs(w - median_width) / max(median_width, 1e-9) < 0.20
    ]
    if len(fingers) < 4:
        return []

    centroids = [_bbox_centroid(polygons[i].bbox_um) for i in fingers]
    centroids_sorted = sorted(zip(centroids, fingers), key=lambda x: x[0][0])
    fingers_sorted = [fi for _, fi in centroids_sorted]

    gaps: list[float] = []
    for k in range(len(centroids_sorted) - 1):
        c1 = centroids_sorted[k][0]
        c2 = centroids_sorted[k + 1][0]
        gaps.append(math.hypot(c2[0] - c1[0], c2[1] - c1[1]))

    if not gaps:
        return []

    mean_gap = sum(gaps) / len(gaps)
    finger_lengths = [max(polygons[i].width_um, polygons[i].height_um) for i in fingers_sorted]
    overlap_length = min(finger_lengths)

    return [DetectedDevice(
        device_type="idc",
        parameters={
            "finger_count": len(fingers_sorted),
            "finger_width_um": round(median_width, 4),
            "finger_pitch_um": round(mean_gap, 4),
            "finger_gap_um": round(mean_gap - median_width, 4),
            "overlap_length_um": round(overlap_length, 4),
            "provenance": {
                "method": "extracted",
                "source": "klayout.db",
                "note": "capacitance requires Elmer FEM or analytical IDC formula",
            },
        },
        polygons=fingers_sorted,
        confidence=0.70,
    )]


def _detect_tlines(
    polygons: list[PolygonRecord],
    m1_indices: list[int],
    used: set[int],
) -> list[DetectedDevice]:
    """Detect transmission lines: M1 polygons longer than 200 µm."""
    devices: list[DetectedDevice] = []
    for i in m1_indices:
        if i in used:
            continue
        p = polygons[i]
        length = max(p.width_um, p.height_um)
        width = min(p.width_um, p.height_um)
        if length < 200.0:
            continue
        devices.append(DetectedDevice(
            device_type="tline",
            parameters={
                "trace_width_um": round(width, 4),
                "length_um": round(length, 4),
                "aspect_ratio": round(p.aspect_ratio, 2),
                "layer": list(p.layer),
                "provenance": {
                    "method": "extracted",
                    "source": "klayout.db",
                    "note": "electrical length requires epsilon_eff from EM solver",
                },
            },
            polygons=[i],
            confidence=0.80,
        ))
    return devices


# ─── Geometry utilities ────────────────────────────────────────────────────────

def _bboxes_overlap(a: list[float], b: list[float]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _bbox_intersection_area(*boxes: list[float]) -> float:
    left = max(box[0] for box in boxes)
    bottom = max(box[1] for box in boxes)
    right = min(box[2] for box in boxes)
    top = min(box[3] for box in boxes)
    if right <= left or top <= bottom:
        return 0.0
    return (right - left) * (top - bottom)


def _bbox_centroid(bbox: list[float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _bbox_centroid_distance(a: list[float], b: list[float]) -> float:
    ca = _bbox_centroid(a)
    cb = _bbox_centroid(b)
    return math.hypot(cb[0] - ca[0], cb[1] - ca[1])


# ─── Output ────────────────────────────────────────────────────────────────────

def write_geometry_extraction(
    extraction: GeometryExtraction,
    output_path: str | Path,
) -> Path:
    """Write geometry_extraction.json to disk."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(extraction.to_dict(), indent=2), encoding="utf-8")
    return out
