"""Adapter boundary tests; replayed fixtures are not new solver evidence."""

import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from textlayout.evidence.contract import EvidenceStatus
from textlayout.external.pyepr_circuit import CircuitRequest, benchmark_plan, run_circuit

ROOT = Path(__file__).resolve().parents[2]
REQUEST = CircuitRequest(ej_over_h_hz=30e9, ec_over_h_hz=150e6)


@pytest.mark.parametrize(
    "values",
    [
        dict(ej_over_h_hz=20e9, ec_over_h_hz=300e6),
        dict(ej_over_h_hz=float("nan"), ec_over_h_hz=150e6),
        dict(ej_over_h_hz="30000000000", ec_over_h_hz=150e6),
        dict(ej_over_h_hz=30e9, ec_over_h_hz=150e6, tolerance=100),
    ],
)
def test_invalid_inputs(values: dict) -> None:
    with pytest.raises(ValidationError):
        CircuitRequest(**values)


def test_preserve_predeclared_plan() -> None:
    original = json.loads((ROOT / "references/pyepr/charge-insensitive-plan.json").read_text())
    plan = benchmark_plan(REQUEST)
    for key in (
        "fock_truncations",
        "charge_cutoffs",
        "charge_offsets",
        "max_last_refinement_hz",
        "max_charge_offset_spread_hz",
        "max_reference_difference_hz",
    ):
        assert plan[key] == original[key]


@pytest.mark.parametrize("defect", [None, "version", "identity", "convergence", "nan"])
def test_retained_output_and_canonical_status(tmp_path: Path, defect: str | None) -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        report = json.loads(
            (
                ROOT / "docs/progress/evidence/2026-10-04-131811/gate-final-first/report.json"
            ).read_text()
        )
        report["cases"] = report["cases"][:1]
        report["version"] = "wrong" if defect == "version" else "1.0.2"
        report["request_sha256"] = hashlib.sha256(Path(command[2]).read_bytes()).hexdigest()
        if defect == "identity":
            report["request_sha256"] = "wrong"
        if defect == "convergence":
            report["cases"][0]["fock"][-2]["f01_hz"] += 100
        if defect == "nan":
            report["cases"][0]["fock"][-1]["f01_hz"] = float("nan")
        Path(command[3]).write_text(json.dumps(report))
        return subprocess.CompletedProcess(command, 0, "fixture replay", "")

    with patch("textlayout.external.pyepr_circuit.subprocess.run", side_effect=run):
        result = run_circuit(REQUEST, python=Path("external-python"), output_dir=tmp_path / "run")
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
        run_circuit(REQUEST, python=Path("external-python"), output_dir=tmp_path / "run")


def test_timeout_retains_partial_logs(tmp_path: Path) -> None:
    error = subprocess.TimeoutExpired(["python"], 1, output=b"partial", stderr=b"diagnostic")
    with patch("textlayout.external.pyepr_circuit.subprocess.run", side_effect=error):
        result = run_circuit(REQUEST, python=Path("python"), output_dir=tmp_path / "run")
    assert result.status == EvidenceStatus.FAILED
    assert not result.execution_completed
    assert (tmp_path / "run/stdout.txt").read_bytes() == b"partial"
    assert not result.quantities
