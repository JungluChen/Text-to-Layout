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


@dataclass(frozen=True)
class SimulationAdapter:
    name: str
    executable: str
    purpose: str
    mode: str
    source_url: str
    install_hint: str
    installed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_simulation_adapters() -> list[dict[str, Any]]:
    """Report local availability of supported superconducting simulators."""
    adapters = [
        SimulationAdapter(
            name="JosephsonCircuits.jl",
            executable="julia",
            purpose="frequency-domain multi-tone harmonic balance, gain, S-parameters, noise",
            mode="external_julia",
            source_url="https://github.com/kpobrien/JosephsonCircuits.jl",
            install_hint=(
                'Install Julia, then run: julia -e "using Pkg; '
                "Pkg.add(url=\\\"https://github.com/kpobrien/JosephsonCircuits.jl\\\")\""
            ),
            installed=shutil.which("julia") is not None,
        ),
        SimulationAdapter(
            name="JoSIM",
            executable="josim",
            purpose="SPICE-like superconducting transient simulation using the RCSJ JJ model",
            mode="external_cli",
            source_url="https://github.com/JoeyDelp/JoSIM",
            install_hint="Install a JoSIM release binary and ensure josim is on PATH.",
            installed=shutil.which("josim") is not None,
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


def _resolved_executable(executable: str) -> str | None:
    path = Path(executable)
    if path.exists():
        return str(path)
    return shutil.which(executable)


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
        parts = [part for part in line.replace(",", " ").split() if part]
        if not parts:
            continue
        if any(any(char.isalpha() for char in part) for part in parts):
            headers = [part.strip() for part in parts]
            continue
        try:
            values = [float(part) for part in parts]
        except ValueError:
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
    cap_f = shunt_capacitance_ff * 1e-15
    return "\n".join(
        [
            "* Text-to-GDS generated JoSIM starter deck",
            f".PARAM IC={ic_ua * 1e-6:.12g}",
            f".PARAM CSH={cap_f:.12g}",
            "IIN in 0 PULSE(0 1u 0 1p 1p 20p 50p)",
            "BJJ in 0 jjmod AREA=1",
            "CSH in 0 {CSH}",
            ".MODEL jjmod JJ(RTYPE=1, VG=2.8m, DELV=0.08m, IC={IC}, RN=10, CAP=0)",
            f".TRAN {timestep_ps:.12g}p {stop_time_ps:.12g}p",
            ".PRINT DEVV BJJ",
            ".END",
        ]
    )


def run_josim_transient(
    *,
    deck_path: str | Path,
    output_path: str | Path,
    josim_executable: str = "josim",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Run JoSIM on a generated deck when the executable is available."""
    command_prefix = _command_prefix(josim_executable)
    command = (command_prefix or [josim_executable]) + [str(deck_path)]
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
    parsed_rows = _parse_numeric_table(completed.stdout)
    payload = {
        "schema": "text-to-gds.josim-transient.v0",
        "adapter": "JoSIM",
        "deck_path": str(deck_path),
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
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
        "result_path": str(output_path),
        "warnings": [] if completed.returncode == 0 else ["JoSIM command failed."],
    }


def write_josephsoncircuits_script(
    sidecar: dict[str, Any],
    *,
    script_path: str | Path,
    result_path: str | Path,
    target_frequency_ghz: float | None,
    target_gain_db: float,
    target_bandwidth_mhz: float | None,
) -> None:
    """Write a Julia command script for the JosephsonCircuits.jl adapter."""
    plan = josephsoncircuits_plan_from_sidecar(
        sidecar,
        target_frequency_ghz=target_frequency_ghz,
        target_gain_db=target_gain_db,
        target_bandwidth_mhz=target_bandwidth_mhz,
    )
    payload = {
        "schema": "text-to-gds.josephsoncircuits.v0",
        "package_loaded": False,
        "package_error": "",
        "plan": plan,
    }
    result_literal = str(Path(result_path)).replace("\\", "\\\\")
    payload_literal = json.dumps(payload).replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    script = f'''# Text-to-GDS generated JosephsonCircuits.jl adapter script.
package_loaded = false
package_error = ""
try
    @eval using JosephsonCircuits
    global package_loaded = true
catch err
    global package_error = sprint(showerror, err)
end

json = """{payload_literal}"""
json = replace(json, "\\"package_loaded\\": false" => "\\"package_loaded\\": " * string(package_loaded))
json = replace(json, "\\"package_error\\": \\"\\"" => "\\"package_error\\": \\"" * replace(package_error, "\\"" => "\\\\\\"") * "\\"")
open("{result_literal}", "w") do io
    write(io, json)
end
println(json)
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
        env={**os.environ, "TEXT_TO_GDS_JC_RESULT": str(result_path)},
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
    target_frequency_ghz: float | None,
    target_gain_db: float = 20.0,
    target_bandwidth_mhz: float | None = None,
) -> dict[str, Any]:
    """Return the command/data plan for a future JosephsonCircuits.jl run."""
    info = sidecar.get("info", {})
    area_um2 = float(info.get("junction_area_um2", 0.0))
    ic_ua = float(info.get("critical_current_ua", 0.0))
    if not ic_ua and area_um2:
        ic_ua = critical_current_ua(area_um2, jc_ua_per_um2=1.0)
    lj_ph = josephson_inductance_ph(ic_ua) if ic_ua else None
    return {
        "adapter": select_adapter("JosephsonCircuits.jl"),
        "target_frequency_ghz": target_frequency_ghz,
        "target_gain_db": target_gain_db,
        "target_bandwidth_mhz": target_bandwidth_mhz,
        "layout_derived_parameters": {
            "junction_area_um2": area_um2,
            "critical_current_ua_at_1ua_per_um2": ic_ua,
            "josephson_inductance_ph_at_1ua_per_um2": lj_ph,
            "ports": sidecar.get("ports", []),
        },
        "next_files": {
            "julia_script": "workspace/artifacts/<name>.josephsoncircuits.jl",
            "simulation_json": "workspace/artifacts/<name>.josephsoncircuits.json",
        },
        "notes": [
            "This adapter is intentionally a command plan until Julia and JosephsonCircuits.jl "
            "are installed locally.",
            "Use layout-extracted JJ, CPW, coupling, and shunt parameters to build the harmonic "
            "balance circuit model.",
        ],
    }
