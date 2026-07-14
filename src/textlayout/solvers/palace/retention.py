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


class RetentionPlanConflict(RuntimeError):
    """An existing retention plan was created for a different request."""


class RetentionRequestFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "textlayout.palace-field-retention-request.v1"
    run_root: str
    evidence_id: str = Field(min_length=64, max_length=64)
    policy: FieldRetentionPolicy
    field_inventory: list[dict[str, int | str]]
    source_hashes: dict[str, str]
    target_modes: list[int]
    competitor_modes: list[int | None]
    ambiguous_iterations: list[int]
    fingerprint_sha256: str = Field(min_length=64, max_length=64)


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
    request_fingerprint: RetentionRequestFingerprint
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


def _build_request_fingerprint(
    run_root: Path,
    fields_by_iteration: list[dict[int, Path]],
    *,
    target_modes: list[int],
    competitor_modes: list[int | None],
    ambiguous_iterations: set[int],
    policy: FieldRetentionPolicy,
    evidence_id: str,
) -> RetentionRequestFingerprint:
    inventory: list[dict[str, int | str]] = []
    source_hashes: dict[str, str] = {}
    for iteration, fields in enumerate(fields_by_iteration):
        for mode, manifest in sorted(fields.items()):
            resolved_manifest = manifest.resolve()
            if not resolved_manifest.is_relative_to(run_root):
                raise ValueError(f"field artifact is outside run namespace: {resolved_manifest}")
            for artifact in field_artifact_files(resolved_manifest):
                resolved = artifact.resolve()
                if not resolved.is_relative_to(run_root):
                    raise ValueError(f"field artifact is outside run namespace: {resolved}")
                relative = resolved.relative_to(run_root).as_posix()
                inventory.append(
                    {
                        "iteration": iteration,
                        "mode": int(mode),
                        "path": relative,
                        "size_bytes": resolved.stat().st_size,
                    }
                )
                source_hashes[relative] = sha256_file(resolved)
    payload = {
        "schema_version": "textlayout.palace-field-retention-request.v1",
        "run_root": run_root.as_posix(),
        "evidence_id": evidence_id,
        "policy": policy.model_dump(mode="json"),
        "field_inventory": inventory,
        "source_hashes": source_hashes,
        "target_modes": list(target_modes),
        "competitor_modes": list(competitor_modes),
        "ambiguous_iterations": sorted(ambiguous_iterations),
    }
    return RetentionRequestFingerprint(
        **payload,
        fingerprint_sha256=sha256_json(payload),
    )


def create_retention_plan(
    run_root: Path,
    fields_by_iteration: list[dict[int, Path]],
    *,
    target_modes: list[int],
    competitor_modes: list[int | None],
    ambiguous_iterations: set[int] | None = None,
    policy: FieldRetentionPolicy | None = None,
    evidence_id: str,
) -> Path:
    """Hash every source and atomically persist an immutable retention plan."""
    root = run_root.resolve()
    plan_path = root / "field_retention_plan.json"
    selected_policy = policy or FieldRetentionPolicy()
    ambiguous = ambiguous_iterations or set()
    fingerprint = _build_request_fingerprint(
        root,
        fields_by_iteration,
        target_modes=target_modes,
        competitor_modes=competitor_modes,
        ambiguous_iterations=ambiguous,
        policy=selected_policy,
        evidence_id=evidence_id,
    )
    if plan_path.exists():
        existing = RetentionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        if existing.request_fingerprint.fingerprint_sha256 != fingerprint.fingerprint_sha256:
            raise RetentionPlanConflict(
                "RETENTION_PLAN_CONFLICT: existing field_retention_plan.json was "
                "created for a different policy, field inventory, source hash, "
                "target mode, competitor mode, or ambiguous iteration set"
            )
        return plan_path
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
        "request_fingerprint": fingerprint.model_dump(mode="json"),
        "policy": selected_policy.model_dump(mode="json"),
        "entries": [entry.model_dump(mode="json") for entry in entries],
    }
    plan = RetentionPlan(**payload, plan_sha256=sha256_json(payload))
    _atomic_json(plan_path, plan.model_dump(mode="json"))
    return plan_path


FaultInjectionPoint = Literal[
    "after_first_move",
    "after_all_moves",
    "before_completion_write",
    "after_completion_write",
    "before_quarantine_deletion",
]


def _maybe_fault(point: FaultInjectionPoint, requested: FaultInjectionPoint | None) -> None:
    if requested == point:
        raise RuntimeError(f"retention fault injection: {point}")


def execute_retention_plan(
    run_root: Path, *, fault_injection: FaultInjectionPoint | None = None
) -> Path:
    """Validate, quarantine, complete atomically, then remove quarantine."""
    root = run_root.resolve()
    plan_path = root / "field_retention_plan.json"
    plan = RetentionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    completion = root / "field_retention_completion.json"
    quarantine = root / ".field-retention-quarantine" / plan.plan_sha256
    if completion.exists():
        for entry in plan.entries:
            if entry.action != "retain":
                continue
            retained = root / entry.path
            if not retained.is_file() or sha256_file(retained) != entry.sha256:
                raise ValueError(
                    f"completed retention hash mismatch or missing: {entry.path}"
                )
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
    moved = 0
    for entry in plan.entries:
        if entry.action != "quarantine":
            continue
        source, target = root / entry.path, quarantine / entry.path
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            moved += 1
            if moved == 1:
                _maybe_fault("after_first_move", fault_injection)
    _maybe_fault("after_all_moves", fault_injection)
    completion_payload = {
        "schema": "textlayout.palace-field-retention-completion.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": plan.plan_sha256,
        "retained_bytes": sum(e.size_bytes for e in plan.entries if e.action == "retain"),
        "quarantined_bytes": sum(e.size_bytes for e in plan.entries if e.action == "quarantine"),
        "entries": [entry.model_dump(mode="json") for entry in plan.entries],
    }
    _maybe_fault("before_completion_write", fault_injection)
    _atomic_json(completion, completion_payload)
    _maybe_fault("after_completion_write", fault_injection)
    if quarantine.exists():
        _maybe_fault("before_quarantine_deletion", fault_injection)
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
    evidence_id: str,
) -> Path:
    create_retention_plan(
        run_root,
        fields_by_iteration,
        target_modes=target_modes,
        competitor_modes=competitor_modes,
        ambiguous_iterations=ambiguous_iterations,
        policy=policy,
        evidence_id=evidence_id,
    )
    return execute_retention_plan(run_root)
