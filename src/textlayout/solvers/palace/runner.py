"""Local, MPI, and container execution with retained process evidence."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from threading import Event

from textlayout.evidence.canonical import sha256_file
from textlayout.simulation.runners import _execution_command
from textlayout.solvers.palace.models import (
    PalaceCapability,
    PalaceRun,
    PalaceUnavailable,
)


def _container_command(
    capability: PalaceCapability,
    *,
    cwd: Path,
    config_name: str,
    processes: int,
) -> list[str]:
    engine = capability.container_engine
    image = capability.container_image
    if engine is None or image is None:
        raise PalaceUnavailable("container capability is missing engine or image")
    basename = Path(engine.removeprefix("wsl:")).name.lower()
    palace_args = (
        ["-serial", config_name]
        if processes == 1
        else ["-np", str(processes), config_name]
    )
    if basename in {"docker", "docker.exe", "podman", "podman.exe"}:
        return [
            engine,
            "run",
            "--rm",
            "-v",
            f"{cwd.resolve()}:/work",
            "-w",
            "/work",
            image,
            *palace_args,
        ]
    if engine.startswith("wsl:"):
        image_path = image.removeprefix("wsl:")
        return _execution_command(engine, ["run", image_path, *palace_args], cwd)
    return [
        engine,
        "run",
        "--bind",
        f"{cwd.resolve()}:/work",
        "--pwd",
        "/work",
        image,
        *palace_args,
    ]


def build_command(
    capability: PalaceCapability,
    config_path: Path,
    *,
    cwd: Path,
    processes: int,
) -> list[str]:
    detected = capability.require()
    if processes < 1:
        raise ValueError("processes must be at least one")
    if detected.execution_kind == "container":
        return _container_command(
            detected, cwd=cwd, config_name=config_path.name, processes=processes
        )
    if detected.executable is None:
        raise PalaceUnavailable("executable capability has no executable")
    if processes > 1 and detected.mpi_launcher is None:
        raise PalaceUnavailable(
            f"{processes} processes requested but no mpirun/mpiexec was found"
        )
    arguments = (
        ["-serial", config_path.name]
        if processes == 1
        else ["-np", str(processes), config_path.name]
    )
    return _execution_command(detected.executable, arguments, cwd)


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _hash_files(paths: list[Path], root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        if not path.is_file():
            continue
        try:
            name = str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            name = path.name
        hashes[name] = sha256_file(path)
    return dict(sorted(hashes.items()))


def run_palace(
    capability: PalaceCapability,
    config_path: Path,
    *,
    cwd: Path,
    timeout_seconds: float = 3600.0,
    processes: int = 1,
    cancel_event: Event | None = None,
    input_paths: list[Path] | None = None,
) -> PalaceRun:
    """Run Palace once and retain every process-level fact on disk."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    cwd = cwd.resolve()
    cwd.mkdir(parents=True, exist_ok=True)
    config_path = config_path.resolve()
    command = build_command(capability, config_path, cwd=cwd, processes=processes)
    stdout_path = cwd / "palace.stdout.txt"
    stderr_path = cwd / "palace.stderr.txt"
    before = {
        path.resolve(): sha256_file(path)
        for path in cwd.rglob("*")
        if path.is_file()
    }
    started = time.perf_counter()
    timed_out = False
    cancelled = False

    creationflags = 0
    if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    with stdout_path.open("w", encoding="utf-8", newline="\n") as stdout, stderr_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as stderr:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=stdout,
                stderr=stderr,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
        except OSError as exc:
            stderr.write(f"[textlayout] failed to start Palace: {exc}\n")
            return_code = -1
        else:
            deadline = started + timeout_seconds
            while process.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    _terminate(process)
                    break
                if time.perf_counter() >= deadline:
                    timed_out = True
                    _terminate(process)
                    break
                time.sleep(0.05)
            return_code = process.returncode if process.returncode is not None else -1
            if timed_out:
                stderr.write(
                    f"[textlayout] Palace exceeded its {timeout_seconds:g}s timeout and was killed.\n"
                )
            if cancelled:
                stderr.write("[textlayout] Palace was cancelled and was killed.\n")

    runtime = time.perf_counter() - started
    if stdout_path.stat().st_size == 0:
        stdout_path.write_text("[textlayout] Palace emitted no stdout.\n", encoding="utf-8")
    if stderr_path.stat().st_size == 0:
        stderr_path.write_text("[textlayout] Palace emitted no stderr.\n", encoding="utf-8")

    after = [path.resolve() for path in cwd.rglob("*") if path.is_file()]
    outputs = []
    for path in after:
        if path in {stdout_path.resolve(), stderr_path.resolve()}:
            continue
        if before.get(path) != sha256_file(path):
            outputs.append(path)
    inputs = [config_path, *(input_paths or [])]
    return PalaceRun(
        command=command,
        return_code=return_code,
        runtime_seconds=runtime,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        output_dir=cwd,
        timed_out=timed_out,
        cancelled=cancelled,
        input_file_hashes=_hash_files(inputs, cwd),
        output_file_hashes=_hash_files(outputs, cwd),
    )
