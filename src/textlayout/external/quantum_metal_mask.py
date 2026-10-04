"""Typed, isolated Quantum Metal positive-mask operation; no junction or physics."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TransmonMaskRequest(BaseModel):
    """Centred, unrotated charge pads and pocket on an explicit positive ground plane."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    pad_width_um: float = Field(gt=0, le=10000)
    pad_height_um: float = Field(gt=0, le=10000)
    pad_gap_um: float = Field(gt=0, le=10000)
    pocket_width_um: float = Field(gt=0, le=50000)
    pocket_height_um: float = Field(gt=0, le=50000)
    chip_width_um: float = Field(gt=0, le=100000)
    chip_height_um: float = Field(gt=0, le=100000)

    @field_validator("*")
    @classmethod
    def require_grid(cls, value: float) -> float:
        if not math.isclose(value / 0.002, round(value / 0.002), rel_tol=0, abs_tol=1e-6):
            raise ValueError("Dimensions must be on a 0.002 um grid for centred edges")
        return value

    @model_validator(mode="after")
    def require_clearance(self) -> Self:
        if not (
            self.chip_width_um > self.pocket_width_um > self.pad_width_um
            and self.chip_height_um
            > self.pocket_height_um
            > 2 * self.pad_height_um + self.pad_gap_um
        ):
            raise ValueError(
                "Chip must strictly contain pocket; pocket must strictly contain both pads"
            )
        return self


class TransmonMaskResult(BaseModel):
    execution_completed: bool = False
    return_code: int | None = None
    geometry_verified: bool = False
    junction_verified: bool = False
    failure_reason: str | None = None
    output_dir: str
    readback: dict[str, Any] | None = None


def generate_transmon_mask(
    request: TransmonMaskRequest, *, python: Path, output_dir: Path, timeout_seconds: float = 120
) -> TransmonMaskResult:
    """Export in an explicit external interpreter and independently read with KLayout."""
    from textlayout.external.quantum_metal_readback import check_mask

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    input_path = output_dir / "request.json"
    input_path.write_text(request.model_dump_json(indent=2) + "\n", encoding="utf-8")
    worker = Path(__file__).with_name("_quantum_metal_worker.py")
    command = [
        str(python.expanduser().absolute()),
        str(worker),
        str(input_path),
        str(output_dir / "geometry"),
    ]
    result = TransmonMaskResult(output_dir=str(output_dir))
    stdout: str | bytes = ""
    stderr: str | bytes = ""
    try:
        p = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        stdout, stderr = p.stdout, p.stderr
        result.execution_completed, result.return_code = True, p.returncode
        if p.returncode != 0:
            raise ValueError("External exporter failed; inspect stderr.txt")
        metadata = json.loads((output_dir / "geometry/export.json").read_text(encoding="utf-8"))
        gds = output_dir / "geometry/transmon.gds"
        if (
            metadata["request"] != request.model_dump()
            or metadata["gds_sha256"] != hashlib.sha256(gds.read_bytes()).hexdigest()
        ):
            raise ValueError("Exporter request or GDS identity mismatch")
        if (
            metadata["versions"] != {"quantum-metal": "0.9.0", "gdstk": "1.0.1"}
            or metadata["export_return_code"] != 1
        ):
            raise ValueError("Exporter version or return code mismatch")
        result.readback = check_mask(gds, request)
        result.geometry_verified = result.readback["geometry_verified"] is True
        if not result.geometry_verified:
            result.failure_reason = str(
                result.readback.get("failure_reason", "Independent geometry check failed")
            )
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        result.failure_reason = "External exporter timed out"
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        result.failure_reason = f"{type(exc).__name__}: {exc}"
    for name, content in [("stdout.txt", stdout), ("stderr.txt", stderr)]:
        (output_dir / name).write_bytes(
            content.encode("utf-8") if isinstance(content, str) else content
        )
    manifest = {
        "request_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
        "command": command,
        "scope": "charge-pad and ground-pocket masks only; no fabrication junction or EM simulation",
        "result": result.model_dump(mode="json"),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return result
