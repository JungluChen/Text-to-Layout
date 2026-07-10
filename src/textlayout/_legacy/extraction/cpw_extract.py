"""CPW-specific geometry extraction from GDS."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from textlayout._legacy.extraction.boolean_extract import _load_region
from textlayout._legacy.extraction.provenance import ExtractionProvenance

Layer = tuple[int, int]

# Speed of light for analytical Z0
_C0 = 2.99792458e8


def _cpw_z0_analytical(
    trace_width_um: float,
    gap_um: float,
    epsilon_r: float = 11.45,
) -> float:
    """Conformal-mapping CPW impedance (infinite substrate approximation)."""
    w = trace_width_um
    g = gap_um
    k = w / (w + 2.0 * g)
    k = min(max(k, 1e-12), 1.0 - 1e-12)
    k_prime = math.sqrt(1.0 - k * k)
    # K(k') via AGM(1, k)
    a_kp, b_kp = 1.0, k_prime
    for _ in range(60):
        a_kp, b_kp = (a_kp + b_kp) / 2.0, math.sqrt(a_kp * b_kp)
        if abs(a_kp - b_kp) < 1e-15:
            break
    kk_prime = math.pi / (2.0 * a_kp)  # K(k')
    # K(k) via AGM(1, k')
    ak, bk = 1.0, math.sqrt(1.0 - k * k)
    for _ in range(60):
        ak, bk = (ak + bk) / 2.0, math.sqrt(ak * bk)
        if abs(ak - bk) < 1e-15:
            break
    kk = math.pi / (2.0 * ak)  # K(k)
    epsilon_eff = (1.0 + epsilon_r) / 2.0
    ratio = kk_prime / kk  # K(k')/K(k)
    z0 = 30.0 * math.pi * ratio / math.sqrt(epsilon_eff)
    return z0


@dataclass
class CPWExtraction:
    """Extracted CPW geometry and derived parameters."""

    trace_width_um: float
    gap_um: float
    length_um: float
    z0_ohm: float
    ground_continuous: bool
    signal_ground_overlap_area_um2: float
    provenance: ExtractionProvenance


def extract_cpw_parameters(
    gds_path: str | Path,
    signal_layer: Layer,
    ground_layer: Layer,
    epsilon_r: float = 11.45,
) -> CPWExtraction:
    """Measure trace width, gap, length from GDS and compute analytical Z0."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    dbu = float(layout.dbu)

    signal_region = _load_region(layout, signal_layer)
    ground_region = _load_region(layout, ground_layer)

    # Signal bbox gives trace width (min dimension) and length (max dimension)
    if signal_region.is_empty():
        raise ValueError(f"No shapes found on signal layer {signal_layer}")

    sig_bbox = signal_region.bbox()
    w = float(sig_bbox.width()) * dbu
    h = float(sig_bbox.height()) * dbu
    trace_width_um = min(w, h)
    length_um = max(w, h)

    # Gap: distance from signal bbox edge to nearest ground edge
    gap_um = 0.0
    if not ground_region.is_empty():
        # Use the separation between signal and ground regions
        sep = signal_region.separation_check(ground_region, 0)
        min_sep = float("inf")
        for edge_pair in sep.each():
            d = float(edge_pair.distance) * dbu
            if d < min_sep:
                min_sep = d
        if math.isfinite(min_sep) and min_sep > 0:
            gap_um = min_sep
        else:
            # Fallback: measure from ground bbox
            gnd_bbox = ground_region.bbox()
            gnd_left = float(gnd_bbox.left) * dbu
            gnd_right = float(gnd_bbox.right) * dbu
            sig_left = float(sig_bbox.left) * dbu
            sig_right = float(sig_bbox.right) * dbu
            gap_candidates = [
                abs(sig_left - gnd_left),
                abs(gnd_right - sig_right),
            ]
            gap_um = min(c for c in gap_candidates if c > 0) if any(c > 0 for c in gap_candidates) else 0.0

    # Overlap area
    overlap = signal_region & ground_region
    overlap_area = sum(float(p.area()) * dbu * dbu for p in overlap.each())

    # Ground continuity
    ground_continuous = ground_region.merged().count() <= 1 if not ground_region.is_empty() else False

    # Analytical Z0
    z0 = _cpw_z0_analytical(trace_width_um, gap_um, epsilon_r) if gap_um > 0 else 0.0

    prov = ExtractionProvenance(
        method="extracted",
        source="klayout.db",
        formula="conformal_mapping_Z0(w, g, eps_r)",
        confidence=0.65,
        unit="ohm",
    )

    return CPWExtraction(
        trace_width_um=trace_width_um,
        gap_um=gap_um,
        length_um=length_um,
        z0_ohm=z0,
        ground_continuous=ground_continuous,
        signal_ground_overlap_area_um2=overlap_area,
        provenance=prov,
    )


def verify_cpw_gap_continuity(
    gds_path: str | Path,
    signal_layer: Layer,
    ground_layer: Layer,
) -> bool:
    """Check that signal and ground layers do not overlap."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    signal = _load_region(layout, signal_layer)
    ground = _load_region(layout, ground_layer)
    overlap = signal & ground
    return overlap.is_empty()


def verify_ground_plane_connectivity(
    gds_path: str | Path,
    ground_layer: Layer,
) -> bool:
    """Check that the ground plane is a single contiguous region."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    region = _load_region(layout, ground_layer)
    if region.is_empty():
        return False
    return region.merged().count() == 1
