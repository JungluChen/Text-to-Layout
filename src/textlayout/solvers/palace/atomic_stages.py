"""Atomic lifecycle evidence for bounded Palace workflow stages."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.canonical import sha256_file, sha256_json

BoundedStageName = Literal[
    "preflight",
    "mesh_generation",
    "solve_state_0",
    "adapt_mesh_0",
    "solve_state_1",
    "field_parse",
    "mode_tracking",
    "energy_validation",
    "field_retention",
    "canonical_evidence",
]


class AtomicStageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "textlayout.palace-atomic-stage.v1"
    stage: BoundedStageName
    state: Literal["STARTED", "COMPLETED", "FAILED"]
    timestamp: str
    command: list[str] | None = None
    return_code: int | None = None
    input_hashes: dict[str, str] = Field(default_factory=dict)
    output_hashes: dict[str, str] = Field(default_factory=dict)
    parsed_result_sha256: str | None = None
    resource_summary_sha256: str | None = None
    owned_children_remaining: bool | None = None
    reason: str | None = None
    evidence_id: str


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_record(path: Path, payload: dict[str, object]) -> AtomicStageRecord:
    record = AtomicStageRecord(**payload, evidence_id=sha256_json(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return record


def _stage_dir(root: Path, stage: BoundedStageName) -> Path:
    return root.resolve() / "atomic_stages" / stage


def start_atomic_stage(
    root: Path,
    stage: BoundedStageName,
    *,
    command: list[str] | None = None,
    inputs: list[Path] | None = None,
) -> AtomicStageRecord:
    directory = _stage_dir(root, stage)
    completed = directory / "stage_completed.json"
    started = directory / "stage_started.json"
    if completed.is_file():
        return read_atomic_stage(completed)
    if started.is_file():
        return read_atomic_stage(started)
    input_hashes = {
        str(path.resolve()): sha256_file(path)
        for path in inputs or []
        if path.is_file()
    }
    payload: dict[str, object] = {
        "stage": stage,
        "state": "STARTED",
        "timestamp": _timestamp(),
        "command": command,
        "input_hashes": input_hashes,
    }
    return _atomic_record(started, payload)


def complete_atomic_stage(
    root: Path,
    stage: BoundedStageName,
    *,
    return_code: int,
    required_outputs: list[Path],
    parsed_result: Path | None,
    resource_summary: Path,
    owned_children_remaining: bool,
    command: list[str] | None = None,
) -> AtomicStageRecord:
    directory = _stage_dir(root, stage)
    completed = directory / "stage_completed.json"
    if completed.is_file():
        record = read_atomic_stage(completed)
        for name, digest in record.output_hashes.items():
            path = Path(name)
            if not path.is_file() or sha256_file(path) != digest:
                raise ValueError(f"{stage}: completed-stage output hash changed: {path}")
        return record
    started = directory / "stage_started.json"
    if not started.is_file():
        raise ValueError(f"{stage}: stage_started.json is required")
    if return_code != 0:
        raise ValueError(f"{stage}: return code is {return_code}, not zero")
    invalid = [path for path in required_outputs if not path.is_file() or path.stat().st_size == 0]
    if invalid:
        raise ValueError(f"{stage}: required outputs are missing or zero bytes: {invalid}")
    if parsed_result is not None and (
        not parsed_result.is_file() or parsed_result.stat().st_size == 0
    ):
        raise ValueError(f"{stage}: parsed result is missing or zero bytes")
    if not resource_summary.is_file() or resource_summary.stat().st_size == 0:
        raise ValueError(f"{stage}: resource summary is missing or zero bytes")
    if owned_children_remaining:
        raise ValueError(f"{stage}: owned Palace/MPI child remains active")
    outputs = {str(path.resolve()): sha256_file(path) for path in required_outputs}
    payload: dict[str, object] = {
        "stage": stage,
        "state": "COMPLETED",
        "timestamp": _timestamp(),
        "command": command,
        "return_code": return_code,
        "output_hashes": outputs,
        "parsed_result_sha256": sha256_file(parsed_result) if parsed_result else None,
        "resource_summary_sha256": sha256_file(resource_summary),
        "owned_children_remaining": False,
    }
    return _atomic_record(completed, payload)


def fail_atomic_stage(
    root: Path,
    stage: BoundedStageName,
    *,
    reason: str,
    return_code: int | None = None,
) -> AtomicStageRecord:
    payload: dict[str, object] = {
        "stage": stage,
        "state": "FAILED",
        "timestamp": _timestamp(),
        "return_code": return_code,
        "reason": reason,
    }
    return _atomic_record(_stage_dir(root, stage) / "stage_failed.json", payload)


def read_atomic_stage(path: Path) -> AtomicStageRecord:
    return AtomicStageRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))


def fail_unfinished_atomic_stages(root: Path, *, reason: str) -> list[AtomicStageRecord]:
    """Finalize every started stage that has neither completion nor failure evidence."""
    failed: list[AtomicStageRecord] = []
    stages: tuple[BoundedStageName, ...] = (
        "preflight",
        "mesh_generation",
        "solve_state_0",
        "adapt_mesh_0",
        "solve_state_1",
        "field_parse",
        "mode_tracking",
        "energy_validation",
        "field_retention",
        "canonical_evidence",
    )
    for stage in stages:
        directory = _stage_dir(root, stage)
        if not (directory / "stage_started.json").is_file():
            continue
        if (directory / "stage_completed.json").is_file():
            continue
        if (directory / "stage_failed.json").is_file():
            continue
        failed.append(fail_atomic_stage(root, stage, reason=reason))
    return failed
