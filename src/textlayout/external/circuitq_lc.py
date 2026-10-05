"""Isolated ideal one-mode CircuitQ circuit adapter; no EM field extraction."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.contract import EvidenceStatus, QuantityEvidence
from textlayout.external._circuitq_lc_worker import assess


class LCRequest(BaseModel):
    """Specified ideal capacitance in F and inductance in H; no geometry extraction."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    capacitance_f: float = Field(ge=8e-14, le=1.2e-13)
    inductance_h: float = Field(ge=6e-8, le=8e-8)


def benchmark_plan(request: LCRequest) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "scope": "two ideal parallel LC circuits; no nonlinear circuit, EM or measurement claim",
        "dimensions": [401, 801, 1601],
        "half_domain_sigma": 8,
        "expanded_dimension": 2001,
        "expanded_half_domain_sigma": 10,
        "frequency_relative_limit": 2e-05,
        "refinement_relative_limit": 2e-05,
        "anharmonicity_over_frequency_limit": 2e-05,
        "domain_relative_limit": 1e-07,
        "scaled_residual_limit": 1e-10,
        "hermiticity_relative_limit": 1e-13,
        "rationale": "Exact ideal LC spacing and zero anharmonicity are analytical references. Gaussian flux sigma=sqrt(hbar*sqrt(L/C)/2); 8-sigma and 10-sigma half-domains suppress tails, compared at equal grid spacing. Second-order finite-difference grid sequence halves spacing. Numerical budget 20 ppm for frequency/refinement/anharmonicity and 0.1 ppm for domain effect; these are computational resolution requirements, not experimental uncertainty. No thresholds change after execution.",
        "reference_h_j_s": 6.62607015e-34,
        "source_revision": "b45978891ac2c25ad7a44973c3cbe836c770e0aa",
    }
    plan["cases"] = [request.model_dump()]
    return plan


class LCResult(BaseModel):
    execution_completed: bool = False
    return_code: int | None = None
    status: EvidenceStatus = EvidenceStatus.FAILED
    numerical_checks_passed: bool = False
    failure_reason: str | None = None
    output_dir: str
    metrics: dict[str, Any] | None = None
    quantities: list[QuantityEvidence] = Field(default_factory=list)


def run_lc(
    request: LCRequest, *, python: Path, output_dir: Path, timeout_seconds: float = 120
) -> LCResult:
    """Retain execution separately from numerical acceptance and measurement claims."""
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    input_path, output_path = output_dir / "request.json", output_dir / "solver.json"
    plan = benchmark_plan(request)
    input_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    worker = Path(__file__).with_name("_circuitq_lc_worker.py")
    command = [str(python.expanduser().absolute()), str(worker), str(input_path), str(output_path)]
    result = LCResult(output_dir=str(output_dir))
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
            raise ValueError("External CircuitQ failed; inspect stderr.txt")
        report = json.loads(output_path.read_text(encoding="utf-8"))
        if (
            report["version"] != "1.2.1"
            or report["request_sha256"] != hashlib.sha256(input_path.read_bytes()).hexdigest()
            or len(report["cases"]) != 1
            or report["cases"][0]["inputs"] != request.model_dump()
        ):
            raise ValueError("Solver version/request identity mismatch")
        case = report["cases"][0]
        reference = 1 / (2 * math.pi * math.sqrt(request.capacitance_f * request.inductance_h))
        result.metrics, result.numerical_checks_passed = assess(case["rows"], plan, reference)
        if not result.numerical_checks_passed:
            result.status = EvidenceStatus.CONVERGENCE_FAILED
            result.failure_reason = (
                "Circuit refinement/reference gates rejected output; retain raw data"
            )
        else:
            result.status = EvidenceStatus.SIMULATION_EXECUTED
            for name in ("frequency_hz", "anharmonicity_hz"):
                result.quantities.append(
                    QuantityEvidence(
                        quantity=name.removesuffix("_hz"),
                        status=result.status,
                        extracted_value=case["rows"][-2][name],
                        extracted_unit="Hz",
                        solver="CircuitQ 1.2.1 natural-unit ideal LC circuit",
                        command=json.dumps(command),
                        input_files=[str(input_path)],
                        output_files=[str(output_path)],
                        parser="textlayout.external.circuitq_lc.run_lc",
                        notes=[
                            "Specified ideal circuit; no EM extraction or measurement validation",
                            "Exact ideal LC reference; numerical discretization, not measured hardware",
                        ],
                    )
                )
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        result.failure_reason = "External CircuitQ timed out; no checkpoint/resume support"
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
        "scope": "ideal parallel LC circuit; no nonlinear/noise, EM or measurement claim",
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
