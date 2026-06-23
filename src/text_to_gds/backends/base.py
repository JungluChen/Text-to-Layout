from __future__ import annotations

import importlib.util
import json
import shutil
from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

BackendStatus = Literal["EXECUTED", "PREPARED", "SKIPPED", "FAILED", "UNSUPPORTED"]


def python_module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def executable_available(executable: str) -> bool:
    return shutil.which(executable) is not None


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def value_record(
    *,
    value: Any,
    unit: str,
    source: str,
    method: str,
    confidence: float,
    artifact: str | Path | None = None,
) -> dict[str, Any]:
    """Create the required provenance wrapper for a report value."""
    return {
        "value": value,
        "unit": unit,
        "source": source,
        "method": method,
        "confidence": max(0.0, min(1.0, float(confidence))),
        "artifact": str(artifact) if artifact is not None else None,
    }


def validate_value_records(values: dict[str, Any]) -> list[str]:
    """Return missing-provenance errors for report values."""
    required = {"value", "unit", "source", "method", "confidence"}
    errors: list[str] = []
    for key, record in values.items():
        if not isinstance(record, dict):
            errors.append(f"{key}: value record must be an object")
            continue
        missing = sorted(required - set(record))
        if missing:
            errors.append(f"{key}: missing {', '.join(missing)}")
        if record.get("source") in {None, "", "LLM", "llm", "guess"}:
            errors.append(f"{key}: source must not be an LLM guess")
    return errors


@dataclass(frozen=True)
class BackendAvailability:
    available: bool
    reason: str
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "reason": self.reason,
            "version": self.version,
        }


class Backend(ABC):
    """Universal orchestration adapter for professional EDA/simulation backends."""

    name: str
    role: str
    source_url: str

    def available(self) -> BackendAvailability:
        raise NotImplementedError

    def generate(self, request: dict[str, Any], *, output_dir: str | Path) -> dict[str, Any]:
        return self._unsupported("generate", output_dir=output_dir)

    def simulate(self, request: dict[str, Any], *, output_dir: str | Path) -> dict[str, Any]:
        return self._unsupported("simulate", output_dir=output_dir)

    def extract(self, request: dict[str, Any], *, output_dir: str | Path) -> dict[str, Any]:
        return self._unsupported("extract", output_dir=output_dir)

    def _status(
        self,
        status: BackendStatus,
        *,
        operation: str,
        reason: str,
        output_dir: str | Path,
        artifacts: dict[str, str] | None = None,
        values: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": "text-to-gds.backend-result.v1",
            "backend": self.name,
            "role": self.role,
            "operation": operation,
            "status": status,
            "reason": reason,
            "source_url": self.source_url,
            "availability": self.available().to_dict(),
            "artifacts": artifacts or {},
            "values": values or {},
        }
        provenance_errors = validate_value_records(payload["values"])
        if provenance_errors:
            payload["status"] = "FAILED"
            payload["reason"] = "invalid value provenance"
            payload["provenance_errors"] = provenance_errors
        if extra:
            payload.update(extra)
        report_path = Path(output_dir) / f"{self.name}_{operation}.json"
        write_json(report_path, payload)
        payload["report_path"] = str(report_path)
        return payload

    def _unsupported(self, operation: str, *, output_dir: str | Path) -> dict[str, Any]:
        return self._status(
            "UNSUPPORTED",
            operation=operation,
            reason=f"{self.name} does not implement {operation}",
            output_dir=output_dir,
        )
