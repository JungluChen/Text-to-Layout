"""Assemble a full openEMS evidence report from a completed (or failed) run.

One honest document per device: what was targeted, what the solver actually
produced, how the model was set up (mesh / ports / boundaries / excitation),
whether the run converged, and the resulting status classification — plus a
diagnosis section whenever the classification is anything short of
PHYSICS_VERIFIED. The report never invents fields: everything is read from
the run directory's own artifacts (driver, manifest, solver logs, Touchstone).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from textlayout.simulation.models import SimulationResult

OPENEMS_EVIDENCE_SCHEMA = "textlayout.openems-evidence.v1"

_MESH_RE = re.compile(r"^mesh\.[xyz] = .*$", re.M)
_PORT_RE = re.compile(r"^\[CSX, port\{\d\}\] = Add\w+Port\(.*$", re.M)
_BC_RE = re.compile(r"^FDTD = SetBoundaryCond\((.*)\);$", re.M)
_EXCITE_RE = re.compile(r"^FDTD = (InitFDTD|SetGaussExcite)\((.*)\);$", re.M)
_ENERGY_RE = re.compile(r"Energy:.*\((\s*-?\d+(?:\.\d+)?)dB\)")
_EXCITE_LEN_RE = re.compile(r"Excitation signal length is:\s+(\d+)\s+timesteps")
_TIMESTEP_RE = re.compile(r"Timestep:\s+(\d+)")


def _driver_summary(driver_path: Path) -> dict[str, Any]:
    if not driver_path.is_file():
        return {"available": False}
    text = driver_path.read_text(encoding="utf-8")
    bc = _BC_RE.search(text)
    return {
        "available": True,
        "mesh_lines": _MESH_RE.findall(text),
        "ports": _PORT_RE.findall(text),
        "boundary_conditions": bc.group(1) if bc else None,
        "excitation": [" = ".join(m) for m in _EXCITE_RE.findall(text)],
    }


def _convergence_summary(stdout_path: Path | None) -> dict[str, Any]:
    if stdout_path is None or not stdout_path.is_file():
        return {"log_available": False}
    text = stdout_path.read_text(encoding="utf-8", errors="replace")
    energies = [float(v) for v in _ENERGY_RE.findall(text)]
    timesteps = [int(v) for v in _TIMESTEP_RE.findall(text)]
    excite = _EXCITE_LEN_RE.search(text)
    excite_ts = int(excite.group(1)) if excite else None
    final_ts = timesteps[-1] if timesteps else None
    return {
        "log_available": True,
        "final_timestep": final_ts,
        "excitation_length_timesteps": excite_ts,
        "excitation_fully_recorded": (
            bool(final_ts and excite_ts and final_ts >= 0.9 * excite_ts)
            if (final_ts and excite_ts)
            else None
        ),
        "final_energy_decay_db": energies[-1] if energies else None,
        "energy_tail_db": energies[-5:],
        "energy_plateaued": (
            len(energies) >= 5 and max(energies[-5:]) - min(energies[-5:]) < 0.2
        ),
    }


def classify(result: SimulationResult) -> tuple[str, str]:
    """(status_label, reason) under the project evidence vocabulary."""
    if result.status == "skipped":
        return "SKIPPED_SOLVER_ABSENT", result.reason
    if result.status == "failed":
        return "SIMULATION_FAILED", result.reason
    if result.status == "executed":
        comparison = result.target_comparison or {}
        if comparison.get("within_tolerance") and result.physics_verified:
            return (
                "PHYSICS_VERIFIED",
                "Real solver output parsed; convergence gates passed; extracted "
                f"value within {comparison.get('tolerance_pct')}% of target.",
            )
        return (
            "SIMULATION_EXECUTED",
            "Real solver output parsed, but the extracted value misses the "
            "target tolerance — executed evidence, NOT physics-verified.",
        )
    return "SIMULATION_INPUT_PREPARED", result.reason


def build_openems_evidence(
    result: SimulationResult,
    *,
    device_type: str,
    target_value: float | None,
    target_unit: str,
    diagnosis: list[str] | None = None,
) -> dict[str, Any]:
    artifacts = dict(result.artifacts)
    run_dir = Path(result.output_dir) if result.output_dir else None
    driver = Path(artifacts["driver"]) if "driver" in artifacts else None
    if driver is not None and not driver.is_absolute() and run_dir is not None:
        driver = run_dir / driver.name if not driver.is_file() else driver
    stdout = Path(artifacts["solver_stdout"]) if "solver_stdout" in artifacts else None

    status_label, reason = classify(result)
    comparison = result.target_comparison or {}
    report: dict[str, Any] = {
        "schema": OPENEMS_EVIDENCE_SCHEMA,
        "device_type": device_type,
        "status": status_label,
        "reason": reason,
        "target_value": target_value,
        "target_unit": target_unit,
        "extracted_quantities": dict(result.extracted_quantities),
        "error_percent": comparison.get("error_pct"),
        "tolerance_percent": comparison.get("tolerance_pct"),
        "within_tolerance": comparison.get("within_tolerance"),
        "solver_backend": result.solver,
        "solver_version": result.solver_version,
        "solver_command": list(result.command or ()),
        "runtime_seconds": result.runtime_seconds,
        "raw_output_paths": artifacts,
        "touchstone_path": artifacts.get("touchstone"),
        "model_setup": _driver_summary(driver) if driver else {"available": False},
        "convergence": _convergence_summary(stdout),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if status_label != "PHYSICS_VERIFIED":
        report["known_issue"] = diagnosis or [reason]
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# openEMS evidence — {report['device_type']}",
        "",
        f"- **Status:** **{report['status']}**",
        f"- **Reason:** {report['reason']}",
        f"- **Target:** {report['target_value']} {report['target_unit']}",
        f"- **Solver:** `{report['solver_backend']}` ({report.get('solver_version')})",
        f"- **Runtime:** {report.get('runtime_seconds')} s",
        f"- **Generated:** {report['timestamp']}",
        "",
        "## Extracted quantities",
        "",
        "```json",
        json.dumps(report["extracted_quantities"], indent=2),
        "```",
        "",
        f"- Error vs target: **{report.get('error_percent')}%** "
        f"(tolerance {report.get('tolerance_percent')}%, "
        f"within: {report.get('within_tolerance')})",
        "",
        "## Convergence",
        "",
        "```json",
        json.dumps(report["convergence"], indent=2),
        "```",
        "",
        "## Model setup (from the generated Octave driver)",
        "",
        "```json",
        json.dumps(report["model_setup"], indent=2),
        "```",
    ]
    if "known_issue" in report:
        lines += ["", "## Known issue / diagnosis", ""]
        lines += [f"- {item}" for item in report["known_issue"]]
    lines += [
        "",
        "## Honesty statement",
        "",
        "Only `PHYSICS_VERIFIED` means: real solver output, parsed cleanly,",
        "convergence gates passed, and the extracted value within the stated",
        "tolerance of the target. Every other label is exactly what it says.",
        "Nothing here is fabrication-ready.",
        "",
    ]
    return "\n".join(lines)


def write_openems_evidence(
    result: SimulationResult,
    out_dir: str | Path,
    *,
    device_type: str,
    target_value: float | None,
    target_unit: str,
    stem: str,
    diagnosis: list[str] | None = None,
) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_openems_evidence(
        result,
        device_type=device_type,
        target_value=target_value,
        target_unit=target_unit,
        diagnosis=diagnosis,
    )
    json_path = out / f"{stem}.json"
    md_path = out / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
