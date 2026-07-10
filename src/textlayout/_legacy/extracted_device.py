from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout._legacy.cpw_physics import synthesize_cpw
from textlayout._legacy.extraction import PHI0_WEBER, layer_bounding_boxes_from_gds
from textlayout._legacy.process import DEFAULT_PROCESS

MethodLabel = Literal["estimated", "extracted", "simulated", "measured"]


class SourceGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gds_path: str
    layer: list[int] | None = None
    layer_name: str | None = None
    bbox_um: list[float] | None = None
    ports: list[dict[str, Any]] = Field(default_factory=list)
    note: str | None = None


class ExtractedQuantity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float
    unit: str
    formula: str
    source_geometry: SourceGeometry
    method_label: MethodLabel
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema: str = "text-to-gds.extracted-device.v1"
    status: Literal["ok", "partial", "failed"]
    device: str
    gds_path: str
    layer_map: dict[str, list[int]]
    process_stack: dict[str, Any]
    polygons: list[dict[str, Any]]
    ports: list[dict[str, Any]]
    quantities: dict[str, ExtractedQuantity]
    issues: list[str] = Field(default_factory=list)


def _source(gds_path: Path, box: dict[str, Any] | None = None, *, ports: list[dict[str, Any]] | None = None, note: str | None = None) -> SourceGeometry:
    return SourceGeometry(
        gds_path=str(gds_path),
        layer=box.get("layer") if box else None,
        layer_name=box.get("layer_name") if box else None,
        bbox_um=box.get("bbox_um") if box else None,
        ports=ports or [],
        note=note,
    )


def _quantity(
    value: float,
    unit: str,
    formula: str,
    source_geometry: SourceGeometry,
    method_label: MethodLabel,
    confidence: float,
) -> ExtractedQuantity:
    return ExtractedQuantity(
        value=float(value),
        unit=unit,
        formula=formula,
        source_geometry=source_geometry,
        method_label=method_label,
        confidence=confidence,
    )


