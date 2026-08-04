"""Phase-1 gates: required imports and the ``textlayout doctor`` command."""

from __future__ import annotations

import json
from pathlib import Path

from textlayout.cli import main
from textlayout.doctor import run_doctor


def test_required_layout_dependencies_import() -> None:
    import klayout.db as kdb
    import gdsfactory as gf
    import langgraph.graph as langgraph

    assert kdb is not None and gf is not None and langgraph is not None


def test_doctor_reports_required_checks_ok(tmp_path: Path) -> None:
    report = run_doctor(output_dir=tmp_path / "probe")
    assert report.ok, [c.to_dict() for c in report.checks if c.status != "FOUND"]
    names = {check.name for check in report.checks}
    assert "Python" in names
    assert "langgraph.graph" in names
    assert "klayout.db" in names
    assert "FasterCap/FastCap" in names
    assert "openEMS" in names
    assert "CSXCAD" in names
    assert "FastHenry/FastHenry2" in names
    assert "output directory write permission" in names


def test_doctor_missing_fastercap_is_absent_not_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TEXTLAYOUT_FASTERCAP", "definitely-not-a-real-solver")
    report = run_doctor(output_dir=tmp_path / "probe")
    fastercap = next(c for c in report.checks if c.name == "FasterCap/FastCap")
    assert fastercap.status == "MISSING"
    assert fastercap.required is False
    assert "skipped" in fastercap.detail.lower()
    assert report.ok  # optional solver absence never fails the environment


def test_doctor_strict_mode_fails_when_fastercap_is_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TEXTLAYOUT_FASTERCAP", "definitely-not-a-real-solver")
    report = run_doctor(output_dir=tmp_path / "probe", strict=True)
    fastercap = next(c for c in report.checks if c.name == "FasterCap/FastCap")
    assert fastercap.status == "MISSING"
    assert fastercap.required is True
    assert report.ok is False


def test_doctor_does_not_treat_an_unprobeable_binary_as_working(
    tmp_path: Path, monkeypatch
) -> None:
    fake = tmp_path / "FasterCap.py"
    fake.write_text("# exists but emits no version banner\n", encoding="utf-8")
    monkeypatch.setenv("TEXTLAYOUT_FASTERCAP", str(fake))

    report = run_doctor(output_dir=tmp_path / "probe")
    fastercap = next(c for c in report.checks if c.name == "FasterCap/FastCap")

    assert fastercap.status == "BROKEN"
    assert fastercap.path == str(fake)
    assert fastercap.smoke_test == "failed: version probe"
    assert report.physics_capabilities["IDC electrostatics"] == "INCOMPLETE"


def test_doctor_cli_json_output(tmp_path: Path, capsys) -> None:
    code = main(["doctor", "--out", str(tmp_path / "probe"), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "textlayout.doctor.v2"
    assert code in (0, 1)
    assert any(check["name"] == "langgraph.graph" for check in payload["checks"])


def test_doctor_v2_reports_system_solver_and_physics_capability_fields(tmp_path: Path) -> None:
    payload = run_doctor(output_dir=tmp_path / "probe").to_dict()

    assert {"os", "architecture", "python", "package_commit", "filesystem"} <= set(
        payload["system"]
    )
    assert len(payload["system"]["package_commit"]) == 40

    allowed = {
        "FOUND",
        "MISSING",
        "BROKEN",
        "WRONG_VERSION",
        "CONTAINER_AVAILABLE",
        "NOT_SUPPORTED_ON_PLATFORM",
        "NOT_TESTED_ON_PLATFORM",
    }
    assert {check["status"] for check in payload["checks"]} <= allowed
    solver = next(check for check in payload["checks"] if check["name"] == "Palace")
    assert {"path", "version", "backend_type", "capabilities", "smoke_test"} <= set(solver)

    capabilities = payload["physics_capabilities"]
    assert {
        "IDC electrostatics",
        "CPW FDTD",
        "Spiral PEEC",
        "Eigenmode FEM",
        "Josephson transient",
        "Josephson harmonic balance",
    } <= set(capabilities)
    assert set(capabilities.values()) <= {
        "PROBE_PASS_ONLY",
        "NOT_INSTALLED",
        "INCOMPLETE",
    }


def test_doctor_json_separates_probe_from_execution_and_certification(tmp_path: Path) -> None:
    payload = run_doctor(output_dir=tmp_path / "probe").to_dict()

    assert {
        "host",
        "runtime",
        "wsl",
        "core_dependencies",
        "external_solvers",
        "capabilities",
    } <= set(payload)
    assert payload["runtime"]["support_state"] == "CORE_TESTED"
    assert payload["capabilities"]["Layout generation"]["state"] == "READY"

    for solver in payload["external_solvers"].values():
        assert solver["evidence_stage"] in {"NOT_INSTALLED", "FOUND", "PROBE_PASS"}
        assert solver["evidence_stage"] not in {
            "EXECUTION_PASS",
            "OUTPUT_PARSED",
            "CONVERGENCE_PROVEN",
        }
        assert solver["support_state"] != "SOLVER_CERTIFIED"


def test_platform_and_solver_state_vocabularies_are_explicit() -> None:
    from textlayout.platform_support import (
        SOLVER_EVIDENCE_STAGE_VALUES,
        SUPPORT_STATE_VALUES,
    )

    assert SUPPORT_STATE_VALUES == {
        "UNTESTED",
        "CORE_TESTED",
        "CORE_CERTIFIED",
        "SOLVER_PARTIAL",
        "SOLVER_CERTIFIED",
        "UNSUPPORTED",
    }
    assert SOLVER_EVIDENCE_STAGE_VALUES == {
        "NOT_INSTALLED",
        "FOUND",
        "PROBE_PASS",
        "EXECUTION_PASS",
        "OUTPUT_PARSED",
        "CONVERGENCE_PROVEN",
    }
