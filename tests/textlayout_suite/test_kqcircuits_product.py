"""Contract tests; process doubles are not numerical evidence."""

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from textlayout.cli import build_parser
from textlayout.external.kqcircuits_bridge import StraightCPWRequest, generate_straight_cpw


@pytest.mark.parametrize(
    "change",
    [
        {"gap_um": 0},
        {"length_um": float("nan")},
        {"width_um": float("inf")},
        {"length_um": 0.0005},
        {"width_um": 1.001},
        {"gap_um": True},
        {"width_um": "10"},
        {"solver": "invented"},
    ],
)
def test_reject_invalid_parameters(change):
    with pytest.raises(ValidationError):
        StraightCPWRequest.model_validate(
            dict(length_um=1000.0, width_um=10.0, gap_um=6.0) | change
        )


def test_missing_runtime_is_retained_failure(tmp_path):
    result = generate_straight_cpw(
        StraightCPWRequest(length_um=1000, width_um=10, gap_um=6),
        python=tmp_path / "missing-python",
        output_dir=tmp_path / "out",
    )
    assert not result.execution_completed and not result.geometry_verified
    assert result.return_code is None
    assert "FileNotFoundError" in result.failure_reason
    assert (tmp_path / "out/manifest.json").is_file()


def test_preserves_existing_run(tmp_path):
    with pytest.raises(FileExistsError):
        generate_straight_cpw(
            StraightCPWRequest(length_um=1000, width_um=10, gap_um=6),
            python=Path("unused"),
            output_dir=tmp_path,
        )


def test_timeout_retains_partial_logs(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            args[0], 1, output=b"partial output", stderr=b"partial error"
        )

    monkeypatch.setattr(subprocess, "run", timeout)
    result = generate_straight_cpw(
        StraightCPWRequest(length_um=1000, width_um=10, gap_um=6),
        python=Path("unused"),
        output_dir=tmp_path / "out",
        timeout_seconds=1,
    )
    assert not result.geometry_verified and "timed out" in result.failure_reason
    assert (tmp_path / "out/stdout.txt").read_bytes() == b"partial output"
    assert (tmp_path / "out/stderr.txt").read_bytes() == b"partial error"


def test_process_exit_alone_does_not_verify_geometry(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "", "")
    )
    result = generate_straight_cpw(
        StraightCPWRequest(length_um=1000, width_um=10, gap_um=6),
        python=Path("unused"),
        output_dir=tmp_path / "out",
    )
    assert result.execution_completed and result.return_code == 0
    assert not result.geometry_verified and result.failure_reason


def test_cli_exposes_explicit_external_runtime():
    args = build_parser().parse_args(
        ["kqcircuits-cpw", "input.json", "--python", "/external/python", "--out", "run"]
    )
    assert args.python == "/external/python"
