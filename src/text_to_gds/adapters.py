from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from text_to_gds.simulation import critical_current_ua, josephson_inductance_ph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_TOOLS_ROOT = Path(os.environ.get("TEXT_TO_GDS_TOOLS", PROJECT_ROOT / ".tools")).resolve()


@dataclass(frozen=True)
class SimulationAdapter:
    name: str
    executable: str
    purpose: str
    mode: str
    source_url: str
    install_hint: str
    installed: bool
    resolved_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _local_executable_candidates(executable: str) -> list[Path]:
    normalized = Path(executable).name.lower()
    if normalized.endswith(".exe"):
        normalized = normalized[:-4]

    env_key = {
        "julia": "TEXT_TO_GDS_JULIA",
        "josim": "TEXT_TO_GDS_JOSIM",
        "josim-cli": "TEXT_TO_GDS_JOSIM",
    }.get(normalized)
    candidates: list[Path] = []
    if env_key and os.environ.get(env_key):
        candidates.append(Path(os.environ[env_key]))

    if normalized == "julia":
        candidates.extend(sorted(LOCAL_TOOLS_ROOT.glob("julia-*/bin/julia.exe"), reverse=True))
        candidates.append(LOCAL_TOOLS_ROOT / "julia" / "bin" / "julia.exe")
    elif normalized in {"josim", "josim-cli"}:
        candidates.extend(sorted(LOCAL_TOOLS_ROOT.glob("josim-*/bin/josim-cli.exe"), reverse=True))
        candidates.append(LOCAL_TOOLS_ROOT / "josim" / "bin" / "josim-cli.exe")
        candidates.append(LOCAL_TOOLS_ROOT / "josim" / "josim.exe")

    return candidates


def _resolved_executable(executable: str) -> str | None:
    path = Path(executable)
    if path.exists():
        return str(path.resolve())
    path_match = shutil.which(executable)
    if path_match:
        return path_match
    for candidate in _local_executable_candidates(executable):
        if candidate.exists():
            return str(candidate.resolve())
    return None


def _adapter_env() -> dict[str, str]:
    env = dict(os.environ)
    local_julia_depot = LOCAL_TOOLS_ROOT / "julia-depot"
    if "JULIA_DEPOT_PATH" not in env and local_julia_depot.exists():
        env["JULIA_DEPOT_PATH"] = str(local_julia_depot)
    return env


def list_simulation_adapters() -> list[dict[str, Any]]:
    """Report local availability of supported superconducting simulators."""
    julia_path = _resolved_executable("julia")
    josim_path = _resolved_executable("josim")
    adapters = [
        SimulationAdapter(
            name="JosephsonCircuits.jl",
            executable="julia",
            purpose="frequency-domain multi-tone harmonic balance, gain, S-parameters, noise",
            mode="external_julia",
            source_url="https://github.com/kpobrien/JosephsonCircuits.jl",
            install_hint=(
                "Run scripts/install_toolchain.ps1 -InstallJulia, or install Julia and run: "
                'julia -e "using Pkg; '
                "Pkg.add(url=\\\"https://github.com/kpobrien/JosephsonCircuits.jl\\\")\""
            ),
            installed=julia_path is not None,
            resolved_path=julia_path,
        ),
        SimulationAdapter(
            name="JoSIM",
            executable="josim",
            purpose="SPICE-like superconducting transient simulation using the RCSJ JJ model",
            mode="external_cli",
            source_url="https://github.com/JoeyDelp/JoSIM",
            install_hint="Run scripts/install_toolchain.ps1 -InstallJoSIM, or install josim-cli on PATH.",
            installed=josim_path is not None,
            resolved_path=josim_path,
        ),
    ]
    return [adapter.to_dict() for adapter in adapters]


def select_adapter(name: str) -> dict[str, Any]:
    normalized = name.lower().replace(" ", "").replace("-", "").replace("_", "")
    for adapter in list_simulation_adapters():
        candidate = adapter["name"].lower().replace(" ", "").replace("-", "").replace("_", "")
        if normalized in {candidate, adapter["mode"]}:
            return adapter
    raise ValueError(f"Unknown simulator adapter: {name}")


def _command_prefix(executable: str) -> list[str] | None:
    resolved = _resolved_executable(executable)
    if resolved is None:
        return None
    if resolved.endswith(".py"):
        return [sys.executable, resolved]
    return [resolved]


