#!/usr/bin/env python
"""Unified circuit-simulator availability checker (stdlib only).

Prints one table — Simulator | Available | Detection Method | Path |
Version/Help | Status | Notes — and encodes the honesty policy:

- JoSIM is the primary backend; PSCAN2 and WRspice are optional.
- Normal mode always exits 0, even when optional simulators are absent.
- Strict mode (``--strict`` or ``TEXTLAYOUT_STRICT_SIMULATORS=1``) exits
  nonzero when a *required* simulator (default: josim; extend with
  ``--require``) is not ready.

Detection here is the reference policy; the runtime adapters in
``src/textlayout/simulation`` follow the same priority order
(environment variable → ``.tools/<sim>/bin`` → PATH), which is enforced by
``tests/textlayout_suite/test_simulator_bootstrap.py``.

An installed simulator never means physics is verified: ``PHYSICS_VERIFIED``
still requires a real extraction plus a real simulation meeting declared
tolerances.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from importlib.util import find_spec
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]

STATUS_READY = "ready"
STATUS_ABSENT = "absent"
STATUS_MANUAL = "manual_install_required"
STATUS_INSTALL_FAILED = "install_failed"
STATUS_SKIPPED_OPTIONAL = "skipped_optional"
STATUS_STRICT_MISSING = "strict_missing"

JOSIM_NAMES = ("josim-cli", "josim-cli.exe", "josim", "josim.exe")
WRSPICE_NAMES = ("wrspice", "wrspice.exe", "wrspice64", "wrspice64.exe")
FASTERCAP_NAMES = ("FasterCap", "FasterCap.exe", "fastcap", "fastcap.exe")

_MANIFEST_NAME = "simulators.json"


@dataclass
class Detection:
    """One simulator's detection outcome (status is assigned later)."""

    name: str
    available: bool = False
    method: str = "none"
    path: str | None = None
    version: str | None = None
    status: str = STATUS_ABSENT
    notes: list[str] = field(default_factory=list)


