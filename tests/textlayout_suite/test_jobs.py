from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from textlayout.cli import build_parser
from textlayout.jobs import cancel_job, collect_job, resume_job, start_job, status_job


def _wait_for_terminal(job_id: str, job_root: Path, *, timeout: float = 15.0):
    deadline = time.time() + timeout
    last = status_job(job_id, job_root=job_root)
    while time.time() < deadline:
        last = status_job(job_id, job_root=job_root)
        if last.status in {
            "completed",
            "failed",
            "cancelled",
            "failed_to_start",
            "collected",
            "CANCELLED",
            "CANCEL_FAILED_ORPHAN_REMAINS",
        }:
            return last
        time.sleep(0.2)
    return last


def test_job_start_collect_records_return_code_and_outputs(tmp_path: Path) -> None:
    work = tmp_path / "work"
    jobs = tmp_path / "jobs"
    work.mkdir()
    command = [
        sys.executable,
        "-c",
        "from pathlib import Path; Path('solver.out').write_text('ok', encoding='utf-8')",
    ]

    started = start_job(command, cwd=work, job_root=jobs)
    assert started.job_id.startswith("job-")
    assert started.manifest_path.is_file()
    assert started.environment_path.is_file()
    environment = json.loads(started.environment_path.read_text(encoding="utf-8"))
    assert environment["clear"]["TEXTLAYOUT_JOB_ID"] == started.job_id
    assert environment["clear"]["TEXTLAYOUT_JOB_DIR"] == str(started.job_dir)
    assert environment["clear"]["TEXTLAYOUT_JOB_ROOT"] == str(jobs.resolve())

    terminal = _wait_for_terminal(started.job_id, jobs)
    assert terminal.status == "completed"
    collected = collect_job(started.job_id, job_root=jobs)
    assert collected.return_code == 0
    assert "solver.out" in collected.output_inventory
    assert collected.stdout_path.is_file()
    assert collected.stderr_path.is_file()
    assert (collected.job_dir / "heartbeat.json").is_file()
    assert collected.finalization_path is not None
    assert collected.finalization_path.is_file()
    finalization = json.loads(collected.finalization_path.read_text(encoding="utf-8"))
    assert finalization["return_code"] == 0
    assert finalization["stdout_sha256"] == collected.stdout_sha256
    assert collected.resource_samples_path is not None
    assert collected.resource_samples_path.is_file()


def test_job_resume_is_post_processing_only(tmp_path: Path) -> None:
    work = tmp_path / "work"
    jobs = tmp_path / "jobs"
    work.mkdir()
    started = start_job(
        [sys.executable, "-c", "print('done')"],
        cwd=work,
        job_root=jobs,
    )
    _wait_for_terminal(started.job_id, jobs)
    resumed = resume_job(started.job_id, job_root=jobs)
    assert resumed.status == "completed"
    resume = resumed.job_dir / "resume.json"
    assert resume.is_file()
    assert "solver process was not relaunched" in resume.read_text(encoding="utf-8")


def test_job_cancel_requests_process_group_termination(tmp_path: Path) -> None:
    work = tmp_path / "work"
    jobs = tmp_path / "jobs"
    work.mkdir()
    started = start_job(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=work,
        job_root=jobs,
    )
    cancelled = cancel_job(started.job_id, job_root=jobs)
    assert cancelled.cancellation_requested is True
    terminal = _wait_for_terminal(started.job_id, jobs)
    assert terminal.status in {"CANCELLED", "CANCEL_FAILED_ORPHAN_REMAINS", "failed"}


def test_jobs_cli_parses_start_and_lifecycle_commands() -> None:
    parser = build_parser()
    started = parser.parse_args(
        ["jobs", "start", "--cwd", ".", "--", "python", "-c", "print(1)"]
    )
    assert started.jobs_command == "start"
    assert started.command == ["--", "python", "-c", "print(1)"]
    status = parser.parse_args(["jobs", "status", "job-abc"])
    assert status.jobs_command == "status"
    assert status.job_id == "job-abc"


def test_palace_cli_parses_background_job_flags() -> None:
    parser = build_parser()
    background = parser.parse_args(
        ["simulate", "palace-resonator", "--out", "out/palace", "--background"]
    )
    assert background.simulate_command == "palace-resonator"
    assert background.background is True
    status = parser.parse_args(
        ["simulate", "palace-resonator", "--out", "out/palace", "--job-status"]
    )
    assert status.job_status is True
    cancel = parser.parse_args(
        ["simulate", "palace-resonator", "--out", "out/palace", "--cancel"]
    )
    assert cancel.cancel is True


def test_job_environment_manifest_hashes_non_allowlisted_values(tmp_path: Path) -> None:
    work = tmp_path / "work"
    jobs = tmp_path / "jobs"
    work.mkdir()
    started = start_job(
        [sys.executable, "-c", "print('ok')"],
        cwd=work,
        job_root=jobs,
        env_overrides={
            "OPENAI_API_KEY": "sk-test-secret",
            "LM_LICENSE_FILE": "27000@license-server",
            "OMP_NUM_THREADS": "2",
        },
    )
    environment = json.loads(started.environment_path.read_text(encoding="utf-8"))
    serialized = json.dumps(environment, sort_keys=True)
    assert environment["clear"]["OMP_NUM_THREADS"] == "2"
    assert "OPENAI_API_KEY" in environment["hashed"]
    assert "LM_LICENSE_FILE" in environment["hashed"]
    assert "sk-test-secret" not in serialized
    assert "27000@license-server" not in serialized
