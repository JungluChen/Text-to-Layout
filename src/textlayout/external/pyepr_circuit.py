"""Isolated ideal one-mode pyEPR circuit adapter; no EM field extraction."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from textlayout.evidence.contract import EvidenceStatus, QuantityEvidence
from textlayout.external._pyepr_numeric import assess


class CircuitRequest(BaseModel):
    """Specified circuit energies in Hz, not quantities extracted from geometry."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    ej_over_h_hz: float = Field(gt=0)
    ec_over_h_hz: float = Field(ge=100e6, le=200e6)

    @model_validator(mode="after")
    def domain(self) -> Self:
        if not 200 <= self.ej_over_h_hz / self.ec_over_h_hz <= 250:
            raise ValueError("Scoped charge-insensitive domain requires 200 <= EJ/EC <= 250")
        return self


def benchmark_plan(request: CircuitRequest) -> dict[str, Any]:
    return {
        "cases": [request.model_dump()],
        "fock_truncations": [16, 24, 32, 40],
        "charge_cutoffs": [25, 35, 45],
        "charge_offsets": [0, 0.25, 0.5],
        "max_last_refinement_hz": 1.0,
        "max_charge_offset_spread_hz": 1.0,
        "max_reference_difference_hz": 2.0,
        "potential": "full cosine",
    }


class CircuitResult(BaseModel):
    execution_completed: bool = False
    return_code: int | None = None
    status: EvidenceStatus = EvidenceStatus.FAILED
    numerical_checks_passed: bool = False
    failure_reason: str | None = None
    output_dir: str
    metrics: dict[str, Any] | None = None
    quantities: list[QuantityEvidence] = Field(default_factory=list)


def run_circuit(
    request: CircuitRequest, *, python: Path, output_dir: Path, timeout_seconds: float = 120
) -> CircuitResult:
    """Retain execution separately from numerical acceptance and measurement claims."""
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    input_path, output_path = output_dir / "request.json", output_dir / "solver.json"
    plan = benchmark_plan(request)
    input_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    worker = Path(__file__).with_name("_pyepr_numeric.py")
    command = [str(python.expanduser().absolute()), str(worker), str(input_path), str(output_path)]
    result = CircuitResult(output_dir=str(output_dir))
    stdout: str | bytes = ""
    stderr: str | bytes = ""
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        stdout, stderr = process.stdout, process.stderr
        result.execution_completed, result.return_code = True, process.returncode
        if process.returncode != 0:
            raise ValueError("External pyEPR failed; inspect stderr.txt")
        report = json.loads(output_path.read_text(encoding="utf-8"))
        if (
            report["version"] != "1.0.2"
            or report["request_sha256"] != hashlib.sha256(input_path.read_bytes()).hexdigest()
            or len(report["cases"]) != 1
            or report["cases"][0]["inputs"] != request.model_dump()
        ):
            raise ValueError("Solver version/request identity mismatch")
        case = report["cases"][0]
        result.metrics, result.numerical_checks_passed = assess(case, plan)
        if not result.numerical_checks_passed:
            result.status = EvidenceStatus.CONVERGENCE_FAILED
            result.failure_reason = (
                "Circuit refinement/reference gates rejected output; retain raw data"
            )
        else:
            result.status = EvidenceStatus.SIMULATION_EXECUTED
            for name in ("f01_hz", "alpha_hz"):
                result.quantities.append(
                    QuantityEvidence(
                        quantity=name.removesuffix("_hz"),
                        status=result.status,
                        extracted_value=case["fock"][-1][name],
                        extracted_unit="Hz",
                        solver="pyEPR-quantum 1.0.2 full-cosine ideal circuit",
                        command=json.dumps(command),
                        input_files=[str(input_path)],
                        output_files=[str(output_path)],
                        parser="textlayout.external.pyepr_circuit.run_circuit",
                        notes=[
                            "Specified ideal circuit; no EM extraction or measurement validation",
                            "Charge-offset references computed independently; not published measurements",
                        ],
                    )
                )
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        result.failure_reason = "External pyEPR timed out; no checkpoint/resume support"
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, IndexError) as exc:
        result.failure_reason = f"{type(exc).__name__}: {exc}"
        result.numerical_checks_passed = False
        result.status = (
            EvidenceStatus.SIMULATION_INVALID if result.return_code == 0 else EvidenceStatus.FAILED
        )
        result.quantities = []
    for name, content in [("stdout.txt", stdout), ("stderr.txt", stderr)]:
        (output_dir / name).write_bytes(
            content.encode("utf-8") if isinstance(content, str) else content
        )
    manifest = {
        "request_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
        "command": command,
        "scope": "ideal single-mode full-cosine circuit; no EM/HFSS, measurement or fabrication claim",
        "result": result.model_dump(mode="json"),
        "artifact_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output_dir.iterdir()
            if p.is_file()
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return result
