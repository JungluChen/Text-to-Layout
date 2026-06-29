"""Physical design review: professional layout analysis for superconducting devices.

Replaces "Looks OK" with specific, actionable findings that an experienced
quantum IC designer would catch during a layout review.
"""

from __future__ import annotations

from typing import Any

from text_to_gds.review.base import finding, review_result

_AGENT = "layout_design_review"


def review_layout_design(
    evidence: dict[str, Any],
    *,
    topology: dict[str, Any] | None = None,
    geometry_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Professional physical design review.

    Parameters
    ----------
    evidence:
        Standard evidence dict with sidecar, gds_path, etc.
    topology:
        Output of ``recognize_topology()``.
    geometry_features:
        Output of ``analyze_geometry()``.

    Returns
    -------
    dict with agent, passed, score, findings.
    """
    sidecar = evidence.get("sidecar") or {}
    info = sidecar.get("info") or {}
    ports = sidecar.get("ports") or []
    findings: list[dict[str, Any]] = []

    # ─── Current crowding risk ─────────────────────────────────────────────
    if geometry_features:
        bottlenecks = geometry_features.get("current_bottlenecks", {})
        for bn in bottlenecks.get("bottlenecks", []):
            severity = "error" if bn.get("risk") == "high" else "warning"
            findings.append(finding(
                _AGENT, severity,
                f"Current crowding risk: {bn['name']} has min width {bn['min_width_um']:.2f} um "
                f"({bn.get('reason', '')}).",
                "Widen the narrow region or add current spreading geometry.",
            ))

    # ─── Flux line too close to SQUID ──────────────────────────────────────
    if topology:
        features = topology.get("features", {})
        if features.get("squid_separation_um") is not None:
            flux_ports = [p for p in ports if any(
                kw in str(p.get("name", "")).lower()
                for kw in ("flux", "bias", "coil", "dc")
            )]
            for fp in flux_ports:
                # Check if flux line is too close (would cause excessive coupling)
                # This is a simplified check; real implementation needs geometry
                findings.append(finding(
                    _AGENT, "info",
                    f"Flux line '{fp.get('name', '')}' present; verify mutual coupling "
                    "region distance from SQUID loop is appropriate.",
                    "Flux line should be 3-10 um from SQUID edge for typical coupling.",
                ))

    # ─── Ground discontinuity ──────────────────────────────────────────────
    if geometry_features:
        ground_info = geometry_features.get("ground_pocket", {})
        if not ground_info.get("has_ground_plane"):
            findings.append(finding(
                _AGENT, "error",
                "No ground plane detected; ground return path is undefined.",
                "Add ground plane with via stitching to ensure return current path.",
            ))
        elif ground_info.get("total_ground_area_um2", 0) < 10000:
            findings.append(finding(
                _AGENT, "warning",
                f"Ground plane area ({ground_info['total_ground_area_um2']:.0f} um^2) "
                "is small; may have poor ground return.",
                "Increase ground plane coverage around active device region.",
            ))

    # ─── IDC bus too narrow ────────────────────────────────────────────────
    if geometry_features:
        idc_info = geometry_features.get("capacitor_paddles", {})
        for paddle in idc_info.get("paddles", []):
            w = paddle.get("width_um", 0)
            if 0 < w < 5.0:
                findings.append(finding(
                    _AGENT, "warning",
                    f"IDC bus width {w:.1f} um may be too narrow for reliable fabrication.",
                    "Widen bus to >5 um or add taper from CPW width.",
                ))

    # ─── Launch transition mismatch ────────────────────────────────────────
    if geometry_features:
        launches = geometry_features.get("launch_transitions", {})
        for launch in launches.get("launches", []):
            port_width = launch.get("width_um")
            cpw_width = info.get("trace_width_um") or info.get("cpw_trace_width_um")
            if port_width and cpw_width:
                ratio = float(port_width) / float(cpw_width)
                if ratio > 5.0:
                    findings.append(finding(
                        _AGENT, "warning",
                        f"Launch pad width ({port_width:.0f} um) is {ratio:.0f}x "
                        f"wider than CPW ({cpw_width:.0f} um); large impedance mismatch.",
                        "Add a tapered transition between launch pad and CPW trace.",
                    ))

    # ─── Airbridge spacing ─────────────────────────────────────────────────
    if geometry_features:
        bridges = geometry_features.get("airbridge_span", {})
        if bridges.get("count", 0) == 0:
            cpw_count = topology.get("features", {}).get("cpw_count", 0) if topology else 0
            if cpw_count > 0:
                findings.append(finding(
                    _AGENT, "warning",
                    "No airbridges detected on CPW lines; may support slotline mode.",
                    "Add airbridges every 100-200 um across CPW to suppress slotline mode.",
                ))

    # ─── Potential slotline mode ───────────────────────────────────────────
    if geometry_features:
        cpw_bends = geometry_features.get("cpw_bends", {})
        if cpw_bends.get("count", 0) > 0:
            # Check for asymmetric ground
            discontinuities = geometry_features.get("cpw_discontinuities", {})
            if discontinuities.get("count", 0) > 0:
                findings.append(finding(
                    _AGENT, "warning",
                    "CPW discontinuities detected; potential slotline mode excitation.",
                    "Ensure symmetric ground on both sides of CPW; add airbridges.",
                ))

    # ─── Large floating metal ──────────────────────────────────────────────
    if geometry_features:
        overall_area = geometry_features.get("overall_area_um2", 0.0)
        if overall_area > 1e7:  # > 10 mm^2
            findings.append(finding(
                _AGENT, "warning",
                f"Large chip area ({overall_area:.0f} um^2); check for floating metal islands.",
                "Verify all metal regions are DC grounded through via connections.",
            ))

    # ─── Ground return discontinuity ───────────────────────────────────────
    ground_stitch = info.get("ground_stitch_pitch_um")
    if ground_stitch is None and geometry_features:
        stitch = geometry_features.get("critical_dimensions", {})
        if not stitch.get("ground_stitch_pitch_um"):
            findings.append(finding(
                _AGENT, "info",
                "No ground stitching pitch specified; ground return quality unknown.",
                "Specify ground stitching via pitch (typically 30-50 um).",
            ))

    # ─── Missing wirebond pads ─────────────────────────────────────────────
    port_names_lower = [str(p.get("name", "")).lower() for p in ports]
    has_gnd_port = any("gnd" in n or "ground" in n for n in port_names_lower)
    if not has_gnd_port and len(ports) >= 2:
        findings.append(finding(
            _AGENT, "warning",
            "No ground wirebond pad detected; return current path may be inadequate.",
            "Add dedicated ground wirebond pads near RF launch points.",
        ))

    result = review_result(_AGENT, findings)
    if geometry_features:
        result["geometry_summary"] = {
            "capacitor_paddles": geometry_features.get("capacitor_paddles", {}).get("count", 0),
            "current_bottlenecks": geometry_features.get("current_bottlenecks", {}).get("count", 0),
            "launch_transitions": geometry_features.get("launch_transitions", {}).get("count", 0),
            "overall_area_um2": geometry_features.get("overall_area_um2", 0.0),
        }
    return result
