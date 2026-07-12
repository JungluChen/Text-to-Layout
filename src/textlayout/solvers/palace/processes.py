"""WSL/Linux process ownership for Palace jobs.

Ownership is anchored on the recorded Linux process group ID created with
``setsid``.  Process discovery may inspect names for reporting, but it never
uses command substrings to decide ownership.
"""

from __future__ import annotations

import base64
import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.canonical import sha256_file, sha256_json
from textlayout.simulation.runners import _windows_to_wsl, _wsl_exe

CancellationStatus = Literal[
    "CANCEL_REQUESTED",
    "CANCELLING",
    "CANCELLED",
    "CANCEL_FAILED_ORPHAN_REMAINS",
]


class LinuxProcessRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pid: int = Field(gt=0)
    parent_pid: int = Field(ge=0)
    process_group_id: int = Field(gt=0)
    start_time_ticks: int = Field(ge=0)
    rss_kb: int = Field(ge=0)
    cpu_time_ticks: int = Field(ge=0)
    cpu_percent: float = Field(ge=0)
    read_bytes: int = Field(ge=0)
    write_bytes: int = Field(ge=0)
    command: str


class SolverProcessRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_: str = Field(default="textlayout.palace-solver-process.v1", alias="schema")
    job_id: str
    linux_pid: int | None = None
    linux_process_group_id: int | None = None
    mpirun_pid: int | None = None
    palace_rank_pids: list[int] = Field(default_factory=list)
    process_start_time_ticks: int | None = None
    command_hash: str
    executable_hash: str | None = None
    working_directory: Path
    record_path: Path
    processes: list[LinuxProcessRecord] = Field(default_factory=list)
    cancellation_status: CancellationStatus | None = None


def is_wsl_command(command: list[str]) -> bool:
    if len(command) < 4 or Path(command[0]).name.lower() != "wsl.exe":
        return False
    return "bash" in command and "-lc" in command


def _wsl_record_path(path: Path) -> str:
    return _windows_to_wsl(path) if os.name == "nt" else str(path)


def wrap_wsl_command_with_ownership(
    command: list[str],
    *,
    job_id: str,
    record_path: Path,
    working_directory: Path,
    executable_hash: str | None,
) -> list[str]:
    """Wrap a ``wsl bash -lc ...`` command in ``setsid`` and record Linux identity."""
    if not is_wsl_command(command) or "bash" not in command or "-lc" not in command:
        return command
    bash_index = command.index("bash")
    original = command[-1]
    record_wsl = _wsl_record_path(record_path)
    work_wsl = _wsl_record_path(working_directory)
    command_hash = sha256_json({"command": command})
    payload = {
        "schema": "textlayout.palace-solver-process.v1",
        "job_id": job_id,
        "command_hash": command_hash,
        "executable_hash": executable_hash,
        "working_directory": str(working_directory.resolve()),
        "record_path": str(record_path.resolve()),
    }
    payload_json = json.dumps(payload, sort_keys=True)
    payload_base64 = base64.b64encode(payload_json.encode("utf-8")).decode("ascii")
    record_script = "\n".join(
        [
            "import base64, json, os",
            f"payload = json.loads(base64.b64decode({payload_base64!r}))",
            "session_pid = os.getppid()",
            "stat = open(f'/proc/{session_pid}/stat', encoding='ascii').read()",
            "fields = stat[stat.rfind(')') + 2:].split()",
            "payload.update({",
            "    'linux_pid': session_pid,",
            "    'linux_process_group_id': os.getpgid(session_pid),",
            "    'process_start_time_ticks': int(fields[19]),",
            "    'mpirun_pid': None,",
            "    'palace_rank_pids': [],",
            "    'processes': [],",
            "})",
            "print(json.dumps(payload, indent=2, sort_keys=True))",
        ]
    )
    inner = "\n".join(
        [
            "set -e",
            f"cd {shlex.quote(work_wsl)}",
            f"python3 -c {shlex.quote(record_script)} > {shlex.quote(record_wsl)}",
            f"exec bash -lc {shlex.quote(original)}",
        ]
    )
    return [
        *command[:bash_index],
        "bash",
        "-lc",
        f"exec setsid --wait bash -lc {shlex.quote(inner)}",
    ]


