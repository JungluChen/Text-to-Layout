from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from textlayout.solvers.palace.processes import (
    LinuxProcessRecord,
    SolverProcessRecord,
    aggregate_process_resources,
    cancel_owned_wsl_process_group,
    inspect_owned_processes,
    wrap_wsl_command_with_ownership,
)


def _record(tmp_path: Path) -> SolverProcessRecord:
    return SolverProcessRecord(
        job_id="job-123",
        linux_pid=101,
        linux_process_group_id=101,
        process_start_time_ticks=500,
        command_hash="a" * 64,
        executable_hash="b" * 64,
        working_directory=tmp_path,
        record_path=tmp_path / "solver_process.json",
    )


def test_wsl_wrapper_preserves_distribution_and_uses_setsid(tmp_path: Path) -> None:
    original = [
        "wsl.exe",
        "-d",
        "Ubuntu",
        "--",
        "bash",
        "-lc",
        "mpirun -np 2 /opt/palace/bin/palace config.json",
    ]
    wrapped = wrap_wsl_command_with_ownership(
        original,
        job_id="job-123",
        record_path=tmp_path / "solver_process.json",
        working_directory=tmp_path,
        executable_hash="b" * 64,
    )
    assert Path(wrapped[0]).name.lower() == "wsl.exe"
    assert wrapped[1:4] == original[1:4]
    assert wrapped[4:6] == ["bash", "-lc"]
    assert "exec setsid --wait" in wrapped[-1]
    assert "mpirun_pid" in wrapped[-1]
    assert "int(os.environ['pid'])" not in wrapped[-1].split("mpirun_pid", 1)[1]


@pytest.mark.skipif(shutil.which("wsl.exe") is None, reason="WSL is not installed")
def test_wsl_wrapper_writes_real_session_identity() -> None:
    working = Path.cwd().resolve()
    record_path = working / "out" / f"test_solver_process_record_{os.getpid()}.json"
    record_path.unlink(missing_ok=True)
    wrapped = wrap_wsl_command_with_ownership(
        ["wsl.exe", "-d", "Ubuntu", "--", "bash", "-lc", "sleep 0.1"],
        job_id="job-live",
        record_path=record_path,
        working_directory=working,
        executable_hash="c" * 64,
    )
    completed = subprocess.run(wrapped, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    record = SolverProcessRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
    assert record.job_id == "job-live"
    assert record.linux_pid is not None
    assert record.linux_process_group_id == record.linux_pid
    assert record.process_start_time_ticks is not None
    record_path.unlink(missing_ok=True)


def test_owned_process_inspection_uses_recorded_pgid(monkeypatch, tmp_path: Path) -> None:
    payload = [
        {
            "pid": 101,
            "parent_pid": 1,
            "process_group_id": 101,
            "start_time_ticks": 500,
            "rss_kb": 100,
            "cpu_time_ticks": 20,
            "cpu_percent": 5.0,
            "read_bytes": 10,
            "write_bytes": 20,
            "command": "/usr/bin/mpirun -np 2 palace config.json",
        },
        {
            "pid": 102,
            "parent_pid": 101,
            "process_group_id": 101,
            "start_time_ticks": 510,
            "rss_kb": 300,
            "cpu_time_ticks": 40,
            "cpu_percent": 10.0,
            "read_bytes": 30,
            "write_bytes": 40,
            "command": "/opt/palace/bin/palace config.json",
        },
    ]
    monkeypatch.setattr(
        "textlayout.solvers.palace.processes._run_wsl",
        lambda script, timeout=20.0: CompletedProcess([], 0, json.dumps(payload), ""),
    )
    processes = inspect_owned_processes(_record(tmp_path))
    assert {process.process_group_id for process in processes} == {101}
    summary = aggregate_process_resources(processes, system_available_memory_kb=1000)
    assert summary["total_rss_kb"] == 400
    assert summary["total_cpu_percent"] == 15.0
    assert summary["read_bytes"] == 40
    assert summary["write_bytes"] == 60
    assert summary["system_available_memory_kb"] == 1000


def test_owned_process_inspection_rejects_recycled_group(monkeypatch, tmp_path: Path) -> None:
    payload = [
        {
            "pid": 101,
            "parent_pid": 1,
            "process_group_id": 101,
            "start_time_ticks": 999,
            "rss_kb": 100,
            "cpu_time_ticks": 20,
            "cpu_percent": 5.0,
            "read_bytes": 0,
            "write_bytes": 0,
            "command": "/unrelated/process",
        }
    ]
    monkeypatch.setattr(
        "textlayout.solvers.palace.processes._run_wsl",
        lambda script, timeout=20.0: CompletedProcess([], 0, json.dumps(payload), ""),
    )
    assert inspect_owned_processes(_record(tmp_path)) == []


def test_cancellation_escalates_and_verifies_owned_group(monkeypatch, tmp_path: Path) -> None:
    record = _record(tmp_path)
    record.record_path.write_text(record.model_dump_json(by_alias=True), encoding="utf-8")
    owned = LinuxProcessRecord(
        pid=102,
        parent_pid=101,
        process_group_id=101,
        start_time_ticks=510,
        rss_kb=10,
        cpu_time_ticks=1,
        cpu_percent=1.0,
        read_bytes=0,
        write_bytes=0,
        command="/opt/palace/bin/palace config.json",
    )
    inspections = iter([[owned], []])
    monkeypatch.setattr(
        "textlayout.solvers.palace.processes.inspect_owned_processes",
        lambda current: next(inspections),
    )
    commands: list[str] = []
    monkeypatch.setattr(
        "textlayout.solvers.palace.processes._run_wsl",
        lambda script, timeout=20.0: (
            commands.append(script) or CompletedProcess([], 0, "", "")
        ),
    )
    monkeypatch.setattr("textlayout.solvers.palace.processes.time.sleep", lambda _: None)
    cancelled = cancel_owned_wsl_process_group(record, grace_seconds=0.0)
    assert cancelled.cancellation_status == "CANCELLED"
    assert any("kill -TERM -101" in command for command in commands)
    assert any("kill -KILL -101" in command for command in commands)
