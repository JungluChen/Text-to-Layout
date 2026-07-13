"""Transaction-safe bounded retention of large Palace field artifacts."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.canonical import sha256_file, sha256_json
from textlayout.solvers.palace.parser import field_artifact_files


class FieldRetentionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    final_accepted_iterations: int = Field(default=3, ge=1)
    retain_target_and_competitor: bool = True
    retain_all_for_ambiguous_modes: bool = True


class RetentionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str
    size_bytes: int = Field(ge=0)
    action: Literal["retain", "quarantine"]
    reason: str


class RetentionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "textlayout.palace-field-retention-plan.v1"
    created_at: str
    policy: FieldRetentionPolicy
    entries: list[RetentionEntry]
    plan_sha256: str = Field(min_length=64, max_length=64)


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _remove_empty_quarantine_root(root: Path) -> None:
    quarantine_root = root / ".field-retention-quarantine"
    if quarantine_root.is_dir() and not any(quarantine_root.iterdir()):
        quarantine_root.rmdir()


def create_retention_plan(
    run_root: Path,
    fields_by_iteration: list[dict[int, Path]],
    *,
    target_modes: list[int],
    competitor_modes: list[int | None],
    ambiguous_iterations: set[int] | None = None,
    policy: FieldRetentionPolicy | None = None,
) -> Path:
    """Hash every source and atomically persist an immutable retention plan."""
    root = run_root.resolve()
    plan_path = root / "field_retention_plan.json"
    if plan_path.exists():
        RetentionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        return plan_path
    selected_policy = policy or FieldRetentionPolicy()
    ambiguous = ambiguous_iterations or set()
    first_retained = max(0, len(fields_by_iteration) - selected_policy.final_accepted_iterations)
    entries: list[RetentionEntry] = []
    for iteration, fields in enumerate(fields_by_iteration):
        keep_modes = {target_modes[iteration]}
        competitor = competitor_modes[iteration]
        if competitor is not None:
            keep_modes.add(competitor)
        if iteration in ambiguous and selected_policy.retain_all_for_ambiguous_modes:
            keep_modes = set(fields)
        for mode, manifest in sorted(fields.items()):
            keep = iteration >= first_retained and mode in keep_modes
            for artifact in field_artifact_files(manifest):
                resolved = artifact.resolve()
                if not resolved.is_relative_to(root):
                    raise ValueError(f"field artifact is outside run namespace: {resolved}")
                entries.append(
                    RetentionEntry(
                        path=resolved.relative_to(root).as_posix(),
                        sha256=sha256_file(resolved),
                        size_bytes=resolved.stat().st_size,
                        action="retain" if keep else "quarantine",
                        reason=(
                            "final accepted iteration and tracked/competing mode"
                            if keep
                            else "outside bounded field retention policy"
                        ),
                    )
                )
    payload = {
        "schema_version": "textlayout.palace-field-retention-plan.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": selected_policy.model_dump(mode="json"),
        "entries": [entry.model_dump(mode="json") for entry in entries],
    }
    plan = RetentionPlan(**payload, plan_sha256=sha256_json(payload))
    _atomic_json(plan_path, plan.model_dump(mode="json"))
    return plan_path


def execute_retention_plan(run_root: Path) -> Path:
    """Validate, quarantine, complete atomically, then remove quarantine."""
    root = run_root.resolve()
    plan_path = root / "field_retention_plan.json"
    plan = RetentionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    completion = root / "field_retention_completion.json"
    quarantine = root / ".field-retention-quarantine" / plan.plan_sha256
    if completion.exists():
        if quarantine.exists():
            shutil.rmtree(quarantine)
        _remove_empty_quarantine_root(root)
        return completion
    for entry in plan.entries:
        source = root / entry.path
        target = quarantine / entry.path
        current = source if source.is_file() else target
        if not current.is_file() or sha256_file(current) != entry.sha256:
            raise ValueError(f"retention source hash mismatch or missing: {entry.path}")
    for entry in plan.entries:
        if entry.action != "quarantine":
            continue
        source, target = root / entry.path, quarantine / entry.path
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
    completion_payload = {
        "schema": "textlayout.palace-field-retention-completion.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": plan.plan_sha256,
        "retained_bytes": sum(e.size_bytes for e in plan.entries if e.action == "retain"),
        "quarantined_bytes": sum(e.size_bytes for e in plan.entries if e.action == "quarantine"),
        "entries": [entry.model_dump(mode="json") for entry in plan.entries],
    }
    _atomic_json(completion, completion_payload)
    if quarantine.exists():
        shutil.rmtree(quarantine)
    _remove_empty_quarantine_root(root)
    return completion


def rollback_retention_plan(run_root: Path) -> None:
    """Restore quarantined files when completion evidence has not been written."""
    root = run_root.resolve()
    if (root / "field_retention_completion.json").exists():
        raise RuntimeError("completed retention cannot be rolled back")
    plan = RetentionPlan.model_validate_json(
        (root / "field_retention_plan.json").read_text(encoding="utf-8")
    )
    quarantine = root / ".field-retention-quarantine" / plan.plan_sha256
    for entry in plan.entries:
        source, target = quarantine / entry.path, root / entry.path
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
    if quarantine.exists():
        shutil.rmtree(quarantine)
    _remove_empty_quarantine_root(root)


def apply_field_retention(
    run_root: Path,
    fields_by_iteration: list[dict[int, Path]],
    *,
    target_modes: list[int],
    competitor_modes: list[int | None],
    ambiguous_iterations: set[int] | None = None,
    policy: FieldRetentionPolicy | None = None,
) -> Path:
    create_retention_plan(
        run_root,
        fields_by_iteration,
        target_modes=target_modes,
        competitor_modes=competitor_modes,
        ambiguous_iterations=ambiguous_iterations,
        policy=policy,
    )
    return execute_retention_plan(run_root)
