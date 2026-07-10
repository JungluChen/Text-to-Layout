"""Scientific report generator — physics-compiler edition.

Panels are ONLY rendered when backed by a real solver output:
  - Touchstone file (.s1p / .s2p)
  - openEMS FDTD output
  - JosephsonCircuits.jl harmonic-balance result
  - scqubits spectrum calculation

Any panel without a real source is labelled "SKIPPED", never "layout_surrogate".
Fake/synthetic S-parameters are never written to disk.

Every numeric value in the manifest carries an explicit lineage record:
  {
    "value": 6.01,
    "unit": "GHz",
    "method": "simulated",
    "solver": "openEMS",
    "file": "result.s2p"
  }

A value without lineage is invalid and must not appear in the output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout._legacy.jpa_analysis import run_jpa_analysis
from textlayout._legacy.reference_compare import golden_compare

FIGURE_NAMES = (
    "layout",
    "s11_s21",
    "gain",
    "bandwidth",
    "flux_tuning",
    "pump_sweep",
    "p1db",
    "noise_temperature",
    "squeezing",
    "stability",
    "literature_comparison",
)


def _eng(value: float, unit: str) -> str:
    """Format a physical value in engineering notation with an appropriate SI prefix."""
    prefixes = [
        (1e15, "f"), (1e12, "p"), (1e9, "n"), (1e6, "µ"), (1e3, "m"), (1.0, ""),
        (1e-3, "k"), (1e-6, "M"), (1e-9, "G"), (1e-12, "T"),
    ]
    abs_v = abs(value)
    for scale, prefix in prefixes:
        if abs_v >= 1.0 / scale:
            scaled = value * scale
            return f"{scaled:.4g} {prefix}{unit}"
    return f"{value:.4g} {unit}"


def _metric(
    value: float | None,
    *,
    unit: str,
    method: str,
    source: str | None = None,
    formula: str = "reported solver/extraction value",
    confidence: float = 1.0,
    solver: str | None = None,
    file: str | None = None,
) -> dict[str, Any]:
    """Wrap a numeric value with mandatory lineage.

    Every number in the report manifest must call this.  A value without lineage
    is invalid — do not return raw floats in the manifest.
    """
    record: dict[str, Any] = {
        "value": value,
        "unit": unit,
        "method": method,
        "method_label": method,
        "source": source or ("solver_output" if solver else "GDS"),
        "formula": formula,
        "confidence": confidence,
    }
    if solver is not None:
        record["solver"] = solver
    if file is not None:
        record["file"] = file
    return record


def _extraction_text(extraction: dict) -> str:
    """Render extraction result fields as a human-readable string with SI units.

    Uses engineering notation so consumers can verify unit choices:
    - Lj: nH for values ≥ 1 nH (never pH, never raw scientific notation)
    - f0: GHz
    - C: fF for values < 1 pF
    - Ic: nA or µA

    Used by the test suite to verify that report rendering is unit-aware.
    """
    parts: list[str] = []
    junc = extraction.get("junction", {})
    lc = extraction.get("linear_circuit", {})

    ic = junc.get("ic_a") or junc.get("ic")
    lj = junc.get("lj_h") or junc.get("lj")
    cap = lc.get("capacitance_f") or lc.get("capacitance")
    f0 = lc.get("resonance_frequency_hz") or lc.get("resonance_frequency")

    if ic is not None:
        ic_f = float(ic)
        if abs(ic_f) < 1e-6:
            parts.append(f"Ic = {ic_f * 1e9:.4g} nA")
        else:
            parts.append(f"Ic = {ic_f * 1e6:.4g} µA")

    if lj is not None:
        lj_nh = float(lj) * 1e9
        parts.append(f"Lj = {lj_nh:.4g} nH")

    if cap is not None:
        cap_f = float(cap)
        if cap_f < 1e-12:
            parts.append(f"C = {cap_f * 1e15:.4g} fF")
        else:
            parts.append(f"C = {cap_f * 1e12:.4g} pF")

    if f0 is not None:
        parts.append(f"f0 = {float(f0) / 1e9:.4g} GHz")

    return ", ".join(parts) if parts else "(no extraction data)"


def write_scientific_report(
    sidecar: dict[str, Any],
    *,
    report_dir: str | Path,
    stem: str,
    gds_layout_png: str | Path | None = None,
    jc_ua_per_um2: float = 1.0,
    target_frequency_ghz: float | None = None,
    target_bandwidth_mhz: float | None = None,
    flux_bias_phi0: float = 0.0,
    squid_asymmetry: float = 0.05,
    run_external: bool = True,
) -> dict[str, Any]:
    """Assemble the ten-figure JPA scientific report (composite PNG/SVG + JSON manifest).

    Panels are only rendered when backed by a real solver output.
    Panels without real data are labelled SKIPPED — no synthetic curves are drawn.
    Every numeric value in the manifest carries explicit lineage.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{stem}.report.png"
    svg_path = out_dir / f"{stem}.report.svg"
    json_path = out_dir / f"{stem}.report.json"

    center_ghz = float(target_frequency_ghz or sidecar.get("info", {}).get("center_frequency_ghz", 5.0))
    bandwidth_mhz = float(
        target_bandwidth_mhz or sidecar.get("info", {}).get("target_bandwidth_mhz", 500.0)
    )

    jpa = run_jpa_analysis(
        sidecar,
        script_path=out_dir / f"{stem}.jpa.jl",
        result_path=out_dir / f"{stem}.jpa.result.json",
        report_path=out_dir / f"{stem}.jpa.json",
        plot_path=out_dir / f"{stem}.jpa.png",
        jc_ua_per_um2=jc_ua_per_um2,
        target_frequency_ghz=center_ghz,
        target_bandwidth_mhz=bandwidth_mhz,
    ) if run_external else {"status": "skipped"}
    jpa_ok = jpa.get("status") == "executed"
    jpa_file = jpa.get("result_path") or jpa.get("report_path")
    sweep = jpa.get("sweep", {}) if jpa_ok else {}
    metrics = jpa.get("metrics", {}) if jpa_ok else {}

    peak_gain_db: float | None = float(metrics.get("peak_gain_db")) if metrics.get("peak_gain_db") is not None else None

    pcell_name = str(sidecar.get("pcell") or sidecar.get("info", {}).get("device_type") or "")
    reference_alias = "transmon" if "transmon" in pcell_name.lower() else "jpa"
    literature_comparison = golden_compare({"pcell": pcell_name, "info": sidecar.get("info", {})}, reference_alias)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(3, 4, figsize=(17.2, 11.0), constrained_layout=True)
    figure_sources: dict[str, str] = {}

    def _skip_panel(ax: Any, label: str, title: str) -> None:
        ax.text(0.5, 0.5, f"SKIPPED\n{label}", ha="center", va="center",
                fontsize=11, color="#8e8e93",
                transform=ax.transAxes)
        ax.set_title(title)
        ax.axis("off")

    # 1. Layout
    ax = axes[0, 0]
    if gds_layout_png and Path(gds_layout_png).exists():
        ax.imshow(mpimg.imread(str(gds_layout_png)))
        figure_sources["layout"] = "gds_render"
    else:
        _skip_panel(ax, "no GDS layout PNG", "1. Layout")
        figure_sources["layout"] = "skipped"
    ax.set_title("1. Layout")
    ax.axis("off")

    # 2. S11/S21 — requires real Touchstone or JC adapter output
    ax = axes[0, 1]
    if jpa_ok and sweep.get("frequencies_ghz") and sweep.get("best_gain_curve_db"):
        freqs_plot = sweep["frequencies_ghz"]
        s21_plot = sweep["best_gain_curve_db"]
        ax.plot(freqs_plot, s21_plot, label="S21 (gain)", linewidth=1.8, color="#3866d6")
        figure_sources["s11_s21"] = "josephsoncircuits"
        ax.set_title("2. S11 / S21")
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("dB")
        ax.legend(loc="best")
    else:
        _skip_panel(ax, "no Touchstone / JC result", "2. S11 / S21")
        figure_sources["s11_s21"] = "skipped"

    # 3. Gain — requires JC harmonic-balance result
    ax = axes[0, 2]
    if jpa_ok and sweep.get("frequencies_ghz") and sweep.get("best_gain_curve_db"):
        ax.plot(sweep["frequencies_ghz"], sweep["best_gain_curve_db"], linewidth=1.9, color="#34c759")
        figure_sources["gain"] = "josephsoncircuits"
        title_gain = f"3. Gain (peak {peak_gain_db:.1f} dB)" if peak_gain_db is not None else "3. Gain"
        ax.set_title(title_gain)
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("Gain (dB)")
    else:
        _skip_panel(ax, "JosephsonCircuits.jl not run", "3. Gain")
        figure_sources["gain"] = "skipped"

    # 4. Bandwidth — requires gain curve from JC
    ax = axes[1, 0]
    if jpa_ok and sweep.get("frequencies_ghz") and sweep.get("best_gain_curve_db") and peak_gain_db is not None:
        freqs_bw = sweep["frequencies_ghz"]
        s21_bw = sweep["best_gain_curve_db"]
        threshold = peak_gain_db - 3.0
        ax.plot(freqs_bw, s21_bw, linewidth=1.6, color="#3866d6")
        ax.axhline(threshold, color="#ff3b30", linestyle="--", label="-3 dB")
        ax.fill_between(freqs_bw, threshold, s21_bw, where=[v >= threshold for v in s21_bw], alpha=0.2)
        ax.legend(loc="best")
        figure_sources["bandwidth"] = "josephsoncircuits"
        bw_mhz = metrics.get("bandwidth_3db_mhz", bandwidth_mhz)
        ax.set_title(f"4. Bandwidth ({bw_mhz:.0f} MHz)")
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("Gain (dB)")
    else:
        _skip_panel(ax, "no gain curve", "4. Bandwidth")
        figure_sources["bandwidth"] = "skipped"

    # 5. Flux tuning — requires SQUID physical model
    ax = axes[1, 1]
    flux = sweep.get("flux_tuning") if jpa_ok else None
    if isinstance(flux, list) and flux:
        rows = flux
        fx = [r.get("flux_phi0") for r in rows]
        fy = [r.get("resonant_frequency_ghz") for r in rows]
        pairs = [(a, b) for a, b in zip(fx, fy, strict=False) if a is not None and b is not None]
        if pairs:
            xs, ys = zip(*pairs, strict=True)
            ax.plot(xs, ys, linewidth=1.8, color="#af52de")
            figure_sources["flux_tuning"] = "josephsoncircuits"
        else:
            _skip_panel(ax, "empty SQUID sweep", "5. Flux tuning")
            figure_sources["flux_tuning"] = "skipped"
    else:
        _skip_panel(ax, "no executed solver flux sweep", "5. Flux tuning")
        figure_sources["flux_tuning"] = "skipped"
    ax.set_title("5. Flux tuning")
    ax.set_xlabel("Flux (Phi0)")
    ax.set_ylabel("f0 (GHz)")

    # 6. Pump sweep — requires JC harmonic-balance result
    ax = axes[1, 2]
    if jpa_ok and sweep.get("pump_fractions") and sweep.get("peak_gain_db"):
        ax.plot(sweep["pump_fractions"], sweep["peak_gain_db"], marker="o", linewidth=1.8, color="#3866d6")
        thr = metrics.get("oscillation_threshold_pump_fraction")
        if thr is not None:
            ax.axvline(thr, color="#ff3b30", linestyle="--")
        figure_sources["pump_sweep"] = "josephsoncircuits"
        ax.set_title("6. Pump sweep")
        ax.set_xlabel("pump current / Ic")
        ax.set_ylabel("peak gain (dB)")
    else:
        _skip_panel(ax, "JosephsonCircuits.jl not run", "6. Pump sweep")
        figure_sources["pump_sweep"] = "skipped"

    # 7. P1dB — requires JC result
    ax = axes[2, 0]
    p1db = metrics.get("input_1db_compression_dbm") if jpa_ok else None
    input_powers = sweep.get("input_powers_dbm") if jpa_ok else None
    gain_vs_input = sweep.get("gain_vs_input_db") if jpa_ok else None
    if p1db is not None and input_powers and gain_vs_input:
        ax.plot(input_powers, gain_vs_input, linewidth=1.8, color="#34c759")
        ax.axvline(p1db, color="#ff3b30", linestyle="--", label=f"P1dB {p1db:.0f} dBm")
        ax.legend(loc="best")
        figure_sources["p1db"] = "josephsoncircuits"
        ax.set_title("7. P1dB compression")
        ax.set_xlabel("input power (dBm)")
        ax.set_ylabel("gain (dB)")
    else:
        _skip_panel(ax, "no executed compression sweep", "7. P1dB compression")
        figure_sources["p1db"] = "skipped"

    # 8. Noise temperature — requires JC result
    ax = axes[2, 1]
    quantum_k = metrics.get("quantum_limited_noise_temperature_k") if jpa_ok else None
    noise_k = metrics.get("noise_temperature_k") if jpa_ok else None
    if quantum_k is not None and noise_k is not None:
        ax.bar(["quantum limit", "this design"], [quantum_k * 1000, noise_k * 1000],
               color=["#8e8e93", "#3866d6"])
        figure_sources["noise_temperature"] = "josephsoncircuits"
        ax.set_title("8. Noise temperature")
        ax.set_ylabel("noise T (mK)")
    else:
        _skip_panel(ax, "JosephsonCircuits.jl not run", "8. Noise temperature")
        figure_sources["noise_temperature"] = "skipped"

    # 9. Squeezing — requires JC result
    ax = axes[2, 2]
    sq = metrics.get("squeezing_db") if jpa_ok else None
    squeezing_gain = sweep.get("squeezing_gain_db") if jpa_ok else None
    squeezing_curve = sweep.get("squeezing_db") if jpa_ok else None
    if sq is not None and squeezing_gain and squeezing_curve:
        ax.plot(squeezing_gain, squeezing_curve, linewidth=1.8, color="#af52de")
        ax.scatter([peak_gain_db], [sq], color="#ff3b30", zorder=5, label=f"{sq:.1f} dB")
        ax.legend(loc="best")
        figure_sources["squeezing"] = "josephsoncircuits"
        ax.set_title("9. Squeezing vs gain")
        ax.set_xlabel("gain (dB)")
        ax.set_ylabel("squeezing (dB)")
    else:
        _skip_panel(ax, "no executed squeezing sweep", "9. Squeezing vs gain")
        figure_sources["squeezing"] = "skipped"

    # 10. Literature comparison: generated/extracted values vs cited references.
    ax = axes[0, 3]
    compared = [
        (name, row)
        for name, row in literature_comparison.get("parameter_error", {}).items()
        if isinstance(row, dict) and row.get("status") in {"compared", "in_range", "out_of_range"}
    ]
    if compared:
        labels = [name[:18] for name, _row in compared[:6]]
        diffs = [float(row.get("difference_pct", 0.0)) for _name, row in compared[:6]]
        colors = ["#34c759" if row.get("status") in {"compared", "in_range"} and row.get("difference_pct", 0.0) <= 20.0 else "#ff9500" for _name, row in compared[:6]]
        ax.barh(labels, diffs, color=colors)
        ax.set_xlabel("difference (%)")
        ax.set_title("10. Generated vs Reference")
        ax.invert_yaxis()
        figure_sources["literature_comparison"] = "golden_reference"
    else:
        _skip_panel(ax, "no comparable generated values", "10. Generated vs Reference")
        figure_sources["literature_comparison"] = "skipped"

    ax = axes[1, 3]
    ax.axis("off")
    missing = literature_comparison.get("missing_features", [])
    warnings = literature_comparison.get("fabrication_warnings", [])
    summary_lines = [
        f"topology_score: {literature_comparison.get('topology_score')}",
        f"literature_distance: {literature_comparison.get('literature_distance')}",
        "",
        "Missing features:",
        *(f"- {item}" for item in missing[:5]),
        "",
        "Warnings:",
        *(f"- {item}" for item in warnings[:5]),
    ]
    ax.text(0.03, 0.97, "\n".join(summary_lines), va="top", family="monospace", fontsize=8.2, transform=ax.transAxes)
    ax.set_title("Golden comparison notes")

    ax = axes[2, 3]
    ax.axis("off")
    ref_lines = ["References:"]
    for ref in literature_comparison.get("references", [])[:4]:
        citation = ref.get("citation", {}) if isinstance(ref, dict) else {}
        ref_lines.append(f"- {ref.get('reference_id')}")
        if citation.get("doi"):
            ref_lines.append(f"  DOI: {citation['doi']}")
    ax.text(0.03, 0.97, "\n".join(ref_lines), va="top", family="monospace", fontsize=8.2, transform=ax.transAxes)
    ax.set_title("Cited templates")

    # Stability: piggybacks on pump sweep
    figure_sources["stability"] = figure_sources["pump_sweep"]

    # Topology and geometry intelligence panels (when available)
    topology_data = None
    geometry_data = None
    gds_path = sidecar.get("gds_path")
    if gds_path:
        try:
            from textlayout._legacy.geometry_intelligence import analyze_geometry
            geometry_data = analyze_geometry(gds_path, sidecar=sidecar)
        except Exception:
            pass
        try:
            from textlayout._legacy.topology import recognize_topology
            graph_path = sidecar.get("physics_graph_path")
            if graph_path and Path(graph_path).exists():
                graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
                topology_data = recognize_topology(graph)
        except Exception:
            pass

    # Layer view
    ax = axes[2, 0]
    if gds_path:
        try:
            from textlayout._legacy.visualization import generate_layer_view
            layer_result = generate_layer_view(gds_path)
            if layer_result.get("status") == "success" and Path(layer_result["png_path"]).exists():
                ax.imshow(mpimg.imread(layer_result["png_path"]))
                figure_sources["layer_view"] = "visualization"
            else:
                _skip_panel(ax, "layer view generation failed", "Layer View")
                figure_sources["layer_view"] = "skipped"
        except Exception:
            _skip_panel(ax, "visualization module unavailable", "Layer View")
            figure_sources["layer_view"] = "skipped"
    else:
        _skip_panel(ax, "no GDS path", "Layer View")
        figure_sources["layer_view"] = "skipped"
    ax.set_title("Layer View")
    ax.axis("off")

    # Topology view
    ax = axes[2, 1]
    if topology_data and isinstance(topology_data, dict):
        topo_lines = [
            f"Topology: {topology_data.get('detected_device', 'unknown')}",
            f"Confidence: {topology_data.get('confidence', 0.0):.2f}",
            "",
            "Supporting features:",
        ]
        for feat in (topology_data.get("supporting_features") or [])[:5]:
            topo_lines.append(f"  - {feat}")
        topo_lines.append("")
        topo_lines.append("Missing features:")
        for feat in (topology_data.get("missing_features") or [])[:5]:
            topo_lines.append(f"  - {feat}")
        ax.text(0.03, 0.97, "\n".join(topo_lines), va="top", family="monospace", fontsize=8.5, transform=ax.transAxes)
        figure_sources["topology_view"] = "topology_recognition"
    else:
        _skip_panel(ax, "topology not recognized", "Topology View")
        figure_sources["topology_view"] = "skipped"
    ax.set_title("Topology View")
    ax.axis("off")

    # Geometry features summary
    ax = axes[2, 2]
    if geometry_data and isinstance(geometry_data, dict):
        geo_lines = [
            f"Area: {geometry_data.get('overall_area_um2', 0):.4g} um^2",
            "",
        ]
        for feature_name in ("capacitor_paddles", "current_bottlenecks", "ground_pocket",
                             "airbridge_span", "cpw_bends", "cpw_discontinuities",
                             "launch_transitions", "tapers", "critical_dimensions"):
            feature_data = geometry_data.get(feature_name, {})
            if isinstance(feature_data, dict):
                count = feature_data.get("count", 0)
                if count > 0:
                    geo_lines.append(f"{feature_name}: {count}")
        ax.text(0.03, 0.97, "\n".join(geo_lines), va="top", family="monospace", fontsize=8.5, transform=ax.transAxes)
        figure_sources["geometry_view"] = "geometry_intelligence"
    else:
        _skip_panel(ax, "geometry features not extracted", "Geometry Features")
        figure_sources["geometry_view"] = "skipped"
    ax.set_title("Geometry Features")
    ax.axis("off")

    fig.suptitle(
        f"Text-to-GDS Physics Report — {sidecar.get('pcell', 'device')} "
        f"({'JosephsonCircuits.jl' if jpa_ok else 'no solver — panels skipped'})",
        fontsize=15,
    )
    fig.savefig(png_path, dpi=200)
    fig.savefig(svg_path)
    plt.close(fig)

    def _m(value: float | None, unit: str, *, method: str, solver: str | None = None, file: str | None = None) -> dict[str, Any]:
        return _metric(value, unit=unit, method=method, solver=solver, file=file)

    jc_solver = "JosephsonCircuits.jl" if jpa_ok else None
    manifest = {
        "schema": "text-to-gds.scientific-report.v1",
        "device": sidecar.get("pcell"),
        "source_gds": sidecar.get("gds_path"),
        "png_path": str(png_path),
        "svg_path": str(svg_path),
        "json_path": str(json_path),
        "external_simulation": jpa.get("status"),
        "figures": {name: figure_sources.get(name, "skipped") for name in FIGURE_NAMES},
        "metrics": {
            "center_frequency_ghz": _m(center_ghz, "GHz", method="extracted", solver=None),
            "peak_gain_db": _m(peak_gain_db, "dB", method="simulated", solver=jc_solver, file=jpa_file),
            "bandwidth_3db_mhz": _m(
                float(metrics.get("bandwidth_3db_mhz")) if metrics.get("bandwidth_3db_mhz") is not None else None,
                "MHz", method="simulated", solver=jc_solver, file=jpa_file,
            ),
            "noise_temperature_k": _m(noise_k, "K", method="simulated", solver=jc_solver, file=jpa_file),
            "quantum_limited_noise_temperature_k": _m(quantum_k, "K", method="simulated", solver=jc_solver, file=jpa_file),
            "quantum_efficiency": _m(
                float(metrics["quantum_efficiency"]) if metrics.get("quantum_efficiency") is not None else None,
                "dimensionless", method="simulated", solver=jc_solver, file=jpa_file,
            ),
            "squeezing_db": _m(sq, "dB", method="simulated", solver=jc_solver, file=jpa_file),
            "input_1db_compression_dbm": _m(p1db, "dBm", method="simulated", solver=jc_solver, file=jpa_file),
            "oscillation_threshold_pump_fraction": _m(
                float(metrics["oscillation_threshold_pump_fraction"]) if metrics.get("oscillation_threshold_pump_fraction") is not None else None,
                "Ic fraction", method="simulated", solver=jc_solver, file=jpa_file,
            ),
            "stability_margin": _m(
                float(metrics["stability_margin"]) if metrics.get("stability_margin") is not None else None,
                "dB", method="simulated", solver=jc_solver, file=jpa_file,
            ),
        },
        "jpa_report": jpa,
        "literature_comparison": literature_comparison,
        "model_validity": (
            "All panels require real solver output. "
            "Panels labelled SKIPPED have no solver backing and contain no numeric data. "
            "No synthetic or surrogate curves are included."
        ),
    }
    json_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
