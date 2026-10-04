"""Contract tests with explicit process doubles; real exports live in evidence."""

import hashlib
import json
import subprocess
from pathlib import Path

import klayout.db as kdb
import pytest
from pydantic import ValidationError

from textlayout.external.quantum_metal_mask import TransmonMaskRequest, generate_transmon_mask

PARAMS = dict(
    pad_width_um=455,
    pad_height_um=90,
    pad_gap_um=30,
    pocket_width_um=650,
    pocket_height_um=650,
    chip_width_um=2000,
    chip_height_um=2000,
)


@pytest.mark.parametrize(
    "change",
    [
        {"pad_width_um": True},
        {"pad_width_um": "455"},
        {"pad_gap_um": float("nan")},
        {"pad_height_um": 0},
        {"chip_width_um": 100002},
        {"pad_gap_um": 0.001},
        {"pocket_width_um": 455},
        {"pocket_height_um": 210},
        {"chip_width_um": 650},
        {"ground_plane": False},
    ],
)
def test_invalid_geometry_is_rejected(change):
    with pytest.raises(ValidationError):
        TransmonMaskRequest.model_validate(PARAMS | change)


def test_missing_runtime_is_not_execution(tmp_path):
    result = generate_transmon_mask(
        TransmonMaskRequest(**PARAMS), python=tmp_path / "missing", output_dir=tmp_path / "out"
    )
    assert not result.execution_completed and not result.geometry_verified
    assert not result.junction_verified and result.failure_reason
    assert (tmp_path / "out/manifest.json").is_file()


def test_preserve_existing_packet(tmp_path):
    with pytest.raises(FileExistsError):
        generate_transmon_mask(
            TransmonMaskRequest(**PARAMS), python=Path("unused"), output_dir=tmp_path
        )


def test_timeout_retains_partial_logs(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1, output=b"partial", stderr=b"warning")

    monkeypatch.setattr(subprocess, "run", timeout)
    result = generate_transmon_mask(
        TransmonMaskRequest(**PARAMS),
        python=Path("unused"),
        output_dir=tmp_path / "out",
        timeout_seconds=1,
    )
    assert not result.execution_completed and not result.geometry_verified
    assert (tmp_path / "out/stdout.txt").read_bytes() == b"partial"


@pytest.mark.parametrize("tamper", ["empty_gds", "wrong_request", "wrong_hash"])
def test_export_success_is_insufficient(tmp_path, monkeypatch, tamper):
    def process(command, **kwargs):
        out = Path(command[-1])
        out.mkdir()
        gds = out / "transmon.gds"
        kdb.Layout().write(str(gds))
        request = TransmonMaskRequest(**PARAMS).model_dump()
        if tamper == "wrong_request":
            request["pad_gap_um"] = 32
        report = {
            "request": request,
            "gds_sha256": hashlib.sha256(gds.read_bytes()).hexdigest(),
            "versions": {"quantum-metal": "0.9.0", "gdstk": "1.0.1"},
            "export_return_code": 1,
        }
        if tamper == "wrong_hash":
            report["gds_sha256"] = "0" * 64
        (out / "export.json").write_text(json.dumps(report))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", process)
    result = generate_transmon_mask(
        TransmonMaskRequest(**PARAMS), python=Path("unused"), output_dir=tmp_path / "out"
    )
    assert result.execution_completed and result.return_code == 0
    assert not result.geometry_verified and not result.junction_verified
    assert result.failure_reason
