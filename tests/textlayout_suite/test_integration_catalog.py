"""The 100-target request is an inventory, not 100 certified integrations."""

from __future__ import annotations

from pathlib import Path

from textlayout.doctor import run_doctor
from textlayout.integrations import load_targets


def test_candidate_catalog_has_ten_ordered_pillars_and_100_unique_slots() -> None:
    targets = load_targets()
    assert len(targets) == 100
    assert [target.id for target in targets] == list(range(1, 101))
    assert [sum(target.pillar == pillar for target in targets) for pillar in range(1, 11)] == [
        10
    ] * 10
    assert targets[10].name == "AWS Palace"
    assert targets[96].name == "LangGraph"


def test_doctor_reports_candidates_without_implying_execution(tmp_path: Path) -> None:
    report = run_doctor(output_dir=tmp_path / "doctor").to_dict()
    candidates = report["integration_targets"]
    assert len(candidates) == 100
    assert all(not entry["source_verified"] for entry in candidates)
    assert all(not entry["license_verified"] for entry in candidates)
    assert all(not entry["execution_verified"] for entry in candidates)
    assert candidates[10]["probe_status"] == report["external_solvers"]["Palace"]["status"]
    assert candidates[10]["probe_scope"] == "solver identity/version probe"
    assert candidates[27]["probe_status"] == "NOT_PROBED"
    assert candidates[42]["probe_status"] == "NOT_PROBED"  # grouped SPICE check is ambiguous
