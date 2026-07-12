"""Persistent local solver job orchestration.

The job runner is intentionally solver-agnostic.  It records process and file
evidence for long-running local tools, while scientific interpretation remains
with the solver-specific adapter and CanonicalEvidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.canonical import sha256_file

JOB_SCHEMA = "textlayout.local-solver-job.v1"
DEFAULT_JOB_ROOT = Path("out") / "jobs"
SECRET_TOKENS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASS", "CREDENTIAL")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _job_id(command: list[str], cwd: Path) -> str:
    seed = {
        "command": command,
        "cwd": str(cwd.resolve()),
        "created_at": _now(),
        "nonce": uuid.uuid4().hex,
    }
    digest = hashlib.sha256(json.dumps(seed, sort_keys=True).encode("utf-8")).hexdigest()
    return f"job-{digest[:16]}"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for attempt in range(20):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def _read_json(path: Path) -> dict[str, Any]:
    last_exc: Exception | None = None
    for _ in range(20):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"{path} did not contain a JSON object")
            return payload
        except (PermissionError, json.JSONDecodeError) as exc:
            last_exc = exc
            time.sleep(0.05)
    if last_exc is not None:
        raise last_exc
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def _posix_getpgid(pid: int) -> int:
    getpgid = getattr(os, "getpgid")
    return int(getpgid(pid))


def _posix_killpg(pgid: int, sig: int) -> None:
    killpg = getattr(os, "killpg")
    killpg(pgid, sig)


def _is_secret_name(name: str) -> bool:
    upper = name.upper()
    return any(token in upper for token in SECRET_TOKENS)


def _environment_manifest(env: dict[str, str]) -> dict[str, Any]:
    exact: dict[str, str] = {}
    redacted: dict[str, str] = {}
    for key, value in sorted(env.items()):
        if _is_secret_name(key):
            redacted[key] = hashlib.sha256(value.encode("utf-8")).hexdigest()
        else:
            exact[key] = value
    return {
        "schema": "textlayout.job-environment.v1",
        "captured_at": _now(),
        "exact": exact,
        "redacted_sha256": redacted,
        "redaction_policy": "values for secret-like variable names are hashed, not stored",
    }


def _inventory(root: Path, *, exclude: Path | None = None) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not root.exists():
        return hashes
    root_resolved = root.resolve()
    exclude_resolved = exclude.resolve() if exclude is not None and exclude.exists() else None
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if exclude_resolved is not None:
            try:
                resolved.relative_to(exclude_resolved)
                continue
            except ValueError:
                pass
        try:
            key = str(resolved.relative_to(root_resolved)).replace("\\", "/")
        except ValueError:
            key = str(resolved)
        hashes[key] = sha256_file(path)
    return hashes


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ '1' }}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.stdout.strip() == "1"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _windows_process(pid: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\";"
                    "if ($p) { $p | Select-Object ProcessId,ParentProcessId,"
                    "CommandLine,WorkingSetSize,KernelModeTime,UserModeTime | ConvertTo-Json }"
                ),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"available": False}
    text = completed.stdout.strip()
    if not text:
        return {"available": False}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"available": False, "raw": text}
    return {
        "available": True,
        "pid": int(payload.get("ProcessId", pid)),
        "parent_pid": int(payload.get("ParentProcessId", 0)),
        "working_set_bytes": int(payload.get("WorkingSetSize", 0) or 0),
        "kernel_mode_time_100ns": int(payload.get("KernelModeTime", 0) or 0),
        "user_mode_time_100ns": int(payload.get("UserModeTime", 0) or 0),
        "command_line": payload.get("CommandLine"),
    }


def _linux_process(pid: int) -> dict[str, Any]:
    proc = Path("/proc") / str(pid)
    if not proc.exists():
        return {"available": False}
    stat_text = (proc / "stat").read_text(encoding="utf-8", errors="replace")
    parts = stat_text.rsplit(") ", 1)[-1].split()
    status = {}
    for line in (proc / "status").read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            status[key.strip()] = value.strip()
    return {
        "available": True,
        "pid": pid,
        "parent_pid": int(parts[1]) if len(parts) > 1 else None,
        "process_group_id": _posix_getpgid(pid),
        "rss_kb": int(status.get("VmRSS", "0 kB").split()[0]),
        "user_time_ticks": int(parts[11]) if len(parts) > 11 else None,
        "system_time_ticks": int(parts[12]) if len(parts) > 12 else None,
        "state": status.get("State"),
    }


def inspect_process(pid: int) -> dict[str, Any]:
    return _windows_process(pid) if os.name == "nt" else _linux_process(pid)


def _wsl_processes(command_hint: str | None = None) -> dict[str, Any]:
    if os.name != "nt":
        return {"available": False, "processes": []}
    wsl = os.environ.get("SystemRoot")
    wsl_exe = Path(wsl or "C:\\Windows") / "System32" / "wsl.exe"
    if not wsl_exe.is_file():
        return {"available": False, "processes": []}
    script = "ps -eo pid,ppid,pgid,rss,comm,args --no-headers"
    try:
        completed = subprocess.run(
            [str(wsl_exe), "bash", "-lc", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "processes": []}
    rows: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) < 6:
            continue
        args = parts[5]
        if command_hint and command_hint not in args:
            continue
        rows.append(
            {
                "pid": int(parts[0]),
                "parent_pid": int(parts[1]),
                "process_group_id": int(parts[2]),
                "rss_kb": int(parts[3]),
                "comm": parts[4],
                "args": args,
            }
        )
    return {"available": completed.returncode == 0, "processes": rows}


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_: str = Field(default=JOB_SCHEMA, alias="schema")
    job_id: str
    status: str
    command: list[str]
    cwd: Path
    job_dir: Path
    inventory_root: Path
    stdout_path: Path
    stderr_path: Path
    manifest_path: Path
    environment_path: Path
    monitor_pid: int | None = None
    pid: int | None = None
    parent_pid: int | None = None
    process_group_id: int | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    return_code: int | None = None
    cancellation_requested: bool = False
    orphan_status: str = "unknown"
    output_inventory: dict[str, str] = Field(default_factory=dict)
    peak_rss_kb: int = 0
    samples: list[dict[str, Any]] = Field(default_factory=list)


def _record_path(job_dir: Path) -> Path:
    return job_dir / "job.json"


def _load_record(job_root: Path, job_id: str) -> JobRecord:
    return JobRecord.model_validate(_read_json(job_root / job_id / "job.json"))


def _save_record(record: JobRecord) -> None:
    path = _record_path(record.job_dir)
    payload = record.model_dump(mode="json", by_alias=True)
    if path.is_file():
        try:
            existing = _read_json(path)
        except (OSError, json.JSONDecodeError):
            existing = {}
        terminal = {"completed", "failed", "cancelled", "failed_to_start", "collected"}
        if existing.get("status") in terminal and payload.get("status") not in terminal:
            return
        if existing.get("cancellation_requested") and not payload.get("cancellation_requested"):
            payload["cancellation_requested"] = True
            if payload.get("status") == "running":
                payload["status"] = "cancel_requested"
    _write_json(path, payload)


def start_job(
    command: list[str],
    *,
    cwd: str | Path = ".",
    job_root: str | Path = DEFAULT_JOB_ROOT,
    env_overrides: dict[str, str] | None = None,
    inventory_root: str | Path | None = None,
) -> JobRecord:
    if not command:
        raise ValueError("command must not be empty")
    cwd_path = Path(cwd).resolve()
    root = Path(job_root).resolve()
    job_id = _job_id(command, cwd_path)
    job_dir = root / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    stdout_path = job_dir / "stdout.txt"
    stderr_path = job_dir / "stderr.txt"
    manifest_path = job_dir / "manifest.json"
    environment_path = job_dir / "environment.json"
    full_env = dict(os.environ)
    full_env.update(env_overrides or {})
    inv_root = Path(inventory_root).resolve() if inventory_root else cwd_path

    manifest = {
        "schema": "textlayout.job-launch-manifest.v1",
        "job_id": job_id,
        "command": command,
        "cwd": str(cwd_path),
        "job_dir": str(job_dir),
        "inventory_root": str(inv_root),
        "created_at": _now(),
        "python": sys.executable,
        "platform": sys.platform,
    }
    _write_json(manifest_path, manifest)
    _write_json(environment_path, _environment_manifest(full_env))
    before_path = job_dir / "input_inventory.json"
    _write_json(before_path, _inventory(inv_root, exclude=job_dir))

    creationflags = 0
    start_new_session = False
    if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        start_new_session = True

    record = JobRecord(
        job_id=job_id,
        status="launching",
        command=command,
        cwd=cwd_path,
        job_dir=job_dir,
        inventory_root=inv_root,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        manifest_path=manifest_path,
        environment_path=environment_path,
        created_at=manifest["created_at"],
    )
    _save_record(record)
    monitor_command = [sys.executable, "-m", "textlayout.jobs", "_run", str(job_dir)]
    with (job_dir / "monitor.stdout.txt").open("w", encoding="utf-8", newline="\n") as mon_out:
        with (job_dir / "monitor.stderr.txt").open(
            "w", encoding="utf-8", newline="\n"
        ) as mon_err:
            monitor = subprocess.Popen(
                monitor_command,
                cwd=cwd_path,
                env=full_env,
                stdout=mon_out,
                stderr=mon_err,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                start_new_session=start_new_session,
            )
    record = record.model_copy(update={"monitor_pid": monitor.pid})
    _save_record(record)
    # Give the monitor a short window to launch the solver and publish its PID.
    deadline = time.time() + 5.0
    while time.time() < deadline:
        current = _load_record(root, job_id)
        if current.pid is not None or current.status == "failed_to_start":
            return current
        time.sleep(0.1)
    return _load_record(root, job_id)


def write_heartbeat(record: JobRecord) -> JobRecord:
    record_path = _record_path(record.job_dir)
    if record_path.is_file():
        try:
            latest = JobRecord.model_validate(_read_json(record_path))
        except json.JSONDecodeError:
            latest = record
        if latest.status in {"completed", "failed", "cancelled", "failed_to_start"}:
            return latest
    sample = sample_job(record)
    heartbeat = {
        "schema": "textlayout.job-heartbeat.v1",
        "job_id": record.job_id,
        "timestamp": _now(),
        "sample": sample,
    }
    _write_json(record.job_dir / "heartbeat.json", heartbeat)
    samples = [*record.samples, sample]
    peak = max(record.peak_rss_kb, int(sample.get("rss_kb", 0) or 0))
    updated = record.model_copy(
        update={
            "samples": samples[-100:],
            "peak_rss_kb": peak,
            "orphan_status": sample.get("orphan_status", record.orphan_status),
        }
    )
    _save_record(updated)
    return updated


def _launch_creation_kwargs() -> dict[str, Any]:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _terminate_process_group(record: JobRecord) -> None:
    if record.pid is None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(record.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return
    try:
        _posix_killpg(record.process_group_id or record.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _monitor_job(job_dir: Path) -> int:
    record = JobRecord.model_validate(_read_json(job_dir / "job.json"))
    before = _read_json(job_dir / "input_inventory.json")
    with record.stdout_path.open("w", encoding="utf-8", newline="\n") as stdout:
        with record.stderr_path.open("w", encoding="utf-8", newline="\n") as stderr:
            try:
                process = subprocess.Popen(
                    record.command,
                    cwd=record.cwd,
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    **_launch_creation_kwargs(),
                )
            except OSError as exc:
                stderr.write(f"[textlayout-job] failed to start command: {exc}\n")
                failed = record.model_copy(
                    update={
                        "status": "failed_to_start",
                        "completed_at": _now(),
                        "return_code": -1,
                        "parent_pid": os.getpid(),
                    }
                )
                _save_record(failed)
                return 1
            process_group_id = process.pid if os.name == "nt" else _posix_getpgid(process.pid)
            running = record.model_copy(
                update={
                    "status": "running",
                    "pid": process.pid,
                    "parent_pid": os.getpid(),
                    "process_group_id": process_group_id,
                    "started_at": _now(),
                    "orphan_status": "not_orphaned",
                }
            )
            _save_record(running)
            while process.poll() is None:
                current = _load_record(running.job_dir.parent, running.job_id)
                current = write_heartbeat(current)
                if current.cancellation_requested:
                    _terminate_process_group(current)
                    break
                time.sleep(1.0)
            return_code = process.wait()
    after = _inventory(record.inventory_root, exclude=record.job_dir)
    outputs = {key: value for key, value in after.items() if before.get(key) != value}
    latest = _load_record(record.job_dir.parent, record.job_id)
    status = "completed" if return_code == 0 else "cancelled" if latest.cancellation_requested else "failed"
    finished = latest.model_copy(
        update={
            "status": status,
            "completed_at": _now(),
            "return_code": return_code,
            "output_inventory": outputs,
            "orphan_status": "not_orphaned",
        }
    )
    _save_record(finished)
    _write_json(record.job_dir / "output_inventory.json", outputs)
    return 0


def sample_job(record: JobRecord) -> dict[str, Any]:
    process = inspect_process(record.pid or -1) if record.pid else {"available": False}
    wsl = _wsl_processes(record.command[-1] if record.command else None)
    rss = int(process.get("rss_kb") or (process.get("working_set_bytes", 0) // 1024) or 0)
    alive = _pid_alive(record.pid or -1)
    parent_alive = _pid_alive(record.parent_pid or -1) if record.parent_pid else False
    orphan_status = (
        "orphaned" if alive and record.parent_pid and not parent_alive else "not_orphaned"
    )
    return {
        "timestamp": _now(),
        "pid": record.pid,
        "alive": alive,
        "parent_pid": record.parent_pid,
        "parent_alive": parent_alive,
        "orphan_status": orphan_status,
        "rss_kb": rss,
        "process": process,
        "wsl_processes": wsl,
    }


def status_job(job_id: str, *, job_root: str | Path = DEFAULT_JOB_ROOT) -> JobRecord:
    record = _load_record(Path(job_root).resolve(), job_id)
    if record.status == "running":
        record = write_heartbeat(record)
        if not _pid_alive(record.pid or -1):
            fresh = _load_record(Path(job_root).resolve(), job_id)
            if fresh.status != "running" or fresh.return_code is not None:
                return fresh
            if record.monitor_pid is not None and _pid_alive(record.monitor_pid):
                return record
            return record
    return record


def collect_job(job_id: str, *, job_root: str | Path = DEFAULT_JOB_ROOT) -> JobRecord:
    record = status_job(job_id, job_root=job_root)
    if record.status == "running":
        return record
    return_code = record.return_code
    if return_code is None and record.pid is not None and not _pid_alive(record.pid):
        # Portable post-hoc collection cannot recover the exact exit status if
        # the parent process already exited; keep it unknown rather than
        # inferring success from files or logs.
        return_code = None
    after = _inventory(record.inventory_root, exclude=record.job_dir)
    before_path = record.job_dir / "input_inventory.json"
    before = _read_json(before_path) if before_path.is_file() else {}
    outputs = {key: value for key, value in after.items() if before.get(key) != value}
    completed = record.completed_at or _now()
    status = "completed" if return_code == 0 else "failed" if return_code else "collected"
    updated = record.model_copy(
        update={
            "status": status,
            "completed_at": completed,
            "return_code": return_code,
            "output_inventory": outputs,
            "orphan_status": "not_orphaned" if not _pid_alive(record.pid or -1) else "running",
        }
    )
    _save_record(updated)
    _write_json(record.job_dir / "output_inventory.json", outputs)
    return updated


def cancel_job(job_id: str, *, job_root: str | Path = DEFAULT_JOB_ROOT) -> JobRecord:
    record = _load_record(Path(job_root).resolve(), job_id)
    requested = record.model_copy(
        update={
            "status": "cancel_requested",
            "cancellation_requested": True,
        }
    )
    _save_record(requested)
    if record.pid is not None and _pid_alive(record.pid):
        _terminate_process_group(record)
    updated = requested.model_copy(
        update={
            "status": "cancel_requested",
            "cancellation_requested": True,
            "completed_at": _now() if not _pid_alive(record.pid or -1) else None,
        }
    )
    _save_record(updated)
    return updated


def resume_job(job_id: str, *, job_root: str | Path = DEFAULT_JOB_ROOT) -> JobRecord:
    """Resume bookkeeping only; never relaunch the solver process."""
    record = status_job(job_id, job_root=job_root)
    if record.status == "running":
        return record
    collected = collect_job(job_id, job_root=job_root)
    _write_json(
        collected.job_dir / "resume.json",
        {
            "schema": "textlayout.job-resume.v1",
            "job_id": job_id,
            "timestamp": _now(),
            "action": "post_processing_only_collect",
            "note": "solver process was not relaunched",
        },
    )
    return collected


def record_summary(record: JobRecord) -> dict[str, Any]:
    return {
        "schema": record.schema_,
        "job_id": record.job_id,
        "status": record.status,
        "command": record.command,
        "cwd": str(record.cwd),
        "job_dir": str(record.job_dir),
        "pid": record.pid,
        "parent_pid": record.parent_pid,
        "process_group_id": record.process_group_id,
        "stdout": str(record.stdout_path),
        "stderr": str(record.stderr_path),
        "return_code": record.return_code,
        "cancellation_requested": record.cancellation_requested,
        "orphan_status": record.orphan_status,
        "peak_rss_kb": record.peak_rss_kb,
        "output_count": len(record.output_inventory),
    }


def _main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] != "_run":
        print("usage: python -m textlayout.jobs _run <job-dir>", file=sys.stderr)
        return 2
    return _monitor_job(Path(args[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(_main())
