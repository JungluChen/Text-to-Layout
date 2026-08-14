from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "generate_nightly_manifest.py"


def _module():
    spec = importlib.util.spec_from_file_location("generate_nightly_manifest", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_passes_only_for_complete_byte_identical_runs(tmp_path: Path) -> None:
    module = _module()
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    for relative in module.DETERMINISTIC_ARTIFACTS:
        (first / relative).write_bytes(relative.encode())
        (second / relative).write_bytes(relative.encode())
    manifest = module.build_manifest(first, second, git_commit="a" * 40)
    assert manifest["passed"] is True
    assert manifest["missing_artifacts"] == []
    assert manifest["mismatched_artifacts"] == []

    (second / "output.gds").write_bytes(b"changed")
    changed = module.build_manifest(first, second, git_commit="a" * 40)
    assert changed["passed"] is False
    assert changed["mismatched_artifacts"] == ["output.gds"]
