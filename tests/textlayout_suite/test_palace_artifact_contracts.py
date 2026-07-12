from __future__ import annotations

from pathlib import Path

from textlayout.solvers.palace.artifacts import (
    ArtifactFingerprint,
    PALACE_ARTIFACT_CONTRACTS,
    scan_palace_artifacts,
)


def test_every_palace_contract_declares_sizes_and_retention() -> None:
    assert set(PALACE_ARTIFACT_CONTRACTS) == {
        "preflight",
        "base_mesh",
        "base_amr",
        "mode_tracking",
        "numerical_sweeps",
        "physical_sensitivity",
        "evidence_promotion",
        "packet_generation",
    }
    for contract in PALACE_ARTIFACT_CONTRACTS.values():
        assert contract.maximum_expected_sizes
        assert contract.retention_policy


def test_contract_prefilters_unchanged_and_reports_undeclared(tmp_path: Path) -> None:
    (tmp_path / "toolchain.json").write_text("{}", encoding="utf-8")
    (tmp_path / "environment.json").write_text("{}", encoding="utf-8")
    (tmp_path / "resource_decision.json").write_text("{}", encoding="utf-8")
    (tmp_path / "fem_model.json").write_text("{}", encoding="utf-8")
    (tmp_path / "surprise.bin").write_bytes(b"x")
    first = scan_palace_artifacts(tmp_path, "preflight")
    previous = {
        entry.path: ArtifactFingerprint(
            path=entry.path,
            size_bytes=entry.size_bytes or 0,
            mtime_ns=entry.mtime_ns or 0,
            sha256=entry.sha256,
        )
        for entry in first.entries
        if entry.sha256 is not None
    }
    second = scan_palace_artifacts(tmp_path, "preflight", previous_manifest=previous)
    assert "surprise.bin" in second.undeclared_outputs
    assert all(
        entry.status == "UNCHANGED"
        for entry in second.entries
        if entry.role != "undeclared"
    )


def test_contract_reports_oversized_declared_output(monkeypatch, tmp_path: Path) -> None:
    for name in (
        "toolchain.json",
        "environment.json",
        "resource_decision.json",
        "fem_model.json",
    ):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    original = PALACE_ARTIFACT_CONTRACTS["preflight"]
    monkeypatch.setitem(
        PALACE_ARTIFACT_CONTRACTS,
        "preflight",
        original.model_copy(update={"maximum_expected_sizes": {"*.json": 1}}),
    )
    report = scan_palace_artifacts(tmp_path, "preflight")
    assert all(entry.status == "OVERSIZE" for entry in report.entries)
