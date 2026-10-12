"""CLI failure paths exercise the actual typed boundary without optional imports."""
import json
from pathlib import Path

import pytest

from textlayout.cli import main


def test_missing_interpreter_reports_skip_as_nonzero(tmp_path: Path, capsys) -> None:
    request = tmp_path / "input.json"
    request.write_text(json.dumps({"capacitance_f": 1e-13, "inductance_h": 1e-7,
                                   "branch_capacitance_f": 1e-20}))
    args = ["sqcircuit-lc", str(request), "--python", str(tmp_path / "absent"),
            "--out", str(tmp_path / "job")]
    assert main(args) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "SKIPPED_SOLVER_ABSENT"
    assert report["quantities"] == []
    original = (tmp_path / "job/request.json").read_bytes()
    assert main(args) == 1
    assert json.loads(capsys.readouterr().err)["error"] == "FileExistsError"
    assert (tmp_path / "job/request.json").read_bytes() == original


@pytest.mark.parametrize("fault", ["missing_branch", "nan_timeout"])
def test_invalid_request_never_creates_run(tmp_path: Path, capsys, fault: str) -> None:
    payload = {"capacitance_f": 1e-13, "inductance_h": 1e-7}
    if fault == "nan_timeout":
        payload["branch_capacitance_f"] = 1e-20
    request = tmp_path / "input.json"
    request.write_text(json.dumps(payload))
    args = ["sqcircuit-lc", str(request), "--python", "absent", "--out", str(tmp_path / "job")]
    if fault == "nan_timeout":
        args += ["--timeout", "nan"]
    assert main(args) == 1
    assert "error" in json.loads(capsys.readouterr().err)
    assert not (tmp_path / "job").exists()