def _parse_numeric_table(text: str) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    headers: list[str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("*", "#", ".")):
            continue
        parts = [part.strip().strip('"') for part in line.replace(",", " ").split() if part]
        if not parts:
            continue
        try:
            values = [float(part) for part in parts]
        except ValueError:
            if any(any(char.isalpha() for char in part) for part in parts):
                headers = [part.strip() for part in parts]
            continue
        if headers and len(headers) == len(values):
            rows.append(dict(zip(headers, values, strict=True)))
        else:
            rows.append({f"col_{index}": value for index, value in enumerate(values)})
    return rows


def josim_netlist_from_sidecar(
    sidecar: dict[str, Any],
    *,
    jc_ua_per_um2: float,
    shunt_capacitance_ff: float,
    stop_time_ps: float = 200.0,
    timestep_ps: float = 1.0,
) -> str:
    """Create a minimal JoSIM-compatible transient deck for the extracted JJ."""
    info = sidecar.get("info", {})
    area_um2 = float(info.get("junction_area_um2", 0.0))
    ic_ua = critical_current_ua(area_um2, jc_ua_per_um2)
    ic_a = ic_ua * 1e-6
    cap_f = max(shunt_capacitance_ff, 0.0) * 1e-15
    timestep_s = timestep_ps * 1e-12
    stop_time_s = stop_time_ps * 1e-12
    lines = [
        "* Text-to-GDS generated JoSIM starter deck",
        "IIN in 0 PULSE(0 1e-6 0 1e-12 1e-12 2e-11 5e-11)",
        "BJJ in 0 jjmod",
        f".MODEL jjmod JJ(RTYPE=1, VG=2.8e-3, DELV=8e-5, ICRIT={ic_a:.12g}, RN=10, R0=100, CAP={cap_f:.12g})",
        f".TRAN {timestep_s:.12g} {stop_time_s:.12g} 0 {timestep_s:.12g}",
        ".PRINT DEVV BJJ",
        ".PRINT PHASE BJJ",
        ".END",
    ]
    if cap_f > 0.0:
        lines.insert(4, f"CSH in 0 {cap_f:.12g}")
    return "\n".join(lines)


