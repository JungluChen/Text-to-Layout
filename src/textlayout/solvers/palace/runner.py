"""Local, MPI, and container execution with retained process evidence."""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

from textlayout.evidence.canonical import sha256_file
from textlayout.simulation.resource_sampler import palace_reported_peak_memory_mb
from textlayout.simulation.runners import _execution_command
from textlayout.solvers.palace.models import (
    PalaceCapability,
    PalaceRun,
    PalaceUnavailable,
)
from textlayout.solvers.palace.processes import (
    cancel_owned_wsl_process_group,
    inspect_owned_processes,
    refresh_solver_process_record,
    wrap_wsl_command_with_ownership,
    write_solver_process_record,
)

_INVENTORY_SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tools",
    ".venv",
    "__pycache__",
    "jobs",
}


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


def _skip_inventory_path(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return True
    return any(part in _INVENTORY_SKIP_DIRS for part in relative.parts)


def _file_fingerprints(root: Path) -> dict[Path, tuple[int, int]]:
    fingerprints: dict[Path, tuple[int, int]] = {}
    for path in root.rglob("*"):
        if not path.is_file() or _skip_inventory_path(path, root):
            continue
        stat = path.stat()
        fingerprints[path.resolve()] = (stat.st_size, stat.st_mtime_ns)
    return fingerprints


def _atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _output_stats(root: Path) -> tuple[int, list[dict[str, object]]]:
    files = [path for path in root.rglob("*") if path.is_file()]
    ranked = sorted(files, key=lambda path: (-path.stat().st_size, str(path)))[:10]
    return sum(path.stat().st_size for path in files), [
        {
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
        }
        for path in ranked
    ]


def run_palace(
    capability: PalaceCapability,
    config_path: Path,
    *,
    cwd: Path,
    timeout_seconds: float = 3600.0,
    processes: int = 1,
    cancel_event: Event | None = None,
    input_paths: list[Path] | None = None,
    max_rss_bytes: int | None = None,
    resource_grace_seconds: float = 5.0,
) -> PalaceRun:
    """Run Palace once and retain every process-level fact on disk."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    cwd = cwd.resolve()
    cwd.mkdir(parents=True, exist_ok=True)
    config_path = config_path.resolve()
    command = build_command(capability, config_path, cwd=cwd, processes=processes)
    job_id = os.environ.get("TEXTLAYOUT_JOB_ID") or f"palace-{uuid.uuid4().hex}"
    process_record_path = cwd / "solver_process.json"
    command = wrap_wsl_command_with_ownership(
        command,
        job_id=job_id,
        record_path=process_record_path,
        working_directory=cwd,
        executable_hash=capability.executable_sha256,
    )
    stdout_path = cwd / "palace.stdout.txt"
    stderr_path = cwd / "palace.stderr.txt"
    before = _file_fingerprints(cwd)
    started = time.perf_counter()
    timed_out = False
    cancelled = False
    resource_limit_terminated = False
    termination_reason: str | None = None
    samples: list[dict[str, object]] = []
    peak_group_rss_bytes = 0
    peak_process_rss_bytes = 0
    resource_summary_path = cwd / "resource_summary.json"
    sample_path = cwd / "resource_samples.json"
    inventory_size = 0
    inventory_largest: list[dict[str, object]] = []
    next_inventory_sample = started

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
            next_resource_sample = started
            while process.poll() is None:
                now = time.perf_counter()
                if now >= next_resource_sample and process_record_path.is_file():
                    record = refresh_solver_process_record(process_record_path)
                    if record is not None:
                        if record.outer_python_pid is None:
                            record = record.model_copy(
                                update={
                                    "outer_python_pid": os.getpid(),
                                    "windows_wsl_pid": process.pid,
                                }
                            )
                            write_solver_process_record(record)
                        owned = inspect_owned_processes(record)
                        rss_values = [item.rss_kb * 1024 for item in owned]
                        group_rss = sum(rss_values)
                        peak_group_rss_bytes = max(peak_group_rss_bytes, group_rss)
                        peak_process_rss_bytes = max(
                            peak_process_rss_bytes, max(rss_values, default=0)
                        )
                        if now >= next_inventory_sample:
                            inventory_size, inventory_largest = _output_stats(cwd)
                            next_inventory_sample = now + 10.0
                        samples.append(
                            {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "outer_python_pid": os.getpid(),
                                "windows_wsl_pid": process.pid,
                                "child_pids": [item.pid for item in owned],
                                "process_group_rss_bytes": group_rss,
                                "process_group_cpu_percent": sum(
                                    item.cpu_percent for item in owned
                                ),
                                "virtual_memory_bytes": sum(
                                    item.virtual_memory_kb * 1024 for item in owned
                                ),
                                "thread_count": sum(item.thread_count for item in owned),
                                "output_directory_size_bytes": inventory_size,
                                "largest_output_files": inventory_largest,
                            }
                        )
                        _atomic_json(sample_path, samples)
                        if max_rss_bytes is not None and group_rss > max_rss_bytes:
                            resource_limit_terminated = True
                            termination_reason = "RESOURCE_LIMIT_TERMINATED"
                            _atomic_json(
                                cwd / "resource_limit_event.json",
                                {
                                    "schema": "textlayout.palace-resource-limit-event.v1",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "job_id": job_id,
                                    "process_group_rss_bytes": group_rss,
                                    "max_rss_bytes": max_rss_bytes,
                                    "action": "terminate_owned_process_group",
                                },
                            )
                            cancel_owned_wsl_process_group(
                                record, grace_seconds=resource_grace_seconds
                            )
                            _terminate(process)
                            break
                    next_resource_sample = now + 1.0
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    termination_reason = "USER_CANCELLED"
                    record = refresh_solver_process_record(process_record_path)
                    if record is not None:
                        cancel_owned_wsl_process_group(
                            record, grace_seconds=resource_grace_seconds
                        )
                    _terminate(process)
                    break
                if now >= deadline:
                    timed_out = True
                    termination_reason = "TIMEOUT"
                    record = refresh_solver_process_record(process_record_path)
                    if record is not None:
                        cancel_owned_wsl_process_group(
                            record, grace_seconds=resource_grace_seconds
                        )
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
            if resource_limit_terminated:
                stderr.write(
                    "[textlayout] Palace exceeded its process-group RSS budget and "
                    "was terminated.\n"
                )

    runtime = time.perf_counter() - started
    if stdout_path.stat().st_size == 0:
        stdout_path.write_text("[textlayout] Palace emitted no stdout.\n", encoding="utf-8")
    if stderr_path.stat().st_size == 0:
        stderr_path.write_text("[textlayout] Palace emitted no stderr.\n", encoding="utf-8")
    palace_peak_mb = palace_reported_peak_memory_mb(
        stdout_path.read_text(encoding="utf-8", errors="replace")
    )

    after = _file_fingerprints(cwd)
    outputs = []
    for path, fingerprint in after.items():
        if path in {stdout_path.resolve(), stderr_path.resolve()}:
            continue
        if before.get(path) != fingerprint:
            outputs.append(path)
    inputs = [config_path, *(input_paths or [])]
    orphan_processes_remaining = False
    final_record = refresh_solver_process_record(process_record_path)
    if final_record is not None:
        remaining = inspect_owned_processes(final_record)
        if remaining:
            final_record = cancel_owned_wsl_process_group(
                final_record, grace_seconds=resource_grace_seconds
            )
            orphan_processes_remaining = bool(final_record.processes)
    _atomic_json(
        resource_summary_path,
        {
            "schema": "textlayout.palace-process-resource-summary.v1",
            "job_id": job_id,
            "sample_count": len(samples),
            "palace_reported_peak_memory_bytes": (
                int(palace_peak_mb * 1024**2) if palace_peak_mb is not None else None
            ),
            "observed_process_peak_rss_bytes": peak_process_rss_bytes,
            "observed_process_group_peak_rss_bytes": peak_group_rss_bytes,
            "configured_max_rss_bytes": max_rss_bytes,
            "termination_reason": termination_reason,
            "orphan_processes_remaining": orphan_processes_remaining,
        },
    )
    return PalaceRun(
        command=command,
        return_code=return_code,
        runtime_seconds=runtime,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        output_dir=cwd,
        timed_out=timed_out,
        cancelled=cancelled,
        resource_limit_terminated=resource_limit_terminated,
        termination_reason=termination_reason,
        resource_summary_path=resource_summary_path,
        orphan_processes_remaining=orphan_processes_remaining,
        input_file_hashes=_hash_files(inputs, cwd),
        output_file_hashes=_hash_files(outputs, cwd),
    )
