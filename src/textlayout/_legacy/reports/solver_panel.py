"""Solver evidence panel generation and validation."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_STATUSES: set[str] = {"EXECUTED", "SKIPPED", "FAILED"}


def check_flat_s_parameters(
    frequencies: list[float],
    s_db: list[float],
    tolerance_db: float = 0.01,
) -> bool:
    """Return True if S-parameters are suspiciously flat (all within tolerance of a single value)."""
    if len(s_db) < 2:
        return False
    ref = s_db[0]
    return all(abs(v - ref) <= tolerance_db for v in s_db)


def solver_evidence_panel(
    solver_name: str,
    status: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    """Create a structured solver evidence panel.

    Raises ValueError for invalid status or missing required fields.
    """
    status = status.upper()
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status {status!r}; must be one of {sorted(VALID_STATUSES)}")

    panel: dict[str, Any] = {
        "schema": "text-to-gds.solver-panel.v1",
        "solver": solver_name,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if status == "EXECUTED":
        required = ("solver_version", "command", "runtime_s", "output_files", "parsed_quantities")
        missing = [k for k in required if k not in details]
        if missing:
            raise ValueError(f"EXECUTED panel requires: {', '.join(missing)}")
        output_files = details["output_files"]
        if not isinstance(output_files, list) or not output_files:
            raise ValueError("EXECUTED panel requires at least one output file")
        for f in output_files:
            if not Path(f).exists():
                raise ValueError(f"Output file does not exist: {f}")
        panel["solver_version"] = details["solver_version"]
        panel["command"] = details["command"]
        panel["runtime_s"] = float(details["runtime_s"])
        panel["output_files"] = [str(f) for f in output_files]
        panel["parsed_quantities"] = dict(details["parsed_quantities"])

        # Check for flat S-parameters (fake data guard)
        pq = details["parsed_quantities"]
        for key in ("S11_dB", "S22_dB", "s11_db", "s22_db"):
            s_data = pq.get(key)
            freqs = pq.get("frequencies_ghz") or pq.get("frequencies")
            if isinstance(s_data, list) and isinstance(freqs, list):
                if check_flat_s_parameters(freqs, s_data):
                    if all(abs(v) < 0.01 for v in s_data):
                        raise ValueError(
                            f"{key} is exactly 0 dB across all frequencies — rejected as fake data"
                        )

    elif status == "SKIPPED":
        reason = details.get("reason")
        if not reason:
            raise ValueError("SKIPPED panel requires 'reason'")
        panel["reason"] = str(reason)

    elif status == "FAILED":
        error = details.get("error")
        if not error:
            raise ValueError("FAILED panel requires 'error'")
        panel["error"] = str(error)

    return panel


def validate_solver_evidence(evidence: dict[str, Any]) -> list[str]:
    """Validate a solver evidence panel dict and return a list of error messages (empty = valid)."""
    errors: list[str] = []

    if "solver" not in evidence:
        errors.append("Missing 'solver' field")
    status = evidence.get("status", "")
    if status not in VALID_STATUSES:
        errors.append(f"Invalid status {status!r}; must be one of {sorted(VALID_STATUSES)}")
        return errors  # cannot validate further

    if status == "EXECUTED":
        for field in ("solver_version", "command", "runtime_s", "output_files", "parsed_quantities"):
            if field not in evidence:
                errors.append(f"EXECUTED panel missing '{field}'")
        output_files = evidence.get("output_files", [])
        if isinstance(output_files, list):
            if not output_files:
                errors.append("EXECUTED panel has empty output_files list")
            for f in output_files:
                if not Path(f).exists():
                    errors.append(f"Output file does not exist: {f}")
        else:
            errors.append("output_files must be a list")

        runtime = evidence.get("runtime_s")
        if runtime is not None and (not isinstance(runtime, (int, float)) or math.isnan(runtime)):
            errors.append("runtime_s must be a finite number")

        pq = evidence.get("parsed_quantities", {})
        if isinstance(pq, dict):
            for key in ("S11_dB", "S22_dB", "s11_db", "s22_db"):
                s_data = pq.get(key)
                freqs = pq.get("frequencies_ghz") or pq.get("frequencies")
                if isinstance(s_data, list) and isinstance(freqs, list):
                    if check_flat_s_parameters(freqs, s_data):
                        if all(abs(v) < 0.01 for v in s_data):
                            errors.append(f"{key} is exactly 0 dB across all frequencies (fake data)")

    elif status == "SKIPPED":
        if not evidence.get("reason"):
            errors.append("SKIPPED panel missing 'reason'")

    elif status == "FAILED":
        if not evidence.get("error"):
            errors.append("FAILED panel missing 'error'")

    return errors


def format_panel_text(panel: dict[str, Any]) -> str:
    """Format a solver evidence panel as a text block for display."""
    status = panel.get("status", "UNKNOWN")
    solver = panel.get("solver", "unknown")
    lines: list[str] = []

    if status == "EXECUTED":
        lines.append("SOLVER EXECUTED")
        lines.append(f"Engine:    {solver} {panel.get('solver_version', '')}")
        lines.append(f"Command:   {panel.get('command', '')}")
        files = panel.get("output_files", [])
        for f in files:
            p = Path(f)
            try:
                size = p.stat().st_size
                lines.append(f"Output:    {p.name} ({size} bytes)")
            except OSError:
                lines.append(f"Output:    {p.name} (file not found)")
        runtime = panel.get("runtime_s")
        if runtime is not None:
            lines.append(f"Runtime:   {runtime:.1f}s")
        ts = panel.get("timestamp", "")
        if ts:
            lines.append(f"Timestamp: {ts}")
        pq = panel.get("parsed_quantities", {})
        if pq:
            lines.append("Quantities:")
            for k, v in sorted(pq.items()):
                if not isinstance(v, (list, dict)):
                    lines.append(f"  {k}: {v}")

    elif status == "SKIPPED":
        lines.append("SOLVER SKIPPED")
        lines.append(f"Engine:    {solver}")
        lines.append(f"Reason:    {panel.get('reason', 'not available')}")

    elif status == "FAILED":
        lines.append("SOLVER FAILED")
        lines.append(f"Engine:    {solver}")
        lines.append(f"Error:     {panel.get('error', 'unknown')}")

    else:
        lines.append(f"SOLVER STATUS: {status}")
        lines.append(f"Engine:    {solver}")

    return "\n".join(lines)
