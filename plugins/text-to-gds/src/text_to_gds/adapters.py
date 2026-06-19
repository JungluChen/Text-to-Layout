from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from importlib.util import find_spec
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
        "ngspice": "TEXT_TO_GDS_NGSPICE",
        "magic": "TEXT_TO_GDS_MAGIC",
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
    elif normalized == "ngspice":
        candidates.extend(sorted(LOCAL_TOOLS_ROOT.glob("ngspice-*/bin/ngspice.exe"), reverse=True))
        candidates.append(LOCAL_TOOLS_ROOT / "ngspice" / "bin" / "ngspice.exe")
        candidates.append(Path("C:/msys64/ucrt64/bin/ngspice.exe"))
        candidates.append(Path("C:/msys64/mingw64/bin/ngspice.exe"))
    elif normalized == "magic":
        candidates.extend(sorted(LOCAL_TOOLS_ROOT.glob("magic-*/magic.exe"), reverse=True))
        candidates.append(LOCAL_TOOLS_ROOT / "magic" / "magic.exe")
        candidates.append(PROJECT_ROOT / "scripts" / "magic_wsl.py")
        candidates.append(LOCAL_TOOLS_ROOT / "magic-wsl.py")
        candidates.append(Path("C:/msys64/ucrt64/bin/magic.exe"))
        candidates.append(Path("C:/msys64/mingw64/bin/magic.exe"))

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
    path_entries = []
    for directory in (Path("C:/msys64/ucrt64/bin"), Path("C:/msys64/usr/bin")):
        if directory.exists():
            path_entries.append(str(directory))
    if path_entries:
        env["PATH"] = os.pathsep.join([*path_entries, env.get("PATH", "")])
    ngspice_lib = Path("C:/msys64/ucrt64/lib/ngspice")
    if "SPICE_LIB_DIR" not in env and ngspice_lib.exists():
        env["SPICE_LIB_DIR"] = str(ngspice_lib)
    return env


