"""Control-flow checks only: these do not execute or validate Palace physics."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_smoke(filename="run_palace_smoke.py"):
    directory = ROOT / "scripts" / "external"
    sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location(
            "palace_smoke_retention", directory / filename
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(directory))


def test_existing_output_is_rejected_before_solver_probe(tmp_path, monkeypatch):
    module = load_smoke()
    sentinel = tmp_path / "eig.csv"
    sentinel.write_bytes(b"retained solver output")

    def forbidden():
        raise AssertionError("must not probe or execute when destination exists")

    monkeypatch.setattr(module, "palace_install_identity", forbidden)
    assert module.main(["--out", str(tmp_path)]) == 2
    assert sentinel.read_bytes() == b"retained solver output"


def test_missing_solver_does_not_claim_smoke_success(tmp_path, monkeypatch):
    module = load_smoke()
    monkeypatch.setattr(module, "palace_install_identity", lambda: None)
    out = tmp_path / "first"
    assert module.main(["--out", str(out)]) == 1
    assert out.is_dir()
    assert not (out / "result.json").exists()


def make_run(module, root, frequency=5.0):
    import json

    root.mkdir()
    config = root / "cavity2d.json"
    config.write_text("fixture: not a physical simulation")
    eig = root / "postpro/eigenmode/eig.csv"
    eig.parent.mkdir(parents=True)
    eig.write_text(f"m,Re{{f}} (GHz)\n1,{frequency}\n")
    report = {
        "status": "SMOKE_TEST_PASSED",
        "return_code": 0,
        "palace_version": module.PALACE_VERSION,
        "palace_commit": module.PALACE_COMMIT,
        "palace_executable_sha256": "a" * 64,
        "input_file_hashes": {"cavity2d.json": module.sha256_file(config)},
        "output_file_hashes": {"postpro/eigenmode/eig.csv": module.sha256_file(eig)},
    }
    (root / "result.json").write_text(json.dumps(report))
    return root


def test_repeat_comparison_rejects_drift_and_tampered_artifacts(tmp_path):
    import pytest

    module = load_smoke("check_palace_smoke_repeat.py")
    first = make_run(module, tmp_path / "first")
    repeat = make_run(module, tmp_path / "repeat", 5.0000001)
    assert module.compare(first, repeat)["passed"] is True
    changed = make_run(module, tmp_path / "changed", 5.00001)
    assert module.compare(first, changed)["passed"] is False
    with pytest.raises(ValueError, match="distinct"):
        module.compare(first, first)
    (repeat / "postpro/eigenmode/eig.csv").write_text("tampered")
    with pytest.raises(ValueError, match="artifact mismatch"):
        module.compare(first, repeat)


def test_consecutive_smoke_runs_drift_criterion(tmp_path):
    module = load_smoke("check_palace_smoke_repeat.py")
    first_dir = tmp_path / "run_1"
    second_dir = tmp_path / "run_2"
    # Frequency drifts by 1e-7 (< 1e-6)
    make_run(module, first_dir, 5.0000000)
    make_run(module, second_dir, 5.0000003)
    comparison = module.compare(first_dir, second_dir)
    assert comparison["passed"] is True
    assert comparison["status"] == "REPEATABLE_SMOKE"
    assert all(drift < 1e-6 for drift in comparison["relative_frequency_drifts"])
