from pathlib import Path

import pytest

from textlayout.solvers.palace.retention import (
    RetentionPlan,
    RetentionPlanConflict,
    apply_field_retention,
    create_retention_plan,
    execute_retention_plan,
    rollback_retention_plan,
)

EVIDENCE_ID = "e" * 64


def _manifest(path: Path, piece: str) -> None:
    path.write_text(
        f'<VTKFile><PUnstructuredGrid><Piece Source="{piece}"/></PUnstructuredGrid></VTKFile>',
        encoding="utf-8",
    )


def test_retention_keeps_target_and_competitor_and_records_deletions(tmp_path: Path) -> None:
    fields: dict[int, Path] = {}
    for mode in (1, 2, 3):
        piece = tmp_path / f"mode{mode}.vtu"
        piece.write_text("field", encoding="utf-8")
        manifest = tmp_path / f"mode{mode}.pvtu"
        _manifest(manifest, piece.name)
        fields[mode] = manifest
    result = apply_field_retention(
        tmp_path,
        [fields],
        target_modes=[2],
        competitor_modes=[1],
        evidence_id=EVIDENCE_ID,
    )
    assert result.is_file()
    assert fields[1].exists() and fields[2].exists()
    assert not fields[3].exists() and not (tmp_path / "mode3.vtu").exists()


def _fields(tmp_path: Path) -> dict[int, Path]:
    fields: dict[int, Path] = {}
    for mode in (1, 2):
        piece = tmp_path / f"resume_mode{mode}.vtu"
        piece.write_text(f"field-{mode}", encoding="utf-8")
        manifest = tmp_path / f"resume_mode{mode}.pvtu"
        _manifest(manifest, piece.name)
        fields[mode] = manifest
    return fields


def _simulate_interrupted_move(tmp_path: Path, plan_path: Path) -> Path:
    plan = RetentionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    entry = next(item for item in plan.entries if item.action == "quarantine")
    source = tmp_path / entry.path
    target = tmp_path / ".field-retention-quarantine" / plan.plan_sha256 / entry.path
    target.parent.mkdir(parents=True, exist_ok=True)
    source.replace(target)
    return source


def test_retention_resumes_after_interrupted_quarantine_move(tmp_path: Path) -> None:
    fields = _fields(tmp_path)
    plan_path = create_retention_plan(
        tmp_path,
        [fields],
        target_modes=[2],
        competitor_modes=[None],
        evidence_id=EVIDENCE_ID,
    )
    moved_source = _simulate_interrupted_move(tmp_path, plan_path)
    completion = execute_retention_plan(tmp_path)
    assert completion.is_file()
    assert not moved_source.exists()
    assert fields[2].exists()
    assert not (tmp_path / ".field-retention-quarantine").exists()


def test_retention_rollback_restores_interrupted_move(tmp_path: Path) -> None:
    fields = _fields(tmp_path)
    plan_path = create_retention_plan(
        tmp_path,
        [fields],
        target_modes=[2],
        competitor_modes=[None],
        evidence_id=EVIDENCE_ID,
    )
    moved_source = _simulate_interrupted_move(tmp_path, plan_path)
    rollback_retention_plan(tmp_path)
    assert moved_source.is_file()
    assert fields[1].is_file() and fields[2].is_file()
    assert not (tmp_path / ".field-retention-quarantine").exists()


def test_retention_rejects_stale_plan_for_different_request(tmp_path: Path) -> None:
    fields = _fields(tmp_path)
    create_retention_plan(
        tmp_path,
        [fields],
        target_modes=[2],
        competitor_modes=[None],
        evidence_id=EVIDENCE_ID,
    )
    with pytest.raises(RetentionPlanConflict, match="RETENTION_PLAN_CONFLICT"):
        create_retention_plan(
            tmp_path,
            [fields],
            target_modes=[1],
            competitor_modes=[None],
            evidence_id=EVIDENCE_ID,
        )


def test_retention_reuses_identical_request_plan(tmp_path: Path) -> None:
    fields = _fields(tmp_path)
    first = create_retention_plan(
        tmp_path,
        [fields],
        target_modes=[2],
        competitor_modes=[None],
        evidence_id=EVIDENCE_ID,
    )
    second = create_retention_plan(
        tmp_path,
        [fields],
        target_modes=[2],
        competitor_modes=[None],
        evidence_id=EVIDENCE_ID,
    )
    assert second == first


def test_retention_resumes_after_completion_written_before_delete(tmp_path: Path) -> None:
    fields = _fields(tmp_path)
    create_retention_plan(
        tmp_path,
        [fields],
        target_modes=[2],
        competitor_modes=[None],
        evidence_id=EVIDENCE_ID,
    )
    with pytest.raises(RuntimeError, match="after_completion_write"):
        execute_retention_plan(tmp_path, fault_injection="after_completion_write")
    completion = execute_retention_plan(tmp_path)
    assert completion.is_file()
    assert not (tmp_path / ".field-retention-quarantine").exists()


@pytest.mark.parametrize(
    "fault",
    ["after_first_move", "after_all_moves", "before_completion_write"],
)
def test_retention_rollback_after_precompletion_faults(tmp_path: Path, fault: str) -> None:
    fields = _fields(tmp_path)
    create_retention_plan(
        tmp_path,
        [fields],
        target_modes=[2],
        competitor_modes=[None],
        evidence_id=EVIDENCE_ID,
    )
    with pytest.raises(RuntimeError, match=fault):
        execute_retention_plan(tmp_path, fault_injection=fault)  # type: ignore[arg-type]
    rollback_retention_plan(tmp_path)
    assert fields[1].is_file() and fields[2].is_file()
    completion = execute_retention_plan(tmp_path)
    assert completion.is_file()
