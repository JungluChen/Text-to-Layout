"""Phase-1 gates: required imports and the ``textlayout doctor`` command."""

from __future__ import annotations

import json
from pathlib import Path

from textlayout.cli import main
from textlayout.doctor import run_doctor


def test_required_layout_dependencies_import() -> None:
    import klayout.db as kdb
    import gdsfactory as gf
    import langgraph

    assert kdb is not None and gf is not None and langgraph is not None


def test_doctor_reports_required_checks_ok(tmp_path: Path) -> None:
    report = run_doctor(output_dir=tmp_path / "probe")
    assert report.ok, [c.to_dict() for c in report.checks if c.status == "fail"]
    names = {check.name for check in report.checks}
    assert "Python version" in names
    assert "LangGraph import" in names
    assert "KLayout Python API import" in names
    assert "FasterCap/FastCap executable discovery" in names
    assert "output directory write permission" in names


def test_doctor_missing_fastercap_is_absent_not_failure(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TEXTLAYOUT_FASTERCAP", "definitely-not-a-real-solver")
    report = run_doctor(output_dir=tmp_path / "probe")
    fastercap = next(
        c for c in report.checks if c.name == "FasterCap/FastCap executable discovery"
    )
    assert fastercap.status == "absent"
    assert fastercap.required is False
    assert "skipped" in fastercap.detail.lower()
    assert report.ok  # optional solver absence never fails the environment


def test_doctor_cli_json_output(tmp_path: Path, capsys) -> None:
    code = main(["doctor", "--out", str(tmp_path / "probe"), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "textlayout.doctor.v1"
    assert code in (0, 1)
    assert any(check["name"] == "LangGraph import" for check in payload["checks"])
