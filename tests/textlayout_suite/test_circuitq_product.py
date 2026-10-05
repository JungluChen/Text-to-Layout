"""Adapter boundary tests; replayed fixtures are not new solver evidence."""

import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from textlayout.evidence.contract import EvidenceStatus
from textlayout.external.circuitq_lc import LCRequest, benchmark_plan, run_lc

ROOT = Path(__file__).resolve().parents[2]
REQUEST = LCRequest(capacitance_f=8e-14, inductance_h=8e-8)


@pytest.mark.parametrize(
    "values",
    [
        dict(capacitance_f=-1, inductance_h=0),
        dict(capacitance_f=float("nan"), inductance_h=8e-8),
        dict(capacitance_f="30000000000", inductance_h=8e-8),
        dict(capacitance_f=8e-14, inductance_h=8e-8, tolerance=100),
    ],
)
def test_invalid_inputs(values: dict) -> None:
    with pytest.raises(ValidationError):
        LCRequest(**values)


def test_preserve_predeclared_plan() -> None:
    original = json.loads((ROOT / "references/circuitq/lc-plan.json").read_text())
    plan = benchmark_plan(REQUEST)
    assert plan == {**original, "cases": [REQUEST.model_dump()]}


@pytest.mark.parametrize("defect", [None, "version", "identity", "convergence", "nan"])
def test_retained_output_and_canonical_status(tmp_path: Path, defect: str | None) -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        report = json.loads(
            (
                ROOT / "docs/progress/evidence/2026-10-05-101038/circuitq-gate-first/report.json"
            ).read_text()
        )
        report["cases"] = report["cases"][:1]
        report["version"] = "wrong" if defect == "version" else "1.2.1"
        report["request_sha256"] = hashlib.sha256(Path(command[2]).read_bytes()).hexdigest()
        if defect == "identity":
            report["request_sha256"] = "wrong"
        if defect == "convergence":
            report["cases"][0]["rows"][-2]["scaled_residual"] = 1e-7
        if defect == "nan":
            report["cases"][0]["rows"][-2]["frequency_hz"] = float("nan")
        Path(command[3]).write_text(json.dumps(report))
        return subprocess.CompletedProcess(command, 0, "fixture replay", "")

    with patch("textlayout.external.circuitq_lc.subprocess.run", side_effect=run):
        result = run_lc(REQUEST, python=Path("external-python"), output_dir=tmp_path / "run")
    assert result.execution_completed
    assert result.numerical_checks_passed == (defect is None)
    if defect is None:
        assert result.status == EvidenceStatus.SIMULATION_EXECUTED
        assert len(result.quantities) == 2
        assert all(q.extracted_unit == "Hz" for q in result.quantities)
    else:
        assert result.quantities == []
        assert result.status in (
            EvidenceStatus.SIMULATION_INVALID,
            EvidenceStatus.CONVERGENCE_FAILED,
        )
    manifest = json.loads((tmp_path / "run/manifest.json").read_text())
    for name, digest in manifest["artifact_sha256"].items():
        assert hashlib.sha256((tmp_path / "run" / name).read_bytes()).hexdigest() == digest
    with pytest.raises(FileExistsError):
        run_lc(REQUEST, python=Path("external-python"), output_dir=tmp_path / "run")


def test_timeout_retains_partial_logs(tmp_path: Path) -> None:
    error = subprocess.TimeoutExpired(["python"], 1, output=b"partial", stderr=b"diagnostic")
    with patch("textlayout.external.circuitq_lc.subprocess.run", side_effect=error):
        result = run_lc(REQUEST, python=Path("python"), output_dir=tmp_path / "run")
    assert result.status == EvidenceStatus.FAILED
    assert not result.execution_completed
    assert (tmp_path / "run/stdout.txt").read_bytes() == b"partial"
    assert not result.quantities
