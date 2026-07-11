"""Shared, pinned Palace/Gmsh installation and validation helpers."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".tools"
PALACE_ROOT = TOOLS / "palace"
INSTALL_RECORD = PALACE_ROOT / "install.json"
INSTALL_REPORT = ROOT / "out" / "toolchain" / "palace_install.json"
CHECK_REPORT = ROOT / "out" / "toolchain" / "palace_check.json"
SMOKE_ROOT = ROOT / "out" / "toolchain" / "palace_smoke"
BENCHMARK_ROOT = ROOT / "out" / "palace_resonator_v017"
REGISTRY = ROOT / "external_tools" / "registry.toml"
LOCK = ROOT / "external_tools" / "lock.toml"
SPACK_ENV = ROOT / "external_tools" / "palace"
SMOKE_MANIFEST = SPACK_ENV / "smoke" / "eigenmode" / "manifest.json"

PALACE_VERSION = "0.17.0"
PALACE_COMMIT = "12d8069afb5aa9e169a17e303d735e120968e9f2"
PALACE_SOURCE_SHA256 = "169f7fe210ea6e771a29bfe0803dd84a774b25b00d2aa3a1f33b9d97a510ff9d"
GMESH_VERSION = "4.15.2"
SPACK_VERSION = "1.1.0"
SPACK_COMMIT = "0c2be44e4ece21eb091ad5de4c97716b7c6d4c87"
SPACK_PACKAGES_COMMIT = "a2928a3376d286ddbf07da62847d5ba5b0fa3c67"


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wsl_executable() -> str | None:
    if os.name != "nt":
        return None
    return shutil.which("wsl.exe") or shutil.which("wsl")


def windows_to_wsl(path: Path) -> str:
    resolved = path.resolve()
    if os.name != "nt":
        return str(resolved)
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[1].lstrip("/")
    return f"/mnt/{drive}/{tail}"


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    timeout: float = 3600,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(completed.stdout, encoding="utf-8")
    if stderr_path is not None:
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.write_text(completed.stderr, encoding="utf-8")
    return completed


def run_wsl(script: str, *, timeout: float = 3600) -> subprocess.CompletedProcess[str]:
    wsl = wsl_executable()
    command = (
        [wsl, "-d", "Ubuntu", "--", "bash", "-lc", script]
        if wsl is not None
        else ["bash", "-lc", script]
    )
    return run(command, timeout=timeout)


def shell_command(script: str) -> list[str]:
    wsl = wsl_executable()
    return (
        [wsl, "-d", "Ubuntu", "--", "bash", "-lc", script]
        if wsl is not None
        else ["bash", "-lc", script]
    )


def gmsh_identity() -> dict[str, Any]:
    from textlayout.mesh.runtime import gmsh_identity as identify

    return identify()


def palace_archive() -> Path:
    return (
        TOOLS
        / "external"
        / "sources"
        / f"palace-{PALACE_COMMIT}.tar.gz"
    )


def verify_palace_archive() -> dict[str, Any]:
    archive = palace_archive()
    if not archive.is_file():
        return {"available": False, "path": str(archive), "sha256": None}
    digest = sha256_file(archive)
    return {
        "available": digest == PALACE_SOURCE_SHA256,
        "path": str(archive),
        "sha256": digest,
        "size_bytes": archive.stat().st_size,
    }


def download(url: str, destination: Path, expected_sha256: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and sha256_file(destination) == expected_sha256:
        return destination
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "textlayout-palace"})
    with urllib.request.urlopen(request, timeout=600) as response, temporary.open("wb") as out:
        shutil.copyfileobj(response, out)
    actual = sha256_file(temporary)
    if actual != expected_sha256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"download hash mismatch for {url}: {actual}")
    temporary.replace(destination)
    return destination


def palace_install_identity() -> dict[str, Any] | None:
    record = read_json(INSTALL_RECORD)
    if record is None:
        return None
    executable = str(record.get("palace_executable", ""))
    target = executable.removeprefix("wsl:")
    probe = (
        run_wsl(
            f"test -x {shlex_quote(target)} && {shlex_quote(target)} --version && "
            f"sha256sum {shlex_quote(target)}",
            timeout=120,
        )
        if executable.startswith("wsl:")
        else run([target, "--version"], timeout=120)
    )
    if probe.returncode != 0 or PALACE_VERSION not in probe.stdout:
        return None
    digest = (
        probe.stdout.strip().splitlines()[-1].split()[0]
        if executable.startswith("wsl:")
        else sha256_file(Path(target))
    )
    if digest != record.get("palace_executable_sha256"):
        return None
    return record


def shlex_quote(value: str) -> str:
    import shlex

    return shlex.quote(value)
