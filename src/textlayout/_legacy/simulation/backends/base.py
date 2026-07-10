"""Common prepare/run/parse/report backend lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BackendRun:
    backend: str
    status: str
    reason: str
    prepared_files: tuple[str, ...] = ()
    result_files: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "text-to-gds.simulation-backend-run.v1",
            "backend": self.backend,
            "status": self.status,
            "reason": self.reason,
            "prepared_files": list(self.prepared_files),
            "result_files": list(self.result_files),
            "metrics": self.metrics,
        }


class BackendLifecycle:
    name = "backend"

    def prepare(self, request: dict[str, Any], output_dir: str | Path) -> BackendRun:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        manifest = out / f"{self.name}.input.json"
        import json

        manifest.write_text(json.dumps(request, indent=2), encoding="utf-8")
        return BackendRun(
            backend=self.name,
            status="input_files_prepared",
            reason="INPUT PREPARED - no numerical result yet",
            prepared_files=(str(manifest),),
        )

    def run(self, prepared: BackendRun) -> BackendRun:
        return BackendRun(
            backend=self.name,
            status="skipped",
            reason="SKIPPED - solver not executed",
            prepared_files=tuple(prepared.prepared_files),
        )

    def parse(self, run: BackendRun) -> BackendRun:
        if run.status != "executed":
            return run
        return run

    def report(self, run: BackendRun) -> dict[str, Any]:
        return run.to_dict()
