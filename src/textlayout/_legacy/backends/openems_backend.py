from __future__ import annotations

from pathlib import Path
from typing import Any

from textlayout._legacy.backends.base import Backend, BackendAvailability, executable_available
from textlayout._legacy.openems_runner import run_openems


class OpenEMSBackend(Backend):
    name = "openems"
    role = "open-source RF S-parameter and microwave EM backend"
    source_url = "https://github.com/thliebig/openEMS"

    def available(self) -> BackendAvailability:
        from textlayout._legacy.tool_discovery import tool_paths
        openems = tool_paths().openems
        if openems:
            return BackendAvailability(True, f"openEMS found at {openems}")
        if executable_available("openEMS"):
            return BackendAvailability(True, "openEMS executable is on PATH")
        return BackendAvailability(False, "openEMS not found in .tools/ or on PATH")

    def simulate(self, request: dict[str, Any], *, output_dir: str | Path) -> dict[str, Any]:
        extraction_path = request.get("extraction_path")
        if not extraction_path:
            return self._status(
                "FAILED",
                operation="simulate",
                reason="openEMS requires extraction_path",
                output_dir=output_dir,
                extra={"request": request},
            )
        out = Path(output_dir)
        result = run_openems(
            extraction_path,
            sim_dir=out / "openems",
            report_path=out / "openems_report.json",
            openems_executable=str(request.get("openems_executable", "openEMS")),
            bandwidth_ghz=float(request.get("bandwidth_ghz", 2.0)),
        )
        status = "EXECUTED" if result.get("status") == "executed" else result.get("status", "failed").upper()
        return self._status(
            status,  # type: ignore[arg-type]
            operation="simulate",
            reason=result.get("reason") or result.get("model_validity") or "openEMS completed",
            output_dir=out,
            artifacts={
                "xml": str(result.get("xml_path")),
                "touchstone": str(result.get("touchstone_path")),
                "report": str(result.get("report_path")),
            },
            extra={"raw_result": result},
        )
