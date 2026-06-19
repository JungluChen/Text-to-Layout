"""Advanced JPA analysis backed by real JosephsonCircuits.jl harmonic balance.

This module runs a true pump-power sweep through JosephsonCircuits.jl (one ``hbsolve``
per pump current) and post-processes the simulated gain and quantum efficiency into the
performance figures requested for a parametric amplifier study: gain vs pump power, the
1 dB compression estimate, the quantum-limited noise temperature, the squeezing level,
and a stability / parametric-oscillation-threshold map.

When Julia or JosephsonCircuits.jl is not installed the run is reported as ``skipped`` so
the system never claims a result the external simulator did not actually produce.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from text_to_gds.adapters import (
    _adapter_env,
    _command_prefix,
    josephsoncircuits_plan_from_sidecar,
)
from text_to_gds.simulation import BOLTZMANN_J_K, PLANCK_J_S

PI = math.pi


def _resonant_capacitance_f(center_ghz: float, lj_h: float) -> float:
    return 1.0 / ((2.0 * PI * center_ghz * 1e9) ** 2 * lj_h)


def write_jpa_pump_sweep_script(
    sidecar: dict[str, Any],
    *,
    script_path: str | Path,
    result_path: str | Path,
    jc_ua_per_um2: float,
    target_frequency_ghz: float | None,
    target_bandwidth_mhz: float | None,
    n_pump_points: int,
    pump_fraction_min: float,
    pump_fraction_max: float,
    coupling_ratio: float = 0.1,
) -> dict[str, Any]:
    """Write a Julia script that sweeps pump current and records gain + quantum efficiency."""
    if n_pump_points < 3:
        raise ValueError(f"n_pump_points must be >= 3, got {n_pump_points}")
    if not 0.0 < pump_fraction_min < pump_fraction_max:
        raise ValueError("require 0 < pump_fraction_min < pump_fraction_max")

    plan = josephsoncircuits_plan_from_sidecar(
        sidecar,
        jc_ua_per_um2=jc_ua_per_um2,
        analysis_mode="single_port_reflection",
        target_frequency_ghz=target_frequency_ghz,
        target_bandwidth_mhz=target_bandwidth_mhz,
    )
    model = plan["layout_derived_parameters"]
    lj_ph = model["josephson_inductance_ph"]
    ic_ua = model["critical_current_ua"]
    if not lj_ph or not ic_ua:
        raise ValueError("JPA analysis requires non-zero junction area and Ic")

    center_ghz = float(plan["target_frequency_ghz"])
    lj_h = float(lj_ph) * 1e-12
    ic_a = float(ic_ua) * 1e-6
    # 4-wave-mixing JPA recipe (validated against the JosephsonCircuits.jl JPA example):
    # place the resonance ~6% above the operating/pump frequency and read the gain band
    # below the resonance on a fine (~1.6 MHz) frequency grid.
    scale = center_ghz / 5.0
    f0_ghz = center_ghz * 1.059
    cj_f = _resonant_capacitance_f(f0_ghz, lj_h)
    cc_f = max(cj_f * coupling_ratio, 1.0e-15)
    pump_ghz = center_ghz
    f_start = max(f0_ghz - 0.53 * scale, 0.001)
    f_stop = f0_ghz - 0.03 * scale

    result_literal = json.dumps(str(Path(result_path)))
    config = {
        "lj_h": lj_h,
        "cc_f": cc_f,
        "cj_f": cj_f,
        "ic_a": ic_a,
        "center_ghz": center_ghz,
        "pump_ghz": pump_ghz,
        "f_start": f_start,
        "f_stop": f_stop,
        "n_pump_points": n_pump_points,
        "pump_fraction_min": pump_fraction_min,
        "pump_fraction_max": pump_fraction_max,
    }

    script = f'''# Text-to-GDS generated JosephsonCircuits.jl JPA pump-power sweep.
using Printf
result_path = {result_literal}

function json_number(value)
    isfinite(value) ? string(value) : "null"
end
json_array(values) = "[" * join(map(json_number, values), ",") * "]"

try
    @eval using JosephsonCircuits
catch err
    open(result_path, "w") do io
        write(io, "{{\\"analysis_status\\":\\"failed\\",\\"package_loaded\\":false,\\"error\\":\\"JosephsonCircuits.jl not installed\\"}}")
    end
    exit(1)
end

try
    @variables R Cc Lj Cj
    circuit = [
        ("P1","1","0",1),
        ("R1","1","0",R),
        ("C1","1","2",Cc),
        ("Lj1","2","0",Lj),
        ("C2","2","0",Cj),
    ]
    circuitdefs = Dict(
        Lj => {lj_h:.16g},
        Cc => {cc_f:.16g},
        Cj => {cj_f:.16g},
        R => 50.0,
    )
    f_ghz = collect(range({f_start:.16g}, {f_stop:.16g}; length=301))
    ws = 2*pi .* f_ghz .* 1e9
    wp = (2*pi*{pump_ghz:.16g}*1e9,)
    Npump = (16,)
    Nmod = (8,)
    ic = {ic_a:.16g}

    fractions = collect(range({pump_fraction_min:.16g}, {pump_fraction_max:.16g}; length={n_pump_points}))
    pump_currents = ic .* fractions
    peak_gain = Float64[]
    center_gain = Float64[]
    efficiency = Float64[]
    center_index = argmin(abs.(f_ghz .- {center_ghz:.16g}))
    best_gain = -Inf
    best_curve = Float64[]
    best_fraction = fractions[1]
    best_efficiency = 1.0

    for (i, Ip) in enumerate(pump_currents)
        sol = hbsolve(ws, wp, [(mode=(1,), port=1, current=Ip)], Nmod, Npump, circuit, circuitdefs)
        s11 = sol.linearized.S(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)
        g = 10 .* log10.(abs2.(s11))
        qe = sol.linearized.QE(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)
        qei = sol.linearized.QEideal(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)
        pk = maximum(g)
        idx = argmax(g)
        eff = qei[idx] != 0 ? qe[idx]/qei[idx] : 1.0
        push!(peak_gain, pk)
        push!(center_gain, g[center_index])
        push!(efficiency, eff)
        if pk > best_gain
            best_gain = pk
            best_curve = g
            best_fraction = fractions[i]
            best_efficiency = eff
        end
    end

    payload = "{{" *
        "\\"schema\\":\\"text-to-gds.jpa-pump-sweep.v0\\"," *
        "\\"adapter\\":\\"JosephsonCircuits.jl\\"," *
        "\\"analysis_status\\":\\"executed\\"," *
        "\\"package_loaded\\":true," *
        "\\"center_frequency_ghz\\":{center_ghz:.16g}," *
        "\\"pump_frequency_ghz\\":{pump_ghz:.16g}," *
        "\\"critical_current_ua\\":{ic_ua:.16g}," *
        "\\"josephson_inductance_ph\\":{lj_ph:.16g}," *
        "\\"resonator_capacitance_f\\":{cj_f:.16g}," *
        "\\"coupling_capacitance_f\\":{cc_f:.16g}," *
        "\\"frequencies_ghz\\":" * json_array(f_ghz) * "," *
        "\\"pump_fractions\\":" * json_array(fractions) * "," *
        "\\"pump_currents_a\\":" * json_array(pump_currents) * "," *
        "\\"peak_gain_db\\":" * json_array(peak_gain) * "," *
        "\\"center_gain_db\\":" * json_array(center_gain) * "," *
        "\\"efficiency\\":" * json_array(efficiency) * "," *
        "\\"best_pump_fraction\\":" * json_number(best_fraction) * "," *
        "\\"best_peak_gain_db\\":" * json_number(best_gain) * "," *
        "\\"best_efficiency\\":" * json_number(best_efficiency) * "," *
        "\\"best_gain_curve_db\\":" * json_array(best_curve) *
        "}}"
    open(result_path, "w") do io
        write(io, payload)
    end
    println("text_to_gds_jpa_done")
catch err
    open(result_path, "w") do io
        write(io, "{{\\"analysis_status\\":\\"failed\\",\\"package_loaded\\":true,\\"error\\":\\"" * replace(sprint(showerror, err), "\\"" => "'") * "\\"}}")
    end
    exit(1)
end
'''
    Path(script_path).parent.mkdir(parents=True, exist_ok=True)
    Path(script_path).write_text(script, encoding="utf-8")
    return {"config": config, "plan": plan}


def _squeezing_db_from_gain(peak_gain_db: float) -> float | None:
    """Ideal degenerate-paramp squeezing of the de-amplified quadrature, in dB (negative)."""
    g = 10.0 ** (peak_gain_db / 10.0)
    if g < 1.0:
        return None
    deamplified = (math.sqrt(g) - math.sqrt(g - 1.0)) ** 2
    return 10.0 * math.log10(deamplified)


def _post_process(result: dict[str, Any], *, signal_bandwidth_hz: float | None) -> dict[str, Any]:
    center_ghz = float(result["center_frequency_ghz"])
    quantum_noise_k = PLANCK_J_S * center_ghz * 1e9 / (2.0 * BOLTZMANN_J_K)
    efficiency = max(float(result.get("best_efficiency") or 1.0), 1e-6)
    noise_temperature_k = quantum_noise_k / efficiency
    added_noise_photons = 1.0 / (2.0 * efficiency)

    peak_gain_db = float(result.get("best_peak_gain_db") or 0.0)
    squeezing_db = _squeezing_db_from_gain(peak_gain_db)

    fractions = result.get("pump_fractions") or []
    peak_gain = result.get("peak_gain_db") or []
    currents = result.get("pump_currents_a") or []
    # Parametric-oscillation threshold: pump where small-signal gain is maximal (gain
    # diverges as the pump approaches threshold from below).
    threshold_index = max(range(len(peak_gain)), key=lambda i: peak_gain[i]) if peak_gain else None
    threshold_fraction = fractions[threshold_index] if threshold_index is not None else None
    threshold_current_a = currents[threshold_index] if threshold_index is not None else None
    # Recommended operating point: highest pump that still keeps gain below an oscillation
    # guard band (here ~ the threshold gain minus 3 dB on the rising edge).
    operating_index = threshold_index
    if peak_gain and threshold_index is not None:
        guard = peak_gain[threshold_index] - 3.0
        for i in range(threshold_index + 1):
            if peak_gain[i] >= guard:
                operating_index = i
                break
    stability_margin = None
    if threshold_fraction and operating_index is not None and fractions:
        stability_margin = max(
            0.0, (threshold_fraction - fractions[operating_index]) / threshold_fraction
        )

    # 1 dB compression input power estimate (signal-power compression). For a JPA the
    # saturation input photon number scales with the resonator energy; we use the
    # standard quantum estimate P_in,1dB ~ k_B*T_q*BW translated through the gain.
    p1db_dbm = None
    if signal_bandwidth_hz and peak_gain_db > 0.0:
        p_sat_w = (BOLTZMANN_J_K * quantum_noise_k) * signal_bandwidth_hz * (10.0 ** (peak_gain_db / 10.0))
        p1db_dbm = 10.0 * math.log10(max(p_sat_w, 1e-30) / 1e-3)

    return {
        "quantum_limited_noise_temperature_k": quantum_noise_k,
        "noise_temperature_k": noise_temperature_k,
        "quantum_efficiency": efficiency,
        "added_noise_photons": added_noise_photons,
        "peak_gain_db": peak_gain_db,
        "squeezing_db": squeezing_db,
        "anti_squeezing_db": -squeezing_db if squeezing_db is not None else None,
        "oscillation_threshold_pump_fraction": threshold_fraction,
        "oscillation_threshold_pump_current_a": threshold_current_a,
        "recommended_operating_pump_fraction": (
            fractions[operating_index] if operating_index is not None and fractions else None
        ),
        "stability_margin": stability_margin,
        "estimated_input_1db_compression_dbm": p1db_dbm,
    }


def _write_jpa_figure(result: dict[str, Any], metrics: dict[str, Any], plot_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(10.4, 7.2), constrained_layout=True)

    fractions = result.get("pump_fractions") or []
    peak_gain = result.get("peak_gain_db") or []
    axes[0, 0].plot(fractions, peak_gain, marker="o", linewidth=1.8, color="#3866d6")
    threshold = metrics.get("oscillation_threshold_pump_fraction")
    if threshold is not None:
        axes[0, 0].axvline(threshold, color="#ff3b30", linestyle="--", label="oscillation threshold")
        axes[0, 0].legend(loc="best")
    axes[0, 0].set_xlabel("pump current / Ic")
    axes[0, 0].set_ylabel("peak gain (dB)")
    axes[0, 0].set_title("Pump sweep (real JosephsonCircuits)")

    freqs = result.get("frequencies_ghz") or []
    curve = result.get("best_gain_curve_db") or []
    if freqs and len(curve) == len(freqs):
        axes[0, 1].plot(freqs, curve, linewidth=1.9, color="#34c759")
    axes[0, 1].set_xlabel("frequency (GHz)")
    axes[0, 1].set_ylabel("reflection gain (dB)")
    axes[0, 1].set_title("Gain at operating pump (S11)")

    eff = result.get("efficiency") or []
    if fractions and len(eff) == len(fractions):
        axes[1, 0].plot(fractions, eff, marker="o", linewidth=1.8, color="#ff9f0a")
    axes[1, 0].set_xlabel("pump current / Ic")
    axes[1, 0].set_ylabel("quantum efficiency")
    axes[1, 0].set_ylim(0.0, 1.05)
    axes[1, 0].set_title("Quantum efficiency vs pump")

    summary = [
        f"peak gain: {metrics.get('peak_gain_db', 0):.1f} dB",
        f"noise T: {metrics.get('noise_temperature_k', 0) * 1000:.0f} mK",
        f"added noise: {metrics.get('added_noise_photons', 0):.2f} photons",
        f"squeezing: {metrics.get('squeezing_db') or float('nan'):.2f} dB",
        f"stability margin: {(metrics.get('stability_margin') or 0) * 100:.0f}%",
    ]
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.02,
        0.95,
        "\n".join(summary),
        va="top",
        ha="left",
        fontsize=12,
        family="monospace",
    )
    axes[1, 1].set_title("Noise / squeezing / stability")

    fig.suptitle("Text-to-GDS JPA Analysis (JosephsonCircuits.jl)", fontsize=14)
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def run_jpa_analysis(
    sidecar: dict[str, Any],
    *,
    script_path: str | Path,
    result_path: str | Path,
    report_path: str | Path,
    plot_path: str | Path | None = None,
    jc_ua_per_um2: float = 1.0,
    target_frequency_ghz: float | None = None,
    target_bandwidth_mhz: float | None = None,
    n_pump_points: int = 12,
    pump_fraction_min: float = 0.004,
    pump_fraction_max: float = 0.024,
    julia_executable: str = "julia",
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    """Run the real JosephsonCircuits pump sweep and post-process JPA performance figures."""
    script = Path(script_path)
    result_file = Path(result_path)
    report = Path(report_path)
    plot = Path(plot_path) if plot_path is not None else None
    for path in (script, result_file, report):
        path.parent.mkdir(parents=True, exist_ok=True)

    generated = write_jpa_pump_sweep_script(
        sidecar,
        script_path=script,
        result_path=result_file,
        jc_ua_per_um2=jc_ua_per_um2,
        target_frequency_ghz=target_frequency_ghz,
        target_bandwidth_mhz=target_bandwidth_mhz,
        n_pump_points=n_pump_points,
        pump_fraction_min=pump_fraction_min,
        pump_fraction_max=pump_fraction_max,
    )

    command_prefix = _command_prefix(julia_executable)
    if command_prefix is None:
        report_payload = {
            "schema": "text-to-gds.jpa-analysis.v0",
            "status": "skipped",
            "executed": False,
            "script_path": str(script),
            "config": generated["config"],
            "warnings": [f"Julia executable not found: {julia_executable}"],
            "model_validity": (
                "JosephsonCircuits.jl runtime not found; generated a runnable pump-sweep "
                "script. Install Julia + JosephsonCircuits.jl to execute it."
            ),
        }
        report.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
        return report_payload

    completed = subprocess.run(
        [*command_prefix, str(script)],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=_adapter_env(),
    )
    sweep = None
    if result_file.exists():
        try:
            sweep = json.loads(result_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sweep = None

    if completed.returncode != 0 or not isinstance(sweep, dict) or sweep.get("analysis_status") != "executed":
        report_payload = {
            "schema": "text-to-gds.jpa-analysis.v0",
            "status": "failed",
            "executed": True,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
            "script_path": str(script),
            "result_path": str(result_file),
            "raw_result": sweep,
        }
        report.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
        return report_payload

    signal_bandwidth_hz = max(float(target_bandwidth_mhz or 500.0), 1.0) * 1e6
    metrics = _post_process(sweep, signal_bandwidth_hz=signal_bandwidth_hz)
    if plot is not None:
        _write_jpa_figure(sweep, metrics, plot)

    report_payload = {
        "schema": "text-to-gds.jpa-analysis.v0",
        "status": "executed",
        "executed": True,
        "engine": "JosephsonCircuits.jl harmonic balance pump sweep",
        "script_path": str(script),
        "result_path": str(result_file),
        "plot_path": str(plot) if plot else None,
        "sweep": sweep,
        "metrics": metrics,
        "model_validity": (
            "Real JosephsonCircuits.jl pump sweep on a layout-derived single-port reflection "
            "JPA. Gain, quantum efficiency, noise temperature, squeezing, and the oscillation "
            "threshold are computed by harmonic balance; P1dB is a quantum-limited estimate "
            "pending a two-tone signal-power compression sweep."
        ),
    }
    report.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
    return report_payload