def _sidecar_dict(sidecar: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if sidecar is None:
        return {}
    if isinstance(sidecar, dict):
        return sidecar
    return json.loads(Path(sidecar).read_text(encoding="utf-8"))


def _device_name(sidecar: dict[str, Any]) -> str:
    info = sidecar.get("info") if isinstance(sidecar.get("info"), dict) else {}
    return str(info.get("device_type") or sidecar.get("pcell") or "unknown")


def _layer_map() -> dict[str, list[int]]:
    return {name: [int(spec.layer[0]), int(spec.layer[1])] for name, spec in DEFAULT_PROCESS.layers.items()}


def _layer_area(boxes: list[dict[str, Any]], layer_name: str) -> float:
    return sum(float(box["area_um2"]) for box in boxes if box.get("layer_name") == layer_name)


def _smallest_box(boxes: list[dict[str, Any]], layer_name: str) -> dict[str, Any] | None:
    candidates = [box for box in boxes if box.get("layer_name") == layer_name]
    if not candidates:
        return None
    return min(candidates, key=lambda box: float(box["area_um2"]))


def _largest_box(boxes: list[dict[str, Any]], layer_name: str) -> dict[str, Any] | None:
    candidates = [box for box in boxes if box.get("layer_name") == layer_name]
    if not candidates:
        return None
    return max(candidates, key=lambda box: float(box["area_um2"]))


def _bbox_gap(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax0, ay0, ax1, ay1 = [float(v) for v in a["bbox_um"]]
    bx0, by0, bx1, by1 = [float(v) for v in b["bbox_um"]]
    dx = max(bx0 - ax1, ax0 - bx1, 0.0)
    dy = max(by0 - ay1, ay0 - by1, 0.0)
    return math.hypot(dx, dy)


def _min_spacing(boxes: list[dict[str, Any]]) -> float | None:
    metal = [box for box in boxes if str(box.get("layer_name", "")).startswith("M")]
    best: float | None = None
    for index, left in enumerate(metal):
        for right in metal[index + 1 :]:
            gap = _bbox_gap(left, right)
            if gap > 0.0:
                best = gap if best is None else min(best, gap)
    return best


def extract_device(
    gds_path: str | Path,
    sidecar: dict[str, Any] | str | Path | None = None,
    *,
    jc_ua_per_um2: float | None = None,
    specific_capacitance_ff_per_um2: float | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Extract layout geometry and first-principles circuit quantities from GDS.

    The result is an ``extracted_device.json``-style dict. Solver-like values are
    never fabricated; if a process input such as ``specific_capacitance_ff_per_um2``
    is absent, dependent quantities are omitted and an issue is recorded.
    """
    gds = Path(gds_path)
    sidecar_data = _sidecar_dict(sidecar)
    info = sidecar_data.get("info") if isinstance(sidecar_data.get("info"), dict) else {}
    ports = sidecar_data.get("ports") if isinstance(sidecar_data.get("ports"), list) else []
    boxes = layer_bounding_boxes_from_gds(gds)
    quantities: dict[str, ExtractedQuantity] = {}
    issues: list[str] = []

    for layer_name in sorted({str(box["layer_name"]) for box in boxes}):
        area = _layer_area(boxes, layer_name)
        source_box = _largest_box(boxes, layer_name)
        if area > 0 and source_box:
            quantities[f"metal_area.{layer_name}"] = _quantity(
                area,
                "um^2",
                f"sum polygon areas on {layer_name}",
                _source(gds, source_box),
                "extracted",
                1.0,
            )

    signal_box = _largest_box(boxes, "M2") or _largest_box(boxes, "M3") or _largest_box(boxes, "M1")
    if signal_box:
        width = min(float(signal_box["width_um"]), float(signal_box["height_um"]))
        length = max(float(signal_box["width_um"]), float(signal_box["height_um"]))
        quantities["conductor_width"] = _quantity(
            width,
            "um",
            "min(width, height) of dominant conductor bbox",
            _source(gds, signal_box),
            "extracted",
            0.9,
        )
        quantities["conductor_length"] = _quantity(
            length,
            "um",
            "max(width, height) of dominant conductor bbox",
            _source(gds, signal_box),
            "extracted",
            0.85,
        )

    spacing = _min_spacing(boxes)
    if spacing is not None:
        quantities["minimum_spacing"] = _quantity(
            spacing,
            "um",
            "minimum non-overlapping bbox distance between metal polygons",
            _source(gds, note="computed from extracted metal bounding boxes"),
            "extracted",
            0.75,
        )

    if ports:
        quantities["port_count"] = _quantity(
            float(len(ports)),
            "count",
            "count(sidecar.ports)",
            _source(gds, ports=ports),
            "extracted",
            1.0,
        )

    jj_box = _smallest_box(boxes, "JJ")
    if jj_box:
        area_um2 = float(jj_box["area_um2"])
        quantities["junction_area"] = _quantity(
            area_um2,
            "um^2",
            "area(JJ polygon)",
            _source(gds, jj_box),
            "extracted",
            1.0,
        )
        if jc_ua_per_um2 is None:
            issues.append("JJ Ic/Lj omitted: jc_ua_per_um2 not supplied")
        else:
            ic_a = area_um2 * float(jc_ua_per_um2) * 1e-6
            lj_h = PHI0_WEBER / (2.0 * math.pi * ic_a)
            quantities["critical_current"] = _quantity(
                ic_a,
                "A",
                "Ic = Jc*A",
                _source(gds, jj_box),
                "estimated",
                0.98,
            )
            quantities["josephson_inductance"] = _quantity(
                lj_h,
                "H",
                "Lj = Phi0/(2*pi*Ic)",
                _source(gds, jj_box),
                "estimated",
                0.98,
            )
            if specific_capacitance_ff_per_um2 is None:
                issues.append("JJ Cj/plasma frequency omitted: specific_capacitance_ff_per_um2 not supplied")
            else:
                cj_f = area_um2 * float(specific_capacitance_ff_per_um2) * 1e-15
                wp_rad_s = 1.0 / math.sqrt(lj_h * cj_f)
                quantities["junction_capacitance"] = _quantity(
                    cj_f,
                    "F",
                    "Cj = Cs*A",
                    _source(gds, jj_box),
                    "estimated",
                    0.85,
                )
                quantities["plasma_frequency"] = _quantity(
                    wp_rad_s,
                    "rad/s",
                    "wp = 1/sqrt(Lj*Cj)",
                    _source(gds, jj_box),
                    "estimated",
                    0.82,
                )

    trace_width = info.get("trace_width_um") or info.get("cpw_trace_width_um")
    gap = info.get("gap_um") or info.get("cpw_gap_um")
    length = info.get("electrical_length_um") or info.get("meander_length_um") or info.get("length_um") or info.get("cpw_length_um")
    eps_eff = info.get("effective_permittivity") or 6.2
    if trace_width is not None and gap is not None and length is not None:
        if info.get("z0_ohm") is not None and info.get("phase_velocity_m_per_s") is not None:
            z0 = float(info["z0_ohm"])
            vp = float(info["phase_velocity_m_per_s"])
        else:
            cpw = synthesize_cpw(
                center_width_um=float(trace_width),
                gap_um=float(gap),
                ground_width_um=float(info.get("ground_width_um", 500.0)),
                epsilon_r=float(eps_eff),
                substrate_thickness_um=float(info.get("substrate_thickness_um", 254.0)),
                frequency_ghz=float(info.get("target_frequency_ghz", info.get("center_frequency_ghz", 6.0))),
                target_impedance_ohm=float(info.get("target_impedance_ohm", 50.0)),
                impedance_tolerance_ohm=float(info.get("impedance_tolerance_ohm", 50.0)),
            )
            z0 = float(cpw["impedance_ohm"])
            vp = float(cpw["phase_velocity_m_per_s"])
        c_per_m = 1.0 / (z0 * vp)
        l_per_m = z0 / vp
        f0 = vp / (4.0 * float(length) * 1e-6)
        src = _source(gds, signal_box, ports=ports, note="CPW dimensions from sidecar and GDS dominant conductor")
        quantities["cpw_capacitance_per_meter"] = _quantity(c_per_m, "F/m", "C' = 1/(Z0*vp)", src, "estimated", 0.82)
        quantities["cpw_inductance_per_meter"] = _quantity(l_per_m, "H/m", "L' = Z0/vp", src, "estimated", 0.82)
        quantities["cpw_impedance"] = _quantity(z0, "ohm", "Z0 = sqrt(L'/C')", src, "estimated", 0.86)
        quantities["cpw_phase_velocity"] = _quantity(vp, "m/s", "vp = 1/sqrt(L'*C')", src, "estimated", 0.86)
        quantities["cpw_quarter_wave_frequency"] = _quantity(f0, "Hz", "f0 = vp/(4*l)", src, "estimated", 0.86)

    status: Literal["ok", "partial", "failed"] = "ok" if not issues else "partial"
    if not boxes:
        status = "failed"
        issues.append("no polygons extracted from GDS")

    device = ExtractedDevice(
        status=status,
        device=_device_name(sidecar_data),
        gds_path=str(gds),
        layer_map=_layer_map(),
        process_stack=DEFAULT_PROCESS.to_dict(),
        polygons=boxes,
        ports=ports,
        quantities=quantities,
        issues=issues,
    )
    payload = device.model_dump(mode="json")
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["output_path"] = str(out)
    return payload