def _run_wsl(script: str, *, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    wsl = _wsl_exe()
    if wsl is None:
        raise RuntimeError("wsl.exe is not available")
    return subprocess.run(
        [wsl, "bash", "-lc", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def aggregate_process_resources(
    processes: list[LinuxProcessRecord], *, system_available_memory_kb: int = 0
) -> dict[str, Any]:
    """Aggregate resource usage for an owned Linux process group sample."""
    return {
        "schema": "textlayout.palace-mpi-resource-sample.v1",
        "process_count": len(processes),
        "total_rss_kb": sum(process.rss_kb for process in processes),
        "total_cpu_time_ticks": sum(process.cpu_time_ticks for process in processes),
        "total_cpu_percent": sum(process.cpu_percent for process in processes),
        "system_available_memory_kb": system_available_memory_kb,
        "read_bytes": sum(process.read_bytes for process in processes),
        "write_bytes": sum(process.write_bytes for process in processes),
        "mpi_rank_count": sum(
            Path(process.command.split(maxsplit=1)[0]).name == "palace"
            for process in processes
            if process.command
        ),
        "process_group_ids": sorted(
            {process.process_group_id for process in processes}
        ),
        "processes": [process.model_dump(mode="json") for process in processes],
    }


def inspect_owned_processes(record: SolverProcessRecord) -> list[LinuxProcessRecord]:
    if record.linux_process_group_id is None:
        return []
    script = f"""python3 - <<'PY'
import json, os
pgid_wanted = {record.linux_process_group_id}
clk = os.sysconf('SC_CLK_TCK')
uptime = float(open('/proc/uptime', encoding='ascii').read().split()[0])
rows = []
for name in os.listdir('/proc'):
    if not name.isdigit():
        continue
    root = '/proc/' + name
    try:
        raw = open(root + '/stat', encoding='utf-8').read()
        fields = raw[raw.rfind(')') + 2:].split()
        ppid, pgid = int(fields[1]), int(fields[2])
        if pgid != pgid_wanted:
            continue
        utime, stime, start = int(fields[11]), int(fields[12]), int(fields[19])
        status = open(root + '/status', encoding='utf-8').read().splitlines()
        rss = next((int(x.split()[1]) for x in status if x.startswith('VmRSS:')), 0)
        io = {{}}
        for line in open(root + '/io', encoding='ascii'):
            key, value = line.split(':', 1)
            io[key] = int(value)
        command = open(root + '/cmdline', 'rb').read().replace(b'\\0', b' ').decode('utf-8', 'replace').strip()
        elapsed = max(uptime - start / clk, 1e-9)
        rows.append({{
            'pid': int(name), 'parent_pid': ppid, 'process_group_id': pgid,
            'start_time_ticks': start, 'rss_kb': rss,
            'cpu_time_ticks': utime + stime,
            'cpu_percent': (utime + stime) / clk / elapsed * 100.0,
            'read_bytes': io.get('read_bytes', 0),
            'write_bytes': io.get('write_bytes', 0),
            'command': command,
        }})
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
        continue
print(json.dumps(rows, sort_keys=True))
PY"""
    completed = _run_wsl(script)
    if completed.returncode != 0:
        return []
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    processes = [LinuxProcessRecord.model_validate(item) for item in payload]
    recorded_identities = {
        (process.pid, process.start_time_ticks) for process in record.processes
    }
    if record.linux_pid is not None and record.process_start_time_ticks is not None:
        recorded_identities.add((record.linux_pid, record.process_start_time_ticks))
    if recorded_identities and not any(
        (process.pid, process.start_time_ticks) in recorded_identities
        for process in processes
    ):
        return []
    return processes


def refresh_solver_process_record(path: str | Path) -> SolverProcessRecord | None:
    record_path = Path(path)
    if not record_path.is_file():
        return None
    record = SolverProcessRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
    processes = inspect_owned_processes(record)
    mpirun = next(
        (
            p.pid
            for p in processes
            if Path(p.command.split(maxsplit=1)[0]).name in {"mpirun", "mpiexec"}
        ),
        None,
    )
    palace_ranks = [
        p.pid
        for p in processes
        if p.command and Path(p.command.split(maxsplit=1)[0]).name == "palace"
    ]
    updated = record.model_copy(
        update={
            "processes": processes,
            "mpirun_pid": mpirun or record.mpirun_pid,
            "palace_rank_pids": palace_ranks,
        }
    )
    record_path.write_text(
        updated.model_dump_json(indent=2, by_alias=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return updated


def cancel_owned_wsl_process_group(
    record: SolverProcessRecord,
    *,
    grace_seconds: float = 5.0,
) -> SolverProcessRecord:
    if record.linux_process_group_id is None:
        return record.model_copy(update={"cancellation_status": "CANCEL_FAILED_ORPHAN_REMAINS"})
    _run_wsl(f"kill -TERM -{record.linux_process_group_id} 2>/dev/null || true")
    deadline = time.time() + grace_seconds
    remaining = inspect_owned_processes(record)
    while time.time() < deadline:
        if not remaining:
            break
        time.sleep(0.2)
        remaining = inspect_owned_processes(record)
    if remaining:
        _run_wsl(f"kill -KILL -{record.linux_process_group_id} 2>/dev/null || true")
        time.sleep(0.2)
        remaining = inspect_owned_processes(record)
    status: CancellationStatus = (
        "CANCEL_FAILED_ORPHAN_REMAINS" if remaining else "CANCELLED"
    )
    updated = record.model_copy(
        update={"processes": remaining, "cancellation_status": status}
    )
    record.record_path.write_text(
        updated.model_dump_json(indent=2, by_alias=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return updated


def solver_process_file_hash(path: str | Path) -> str | None:
    file_path = Path(path)
    return sha256_file(file_path) if file_path.is_file() else None