def list_simulation_adapters() -> list[dict[str, Any]]:
    """Report local availability of supported superconducting simulators."""
    julia_path = _resolved_executable("julia")
    josim_path = _resolved_executable("josim")
    ngspice_path = _resolved_executable("ngspice")
    magic_path = _resolved_executable("magic")
    pyspice_spec = find_spec("PySpice")
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
        SimulationAdapter(
            name="ngspice",
            executable="ngspice",
            purpose="SPICE circuit simulation for layout-derived JJ/LJPA starter decks and compact models",
            mode="external_spice_cli",
            source_url="https://ngspice.sourceforge.io/",
            install_hint="Install ngspice on PATH or set TEXT_TO_GDS_NGSPICE to the executable.",
            installed=ngspice_path is not None,
            resolved_path=ngspice_path,
        ),
        SimulationAdapter(
            name="PySpice",
            executable="python",
            purpose="Python orchestration layer for ngspice-backed circuit simulation and plotting",
            mode="python_spice_module",
            source_url="https://github.com/PySpice-org/PySpice",
            install_hint="Install PySpice plus a compatible ngspice shared library before enabling this adapter.",
            installed=pyspice_spec is not None,
            resolved_path=pyspice_spec.origin if pyspice_spec else None,
        ),
        SimulationAdapter(
            name="Magic VLSI",
            executable="magic",
            purpose="VLSI layout extraction/DRC handoff before SPICE netlist simulation",
            mode="layout_extraction_cli",
            source_url="http://opencircuitdesign.com/magic/",
            install_hint="Install Magic VLSI on PATH or set TEXT_TO_GDS_MAGIC to the executable.",
            installed=magic_path is not None,
            resolved_path=magic_path,
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


def magic_script_for_gds(
    *,
    gds_path: str | Path,
    report_path: str | Path,
    spice_path: str | Path,
    extract_path: str | Path,
    top_cell: str | None = None,
    tech_file: str | Path | None = None,
) -> str:
    """Create a Magic TCL script for local GDS import, extraction, and SPICE export."""
    gds = str(Path(gds_path).resolve()).replace("\\", "/")
    report = str(Path(report_path).resolve()).replace("\\", "/")
    spice = str(Path(spice_path).resolve()).replace("\\", "/")
    extract = str(Path(extract_path).resolve()).replace("\\", "/")
    top = top_cell or Path(gds_path).stem
    lines = [
        "# Text-to-GDS generated Magic extraction script",
        f'set report_path "{report}"',
        f'set spice_path "{spice}"',
        f'set extract_path "{extract}"',
        "set status executed",
        "set warnings {}",
        "tech load scmos",
        f'gds read "{gds}"',
        f'load "{top}"',
        "select top cell",
        "expand",
        "extract all",
        'ext2spice lvs',
        'ext2spice cthresh 0',
        'ext2spice rthresh 0',
        f'ext2spice -o "{spice}"',
        f'if {{[file exists "{top}.ext"]}} {{ file copy -force "{top}.ext" "{extract}" }}',
        f'puts "text_to_gds_magic_spice {spice}"',
        f'puts "text_to_gds_magic_extract {extract}"',
        "set fp [open $report_path w]",
        'puts $fp "schema,status,top_cell,spice_path,extract_path"',
        f'puts $fp "text-to-gds.magic-extraction.v0,$status,{top},{spice},{extract}"',
        "close $fp",
        "quit -noprompt",
    ]
    if tech_file is not None:
        tech = str(Path(tech_file).resolve()).replace("\\", "/")
        lines[6] = f'tech load "{tech}"'
    return "\n".join(lines)


def run_magic_extraction(
    *,
    gds_path: str | Path,
    script_path: str | Path,
    report_path: str | Path,
    spice_path: str | Path,
    extract_path: str | Path,
    top_cell: str | None = None,
    tech_file: str | Path | None = None,
    magic_executable: str = "magic",
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Run Magic VLSI extraction when the executable is available."""
    script = magic_script_for_gds(
        gds_path=gds_path,
        report_path=report_path,
        spice_path=spice_path,
        extract_path=extract_path,
        top_cell=top_cell,
        tech_file=tech_file,
    )
    Path(script_path).write_text(script, encoding="utf-8")

    command_prefix = _command_prefix(magic_executable)
    command = (command_prefix or [magic_executable]) + [
        "-dnull",
        "-noconsole",
        str(script_path),
    ]
    if command_prefix is None:
        return {
            "adapter": "Magic VLSI",
            "status": "skipped",
            "executed": False,
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "script_path": str(script_path),
            "spice_path": str(spice_path),
            "extract_path": str(extract_path),
            "warnings": [f"Magic executable not found: {magic_executable}"],
        }

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=Path(extract_path).parent,
        env=_adapter_env(),
        timeout=timeout_seconds,
    )
    report_file = Path(report_path)
    report_text = report_file.read_text(encoding="utf-8") if report_file.exists() else ""
    warning_lines = [
        line.strip()
        for line in (completed.stderr + "\n" + completed.stdout).splitlines()
        if any(
            marker in line.lower()
            for marker in (
                "warning:",
                "error while reading",
                "unknown layer",
                "couldn't",
                "could not",
                "invalid command",
                "no such file",
            )
        )
    ]
    if not Path(spice_path).exists():
        warning_lines.append("Magic did not produce a SPICE netlist.")
    if not Path(extract_path).exists():
        warning_lines.append("Magic did not produce an .ext extraction file.")
    status = "failed"
    if completed.returncode == 0:
        status = "executed_with_warnings" if warning_lines else "executed"
    payload = {
        "schema": "text-to-gds.magic-extraction.v0",
        "adapter": "Magic VLSI",
        "gds_path": str(gds_path),
        "script_path": str(script_path),
        "report_path": str(report_path),
        "spice_path": str(spice_path),
        "extract_path": str(extract_path),
        "top_cell": top_cell or Path(gds_path).stem,
        "tech_file": str(tech_file) if tech_file else None,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "report": report_text,
        "spice_exists": Path(spice_path).exists(),
        "extract_exists": Path(extract_path).exists(),
        "warnings": warning_lines,
    }
    Path(report_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "adapter": "Magic VLSI",
        "status": status,
        "executed": True,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "script_path": str(script_path),
        "report_path": str(report_path),
        "spice_path": str(spice_path),
        "extract_path": str(extract_path),
        "spice_exists": Path(spice_path).exists(),
        "extract_exists": Path(extract_path).exists(),
        "warnings": warning_lines if completed.returncode == 0 else ["Magic VLSI command failed."],
    }


def _spice_number(value: float) -> str:
    return f"{value:.12g}"


def ngspice_netlist_from_sidecar(
    sidecar: dict[str, Any],
    *,
    output_data_path: str | Path,
    jc_ua_per_um2: float,
    shunt_capacitance_ff: float,
    target_frequency_ghz: float | None = None,
    target_bandwidth_mhz: float | None = None,
    coupling_capacitance_ff: float | None = None,
    resonator_capacitance_ff: float | None = None,
    stop_time_ps: float = 200.0,
    timestep_ps: float = 1.0,
) -> str:
    """Create a minimal ngspice starter deck from layout-derived sidecar metadata."""
    _validate_optional_capacitance("coupling_capacitance_ff", coupling_capacitance_ff)
    _validate_optional_capacitance("resonator_capacitance_ff", resonator_capacitance_ff)

    info = sidecar.get("info", {})
    area_um2 = float(info.get("junction_area_um2", 0.0))
    ic_ua = critical_current_ua(area_um2, jc_ua_per_um2)
    lj_ph = josephson_inductance_ph(ic_ua)
    if lj_ph is None:
        raise ValueError("ngspice simulation requires non-zero junction area and Ic")

    lj_h = lj_ph * 1e-12
    cj_f = max(shunt_capacitance_ff, 0.0) * 1e-15
    center_ghz = _target_value(sidecar, "center_frequency_ghz", target_frequency_ghz, 5.0)
    bandwidth_mhz = _target_value(sidecar, "target_bandwidth_mhz", target_bandwidth_mhz, 500.0)
    span_ghz = max(bandwidth_mhz / 1000.0, 0.1)
    f_start_hz = max((center_ghz - span_ghz / 2.0) * 1e9, 1.0)
    f_stop_hz = (center_ghz + span_ghz / 2.0) * 1e9
    resonant_cap_f = 1.0 / ((2.0 * 3.141592653589793 * center_ghz * 1e9) ** 2 * lj_h)
    total_cap_f = (
        max(float(resonator_capacitance_ff), 1.0) * 1e-15
        if resonator_capacitance_ff is not None and resonator_capacitance_ff > 0.0
        else resonant_cap_f
    )
    coupling_cap_f = (
        max(float(coupling_capacitance_ff), 0.0) * 1e-15
        if coupling_capacitance_ff is not None
        else max(total_cap_f * 0.05, 5.0e-15)
    )
    csh_f = max(total_cap_f - cj_f, 1.0e-15)
    output_data = str(Path(output_data_path)).replace("\\", "/")

    if supports_multiport_ljpa(sidecar):
        lines = [
            "* Text-to-GDS generated ngspice LJPA starter deck",
            "* Linearized small-signal model from layout-derived JJ area; not EM signoff.",
            f".param LJ={_spice_number(lj_h)}",
            f".param CJ={_spice_number(max(cj_f, 1.0e-18))}",
            f".param CSH={_spice_number(csh_f)}",
            f".param CC={_spice_number(coupling_cap_f)}",
            "VIN src 0 AC 1",
            "RSRC src in 50",
            "CIN in res {CC}",
            "LJJ res 0 {LJ}",
            "CJ res 0 {CJ}",
            "CSH res 0 {CSH}",
            "COUT res out {CC}",
            "RLOAD out 0 50",
            f".ac lin 81 {_spice_number(f_start_hz)} {_spice_number(f_stop_hz)}",
            ".control",
            "set filetype=ascii",
            "run",
            f"wrdata {output_data} frequency vdb(out) vp(out) vdb(in) vp(in)",
            "quit",
            ".endc",
            ".end",
        ]
    else:
        timestep_s = timestep_ps * 1e-12
        stop_time_s = stop_time_ps * 1e-12
        lines = [
            "* Text-to-GDS generated ngspice JJ starter deck",
            "* JJ is linearized as Lj plus optional shunt capacitance; not RCSJ signoff.",
            f".param LJ={_spice_number(lj_h)}",
            f".param CJ={_spice_number(max(cj_f, 1.0e-18))}",
            "IIN in 0 PULSE(0 1u 0 1p 1p 20p 50p)",
            "LJJ in jj {LJ}",
            "RSH jj 0 50",
            "CJ jj 0 {CJ}",
            f".tran {_spice_number(timestep_s)} {_spice_number(stop_time_s)}",
            ".control",
            "set filetype=ascii",
            "run",
            f"wrdata {output_data} time v(in) v(jj)",
            "quit",
            ".endc",
            ".end",
        ]
    return "\n".join(lines)


def run_ngspice(
    *,
    deck_path: str | Path,
    output_path: str | Path,
    data_path: str | Path,
    ngspice_executable: str = "ngspice",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Run ngspice on a generated deck when the executable is available."""
    command_prefix = _command_prefix(ngspice_executable)
    log_path = Path(output_path).with_suffix(".log")
    command = (command_prefix or [ngspice_executable]) + [
        "-b",
        "-o",
        str(log_path),
        str(deck_path),
    ]
    if command_prefix is None:
        return {
            "adapter": "ngspice",
            "status": "skipped",
            "executed": False,
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "parsed_rows": [],
            "warnings": [f"ngspice executable not found: {ngspice_executable}"],
        }

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=Path(deck_path).parent,
        env=_adapter_env(),
        timeout=timeout_seconds,
    )
    data_file = Path(data_path)
    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    data_text = data_file.read_text(encoding="utf-8") if data_file.exists() else ""
    parsed_rows = _parse_numeric_table(data_text or completed.stdout or log_text)
    payload = {
        "schema": "text-to-gds.ngspice.v0",
        "adapter": "ngspice",
        "deck_path": str(deck_path),
        "output_data_path": str(data_file),
        "log_path": str(log_path),
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "log": log_text,
        "output_data": data_text,
        "parsed_rows": parsed_rows,
    }
    Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "adapter": "ngspice",
        "status": "executed" if completed.returncode == 0 else "failed",
        "executed": True,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "parsed_rows": parsed_rows,
        "output_data_path": str(data_file),
        "log_path": str(log_path),
        "result_path": str(output_path),
        "warnings": [] if completed.returncode == 0 else ["ngspice command failed."],
    }


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
        env=_adapter_env(),
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


