"""Platform certification is generated from structured execution evidence."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "platform" / "verify_platform.py"


def _module():
    spec = importlib.util.spec_from_file_location("verify_platform", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _blocked_fixture() -> dict:
    return {
        "schema": "textlayout.platform-certification.v1",
        "platform": "wsl2",
        "real_execution": False,
        "support_state": "UNTESTED",
        "certification": "BLOCKED_AWAITING_REAL_EXECUTION",
        "blocking_reason": "real WSL2 host was unavailable",
        "core_pass": False,
        "git_sha": "a" * 40,
        "host": {
            "os": "Darwin",
            "os_release": "24.5.0",
            "architecture": "arm64",
            "wsl_detected": False,
            "wsl_version": None,
            "wsl_distribution": None,
            "repository_filesystem": None,
            "solver_root": "/tmp/solver",
            "solver_filesystem": None,
            "windows_mount_warning": None,
        },
        "python_runs": [],
        "solvers": {},
        "capabilities": {},
    }


def test_blocked_wsl_report_cannot_claim_certification() -> None:
    rendered = _module().render_markdown(_blocked_fixture(), "out/platform/wsl2_ubuntu.json")
    assert "**Real execution:** `False`" in rendered
    assert "**Support state:** `UNTESTED`" in rendered
    assert "explicit non-certification record" in rendered
    assert "Ubuntu CI is not WSL2 evidence" in rendered
    assert "CORE_CERTIFIED" not in rendered


def test_platform_shell_collectors_are_strict_and_use_one_json_renderer() -> None:
    macos = (ROOT / "scripts" / "platform" / "verify_macos.sh").read_text(encoding="utf-8")
    wsl = (ROOT / "scripts" / "platform" / "verify_wsl.sh").read_text(encoding="utf-8")
    for script in (macos, wsl):
        assert "set -euo pipefail" in script
        assert "verify_platform.py" in script
    assert '"$(uname -s)" != "Darwin"' in macos
    assert "grep -qi microsoft /proc/version" in wsl
    assert "uname -a" in wsl and "lsb_release -a" in wsl


def test_rendering_is_deterministic() -> None:
    module = _module()
    evidence = _blocked_fixture()
    first = module.render_markdown(evidence, "out/platform/wsl2_ubuntu.json")
    second = module.render_markdown(evidence, "out/platform/wsl2_ubuntu.json")
    assert first == second


def test_solver_and_platform_state_vocabularies_are_not_booleans() -> None:
    module = _module()
    assert module.SUPPORT_STATES == {
        "UNTESTED",
        "CORE_TESTED",
        "CORE_CERTIFIED",
        "SOLVER_PARTIAL",
        "SOLVER_CERTIFIED",
        "UNSUPPORTED",
    }
    assert module.SOLVER_STAGES == {
        "NOT_INSTALLED",
        "FOUND",
        "PROBE_PASS",
        "EXECUTION_PASS",
        "OUTPUT_PARSED",
        "CONVERGENCE_PROVEN",
    }


def test_probe_only_status_cannot_be_promoted_to_execution() -> None:
    module = _module()
    assert module.simulation_stage({"simulation_status": "SKIPPED_SOLVER_ABSENT"}) == ("PROBE_PASS")
    assert module.simulation_stage({"simulation_status": "SIMULATION_EXECUTED"}) == (
        "EXECUTION_PASS"
    )
    assert module.simulation_stage({"simulation_status": "OUTPUT_PARSED"}) == ("OUTPUT_PARSED")
    assert module.simulation_stage({"simulation_status": "NUMERICALLY_CONVERGED"}) == (
        "CONVERGENCE_PROVEN"
    )
