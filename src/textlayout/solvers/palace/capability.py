"""Detection and immutable identity capture for Palace, MPI, and containers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textlayout.evidence.canonical import sha256_file
from textlayout._paths import repository_root
from textlayout.simulation.runners import (
    _execution_command,
    _windows_to_wsl,
    find_executable,
)
from textlayout.solvers.palace.models import PalaceCapability

_WSL_PREFIX = "wsl:"
_INSTALL_RECORD = repository_root() / ".tools" / "palace" / "install.json"
PALACE_REQUIRED_VERSION = "0.17.0"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(
    r"Palace\s+(?:version:?\s*)?\(?v?"
    r"([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:-[0-9]+-g[0-9a-f]+)?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PalaceInstallResolution:
    """Validation result for the shared Palace installation record."""

    record_path: Path
    record: dict[str, Any] | None
    capability: PalaceCapability | None
    rejection_reasons: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.record is not None and self.capability is not None


def _wsl_exe() -> str:
    return shutil.which("wsl") or "wsl"


def _hash_executable(executable: str) -> str | None:
    if executable.startswith(_WSL_PREFIX):
        target = executable.removeprefix(_WSL_PREFIX)
        try:
            completed = subprocess.run(
                [_wsl_exe(), "sha256sum", target],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        token = completed.stdout.split(maxsplit=1)
        return token[0] if token and len(token[0]) == 64 else None
    path = Path(executable)
    return sha256_file(path) if path.is_file() else None


def _probe(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = _VERSION_RE.search(f"{completed.stdout}\n{completed.stderr}")
    return match.group(1) if match else None


def _probe_executable_version(executable: str) -> str | None:
    for flags in (["--version"], ["--help"], ["-h"], []):
        version = _probe(_execution_command(executable, list(flags), Path.cwd()))
        if version:
            return version
    return None


def resolve_palace_install(
    record_path: str | Path | None = None,
    *,
    required_version: str = PALACE_REQUIRED_VERSION,
) -> PalaceInstallResolution:
    """Validate one native-Linux or Windows/WSL Palace install record.

    A manifest is discovery metadata, not evidence by itself. Acceptance
    requires an ``INSTALLED`` record, the pinned version, a runnable live
    executable, and a SHA-256 that matches the current executable bytes.
    """
    path = Path(record_path) if record_path is not None else _INSTALL_RECORD
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return PalaceInstallResolution(path, None, None)
    except (OSError, json.JSONDecodeError) as exc:
        return PalaceInstallResolution(path, None, None, (f"invalid install record: {exc}",))
    if not isinstance(payload, dict):
        return PalaceInstallResolution(path, None, None, ("install record is not an object",))

    problems: list[str] = []
    if payload.get("status") != "INSTALLED":
        problems.append("install status is not INSTALLED")
    recorded_version = payload.get("palace_version")
    if recorded_version != required_version:
        problems.append(
            f"recorded Palace version {recorded_version!r} is not {required_version!r}"
        )
    executable = payload.get("palace_executable")
    if not isinstance(executable, str) or not executable:
        problems.append("palace_executable is missing")
        executable = ""
    expected_hash = payload.get("palace_executable_sha256")
    if not isinstance(expected_hash, str) or not _SHA256_RE.fullmatch(expected_hash.casefold()):
        problems.append("palace_executable_sha256 is not a SHA-256 digest")
        expected_hash = ""

    if executable and not executable.startswith(_WSL_PREFIX):
        executable_path = Path(executable)
        if not executable_path.is_file():
            problems.append(f"Palace executable does not exist: {executable}")
        elif not os.access(executable_path, os.X_OK):
            problems.append(f"Palace executable is not executable: {executable}")

    live_version = _probe_executable_version(executable) if executable and not problems else None
    if executable and not problems and live_version != required_version:
        problems.append(
            f"live Palace version {live_version!r} is not {required_version!r}"
        )
    actual_hash = _hash_executable(executable) if executable and not problems else None
    if executable and not problems and actual_hash != expected_hash.casefold():
        problems.append(
            "Palace executable SHA-256 does not match install record "
            f"({actual_hash!r} != {expected_hash.casefold()!r})"
        )
    if problems:
        return PalaceInstallResolution(path, payload, None, tuple(problems))

    return PalaceInstallResolution(
        path,
        payload,
        PalaceCapability(
            execution_kind="executable",
            executable=executable,
            version=live_version,
            executable_sha256=actual_hash,
        ),
    )


def validated_palace_install_record(
    record_path: str | Path | None = None,
    *,
    required_version: str = PALACE_REQUIRED_VERSION,
) -> dict[str, Any] | None:
    """Return the shared install record only when live validation accepts it."""
    resolution = resolve_palace_install(record_path, required_version=required_version)
    return resolution.record if resolution.accepted else None


def _inspect_oci_image(engine: str, image: str) -> str | None:
    try:
        completed = subprocess.run(
            [engine, "image", "inspect", image, "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    digests = payload.get("RepoDigests") or []
    for item in digests:
        text = str(item)
        if "@sha256:" in text:
            return text.rsplit("@", 1)[-1]
    image_id = str(payload.get("Id") or "")
    return image_id if image_id.startswith("sha256:") else None


def _probe_oci_version(engine: str, image: str) -> str | None:
    for flags in (["--version"], ["--help"], ["-h"]):
        version = _probe([engine, "run", "--rm", image, *flags])
        if version:
            return version
    return None


def _detect_sif(
    path: str | None,
    *,
    finder: Callable[..., str | None],
    probe_version: bool,
) -> PalaceCapability | None:
    if not path:
        return None
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        return None
    engine = finder(("apptainer", "singularity"), None, env_var="TEXTLAYOUT_APPTAINER")
    if engine is None:
        return None
    version = (
        _probe(_execution_command(engine, ["run", source.name, "--version"], source.parent))
        if probe_version
        else None
    )
    image = f"wsl:{_windows_to_wsl(source)}" if engine.startswith(_WSL_PREFIX) else str(source)
    return PalaceCapability(
        execution_kind="container",
        version=version,
        container_engine=engine,
        container_image=image,
        container_digest=f"sha256:{sha256_file(source)}",
        mpi_launcher=f"{engine}:internal",
    )


def _detect_oci(
    image: str | None,
    *,
    finder: Callable[..., str | None],
    probe_version: bool,
) -> PalaceCapability | None:
    if not image:
        return None
    engine = finder(("docker", "podman"), None, env_var="TEXTLAYOUT_CONTAINER_ENGINE")
    if engine is None:
        return None
    digest = _inspect_oci_image(engine, image)
    if digest is None:
        return None
    return PalaceCapability(
        execution_kind="container",
        version=_probe_oci_version(engine, image) if probe_version else None,
        container_engine=engine,
        container_image=image,
        container_digest=digest,
        mpi_launcher=f"{engine}:internal",
    )


def detect_palace(
    explicit: str | None = None,
    *,
    container_image: str | None = None,
    container_path: str | None = None,
    container_digest: str | None = None,
    probe_version: bool = True,
    finder: Callable[..., str | None] | None = None,
) -> PalaceCapability:
    """Return a runnable, identified capability or an explicit absent result.

    Container images are never pulled implicitly. Set ``TEXTLAYOUT_PALACE_IMAGE``
    to an already-present OCI image, or ``TEXTLAYOUT_PALACE_SIF`` to a local SIF.
    """
    locate = finder or find_executable
    install_rejection: tuple[str, ...] = ()
    if (
        explicit is None
        and not os.environ.get("TEXTLAYOUT_PALACE")
        and _INSTALL_RECORD.is_file()
    ):
        installed = resolve_palace_install(_INSTALL_RECORD)
        if installed.capability is not None:
            launcher = locate(("mpirun", "mpiexec"), None, env_var="TEXTLAYOUT_MPIRUN")
            return installed.capability.model_copy(update={"mpi_launcher": launcher})
        install_rejection = installed.rejection_reasons
    executable = locate(("palace", "palace.exe"), explicit, env_var="TEXTLAYOUT_PALACE")
    if executable is not None:
        launcher = locate(("mpirun", "mpiexec"), None, env_var="TEXTLAYOUT_MPIRUN")
        return PalaceCapability(
            execution_kind="executable",
            executable=executable,
            version=_probe_executable_version(executable) if probe_version else None,
            executable_sha256=_hash_executable(executable),
            container_digest=container_digest,
            mpi_launcher=launcher,
        )

    sif = _detect_sif(
        container_path or os.environ.get("TEXTLAYOUT_PALACE_SIF"),
        finder=locate,
        probe_version=probe_version,
    )
    if sif is not None:
        return sif

    oci = _detect_oci(
        container_image or os.environ.get("TEXTLAYOUT_PALACE_IMAGE"),
        finder=locate,
        probe_version=probe_version,
    )
    if oci is not None:
        return oci

    return PalaceCapability(
        unavailable_reason=(
            "Palace was not found as an executable, a local SIF with Apptainer/"
            "Singularity, or an already-present OCI image. Set TEXTLAYOUT_PALACE, "
            "TEXTLAYOUT_PALACE_SIF, or TEXTLAYOUT_PALACE_IMAGE."
            + (
                " The installation record was rejected: " + "; ".join(install_rejection) + "."
                if install_rejection
                else ""
            )
        )
    )


def capability_report(capability: PalaceCapability | None = None) -> dict[str, Any]:
    detected = capability or detect_palace()
    return detected.model_dump(mode="json") | {
        "available": detected.available,
        "identified": detected.identified,
        "status": "AVAILABLE" if detected.available else "SKIPPED_SOLVER_ABSENT",
    }