def _sidecar_port_names(sidecar: dict[str, Any]) -> set[str]:
    return {
        str(port.get("name"))
        for port in sidecar.get("ports", [])
        if isinstance(port, dict) and port.get("name")
    }


def supports_multiport_ljpa(sidecar: dict[str, Any]) -> bool:
    """Return whether the sidecar has the minimum metadata for the LJPA two-port model."""
    info = sidecar.get("info", {})
    ports = _sidecar_port_names(sidecar)
    return (
        sidecar.get("pcell") == "lumped_element_jpa_seed"
        or info.get("device_type") == "lumped_element_jpa_seed"
    ) and {"rf_in", "rf_out"} <= ports


def resolve_josephsoncircuits_analysis_mode(
    sidecar: dict[str, Any],
    analysis_mode: str = "auto",
) -> str:
    """Resolve JosephsonCircuits analysis mode from user intent and sidecar shape."""
    normalized = analysis_mode.lower().replace("_", "-")
    aliases = {
        "auto": "auto",
        "multiport-ljpa": "multiport_ljpa",
        "multiport": "multiport_ljpa",
        "ljpa": "multiport_ljpa",
        "single-port-reflection": "single_port_reflection",
        "single-port": "single_port_reflection",
        "reflection": "single_port_reflection",
    }
    if normalized not in aliases:
        raise ValueError(
            "analysis_mode must be one of auto, multiport_ljpa, or single_port_reflection"
        )
    requested = aliases[normalized]
    if requested == "auto":
        return "multiport_ljpa" if supports_multiport_ljpa(sidecar) else "single_port_reflection"
    if requested == "multiport_ljpa" and not supports_multiport_ljpa(sidecar):
        raise ValueError(
            "multiport_ljpa analysis requires a lumped_element_jpa_seed sidecar with rf_in "
            "and rf_out ports"
        )
    return requested