def run_josim_transient(
    *,
    deck_path: str | Path,
    output_path: str | Path,
    josim_executable: str = "josim",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Run JoSIM on a generated deck when the executable is available."""
    command_prefix = _command_prefix(josim_executable)
    output_csv_path = Path(output_path).with_suffix(".csv")
    command = (command_prefix or [josim_executable]) + [
        "-o",
        str(output_csv_path),
        str(deck_path),
    ]
    if command_prefix is None:
        return {
            "adapter": "JoSIM",
            "status": "skipped",
            "executed": False,
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "parsed_rows": [],
            "warnings": [f"JoSIM executable not found: {josim_executable}"],
        }

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    output_text = output_csv_path.read_text(encoding="utf-8") if output_csv_path.exists() else ""
    parsed_rows = _parse_numeric_table(output_text or completed.stdout)
    payload = {
        "schema": "text-to-gds.josim-transient.v0",
        "adapter": "JoSIM",
        "deck_path": str(deck_path),
        "output_csv_path": str(output_csv_path),
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "output_csv": output_text,
        "parsed_rows": parsed_rows,
    }
    Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "adapter": "JoSIM",
        "status": "executed" if completed.returncode == 0 else "failed",
        "executed": True,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "parsed_rows": parsed_rows,
        "output_csv_path": str(output_csv_path),
        "result_path": str(output_path),
        "warnings": [] if completed.returncode == 0 else ["JoSIM command failed."],
    }


def write_josephsoncircuits_script(
    sidecar: dict[str, Any],
    *,
    script_path: str | Path,
    result_path: str | Path,
    jc_ua_per_um2: float,
    shunt_capacitance_ff: float,
    target_frequency_ghz: float | None,
    target_gain_db: float,
    target_bandwidth_mhz: float | None,
) -> None:
    """Write a Julia harmonic-balance starter script for JosephsonCircuits.jl."""
    plan = josephsoncircuits_plan_from_sidecar(
        sidecar,
        jc_ua_per_um2=jc_ua_per_um2,
        target_frequency_ghz=target_frequency_ghz,
        target_gain_db=target_gain_db,
        target_bandwidth_mhz=target_bandwidth_mhz,
    )
    model = plan["layout_derived_parameters"]
    center_ghz = float(target_frequency_ghz or 5.0)
    lj_h = float(model["josephson_inductance_ph"]) * 1e-12
    resonant_cap_f = 1.0 / ((2.0 * 3.141592653589793 * center_ghz * 1e9) ** 2 * lj_h)
    cj_f = (
        max(float(shunt_capacitance_ff), 1.0) * 1e-15
        if shunt_capacitance_ff > 0.0
        else resonant_cap_f
    )
    cc_f = max(cj_f * 0.1, 5.0e-15)
    span_ghz = max(float(target_bandwidth_mhz or 500.0) / 1000.0, 0.1)
    f_start_ghz = max(center_ghz - span_ghz / 2.0, 0.001)
    f_stop_ghz = center_ghz + span_ghz / 2.0
    pump_frequency_ghz = center_ghz + 0.00001
    ic_a = float(model["critical_current_ua"]) * 1e-6
    pump_current_a = max(ic_a * 0.017, 1e-12)
    result_literal = str(Path(result_path)).replace("\\", "\\\\")
    plan_literal = json.dumps(plan).replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    script = f'''# Text-to-GDS generated JosephsonCircuits.jl harmonic-balance starter.
using Printf

result_path = "{result_literal}"
plan_json = """{plan_literal}"""

function json_escape(value)
    text = string(value)
    text = replace(text, "\\\\" => "\\\\\\\\")
    text = replace(text, "\\"" => "\\\\\\"")
    text = replace(text, "\\n" => "\\\\n")
    return "\\"" * text * "\\""
end

function json_number(value)
    if isfinite(value)
        return string(value)
    end
    return "null"
end

function json_array(values)
    return "[" * join(map(json_number, values), ",") * "]"
end

function write_failure(package_loaded, package_error, simulation_error)
    payload = "{{" *
        "\\"schema\\":\\"text-to-gds.josephsoncircuits.v0\\"," *
        "\\"adapter\\":\\"JosephsonCircuits.jl\\"," *
        "\\"analysis_status\\":\\"failed\\"," *
        "\\"package_loaded\\":" * string(package_loaded) * "," *
        "\\"package_error\\":" * json_escape(package_error) * "," *
        "\\"simulation_error\\":" * json_escape(simulation_error) * "," *
        "\\"plan\\":" * plan_json *
        "}}"
    open(result_path, "w") do io
        write(io, payload)
    end
    println(payload)
end

try
    @eval using JosephsonCircuits
catch err
    write_failure(false, sprint(showerror, err), "")
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
    f_ghz = collect(range({f_start_ghz:.16g}, {f_stop_ghz:.16g}; length=41))
    ws = 2*pi .* f_ghz .* 1e9
    wp = (2*pi*{pump_frequency_ghz:.16g}*1e9,)
    sources = [(mode=(1,), port=1, current={pump_current_a:.16g})]
    Npumpharmonics = (8,)
    Nmodulationharmonics = (4,)

    solved = hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics, circuit, circuitdefs)
    s11 = solved.linearized.S(
        outputmode=(0,),
        outputport=1,
        inputmode=(0,),
        inputport=1,
        freqindex=:,
    )
    reflection_gain_db = 10 .* log10.(abs2.(s11))
    peak_gain_db = maximum(reflection_gain_db)
    peak_index = argmax(reflection_gain_db)
    center_index = argmin(abs.(f_ghz .- {center_ghz:.16g}))
    threshold = peak_gain_db - 3.0
    bandwidth_points = count(x -> x >= threshold, reflection_gain_db)
    step_mhz = length(f_ghz) > 1 ? (f_ghz[2] - f_ghz[1]) * 1000.0 : 0.0
    bandwidth_3db_mhz = bandwidth_points * step_mhz

    payload = "{{" *
        "\\"schema\\":\\"text-to-gds.josephsoncircuits.v0\\"," *
        "\\"adapter\\":\\"JosephsonCircuits.jl\\"," *
        "\\"analysis_status\\":\\"executed\\"," *
        "\\"analysis_type\\":\\"single_port_reflection_harmonic_balance\\"," *
        "\\"package_loaded\\":true," *
        "\\"target_frequency_ghz\\":{center_ghz:.16g}," *
        "\\"target_gain_db\\":{target_gain_db:.16g}," *
        "\\"target_bandwidth_mhz\\":{float(target_bandwidth_mhz or 0.0):.16g}," *
        "\\"model\\":{{" *
            "\\"lj_h\\":{lj_h:.16g}," *
            "\\"cj_f\\":{cj_f:.16g}," *
            "\\"cc_f\\":{cc_f:.16g}," *
            "\\"pump_frequency_ghz\\":{pump_frequency_ghz:.16g}," *
            "\\"pump_current_a\\":{pump_current_a:.16g}," *
            "\\"source\\":\\"layout-derived JJ plus default coupling and shunt capacitance assumptions\\"" *
        "}}," *
        "\\"frequencies_ghz\\":" * json_array(f_ghz) * "," *
        "\\"reflection_gain_db\\":" * json_array(reflection_gain_db) * "," *
        "\\"peak_gain_db\\":" * json_number(peak_gain_db) * "," *
        "\\"peak_frequency_ghz\\":" * json_number(f_ghz[peak_index]) * "," *
        "\\"center_gain_db\\":" * json_number(reflection_gain_db[center_index]) * "," *
        "\\"bandwidth_3db_mhz\\":" * json_number(bandwidth_3db_mhz) * "," *
        "\\"plan\\":" * plan_json *
        "}}"
    open(result_path, "w") do io
        write(io, payload)
    end
    println(payload)
catch err
    write_failure(true, "", sprint(showerror, err))
    exit(1)
end
'''
    Path(script_path).write_text(script, encoding="utf-8")


def run_josephsoncircuits(
    *,
    script_path: str | Path,
    result_path: str | Path,
    julia_executable: str = "julia",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Run a generated JosephsonCircuits.jl Julia script when Julia is available."""
    command_prefix = _command_prefix(julia_executable)
    command = (command_prefix or [julia_executable]) + [str(script_path)]
    if command_prefix is None:
        return {
            "adapter": "JosephsonCircuits.jl",
            "status": "skipped",
            "executed": False,
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "result": None,
            "warnings": [f"Julia executable not found: {julia_executable}"],
        }

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env={**_adapter_env(), "TEXT_TO_GDS_JC_RESULT": str(result_path)},
    )
    result_payload = None
    result_file = Path(result_path)
    if result_file.exists():
        try:
            result_payload = json.loads(result_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            result_payload = {"raw": result_file.read_text(encoding="utf-8")}
    return {
        "adapter": "JosephsonCircuits.jl",
        "status": "executed" if completed.returncode == 0 else "failed",
        "executed": True,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "result_path": str(result_path),
        "result": result_payload,
        "warnings": [] if completed.returncode == 0 else ["JosephsonCircuits.jl command failed."],
    }


def josephsoncircuits_plan_from_sidecar(
    sidecar: dict[str, Any],
    *,
    jc_ua_per_um2: float = 1.0,
    target_frequency_ghz: float | None,
    target_gain_db: float = 20.0,
    target_bandwidth_mhz: float | None = None,
) -> dict[str, Any]:
    """Return the command/data plan for a JosephsonCircuits.jl harmonic-balance run."""
    info = sidecar.get("info", {})
    area_um2 = float(info.get("junction_area_um2", 0.0))
    ic_ua = critical_current_ua(area_um2, jc_ua_per_um2=jc_ua_per_um2) if area_um2 else 0.0
    lj_ph = josephson_inductance_ph(ic_ua) if ic_ua else None
    return {
        "adapter": select_adapter("JosephsonCircuits.jl"),
        "target_frequency_ghz": target_frequency_ghz,
        "target_gain_db": target_gain_db,
        "target_bandwidth_mhz": target_bandwidth_mhz,
        "layout_derived_parameters": {
            "junction_area_um2": area_um2,
            "jc_ua_per_um2": jc_ua_per_um2,
            "critical_current_ua": ic_ua,
            "josephson_inductance_ph": lj_ph,
            "ports": sidecar.get("ports", []),
        },
        "next_files": {
            "julia_script": "workspace/artifacts/<name>.josephsoncircuits.jl",
            "simulation_json": "workspace/artifacts/<name>.josephsoncircuits.json",
        },
        "notes": [
            "This adapter runs a single-port reflection harmonic-balance starter model.",
            "Coupling and shunt capacitance defaults are placeholders unless explicit "
            "capacitance values are supplied.",
            "Use layout-extracted CPW, coupling, and shunt networks for signoff-grade gain/noise.",
        ],
    }
