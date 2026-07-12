"""Pinned ParaView identity and isolated-install helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from _common import ROOT, sha256_file

VERSION = "5.13.3"
COMMIT = "33274c1e71474b91721a41e3c449277d1e67d1ae"
BINARY_URL = "https://www.paraview.org/files/v5.13/ParaView-5.13.3-Windows-Python3.10-msvc2017-AMD64.msi"
BINARY_SHA256 = "1366a4b1be5047ef03b7bad312dd7fb9a8728dd246a7ca085b9b6e8d86868b3b"
BINARY_SIZE = 416_665_600
ROOT_DIR = ROOT / ".tools" / "paraview"
MSI = ROOT_DIR / "ParaView-5.13.3-Windows-Python3.10-msvc2017-AMD64.msi"
PREFIX = ROOT_DIR / VERSION
INSTALL_RECORD = ROOT_DIR / "install.json"
INSTALL_REPORT = ROOT / "out" / "toolchain" / "paraview_install.json"
SMOKE_ROOT = ROOT / "out" / "toolchain" / "paraview_smoke"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def find_pvpython() -> Path | None:
    matches = sorted(PREFIX.glob("**/pvpython.exe"))
    return matches[0].resolve() if matches else None


def identity() -> dict[str, Any] | None:
    executable = find_pvpython()
    if executable is None:
        return None
    completed = subprocess.run(
        [str(executable), "--version"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    output = completed.stdout + completed.stderr
    if completed.returncode != 0 or VERSION not in output:
        return None
    return {
        "status": "IDENTITY_VERIFIED",
        "version": VERSION,
        "commit": COMMIT,
        "executable": str(executable),
        "executable_sha256": sha256_file(executable),
        "version_output": output.strip(),
    }