def _target_value(
    sidecar: dict[str, Any],
    key: str,
    explicit: float | None,
    default: float,
) -> float:
    if explicit is not None:
        return float(explicit)
    info = sidecar.get("info", {})
    value = info.get(key)
    return float(value) if value is not None else default


def _validate_optional_capacitance(name: str, value: float | None) -> None:
    if value is not None and value < 0.0:
        raise ValueError(f"{name} must be non-negative, got {value}")


def write_josephsoncircuits_script(
    sidecar: dict[str, Any],
    *,
    script_path: str | Path,
    result_path: str | Path,
    jc_ua_per_um2: float,
    shunt_capacitance_ff: float,
    analysis_mode: str = "auto",
    pump_current_fraction: float = 0.017,
    coupling_capacitance_ff: float | None = None,
    resonator_capacitance_ff: float | None = None,
    target_frequency_ghz: float | None,
    target_gain_db: float,
    target_bandwidth_mhz: float | None,
) -> None:
    """Write a Julia harmonic-balance starter script for JosephsonCircuits.jl."""
    if pump_current_fraction <= 0.0:
        raise ValueError(f"pump_current_fraction must be positive, got {pump_current_fraction}")
    _validate_optional_capacitance("coupling_capacitance_ff", coupling_capacitance_ff)
    _validate_optional_capacitance("resonator_capacitance_ff", resonator_capacitance_ff)

    resolved_analysis = resolve_josephsoncircuits_analysis_mode(sidecar, analysis_mode)
    center_ghz = _target_value(sidecar, "center_frequency_ghz", target_frequency_ghz, 5.0)
    bandwidth_mhz = _target_value(sidecar, "target_bandwidth_mhz", target_bandwidth_mhz, 500.0)
    span_ghz = max(bandwidth_mhz / 1000.0, 0.1)
    f_start_ghz = max(center_ghz - span_ghz / 2.0, 0.001)
    f_stop_ghz = center_ghz + span_ghz / 2.0
    pump_frequency_ghz = center_ghz + 0.00001

    plan = josephsoncircuits_plan_from_sidecar(
        sidecar,
        jc_ua_per_um2=jc_ua_per_um2,
        analysis_mode=analysis_mode,
        pump_current_fraction=pump_current_fraction,
        coupling_capacitance_ff=coupling_capacitance_ff,
        resonator_capacitance_ff=resonator_capacitance_ff,
        target_frequency_ghz=target_frequency_ghz,
        target_gain_db=target_gain_db,
        target_bandwidth_mhz=target_bandwidth_mhz,
    )
    model = plan["layout_derived_parameters"]
    if model["josephson_inductance_ph"] is None:
        raise ValueError("JosephsonCircuits analysis requires non-zero junction area and Ic")

    lj_h = float(model["josephson_inductance_ph"]) * 1e-12
    ic_a = float(model["critical_current_ua"]) * 1e-6
    pump_current_a = max(ic_a * pump_current_fraction, 1e-12)
    resonant_cap_f = 1.0 / ((2.0 * 3.141592653589793 * center_ghz * 1e9) ** 2 * lj_h)
    total_cap_f = (
        max(float(resonator_capacitance_ff), 1.0) * 1e-15
        if resonator_capacitance_ff is not None and resonator_capacitance_ff > 0.0
        else resonant_cap_f
    )
    if resolved_analysis == "single_port_reflection":
        cj_f = (
            max(float(shunt_capacitance_ff), 1.0) * 1e-15
            if shunt_capacitance_ff > 0.0
            else total_cap_f
        )
        cc_f = (
            max(float(coupling_capacitance_ff), 0.0) * 1e-15
            if coupling_capacitance_ff is not None
            else max(cj_f * 0.1, 5.0e-15)
        )
    else:
        cj_f = max(float(shunt_capacitance_ff), 0.0) * 1e-15
        csh_f = max(total_cap_f - cj_f, 1.0e-15)
        cc_f = (
            max(float(coupling_capacitance_ff), 0.0) * 1e-15
            if coupling_capacitance_ff is not None
            else max(total_cap_f * 0.05, 5.0e-15)
        )
        lr_h = max(0.05 * lj_h, 1.0e-12)

    result_literal = json.dumps(str(Path(result_path)))
    plan_literal = json.dumps(json.dumps(plan))
    analysis_type = (
        "multiport_ljpa_harmonic_balance"
        if resolved_analysis == "multiport_ljpa"
        else "single_port_reflection_harmonic_balance"
    )
    analysis_type_literal = json.dumps(analysis_type)
    script = f'''# Text-to-GDS generated JosephsonCircuits.jl harmonic-balance starter.
using Printf

result_path = {result_literal}
plan_json = {plan_literal}
analysis_type = {analysis_type_literal}

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
        "\\"analysis_type\\":" * json_escape(analysis_type) * "," *
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
'''

    if resolved_analysis == "single_port_reflection":
        script += f'''    @variables R Cc Lj Cj
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
    left_index = peak_index
    right_index = peak_index
    while left_index > 1 && reflection_gain_db[left_index - 1] >= threshold
        left_index -= 1
    end
    while right_index < length(reflection_gain_db) && reflection_gain_db[right_index + 1] >= threshold
        right_index += 1
    end
    bandwidth_3db_mhz = length(f_ghz) > 1 ? (f_ghz[right_index] - f_ghz[left_index]) * 1000.0 : 0.0

    payload = "{{" *
        "\\"schema\\":\\"text-to-gds.josephsoncircuits.v0\\"," *
        "\\"adapter\\":\\"JosephsonCircuits.jl\\"," *
        "\\"analysis_status\\":\\"executed\\"," *
        "\\"analysis_type\\":\\"single_port_reflection_harmonic_balance\\"," *
        "\\"package_loaded\\":true," *
        "\\"target_frequency_ghz\\":{center_ghz:.16g}," *
        "\\"target_gain_db\\":{target_gain_db:.16g}," *
        "\\"target_bandwidth_mhz\\":{bandwidth_mhz:.16g}," *
        "\\"model\\":{{" *
            "\\"port_impedance_ohm\\":50.0," *
            "\\"lj_h\\":{lj_h:.16g}," *
            "\\"cj_f\\":{cj_f:.16g}," *
            "\\"cc_f\\":{cc_f:.16g}," *
            "\\"pump_frequency_ghz\\":{pump_frequency_ghz:.16g}," *
            "\\"pump_current_a\\":{pump_current_a:.16g}," *
            "\\"pump_current_fraction\\":{pump_current_fraction:.16g}," *
            "\\"source\\":\\"layout-derived JJ plus default coupling and capacitance assumptions\\"" *
        "}}," *
        "\\"frequencies_ghz\\":" * json_array(f_ghz) * "," *
        "\\"reflection_gain_db\\":" * json_array(reflection_gain_db) * "," *
        "\\"peak_gain_db\\":" * json_number(peak_gain_db) * "," *
        "\\"peak_frequency_ghz\\":" * json_number(f_ghz[peak_index]) * "," *
        "\\"center_gain_db\\":" * json_number(reflection_gain_db[center_index]) * "," *
        "\\"bandwidth_3db_mhz\\":" * json_number(bandwidth_3db_mhz) * "," *
        "\\"plan\\":" * plan_json *
        "}}"
'''
    else:
        script += f'''    @variables R Ccin Ccout Lj Cj Csh Lr
    circuit = [
        ("P1","1","0",1),
        ("R1","1","0",R),
        ("CIN","1","2",Ccin),
        ("LRES","2","3",Lr),
        ("Lj1","3","0",Lj),
        ("CJ","3","0",Cj),
        ("CSH","3","0",Csh),
        ("COUT","3","4",Ccout),
        ("P2","4","0",2),
        ("R2","4","0",R),
    ]
    circuitdefs = Dict(
        Lj => {lj_h:.16g},
        Cj => {cj_f:.16g},
        Csh => {csh_f:.16g},
        Ccin => {cc_f:.16g},
        Ccout => {cc_f:.16g},
        Lr => {lr_h:.16g},
        R => 50.0,
    )
    f_ghz = collect(range({f_start_ghz:.16g}, {f_stop_ghz:.16g}; length=81))
    ws = 2*pi .* f_ghz .* 1e9
    wp = (2*pi*{pump_frequency_ghz:.16g}*1e9,)
    sources = [(mode=(1,), port=1, current={pump_current_a:.16g})]
    Npumpharmonics = (8,)
    Nmodulationharmonics = (4,)

    solved = hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics, circuit, circuitdefs)

    function s_db(outputport, inputport)
        values = solved.linearized.S(
            outputmode=(0,),
            outputport=outputport,
            inputmode=(0,),
            inputport=inputport,
            freqindex=:,
        )
        return 10 .* log10.(abs2.(values))
    end

    s11_db = s_db(1, 1)
    s21_db = s_db(2, 1)
    s12_db = s_db(1, 2)
    s22_db = s_db(2, 2)
    peak_s21_gain_db = maximum(s21_db)
    peak_index = argmax(s21_db)
    center_index = argmin(abs.(f_ghz .- {center_ghz:.16g}))
    threshold = peak_s21_gain_db - 3.0
    left_index = peak_index
    right_index = peak_index
    while left_index > 1 && s21_db[left_index - 1] >= threshold
        left_index -= 1
    end
    while right_index < length(s21_db) && s21_db[right_index + 1] >= threshold
        right_index += 1
    end
    bandwidth_3db_mhz = length(f_ghz) > 1 ? (f_ghz[right_index] - f_ghz[left_index]) * 1000.0 : 0.0
    gain_error_db = peak_s21_gain_db - {target_gain_db:.16g}
    bandwidth_error_mhz = bandwidth_3db_mhz - {bandwidth_mhz:.16g}
    frequency_error_ghz = f_ghz[peak_index] - {center_ghz:.16g}

    payload = "{{" *
        "\\"schema\\":\\"text-to-gds.josephsoncircuits.v0\\"," *
        "\\"adapter\\":\\"JosephsonCircuits.jl\\"," *
        "\\"analysis_status\\":\\"executed\\"," *
        "\\"analysis_type\\":\\"multiport_ljpa_harmonic_balance\\"," *
        "\\"package_loaded\\":true," *
        "\\"target_frequency_ghz\\":{center_ghz:.16g}," *
        "\\"target_gain_db\\":{target_gain_db:.16g}," *
        "\\"target_bandwidth_mhz\\":{bandwidth_mhz:.16g}," *
        "\\"model\\":{{" *
            "\\"port_impedance_ohm\\":50.0," *
            "\\"lj_h\\":{lj_h:.16g}," *
            "\\"lres_h\\":{lr_h:.16g}," *
            "\\"cj_f\\":{cj_f:.16g}," *
            "\\"csh_f\\":{csh_f:.16g}," *
            "\\"ccin_f\\":{cc_f:.16g}," *
            "\\"ccout_f\\":{cc_f:.16g}," *
            "\\"target_resonator_capacitance_f\\":{total_cap_f:.16g}," *
            "\\"pump_frequency_ghz\\":{pump_frequency_ghz:.16g}," *
            "\\"pump_current_a\\":{pump_current_a:.16g}," *
            "\\"pump_current_fraction\\":{pump_current_fraction:.16g}," *
            "\\"source\\":\\"layout-derived two-port lumped LJPA starter; not EM signoff\\"" *
        "}}," *
        "\\"frequencies_ghz\\":" * json_array(f_ghz) * "," *
        "\\"s_parameters_db\\":{{" *
            "\\"s11_db\\":" * json_array(s11_db) * "," *
            "\\"s21_db\\":" * json_array(s21_db) * "," *
            "\\"s12_db\\":" * json_array(s12_db) * "," *
            "\\"s22_db\\":" * json_array(s22_db) *
        "}}," *
        "\\"peak_s21_gain_db\\":" * json_number(peak_s21_gain_db) * "," *
        "\\"peak_s21_frequency_ghz\\":" * json_number(f_ghz[peak_index]) * "," *
        "\\"center_s21_gain_db\\":" * json_number(s21_db[center_index]) * "," *
        "\\"bandwidth_3db_mhz\\":" * json_number(bandwidth_3db_mhz) * "," *
        "\\"target_errors\\":{{" *
            "\\"gain_error_db\\":" * json_number(gain_error_db) * "," *
            "\\"bandwidth_error_mhz\\":" * json_number(bandwidth_error_mhz) * "," *
            "\\"frequency_error_ghz\\":" * json_number(frequency_error_ghz) *
        "}}," *
        "\\"plan\\":" * plan_json *
        "}}"
'''

    script += '''    open(result_path, "w") do io
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
    analysis_mode: str = "auto",
    pump_current_fraction: float = 0.017,
    coupling_capacitance_ff: float | None = None,
    resonator_capacitance_ff: float | None = None,
    target_frequency_ghz: float | None = None,
    target_gain_db: float = 20.0,
    target_bandwidth_mhz: float | None = None,
) -> dict[str, Any]:
    """Return the command/data plan for a JosephsonCircuits.jl harmonic-balance run."""
    info = sidecar.get("info", {})
    area_um2 = float(info.get("junction_area_um2", 0.0))
    ic_ua = critical_current_ua(area_um2, jc_ua_per_um2=jc_ua_per_um2) if area_um2 else 0.0
    lj_ph = josephson_inductance_ph(ic_ua) if ic_ua else None
    resolved_analysis = resolve_josephsoncircuits_analysis_mode(sidecar, analysis_mode)
    center_ghz = _target_value(sidecar, "center_frequency_ghz", target_frequency_ghz, 5.0)
    bandwidth_mhz = _target_value(sidecar, "target_bandwidth_mhz", target_bandwidth_mhz, 500.0)
    analysis_type = (
        "multiport_ljpa_harmonic_balance"
        if resolved_analysis == "multiport_ljpa"
        else "single_port_reflection_harmonic_balance"
    )
    if resolved_analysis == "multiport_ljpa":
        notes = [
            "This adapter runs a two-port lumped LJPA harmonic-balance starter model.",
            "It derives Lj from the sidecar JJ area and Jc, derives a target resonator "
            "capacitance from the requested center frequency unless overridden, and exports "
            "S11/S21/S12/S22 gain arrays.",
            "Treat the model as layout-derived circuit iteration, not EM or foundry signoff.",
        ]
    else:
        notes = [
            "This adapter runs a single-port reflection harmonic-balance starter model.",
            "Coupling and capacitance defaults are placeholders unless explicit capacitance "
            "values are supplied.",
            "Use extracted CPW, coupling, and shunt networks for signoff-grade gain/noise.",
        ]
    return {
        "adapter": select_adapter("JosephsonCircuits.jl"),
        "analysis_mode": resolved_analysis,
        "analysis_type": analysis_type,
        "auto_multiport_eligible": supports_multiport_ljpa(sidecar),
        "target_frequency_ghz": center_ghz,
        "target_gain_db": target_gain_db,
        "target_bandwidth_mhz": bandwidth_mhz,
        "user_requested": {
            "analysis_mode": analysis_mode,
            "target_frequency_ghz": target_frequency_ghz,
            "target_bandwidth_mhz": target_bandwidth_mhz,
            "coupling_capacitance_ff": coupling_capacitance_ff,
            "resonator_capacitance_ff": resonator_capacitance_ff,
            "pump_current_fraction": pump_current_fraction,
        },
        "layout_derived_parameters": {
            "junction_area_um2": area_um2,
            "jc_ua_per_um2": jc_ua_per_um2,
            "critical_current_ua": ic_ua,
            "josephson_inductance_ph": lj_ph,
            "ports": sidecar.get("ports", []),
        },
        "model_assumptions": {
            "port_impedance_ohm": 50.0,
            "default_pump_current_fraction": pump_current_fraction,
            "default_coupling_capacitance": (
                "5 percent of derived target resonator capacitance, minimum 5 fF"
                if coupling_capacitance_ff is None
                else f"{coupling_capacitance_ff} fF"
            ),
            "default_resonator_capacitance": (
                "derived from Lj and target center frequency"
                if resonator_capacitance_ff is None
                else f"{resonator_capacitance_ff} fF"
            ),
        },
        "next_files": {
            "julia_script": "workspace/artifacts/<name>.josephsoncircuits.jl",
            "simulation_json": "workspace/artifacts/<name>.josephsoncircuits.json",
        },
        "notes": notes,
    }