def default_tools_dir(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    override = env.get("TEXTLAYOUT_TOOLS_DIR")
    return Path(override) if override else REPO_ROOT / ".tools"


def manifest_path(tools_dir: Path) -> Path:
    return tools_dir / _MANIFEST_NAME


def read_manifest(tools_dir: Path) -> dict:
    path = manifest_path(tools_dir)
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        return {}


def write_manifest_entry(tools_dir: Path, simulator: str, entry: dict) -> None:
    tools_dir.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(tools_dir)
    manifest[simulator] = entry
    manifest_path(tools_dir).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def capture_version(executable: str) -> str | None:
    """Best-effort one-line version/help banner; never raises."""
    for flag in ("--version", "-v", "--help", "-h"):
        try:
            result = subprocess.run(
                [executable, flag],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        text = (result.stdout or result.stderr).strip()
        if text:
            for line in text.splitlines():
                if line.strip():
                    return line.strip()[:120]
    return None


def _resolve_env_candidate(candidate: str) -> str | None:
    path = Path(candidate)
    if path.is_file():
        return str(path)
    return shutil.which(candidate)


def _detect_executable(
    name: str,
    env_var: str,
    executable_names: tuple[str, ...],
    tool_subdir: str,
    tools_dir: Path,
    env: Mapping[str, str],
) -> Detection:
    """Shared priority: env var → .tools/<sim>/bin/<names> → PATH <names>."""
    detection = Detection(name=name)
    candidate = env.get(env_var)
    if candidate:
        resolved = _resolve_env_candidate(candidate)
        if resolved:
            detection.available = True
            detection.method = f"env:{env_var}"
            detection.path = resolved
            return detection
        detection.notes.append(f"{env_var} is set but does not resolve to a file")
    bin_dir = tools_dir / tool_subdir / "bin"
    for exe_name in executable_names:
        tool_path = bin_dir / exe_name
        if tool_path.is_file():
            detection.available = True
            detection.method = "tools_dir"
            detection.path = str(tool_path)
            return detection
    for exe_name in executable_names:
        found = shutil.which(exe_name)
        if found:
            detection.available = True
            detection.method = "path"
            detection.path = found
            return detection
    return detection


def detect_josim(
    tools_dir: Path | None = None, env: Mapping[str, str] | None = None
) -> Detection:
    env = os.environ if env is None else env
    tools_dir = default_tools_dir(env) if tools_dir is None else tools_dir
    return _detect_executable(
        "JoSIM", "TEXTLAYOUT_JOSIM", JOSIM_NAMES, "josim", tools_dir, env
    )


def detect_wrspice(
    tools_dir: Path | None = None, env: Mapping[str, str] | None = None
) -> Detection:
    env = os.environ if env is None else env
    tools_dir = default_tools_dir(env) if tools_dir is None else tools_dir
    return _detect_executable(
        "WRspice", "TEXTLAYOUT_WRSPICE", WRSPICE_NAMES, "wrspice", tools_dir, env
    )


def detect_pscan2(
    tools_dir: Path | None = None, env: Mapping[str, str] | None = None
) -> Detection:
    """PSCAN2 policy: env var → importable Python module → conda hint."""
    env = os.environ if env is None else env
    del tools_dir  # PSCAN2 is a Python package, not a .tools binary
    detection = Detection(name="PSCAN2")
    candidate = env.get("TEXTLAYOUT_PSCAN2")
    if candidate:
        resolved = _resolve_env_candidate(candidate)
        if resolved:
            detection.available = True
            detection.method = "env:TEXTLAYOUT_PSCAN2"
            detection.path = resolved
            return detection
        detection.notes.append("TEXTLAYOUT_PSCAN2 is set but does not resolve to a file")
    try:
        spec = find_spec("pscan2")
    except (ImportError, ValueError):
        spec = None
    if spec is not None:
        detection.available = True
        detection.method = "python_import"
        detection.path = spec.origin or "importable module"
        detection.version = "python module 'pscan2' importable"
        return detection
    conda = shutil.which("conda") or shutil.which("mamba")
    if conda:
        detection.notes.append(
            f"conda/mamba found at {conda}; see docs/simulators/install.md for PSCAN2 setup"
        )
    return detection


def detect_fastercap(
    tools_dir: Path | None = None, env: Mapping[str, str] | None = None
) -> Detection:
    env = os.environ if env is None else env
    tools_dir = default_tools_dir(env) if tools_dir is None else tools_dir
    manifest = read_manifest(tools_dir)
    detection = _detect_executable(
        "FasterCap", "TEXTLAYOUT_FASTERCAP", FASTERCAP_NAMES, "FasterCap", tools_dir, env
    )
    if not detection.available:
        recorded = manifest.get("fastercap", {})
        recorded_path = recorded.get("path")
        if isinstance(recorded_path, str) and recorded_path:
            detection.method = f"manifest:{recorded.get('method', 'recorded')}"
            detection.path = recorded_path
            if os.name == "nt" and str(recorded.get("method", "")).startswith("wsl"):
                detection.notes.append("WSL-built FasterCap recorded; run inside Ubuntu/WSL to execute")
    if detection.available and detection.path:
        suffix = Path(detection.path).suffix.lower()
        if os.name == "nt" and suffix not in (".exe", ".bat", ".cmd"):
            detection.available = False
            recorded = manifest.get("fastercap", {})
            recorded_path = recorded.get("path")
            if isinstance(recorded_path, str) and recorded_path:
                detection.method = f"manifest:{recorded.get('method', 'recorded')}"
                detection.path = recorded_path
            else:
                detection.method = "tools_dir"
                detection.path = None
            detection.notes.append("found a non-Windows executable; install/run FasterCap from WSL")
    return detection


def _assign_status(
    detection: Detection,
    *,
    simulator_key: str,
    strict: bool,
    required: set[str],
    manifest: dict,
) -> None:
    """Apply the status vocabulary and honesty notes."""
    if detection.available:
        detection.status = STATUS_READY
        detection.notes.append(
            "installed != physics verified; PHYSICS_VERIFIED needs real extraction "
            "+ simulation within tolerance"
        )
        return
    recorded = manifest.get(simulator_key, {})
    if simulator_key == "fastercap" and recorded.get("status") == STATUS_READY:
        detection.status = STATUS_READY
        detection.notes.append(
            "verified WSL/Linux FasterCap recorded; execute it from Ubuntu/WSL"
        )
        detection.notes.append(
            "installed != physics verified; PHYSICS_VERIFIED needs real extraction "
            "+ simulation within tolerance"
        )
        return
    if recorded.get("status") == STATUS_INSTALL_FAILED:
        detection.status = STATUS_INSTALL_FAILED
        reason = recorded.get("reason")
        if reason:
            detection.notes.append(f"last install attempt failed: {reason}")
    elif simulator_key == "josim":
        detection.status = STATUS_ABSENT
        detection.notes.append("primary backend; run `make setup-simulators` to install")
    elif simulator_key == "fastercap":
        detection.status = STATUS_MANUAL
        detection.notes.append(
            "capacitance extraction is WSL/Linux-first; run `python scripts/bootstrap_simulators.py`"
        )
    else:
        detection.status = STATUS_MANUAL
        detection.notes.append(
            "optional backend; automatic install is not reliable - see "
            "docs/simulators/install.md"
        )
    if strict:
        if simulator_key in required:
            detection.status = STATUS_STRICT_MISSING
        elif detection.status in (STATUS_MANUAL, STATUS_ABSENT):
            detection.status = STATUS_SKIPPED_OPTIONAL


def collect_reports(
    tools_dir: Path,
    *,
    strict: bool = False,
    required: set[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> list[Detection]:
    env = os.environ if env is None else env
    required = {"josim"} if required is None else required
    manifest = read_manifest(tools_dir)
    reports: list[Detection] = []
    for key, detector in (
        ("josim", detect_josim),
        ("fastercap", detect_fastercap),
        ("pscan2", detect_pscan2),
        ("wrspice", detect_wrspice),
    ):
        detection = detector(tools_dir, env)
        if detection.available and detection.version is None and detection.path:
            detection.version = capture_version(detection.path)
        _assign_status(
            detection,
            simulator_key=key,
            strict=strict,
            required=required,
            manifest=manifest,
        )
        reports.append(detection)
    return reports


def render_table(reports: list[Detection]) -> str:
    headers = (
        "Simulator",
        "Available",
        "Detection Method",
        "Path",
        "Version/Help",
        "Status",
        "Notes",
    )
    rows = [headers]
    for report in reports:
        rows.append(
            (
                report.name,
                "yes" if report.available else "no",
                report.method,
                report.path or "-",
                (report.version or "-")[:60],
                report.status,
                "; ".join(report.notes) or "-",
            )
        )
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(headers))]
    lines = []
    for index, row in enumerate(rows):
        lines.append(" | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
        if index == 0:
            lines.append("-+-".join("-" * width for width in widths))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tools-dir",
        default=None,
        help="Local simulator directory (default: <repo>/.tools or TEXTLAYOUT_TOOLS_DIR).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero when a required simulator is missing "
        "(also enabled by TEXTLAYOUT_STRICT_SIMULATORS=1).",
    )
    parser.add_argument(
        "--require",
        default="josim",
        help="Comma-separated simulators required in strict mode (default: josim).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of the table."
    )
    args = parser.parse_args(argv)

    strict = args.strict or os.environ.get("TEXTLAYOUT_STRICT_SIMULATORS") == "1"
    required = {name.strip().lower() for name in args.require.split(",") if name.strip()}
    tools_dir = Path(args.tools_dir) if args.tools_dir else default_tools_dir()

    reports = collect_reports(tools_dir, strict=strict, required=required)
    if args.json:
        print(json.dumps([asdict(report) for report in reports], indent=2))
    else:
        print(f"platform: {platform.platform()}  python: {platform.python_version()}")
        print(f"tools dir: {tools_dir}")
        print()
        print(render_table(reports))
        print()
        print(
            "Reminder: circuit simulators do not replace geometry-level extraction; "
            "FasterCap/FastCap is required for IDC capacitance evidence."
        )
    if strict:
        missing = [report for report in reports if report.status == STATUS_STRICT_MISSING]
        if missing:
            names = ", ".join(report.name for report in missing)
            print(f"\nSTRICT MODE FAILURE: required simulators missing: {names}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
