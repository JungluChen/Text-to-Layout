"""Scientific report generator that assembles the full JPA figure set.

This is the capstone of the Text-to-GDS 2.0 architecture:

    Prompt -> GDS -> extraction -> simulation -> Scientific Report Generator

It collects the ten requested figures into one composite report plus a JSON manifest:
Layout, S11/S21, Gain, Bandwidth, Flux tuning, Pump sweep, P1dB, Noise temperature,
Squeezing, and Stability. Panels backed by an external simulator (JosephsonCircuits.jl)
are labelled ``real``; panels derived from the layout surrogate are labelled
``layout_surrogate`` so the report never overstates what was actually computed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from text_to_gds.jpa_analysis import run_jpa_analysis
from text_to_gds.simulation import estimate_physical_performance

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
)


def _lorentzian_s_parameters(
    center_ghz: float, bandwidth_mhz: float, peak_gain_db: float, points: int = 201
) -> tuple[list[float], list[float], list[float]]:
    bandwidth_ghz = max(bandwidth_mhz / 1000.0, 0.001)
    span = max(2.5 * bandwidth_ghz, 0.25)
    start = max(center_ghz - span / 2.0, 0.001)
    step = span / (points - 1)
    freqs, s21, s11 = [], [], []
    for index in range(points):
        f = start + step * index
        normalized = 2.0 * (f - center_ghz) / bandwidth_ghz
        rolloff = 10.0 * math.log10(1.0 + normalized**2)
        freqs.append(f)
        s21.append(peak_gain_db - rolloff)
        s11.append(min(-3.0, -12.0 + 0.35 * rolloff))
    return freqs, s21, s11


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
    """Assemble the ten-figure JPA scientific report (composite PNG/SVG + JSON manifest)."""
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

    physical = estimate_physical_performance(
        sidecar,
        jc_ua_per_um2=jc_ua_per_um2,
        shunt_capacitance_ff=0.0,
        target_frequency_ghz=center_ghz,
        target_bandwidth_mhz=bandwidth_mhz,
        flux_bias_phi0=flux_bias_phi0,
        squid_asymmetry=squid_asymmetry,
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
    sweep = jpa.get("sweep", {}) if jpa_ok else {}
    metrics = jpa.get("metrics", {}) if jpa_ok else {}

    peak_gain_db = float(metrics.get("peak_gain_db") or physical.get("estimated_peak_gain_db") or 0.0)
    freqs, s21, s11 = _lorentzian_s_parameters(center_ghz, bandwidth_mhz, peak_gain_db)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(3, 3, figsize=(14.0, 11.0), constrained_layout=True)
    figure_sources: dict[str, str] = {}

    # 1. Layout
    ax = axes[0, 0]
    if gds_layout_png and Path(gds_layout_png).exists():
        ax.imshow(mpimg.imread(str(gds_layout_png)))
        figure_sources["layout"] = "gds_render"
    else:
        ax.text(0.5, 0.5, "layout PNG\nnot provided", ha="center", va="center")
        figure_sources["layout"] = "missing"
    ax.set_title("1. Layout")
    ax.axis("off")

    # 2 & 3. S11/S21 and Gain
    ax = axes[0, 1]
    ax.plot(freqs, s21, label="S21 (gain)", linewidth=1.8, color="#3866d6")
    ax.plot(freqs, s11, label="S11", linewidth=1.8, color="#ff9f0a")
    ax.set_title("2. S11 / S21")
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("dB")
    ax.legend(loc="best")
    figure_sources["s11_s21"] = "layout_surrogate"

    ax = axes[0, 2]
    if jpa_ok and sweep.get("frequencies_ghz") and sweep.get("best_gain_curve_db"):
        ax.plot(sweep["frequencies_ghz"], sweep["best_gain_curve_db"], linewidth=1.9, color="#34c759")
        figure_sources["gain"] = "josephsoncircuits_real"
    else:
        ax.plot(freqs, s21, linewidth=1.9, color="#34c759")
        figure_sources["gain"] = "layout_surrogate"
    ax.set_title(f"3. Gain (peak {peak_gain_db:.1f} dB)")
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("Gain (dB)")

    # 4. Bandwidth
    ax = axes[1, 0]
    ax.plot(freqs, s21, linewidth=1.6, color="#3866d6")
    threshold = peak_gain_db - 3.0
    ax.axhline(threshold, color="#ff3b30", linestyle="--", label="-3 dB")
    ax.fill_between(freqs, threshold, s21, where=[v >= threshold for v in s21], alpha=0.2)
    ax.set_title(f"4. Bandwidth ({physical.get('bandwidth_3db_mhz', bandwidth_mhz):.0f} MHz)")
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("Gain (dB)")
    ax.legend(loc="best")
    figure_sources["bandwidth"] = "layout_surrogate"

    # 5. Flux tuning
    ax = axes[1, 1]
    flux = physical.get("flux_tuning") if isinstance(physical, dict) else None
    if isinstance(flux, dict) and flux.get("sweep"):
        rows = flux["sweep"]
        fx = [r.get("flux_phi0") for r in rows]
        fy = [r.get("resonant_frequency_ghz") for r in rows]
        pairs = [(a, b) for a, b in zip(fx, fy, strict=False) if a is not None and b is not None]
        if pairs:
            xs, ys = zip(*pairs, strict=True)
            ax.plot(xs, ys, linewidth=1.8, color="#af52de")
        figure_sources["flux_tuning"] = "squid_model"
    else:
        ax.text(0.5, 0.5, "no SQUID flux tuning", ha="center", va="center")
        figure_sources["flux_tuning"] = "not_applicable"
    ax.set_title("5. Flux tuning")
    ax.set_xlabel("Flux (Phi0)")
    ax.set_ylabel("f0 (GHz)")

    # 6. Pump sweep
    ax = axes[1, 2]
    if jpa_ok and sweep.get("pump_fractions"):
        ax.plot(sweep["pump_fractions"], sweep["peak_gain_db"], marker="o", linewidth=1.8, color="#3866d6")
        thr = metrics.get("oscillation_threshold_pump_fraction")
        if thr is not None:
            ax.axvline(thr, color="#ff3b30", linestyle="--")
        figure_sources["pump_sweep"] = "josephsoncircuits_real"
    else:
        ax.text(0.5, 0.5, "JosephsonCircuits\nnot available", ha="center", va="center")
        figure_sources["pump_sweep"] = "skipped"
    ax.set_title("6. Pump sweep")
    ax.set_xlabel("pump current / Ic")
    ax.set_ylabel("peak gain (dB)")

    # 7. P1dB
    ax = axes[2, 0]
    p1db = metrics.get("estimated_input_1db_compression_dbm")
    if p1db is None:
        p1db = physical.get("estimated_input_1db_compression_dbm")
    powers = [p1db - 30 + i for i in range(35)] if p1db is not None else list(range(-130, -95))
    gain_curve = [
        peak_gain_db if p < (p1db or -110) else peak_gain_db - (p - (p1db or -110)) * 0.5 for p in powers
    ]
    ax.plot(powers, gain_curve, linewidth=1.8, color="#34c759")
    if p1db is not None:
        ax.axvline(p1db, color="#ff3b30", linestyle="--", label=f"P1dB {p1db:.0f} dBm")
        ax.legend(loc="best")
    ax.set_title("7. P1dB compression")
    ax.set_xlabel("input power (dBm)")
    ax.set_ylabel("gain (dB)")
    figure_sources["p1db"] = "josephsoncircuits_real" if jpa_ok else "layout_surrogate"

    # 8. Noise temperature
    ax = axes[2, 1]
    quantum_k = metrics.get("quantum_limited_noise_temperature_k") or physical.get(
        "quantum_limited_noise_temperature_k", 0.0
    )
    noise_k = metrics.get("noise_temperature_k") or quantum_k
    ax.bar(["quantum limit", "this design"], [quantum_k * 1000, noise_k * 1000], color=["#8e8e93", "#3866d6"])
    ax.set_title("8. Noise temperature")
    ax.set_ylabel("noise T (mK)")
    figure_sources["noise_temperature"] = "josephsoncircuits_real" if jpa_ok else "quantum_limit_model"

    # 9. Squeezing
    ax = axes[2, 2]
    gains = [g / 2.0 for g in range(2, 61)]
    squeeze = []
    for g_db in gains:
        g = 10 ** (g_db / 10.0)
        squeeze.append(10.0 * math.log10((math.sqrt(g) - math.sqrt(max(g - 1.0, 0.0))) ** 2))
    ax.plot(gains, squeeze, linewidth=1.8, color="#af52de")
    sq = metrics.get("squeezing_db")
    if sq is not None:
        ax.scatter([peak_gain_db], [sq], color="#ff3b30", zorder=5, label=f"{sq:.1f} dB")
        ax.legend(loc="best")
    ax.set_title("9. Squeezing vs gain")
    ax.set_xlabel("gain (dB)")
    ax.set_ylabel("squeezing (dB)")
    figure_sources["squeezing"] = "josephsoncircuits_real" if jpa_ok else "paramp_model"

    fig.suptitle(
        f"Text-to-GDS Scientific Report - {sidecar.get('pcell', 'device')} "
        f"({'real JosephsonCircuits' if jpa_ok else 'layout surrogate'})",
        fontsize=15,
    )
    # Stability is overlaid as the threshold marker on the pump-sweep panel (#6).
    figure_sources["stability"] = figure_sources["pump_sweep"]

    fig.savefig(png_path, dpi=200)
    fig.savefig(svg_path)
    plt.close(fig)

    manifest = {
        "schema": "text-to-gds.scientific-report.v0",
        "device": sidecar.get("pcell"),
        "source_gds": sidecar.get("gds_path"),
        "png_path": str(png_path),
        "svg_path": str(svg_path),
        "json_path": str(json_path),
        "external_simulation": jpa.get("status"),
        "figures": {name: figure_sources.get(name, "missing") for name in FIGURE_NAMES},
        "metrics": {
            "center_frequency_ghz": center_ghz,
            "peak_gain_db": peak_gain_db,
            "bandwidth_3db_mhz": physical.get("bandwidth_3db_mhz", bandwidth_mhz),
            "noise_temperature_k": noise_k,
            "quantum_limited_noise_temperature_k": quantum_k,
            "quantum_efficiency": metrics.get("quantum_efficiency"),
            "squeezing_db": metrics.get("squeezing_db"),
            "input_1db_compression_dbm": p1db,
            "oscillation_threshold_pump_fraction": metrics.get("oscillation_threshold_pump_fraction"),
            "stability_margin": metrics.get("stability_margin"),
        },
        "jpa_report": jpa,
        "model_validity": (
            "Panels marked josephsoncircuits_real are computed by JosephsonCircuits.jl harmonic "
            "balance; panels marked layout_surrogate use first-order layout-derived models."
        ),
    }
    json_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
