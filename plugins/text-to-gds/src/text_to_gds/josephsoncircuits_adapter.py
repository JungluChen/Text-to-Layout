"""JosephsonCircuits.jl adapter that reads directly from extraction.json.

This adapter:
  1. Reads extraction.json and requires lj_h and capacitance_f.
  2. Generates a Julia harmonic-balance script from those extracted values.
  3. Runs Julia if available; returns status="skipped" when not installed.
  4. Never synthesizes gain, noise, or squeezing without an executed result.

If required extracted parameters are missing the adapter returns status="failed"
with an explicit reason — it does not fall back to a heuristic model.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from text_to_gds.adapters import _adapter_env, _command_prefix
from text_to_gds.extraction_schema import (
    read_capacitance,
    read_ic,
    read_impedance,
    read_lj,
)

PI = math.pi


def _failed(reason: str, report_path: Path) -> dict[str, Any]:
    result = {
        "schema": "text-to-gds.josephsoncircuits-adapter.v1",
        "status": "failed",
        "reason": reason,
        "executed": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report_path)
    return result


def _build_julia_script(
    *,
    lj_h: float,
    capacitance_f: float,
    ic_a: float,
    impedance_ohm: float,
    pump_frequency_ghz: float,
    center_frequency_ghz: float,
    n_pump_points: int,
    pump_fraction_min: float,
    pump_fraction_max: float,
    result_path: Path,
) -> str:
    """Return a Julia JosephsonCircuits.jl harmonic-balance pump-sweep script."""
    # Coupling capacitance: 5% of resonator capacitance, minimum 1 fF
    cc_f = max(capacitance_f * 0.05, 1e-15)
    f_start = max(center_frequency_ghz - 0.5, 0.001)
    f_stop = center_frequency_ghz + 0.5
    result_literal = json.dumps(str(result_path))

    return f'''# Text-to-GDS generated JosephsonCircuits.jl script.
# Lj={lj_h:.6g} H  C={capacitance_f:.6g} F  Ic={ic_a:.6g} A
using Printf
result_path = {result_literal}

function json_number(v)
    isfinite(v) ? string(v) : "null"
end
json_array(a) = "[" * join(map(json_number, a), ",") * "]"

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
        Cj => {capacitance_f:.16g},
        R  => {impedance_ohm:.6g},
    )
    f_ghz = collect(range({f_start:.16g}, {f_stop:.16g}; length=201))
    ws = 2*pi .* f_ghz .* 1e9
    wp = (2*pi*{pump_frequency_ghz:.16g}*1e9,)
    Npump = (8,)
    Nmod  = (4,)
    ic = {ic_a:.16g}

    fractions = collect(range({pump_fraction_min:.16g}, {pump_fraction_max:.16g}; length={n_pump_points}))
    pump_currents = ic .* fractions
    peak_gain = Float64[]
    center_gain = Float64[]
    center_idx = argmin(abs.(f_ghz .- {center_frequency_ghz:.16g}))
    best_gain = -Inf
    best_curve = Float64[]
    best_fraction = fractions[1]

    for (i, Ip) in enumerate(pump_currents)
        sol = hbsolve(ws, wp, [(mode=(1,), port=1, current=Ip)], Nmod, Npump, circuit, circuitdefs)
        s11 = sol.linearized.S(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)
        g   = 10 .* log10.(abs2.(s11))
        pk  = maximum(g)
        push!(peak_gain, pk)
        push!(center_gain, g[center_idx])
        if pk > best_gain
            best_gain = pk
            best_curve = g
            best_fraction = fractions[i]
        end
    end

    payload = "{{" *
        "\\"schema\\":\\"text-to-gds.josephsoncircuits.v1\\"," *
        "\\"analysis_status\\":\\"executed\\"," *
        "\\"package_loaded\\":true," *
        "\\"lj_h\\":{lj_h:.16g}," *
        "\\"capacitance_f\\":{capacitance_f:.16g}," *
        "\\"ic_a\\":{ic_a:.16g}," *
        "\\"center_frequency_ghz\\":{center_frequency_ghz:.16g}," *
        "\\"pump_frequency_ghz\\":{pump_frequency_ghz:.16g}," *
        "\\"frequencies_ghz\\":" * json_array(f_ghz) * "," *
        "\\"pump_fractions\\":" * json_array(fractions) * "," *
        "\\"peak_gain_db\\":" * json_array(peak_gain) * "," *
        "\\"center_gain_db\\":" * json_array(center_gain) * "," *
        "\\"best_pump_fraction\\":" * json_number(best_fraction) * "," *
        "\\"best_peak_gain_db\\":" * json_number(best_gain) * "," *
        "\\"best_gain_curve_db\\":" * json_array(best_curve) *
        "}}"
    open(result_path, "w") do io
        write(io, payload)
    end
    println("text_to_gds_jc_done")
catch err
    open(result_path, "w") do io
        write(io, "{{\\"analysis_status\\":\\"failed\\",\\"package_loaded\\":true,\\"error\\":\\"" * replace(sprint(showerror, err), "\\"" => "'") * "\\"}}")
    end
    exit(1)
end
'''


def _build_passive_julia_script(
    *,
    lj_h: float,
    capacitance_f: float,
    impedance_ohm: float,
    center_frequency_ghz: float,
    result_path: Path,
) -> str:
    """Julia script for passive small-signal JJ S-parameter simulation (linear, undriven)."""
    cc_f = max(capacitance_f * 0.05, 1e-15)
    f_start = max(center_frequency_ghz - 1.0, 0.001)
    f_stop = center_frequency_ghz + 1.0
    result_literal = json.dumps(str(result_path))

    return f'''# Text-to-GDS: Passive JJ small-signal S-parameter simulation (linear, undriven).
# mode=passive  Lj={lj_h:.6g} H  C={capacitance_f:.6g} F
using Printf
result_path = {result_literal}

function json_number(v)
    isfinite(v) ? string(v) : "null"
end
json_array(a) = "[" * join(map(json_number, a), ",") * "]"

try
    @eval using JosephsonCircuits
catch err
    open(result_path, "w") do io
        write(io, "{{\\"analysis_status\\":\\"failed\\",\\"package_loaded\\":false,\\"mode\\":\\"passive\\",\\"error\\":\\"JosephsonCircuits.jl not installed\\"}}")
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
        Cj => {capacitance_f:.16g},
        R  => {impedance_ohm:.6g},
    )
    f_ghz = collect(range({f_start:.16g}, {f_stop:.16g}; length=401))
    ws = 2*pi .* f_ghz .* 1e9
    sol = hbsolve(ws, (), [], (0,), (0,), circuit, circuitdefs)
    s11 = [sol.linearized.S(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=i)
           for i in 1:length(ws)]
    s21 = [sol.linearized.S(outputmode=(0,), outputport=2, inputmode=(0,), inputport=1, freqindex=i)
           for i in 1:length(ws) if length(sol.linearized.portindices) >= 2]
    if length(s21) == 0
        s21 = fill(complex(0.0), length(ws))
    end
    s11_db = 20 .* log10.(max.(abs.(s11), 1e-300))
    s21_db = 20 .* log10.(max.(abs.(s21), 1e-300))

    payload = "{{\\"schema\\":\\"text-to-gds.josephsoncircuits.v1\\"," *
        "\\"analysis_status\\":\\"executed\\"," *
        "\\"package_loaded\\":true," *
        "\\"mode\\":\\"passive\\"," *
        "\\"lj_h\\":{lj_h:.16g}," *
        "\\"capacitance_f\\":{capacitance_f:.16g}," *
        "\\"center_frequency_ghz\\":{center_frequency_ghz:.16g}," *
        "\\"frequencies_ghz\\":" * json_array(f_ghz) * "," *
        "\\"s11_db\\":" * json_array(s11_db) * "," *
        "\\"s21_db\\":" * json_array(s21_db) *
        "}}"
    open(result_path, "w") do io
        write(io, payload)
    end
    println("text_to_gds_jc_done")
catch err
    open(result_path, "w") do io
        write(io, "{{\\"analysis_status\\":\\"failed\\",\\"package_loaded\\":true,\\"mode\\":\\"passive\\",\\"error\\":\\"" * replace(sprint(showerror, err), "\\"" => "'") * "\\"}}")
    end
    exit(1)
end
'''


def _write_passive_plot(result: dict[str, Any], plot_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(8.0, 4.8), constrained_layout=True)

    freqs = result.get("frequencies_ghz") or []
    s11 = result.get("s11_db") or []
    s21 = result.get("s21_db") or []
    if freqs and len(s11) == len(freqs):
        ax.plot(freqs, s11, linewidth=1.8, color="#3866d6", label="S11 (dB)")
    if freqs and len(s21) == len(freqs):
        ax.plot(freqs, s21, linewidth=1.8, color="#34c759", label="S21 (dB)", linestyle="--")
    ax.legend(loc="best")
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_title(
        f"Passive JJ small signal response (JosephsonCircuits.jl)\n"
        f"Lj = {result.get('lj_h', 0)*1e9:.3g} nH  "
        f"C = {result.get('capacitance_f', 0)*1e12:.3g} pF",
        fontsize=11,
    )
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def _write_plot(result: dict[str, Any], plot_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.8), constrained_layout=True)

    fracs = result.get("pump_fractions") or []
    peak = result.get("peak_gain_db") or []
    if fracs and len(peak) == len(fracs):
        axes[0].plot(fracs, peak, marker="o", linewidth=1.8, color="#3866d6")
    axes[0].set_xlabel("pump current / Ic")
    axes[0].set_ylabel("peak S11 gain (dB)")
    axes[0].set_title("Pump sweep (JosephsonCircuits.jl)")

    freqs = result.get("frequencies_ghz") or []
    curve = result.get("best_gain_curve_db") or []
    if freqs and len(curve) == len(freqs):
        axes[1].plot(freqs, curve, linewidth=1.9, color="#34c759")
    else:
        axes[1].text(0.5, 0.5, "No gain curve (solver not executed)", ha="center", va="center")
    axes[1].set_xlabel("frequency (GHz)")
    axes[1].set_ylabel("S11 reflection gain (dB)")
    axes[1].set_title("Gain at best pump point")

    fig.suptitle("JosephsonCircuits.jl harmonic-balance JPA", fontsize=13)
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def run_josephsoncircuits(
    extraction_path: str | Path,
    *,
    script_path: str | Path,
    result_path: str | Path,
    report_path: str | Path,
    plot_path: str | Path | None = None,
    mode: str = "passive",
    pump_frequency_ghz: float | None = None,
    pump_fraction_min: float = 0.004,
    pump_fraction_max: float = 0.024,
    n_pump_points: int = 12,
    julia_executable: str | None = None,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    """Run a JosephsonCircuits.jl simulation from extraction.json.

    mode="passive"  — small-signal S-parameter response, no pump.
                      Title: "Passive JJ small signal response".
    mode="jpa"      — harmonic-balance pump sweep.  Requires pump_frequency_ghz.
                      Returns status="failed" if pump is not specified.
                      NEVER labels a result as JPA without an executed pump sweep.

    Returns status="failed" if required extracted parameters are missing.
    Returns status="skipped" if Julia or JosephsonCircuits.jl is not installed.
    Returns status="executed" with sweep data only after a real solver run.
    """
    if mode not in ("passive", "jpa"):
        return _failed(f"unknown mode {mode!r}; choose 'passive' or 'jpa'", Path(report_path))
    if mode == "jpa" and pump_frequency_ghz is None:
        return _failed(
            "mode='jpa' requires pump_frequency_ghz; "
            "passive small-signal results must not be labelled as JPA",
            Path(report_path),
        )
    script = Path(script_path)
    result_file = Path(result_path)
    report = Path(report_path)
    plot = Path(plot_path) if plot_path is not None else None
    for p in (script, result_file, report):
        p.parent.mkdir(parents=True, exist_ok=True)

    # --- load and validate extraction ---
    try:
        extraction = json.loads(Path(extraction_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _failed(f"cannot read extraction.json: {e}", report)

    if extraction.get("schema") != "text-to-gds.extraction.v1":
        return _failed("extraction.json schema is not text-to-gds.extraction.v1", report)

    lj_h = read_lj(extraction)
    if lj_h is None:
        return _failed(
            "JosephsonCircuits requires Josephson inductance (lj_h); "
            "run extract_layout with jc_ua_per_um2 first",
            report,
        )

    capacitance_f = read_capacitance(extraction)
    if capacitance_f is None:
        return _failed(
            "JosephsonCircuits requires capacitance_f; "
            "supply capacitance_ff to extract_layout",
            report,
        )

    ic_a = read_ic(extraction)
    if ic_a is None:
        return _failed(
            "JosephsonCircuits requires critical current (ic_a) from extraction",
            report,
        )

    impedance_ohm = read_impedance(extraction) or 50.0

    # derive center frequency from extracted L and C
    center_ghz = 1.0 / (2.0 * PI * math.sqrt(lj_h * capacitance_f)) / 1e9
    pump_ghz = pump_frequency_ghz if pump_frequency_ghz is not None else center_ghz

    # --- generate Julia script (mode-dependent) ---
    if mode == "passive":
        julia_code = _build_passive_julia_script(
            lj_h=lj_h,
            capacitance_f=capacitance_f,
            impedance_ohm=impedance_ohm,
            center_frequency_ghz=center_ghz,
            result_path=result_file,
        )
    else:
        julia_code = _build_julia_script(
            lj_h=lj_h,
            capacitance_f=capacitance_f,
            ic_a=ic_a,
            impedance_ohm=impedance_ohm,
            pump_frequency_ghz=pump_ghz,
            center_frequency_ghz=center_ghz,
            n_pump_points=n_pump_points,
            pump_fraction_min=pump_fraction_min,
            pump_fraction_max=pump_fraction_max,
            result_path=result_file,
        )
    script.write_text(julia_code, encoding="utf-8")

    solver_inputs: dict[str, Any] = {
        "mode": mode,
        "lj_h": lj_h,
        "capacitance_f": capacitance_f,
        "ic_a": ic_a,
        "impedance_ohm": impedance_ohm,
        "center_frequency_ghz": center_ghz,
        "lineage": {
            "lj_h": extraction.get("lineage", {}).get("junction.lj", {}),
            "capacitance_f": extraction.get("lineage", {}).get("linear_circuit.capacitance", {}),
            "ic_a": extraction.get("lineage", {}).get("junction.ic", {}),
        },
    }
    if mode == "jpa":
        solver_inputs["pump_frequency_ghz"] = pump_ghz
        solver_inputs["n_pump_points"] = n_pump_points

    # --- check Julia availability ---
    if julia_executable is None:
        from text_to_gds.tool_discovery import tool_paths
        julia_executable = tool_paths().julia or "julia"
    command_prefix = _command_prefix(julia_executable)
    if command_prefix is None:
        payload: dict[str, Any] = {
            "schema": "text-to-gds.josephsoncircuits-adapter.v1",
            "status": "skipped",
            "executed": False,
            "reason": f"Julia executable not found: {julia_executable}",
            "script_path": str(script),
            "solver_inputs": solver_inputs,
            "model_note": (
                "Generated runnable JosephsonCircuits.jl script. "
                "Install Julia + JosephsonCircuits.jl to execute."
            ),
        }
        report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["report_path"] = str(report)
        return payload

    # --- run Julia ---
    completed = subprocess.run(
        [*command_prefix, str(script)],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=_adapter_env(),
    )
    sweep: dict[str, Any] | None = None
    if result_file.exists():
        try:
            sweep = json.loads(result_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sweep = None

    if (
        completed.returncode != 0
        or not isinstance(sweep, dict)
        or sweep.get("analysis_status") != "executed"
    ):
        payload = {
            "schema": "text-to-gds.josephsoncircuits-adapter.v1",
            "status": "failed",
            "executed": True,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
            "script_path": str(script),
            "result_path": str(result_file),
            "solver_inputs": solver_inputs,
            "raw_result": sweep,
        }
        report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["report_path"] = str(report)
        return payload

    if plot is not None:
        if mode == "passive":
            _write_passive_plot(sweep, plot)
        else:
            _write_plot(sweep, plot)

    if mode == "passive":
        engine_desc = "JosephsonCircuits.jl passive small-signal"
        validity = (
            "Passive JJ small signal response — no pump. "
            "S-parameters from JosephsonCircuits.jl linear solve. "
            "Lj and C sourced from extraction.json."
        )
    else:
        engine_desc = "JosephsonCircuits.jl harmonic balance (JPA)"
        validity = (
            "JPA harmonic-balance sweep. "
            "Gain and pump threshold from executed solver output only. "
            "Lj and C sourced from extraction.json (never estimated)."
        )

    payload = {
        "schema": "text-to-gds.josephsoncircuits-adapter.v1",
        "status": "executed",
        "executed": True,
        "mode": mode,
        "engine": engine_desc,
        "script_path": str(script),
        "result_path": str(result_file),
        "report_path": str(report),
        "plot_path": str(plot) if plot else None,
        "solver_inputs": solver_inputs,
        "sweep": sweep,
        "best_peak_gain_db": sweep.get("best_peak_gain_db") if mode == "jpa" else None,
        "best_pump_fraction": sweep.get("best_pump_fraction") if mode == "jpa" else None,
        "model_validity": validity,
    }
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
