"""Timeout evidence retention; synthetic output is not numerical validation."""

import subprocess
from pathlib import Path

import pytest

from textlayout.solvers import base, josephsoncircuits


@pytest.mark.parametrize("output", [b"partial\xff\xe2", "partial text", None])
def test_timeout_preserves_output_and_exception(tmp_path, monkeypatch, output):
    failure = subprocess.TimeoutExpired(["solver"], 1, output=output, stderr=b"warning\n")

    def timeout(*args, **kwargs):
        raise failure

    monkeypatch.setattr(base.subprocess, "run", timeout)
    # A new empty timeout must overwrite logs left by an earlier invocation.
    (tmp_path / "solver.stdout.txt").write_bytes(b"stale previous result")
    with pytest.raises(subprocess.TimeoutExpired) as raised:
        base.run_subprocess(["solver"], cwd=tmp_path, timeout_seconds=1)
    assert raised.value is failure
    expected = output.encode("utf-8") if isinstance(output, str) else output or b""
    assert (tmp_path / "solver.stdout.txt").read_bytes() == expected
    assert (tmp_path / "solver.stderr.txt").read_bytes() == b"warning\n"


def test_josephson_timeout_exposes_logs_without_promoting_evidence(tmp_path, monkeypatch):
    prepared = josephsoncircuits.prepare_jpa_netlist(
        {
            "schema": "textlayout.josephsoncircuits-netlist.v1",
            "capacitances_f": [1e-12],
            "inductances_h": [1e-9],
            "junctions": [{"critical_current_a": 1e-6}],
        },
        tmp_path,
    )

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(["julia"], 1, output=b"partial", stderr=b"warning")

    monkeypatch.setattr(josephsoncircuits, "discover_julia", lambda explicit: "/fake/julia")
    monkeypatch.setattr(base.subprocess, "run", timeout)
    result = josephsoncircuits.execute_josephsoncircuits(prepared, timeout_seconds=1)
    assert result.status == "failed"
    assert result.physics_verified is False
    assert result.return_code is None
    assert Path(result.artifacts["solver_stdout"]).read_bytes() == b"partial"
    assert Path(result.artifacts["solver_stderr"]).read_bytes() == b"warning"
