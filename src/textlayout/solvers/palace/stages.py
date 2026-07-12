"""Persistent stage records for the Palace resonator benchmark."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.canonical import sha256_file, sha256_json
from textlayout.solvers.palace.models import PalaceCapability

StageName = Literal[
    "preflight",
    "base_mesh",
    "base_amr",
    "mode_tracking",
    "numerical_sweeps",
    "physical_sensitivity",
    "evidence_promotion",
    "packet_generation",
]

STAGE_ORDER: tuple[StageName, ...] = (
    "preflight",
    "base_mesh",
    "base_amr",
    "mode_tracking",
    "numerical_sweeps",
    "physical_sensitivity",
    "evidence_promotion",
    "packet_generation",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StageRecord(BaseModel):
    """Immutable evidence record for one resumable Palace workflow stage."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_: str = Field(default="textlayout.palace-stage-record.v1", alias="schema")
    stage: StageName
    status: str
    input_hashes: dict[str, str] = Field(default_factory=dict)
    output_hashes: dict[str, str] = Field(default_factory=dict)
    command: list[str] | None = None
    return_code: int | None = None
    runtime_seconds: float | None = None
    started_at: str
    completed_at: str
    executable_identity: dict[str, Any] = Field(default_factory=dict)
    upstream_stage_evidence_ids: list[str] = Field(default_factory=list)
    evidence_id: str
    notes: list[str] = Field(default_factory=list)


def relative_hashes(paths: list[Path], root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    root_resolved = root.resolve()
    for path in paths:
        if not path.is_file():
            continue
        try:
            key = str(path.resolve().relative_to(root_resolved)).replace("\\", "/")
        except ValueError:
            key = str(path)
        hashes[key] = sha256_file(path)
    return dict(sorted(hashes.items()))


def stage_identity_payload(
    *,
    stage: StageName,
    status: str,
    input_hashes: dict[str, str],
    output_hashes: dict[str, str],
    command: list[str] | None,
    return_code: int | None,
    executable_identity: dict[str, Any],
    upstream_stage_evidence_ids: list[str],
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "input_hashes": input_hashes,
        "output_hashes": output_hashes,
        "command": command,
        "return_code": return_code,
        "executable_identity": executable_identity,
        "upstream_stage_evidence_ids": upstream_stage_evidence_ids,
    }


def executable_identity(capability: PalaceCapability) -> dict[str, Any]:
    return {
        "name": "Palace",
        "version": capability.version,
        "execution_kind": capability.execution_kind,
        "executable": capability.executable,
        "executable_sha256": capability.executable_sha256,
        "mpi_launcher": capability.mpi_launcher,
    }


def write_stage_record(
    root: Path,
    *,
    stage: StageName,
    status: str,
    input_hashes: dict[str, str] | None = None,
    output_hashes: dict[str, str] | None = None,
    command: list[str] | None = None,
    return_code: int | None = None,
    runtime_seconds: float | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    capability: PalaceCapability,
    upstream_stage_evidence_ids: list[str] | None = None,
    notes: list[str] | None = None,
) -> StageRecord:
    inputs = input_hashes or {}
    outputs = output_hashes or {}
    upstream = upstream_stage_evidence_ids or []
    exe = executable_identity(capability)
    evidence_id = sha256_json(
        stage_identity_payload(
            stage=stage,
            status=status,
            input_hashes=inputs,
            output_hashes=outputs,
            command=command,
            return_code=return_code,
            executable_identity=exe,
            upstream_stage_evidence_ids=upstream,
        )
    )
    record = StageRecord(
        stage=stage,
        status=status,
        input_hashes=inputs,
        output_hashes=outputs,
        command=command,
        return_code=return_code,
        runtime_seconds=runtime_seconds,
        started_at=started_at or completed_at or utc_now(),
        completed_at=completed_at or utc_now(),
        executable_identity=exe,
        upstream_stage_evidence_ids=upstream,
        evidence_id=evidence_id,
        notes=notes or [],
    )
    stages = root / "stages"
    stages.mkdir(parents=True, exist_ok=True)
    target = stages / f"{stage}.json"
    if target.is_file():
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing.get("evidence_id") != evidence_id:
            archive = stages / "history" / f"{stage}.{int(time.time())}.json"
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_text(
                json.dumps(existing, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    target.write_text(
        record.model_dump_json(indent=2, by_alias=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return record


def read_stage_records(root: Path) -> list[StageRecord]:
    records: list[StageRecord] = []
    for stage in STAGE_ORDER:
        path = root / "stages" / f"{stage}.json"
        if not path.is_file():
            continue
        records.append(StageRecord.model_validate_json(path.read_text(encoding="utf-8")))
    return records


def orphan_process_report() -> dict[str, Any]:
    """Best-effort local Palace/MPI process inventory."""
    if os.name == "nt":
        import subprocess

        ps = (
            "Get-Process | Where-Object { "
            "$_.ProcessName -match 'palace|mpirun|mpiexec|orted|prte' "
            "} | Select-Object Id,ProcessName,CPU,WorkingSet64 | ConvertTo-Json"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return {"checked": False, "processes": []}
        text = completed.stdout.strip()
        if not text:
            return {"checked": True, "processes": []}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {"checked": False, "processes": [], "raw": text}
        return {"checked": True, "processes": payload if isinstance(payload, list) else [payload]}
    return {"checked": False, "processes": []}


def status_report(root: Path) -> dict[str, Any]:
    records = read_stage_records(root)
    by_stage = {record.stage: record for record in records}
    return {
        "schema": "textlayout.palace-resonator-status.v1",
        "output_dir": str(root.resolve()),
        "stages": [
            {
                "stage": stage,
                "status": by_stage[stage].status if stage in by_stage else "missing",
                "evidence_id": by_stage[stage].evidence_id if stage in by_stage else None,
                "completed_at": by_stage[stage].completed_at if stage in by_stage else None,
            }
            for stage in STAGE_ORDER
        ],
        "orphan_processes": orphan_process_report(),
    }
