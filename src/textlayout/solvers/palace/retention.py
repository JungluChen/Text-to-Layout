"""Bounded retention of large Palace field artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.canonical import sha256_file
from textlayout.solvers.palace.config import write_json
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
    action: str
    reason: str


def apply_field_retention(
    run_root: Path,
    fields_by_iteration: list[dict[int, Path]],
    *,
    target_modes: list[int],
    competitor_modes: list[int | None],
    ambiguous_iterations: set[int] | None = None,
    policy: FieldRetentionPolicy | None = None,
) -> Path:
    """Apply retention only below ``run_root`` and write an immutable manifest."""
    root = run_root.resolve()
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
            artifacts = field_artifact_files(manifest)
            keep = iteration >= first_retained and mode in keep_modes
            reason = (
                "final accepted iteration and tracked/competing mode"
                if keep
                else "outside bounded field retention policy"
            )
            for artifact in artifacts:
                resolved = artifact.resolve()
                if not resolved.is_relative_to(root):
                    raise ValueError(f"field artifact is outside run namespace: {resolved}")
                digest = sha256_file(resolved)
                size = resolved.stat().st_size
                relative = resolved.relative_to(root).as_posix()
                action = "retained" if keep else "deleted"
                entries.append(
                    RetentionEntry(
                        path=relative,
                        sha256=digest,
                        size_bytes=size,
                        action=action,
                        reason=reason,
                    )
                )
                if not keep:
                    resolved.unlink()
    manifest_path = root / "field_retention_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"immutable retention manifest already exists: {manifest_path}")
    write_json(
        {
            "schema": "textlayout.palace-field-retention.v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "policy": selected_policy.model_dump(mode="json"),
            "entries": [entry.model_dump(mode="json") for entry in entries],
        },
        manifest_path,
    )
    return manifest_path
