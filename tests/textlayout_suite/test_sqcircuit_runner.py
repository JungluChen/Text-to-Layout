"""Simulated process failures and retained-real-packet boundary tests."""

import json
import subprocess
from pathlib import Path

import pytest

from textlayout.evidence.contract import EvidenceStatus
from textlayout.external.sqcircuit_lc import SQcircuitLCRequest
from textlayout.external.sqcircuit_runner import run_sqcircuit_lc

REQUEST = SQcircuitLCRequest(capacitance_f=1e-13, inductance_h=1e-7, branch_capacitance_f=1e-20)
RAW = Path(__file__).resolve().parents[2] / (
    "docs/progress/evidence/2026-10-11-154025/sqc-worker-first.json"
)


@pytest.mark.parametrize("fault", ["absent", "timeout", "exit", "missing_output"])
def test_process_failure_retains_no_quantities(tmp_path: Path, monkeypatch, fault: str) -> None:
    def fake(command, **kwargs):
        if fault == "absent":
            raise FileNotFoundError("missing interpreter")
        if fault == "timeout":
            raise subprocess.TimeoutExpired(command, 1, output=b"partial", stderr=b"diagnostic")
        return subprocess.CompletedProcess(command, 3 if fault == "exit" else 0, "", "failed")

    monkeypatch.setattr("textlayout.external.sqcircuit_runner.subprocess.run", fake)
    out = tmp_path / "job"
    result = run_sqcircuit_lc(REQUEST, python=Path("fake-python"), output_dir=out)
    assert not result.quantities
    assert result.status == {
        "absent": EvidenceStatus.SKIPPED_SOLVER_ABSENT,
        "timeout": EvidenceStatus.FAILED,
        "exit": EvidenceStatus.FAILED,
        "missing_output": EvidenceStatus.SIMULATION_INVALID,
    }[fault]
    assert (out / "manifest.json").is_file()
    if fault == "timeout":
        assert (out / "stdout.txt").read_bytes() == b"partial"
        assert (out / "stderr.txt").read_bytes() == b"diagnostic"


@pytest.mark.parametrize("fault", ["none", "source", "input", "numerical", "malformed"])
def test_packet_assessment_boundary(tmp_path: Path, monkeypatch, fault: str) -> None:
    def fake(command, **kwargs):
        report = json.loads(RAW.read_text())
        if fault == "source":
            report["source_sha256"]["circuit.py"] = "0" * 64
        elif fault == "input":
            report["request_sha256"] = "0" * 64
        elif fault == "numerical":
            report["rows"][0]["eigenvalues_rad_s"][1] += 10000
        elif fault == "malformed":
            report["rows"][0]["eigenvectors_imag"] = 0
        Path(command[-1]).write_text(json.dumps(report))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("textlayout.external.sqcircuit_runner.subprocess.run", fake)
    result = run_sqcircuit_lc(REQUEST, python=Path("fake-python"), output_dir=tmp_path / "job")
    if fault == "none":
        assert result.status == EvidenceStatus.SIMULATION_EXECUTED
        assert len(result.quantities) == 1
        assert result.quantities[0].extracted_unit == "Hz"
    else:
        assert not result.quantities
        assert result.status == (
            EvidenceStatus.CONVERGENCE_FAILED if fault == "numerical"
            else EvidenceStatus.SIMULATION_INVALID
        )


def test_invalid_timeout_creates_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        run_sqcircuit_lc(REQUEST, python=Path("absent"), output_dir=tmp_path / "job",
                        timeout_seconds=float("nan"))
    assert not (tmp_path / "job").exists()
