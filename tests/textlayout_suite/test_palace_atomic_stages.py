from pathlib import Path

import pytest

from textlayout.solvers.palace.atomic_stages import (
    complete_atomic_stage,
    fail_atomic_stage,
    start_atomic_stage,
)


def test_atomic_stage_requires_finalized_nonzero_outputs(tmp_path: Path) -> None:
    start_atomic_stage(tmp_path, "solve_state_0")
    output = tmp_path / "field.vtu"
    output.touch()
    resource = tmp_path / "resource.json"
    resource.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="missing or zero"):
        complete_atomic_stage(
            tmp_path,
            "solve_state_0",
            return_code=0,
            required_outputs=[output],
            parsed_result=None,
            resource_summary=resource,
            owned_children_remaining=False,
        )


def test_atomic_stage_rejects_orphan_and_records_failure(tmp_path: Path) -> None:
    start_atomic_stage(tmp_path, "solve_state_1")
    output = tmp_path / "field.vtu"
    output.write_text("field", encoding="utf-8")
    resource = tmp_path / "resource.json"
    resource.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="child remains"):
        complete_atomic_stage(
            tmp_path,
            "solve_state_1",
            return_code=0,
            required_outputs=[output],
            parsed_result=None,
            resource_summary=resource,
            owned_children_remaining=True,
        )
    failed = fail_atomic_stage(tmp_path, "solve_state_1", reason="orphan remains")
    assert failed.state == "FAILED"


def test_atomic_stage_completion_has_hashes(tmp_path: Path) -> None:
    start_atomic_stage(tmp_path, "field_parse")
    output = tmp_path / "parsed.json"
    output.write_text("{}", encoding="utf-8")
    resource = tmp_path / "resource.json"
    resource.write_text("{}", encoding="utf-8")
    completed = complete_atomic_stage(
        tmp_path,
        "field_parse",
        return_code=0,
        required_outputs=[output],
        parsed_result=output,
        resource_summary=resource,
        owned_children_remaining=False,
    )
    assert completed.state == "COMPLETED"
    assert completed.output_hashes
    assert start_atomic_stage(tmp_path, "field_parse").evidence_id == completed.evidence_id
    output.write_text('{"changed": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="output hash changed"):
        complete_atomic_stage(
            tmp_path,
            "field_parse",
            return_code=0,
            required_outputs=[output],
            parsed_result=output,
            resource_summary=resource,
            owned_children_remaining=False,
        )
