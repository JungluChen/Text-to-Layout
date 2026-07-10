"""External tool registry and license-boundary gates."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from textlayout.solvers.josephsoncircuits import (  # noqa: E402
    execute_josephsoncircuits,
    prepare_jpa_netlist,
)

SCRIPTS = REPO_ROOT / "scripts" / "external"


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


COMMON = _load_script("_common")
NOTICES = _load_script("generate_notices")


def test_registry_entries_are_pinned_license_aware_and_locked():
    registry = COMMON.load_registry()
    problems = COMMON.validate_registry(registry)
    assert problems == []
    assert {tool["id"] for tool in registry.tools} == set(registry.locked)

    for tool in registry.tools:
        assert tool["pinned_commit"] != tool["pinned_ref"] or len(tool["pinned_commit"]) == 40
        assert len(tool["source_archive_sha256"]) == 64
        assert tool["source_archive_url"].endswith(f"{tool['pinned_commit']}.tar.gz")
        assert tool["redistribute_binaries"] is False
        if tool["spdx_license"].startswith("GPL"):
            assert "file exchange" in tool["integration_mode"]
            assert "process" in tool["integration_mode"]
        if tool["spdx_license"] == "NOASSERTION":
            assert tool["human_review_required"] is True


def test_notices_are_generated_from_registry():
    expected = NOTICES.render_notices()
    actual = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert actual == expected


def test_external_check_cli_writes_reports():
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / "check.py"), "--check-notices"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    for name in (
        "toolchain_report.json",
        "license_report.json",
        "benchmark_report.json",
        "sbom.spdx.json",
    ):
        assert (REPO_ROOT / "out" / "toolchain" / name).is_file()


def test_josephsoncircuits_missing_runtime_is_skipped_not_executed(tmp_path):
    prepared = prepare_jpa_netlist(
        {
            "schema": "textlayout.josephsoncircuits-netlist.v1",
            "capacitances_f": [1e-12],
            "inductances_h": [1e-9],
            "junctions": [{"critical_current_a": 1e-6}],
        },
        tmp_path,
    )
    result = execute_josephsoncircuits(prepared, executable="definitely-not-julia")
    assert result.status == "skipped"
    assert result.solver_executed is False
    assert result.physics_verified is False
    assert "SKIPPED_SOLVER_ABSENT" in result.reason
