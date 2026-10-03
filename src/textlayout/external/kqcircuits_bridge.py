"""KQCircuits process-isolated bridge policy."""

from __future__ import annotations

from dataclasses import dataclass


# Product validation happens before crossing the process/file boundary.
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


@dataclass(frozen=True, slots=True)
class KQCircuitsBridgePolicy:
    """Policy record for the GPL KQCircuits integration boundary."""

    integration_mode: str = "process-isolated GDS/JSON/runset/result file exchange"
    copies_source_into_core: bool = False
    physics_verified_by_presence: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "textlayout.kqcircuits-bridge-policy.v1",
            "integration_mode": self.integration_mode,
            "copies_source_into_core": self.copies_source_into_core,
            "physics_verified_by_presence": self.physics_verified_by_presence,
        }


class StraightCPWRequest(BaseModel):
    """Supported scope: straight gap masks, micrometres, fixed 1 nm grid."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    length_um: float = Field(gt=0, le=100000)
    width_um: float = Field(gt=0, le=10000)
    gap_um: float = Field(gt=0, le=10000)

    @field_validator("length_um", "width_um", "gap_um")
    @classmethod
    def require_grid(cls, value: float, info: Any) -> float:
        step = 0.002 if info.field_name == "width_um" else 0.001
        if not math.isclose(value / step, round(value / step), rel_tol=0, abs_tol=1e-6):
            raise ValueError(f"{info.field_name} must lie on the {step} um grid")
        return value


class KQCircuitsGeometryResult(BaseModel):
    """Geometry result only: no simulation or physical validation status."""

    execution_completed: bool = False
    geometry_verified: bool = False
    return_code: int | None = None
    failure_reason: str | None = None
    output_dir: str
    report: dict[str, Any] | None = None


def generate_straight_cpw(
    request: StraightCPWRequest,
    *,
    python: Path,
    output_dir: Path,
    timeout_seconds: float = 120,
) -> KQCircuitsGeometryResult:
    """Execute a pinned external interpreter, retain logs, verify returned hashes.

    Never installs dependencies or overwrites an existing run. This API does not
    import KQCircuits into the core or claim electrical properties.
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    input_path = output_dir / "request.json"
    input_path.write_text(request.model_dump_json(indent=2) + "\n", encoding="utf-8")
    worker = Path(__file__).with_name("_kqcircuits_worker.py")
    command = [
        str(python.expanduser().absolute()),
        str(worker),
        "--request",
        str(input_path),
        "--out",
        str(output_dir / "geometry"),
    ]
    result = KQCircuitsGeometryResult(output_dir=str(output_dir))
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
        result.return_code = process.returncode
        result.execution_completed = True
        if process.returncode != 0:
            result.failure_reason = "External geometry process failed; inspect stderr.txt"
        else:
            report_path = output_dir / "geometry" / "report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            cases = report["cases"]
            if len(cases) != 1:
                raise ValueError("Expected exactly one generated case")
            case = cases[0]
            if any(case[key] != value for key, value in request.model_dump().items()):
                raise ValueError("Returned geometry belongs to different parameters")
            gds = output_dir / "geometry" / "case-0.gds"
            if (
                case["gds_file"] != gds.name
                or hashlib.sha256(gds.read_bytes()).hexdigest() != case["gds_sha256"]
            ):
                raise ValueError("GDS output identity mismatch")
            if report.get("passed") is not True or case.get("geometry_check_passed") is not True:
                raise ValueError("Geometry acceptance did not pass")
            result.report = report
            result.geometry_verified = True
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        result.failure_reason = "External geometry process timed out"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.failure_reason = f"{type(exc).__name__}: {exc}"
    for name, data in [("stdout.txt", stdout), ("stderr.txt", stderr)]:
        (output_dir / name).write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
    manifest = {
        "command": command,
        "request_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
        "scope": "straight CPW mask geometry; no EM simulation",
        "result": result.model_dump(mode="json"),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return result
