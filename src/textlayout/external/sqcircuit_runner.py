"""Isolated typed SQcircuit LC execution with canonical, bounded evidence."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from textlayout.evidence.contract import EvidenceStatus, QuantityEvidence
from textlayout.external.sqcircuit_assessment import SQcircuitLCAssessment, assess_sqcircuit_lc
from textlayout.external.sqcircuit_lc import (
    SQcircuitLCPlan,
    SQcircuitLCRequest,
    prepare_sqcircuit_lc,
)

SOURCE_SHA256 = {
    "circuit.py": "81e03763c9aef465e6c42072fee3a54cf40dd908e29995e9aa24acd2a3fae9ed",
    "elements.py": "392533e65df7169348031f2784ffae383e848acb2928070e82f22b53350d557c",
    "units.py": "9945d9649a390c7817d0ef62238e0e1ce442a50e3a283e8917d8049ebffa7009",
}


class SQcircuitLCResult(BaseModel):
    status: EvidenceStatus = EvidenceStatus.FAILED
    return_code: int | None = None
    execution_completed: bool = False
    failure_reason: str | None = None
    output_dir: str
    assessment: SQcircuitLCAssessment | None = None
    quantities: list[QuantityEvidence] = Field(default_factory=list)


def run_sqcircuit_lc(
    request: SQcircuitLCRequest, *, python: Path, output_dir: Path,
    timeout_seconds: float = 120,
) -> SQcircuitLCResult:
    """Run one bounded ideal LC diagnostic, retaining rejected/partial evidence.

    Fresh directory required. Missing interpreter is skipped; import/process
    failures fail; malformed/identity-mismatched output is invalid. Only passing
    raw assessment produces a SIMULATION_EXECUTED frequency, never validation.
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    prepared = prepare_sqcircuit_lc(request, output_dir=output_dir)
    input_path = Path(prepared.input_path)
    directory = input_path.parent
    output_path = directory / "raw.json"
    worker = Path(__file__).with_name("_sqcircuit_lc_worker.py")
    command = [str(python.expanduser().absolute()), str(worker), str(input_path), str(output_path)]
    result = SQcircuitLCResult(output_dir=str(directory))
    stdout: str | bytes = ""
    stderr: str | bytes = ""
    try:
        process = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout_seconds, check=False,
        )
        stdout, stderr = process.stdout, process.stderr
        result.execution_completed = True
        result.return_code = process.returncode
        if process.returncode != 0:
            raise RuntimeError("SQcircuit worker failed; inspect stderr.txt")
        report = json.loads(output_path.read_text(encoding="utf-8"))
        plan = SQcircuitLCPlan.model_validate_json(input_path.read_text(encoding="utf-8"))
        if (
            hashlib.sha256(input_path.read_bytes()).hexdigest() != prepared.input_sha256
            or report["request_sha256"] != prepared.input_sha256
            or report["schema_name"] != "textlayout.sqcircuit-lc-raw.v1"
            or report["inputs"] != request.model_dump()
            or report["method"] != plan.method
            or report["source_sha256"] != SOURCE_SHA256
            or report["versions"]["SQcircuit"] != plan.sqcircuit_version
            or report["numerical_acceptance"] != "NOT_EVALUATED"
        ):
            raise ValueError("SQcircuit packet identity mismatch")
        for key in ("python_version", "python_executable", "platform"):
            if not isinstance(report[key], str) or not report[key]:
                raise ValueError("Missing runtime provenance")
        for key in ("numpy", "scipy", "qutip", "torch", "sympy"):
            if not isinstance(report["versions"][key], str) or not report["versions"][key]:
                raise ValueError("Missing numerical dependency version")
        result.assessment = assess_sqcircuit_lc(plan, report["rows"])
        if not result.assessment.numerical_checks_passed:
            result.status = EvidenceStatus.CONVERGENCE_FAILED
            result.failure_reason = "Fixed LC numerical checks rejected raw output"
        else:
            values = report["rows"][-1]["eigenvalues_rad_s"]
            frequency = (values[1] - values[0]) / (2 * math.pi)
            quantity = QuantityEvidence(
                quantity="frequency", status=EvidenceStatus.SIMULATION_EXECUTED,
                extracted_value=frequency, extracted_unit="Hz",
                solver="SQcircuit 1.0.0 Hamiltonian + NumPy dense eigh",
                command=json.dumps(command), input_files=[str(input_path)],
                output_files=[str(output_path)],
                parser="textlayout.external.sqcircuit_runner.run_sqcircuit_lc",
                notes=[
                    "Specified ideal parallel LC with explicit additional branch capacitance",
                    "Exact LC reference; no EM extraction, nonlinear or measurement validation",
                    "Harmonic-basis truncation check is not spatial convergence",
                ],
            )
            result.status = EvidenceStatus.SIMULATION_EXECUTED
            result.quantities = [quantity]
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        result.failure_reason = "SQcircuit worker timed out; partial logs retained; no resume"
    except FileNotFoundError as exc:
        result.status = (
            EvidenceStatus.SKIPPED_SOLVER_ABSENT if result.return_code is None
            else EvidenceStatus.SIMULATION_INVALID
        )
        result.failure_reason = f"Missing interpreter or output: {exc}"
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, IndexError) as exc:
        result.status = (
            EvidenceStatus.SIMULATION_INVALID if result.return_code == 0 else EvidenceStatus.FAILED
        )
        result.failure_reason = f"{type(exc).__name__}: {exc}"
        result.quantities = []
    for name, content in (("stdout.txt", stdout), ("stderr.txt", stderr)):
        (directory / name).write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
    (directory / "result.json").write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    manifest = {
        "command": command, "request_sha256": prepared.input_sha256,
        "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
        "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in directory.iterdir() if p.is_file()},
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return result
