from __future__ import annotations

from pathlib import Path
from typing import Any

from textlayout._legacy.backends.base import Backend, BackendAvailability, executable_available, value_record
from textlayout._legacy.palace_bridge import write_palace_project


class PalaceBackend(Backend):
    name = "palace"
    role = "open-source eigenmode FEM backend"
    source_url = "https://github.com/awslabs/palace"

    def available(self) -> BackendAvailability:
        if executable_available("palace"):
            return BackendAvailability(True, "palace executable is on PATH")
        return BackendAvailability(False, "palace executable is not on PATH")

    def simulate(self, request: dict[str, Any], *, output_dir: str | Path) -> dict[str, Any]:
        gds_path = request.get("gds_path")
        if not gds_path:
            return self._status(
                "FAILED",
                operation="simulate",
                reason="Palace requires gds_path",
                output_dir=output_dir,
                extra={"request": request},
            )
        out = Path(output_dir)
        result = write_palace_project(
            gds_path,
            config_path=out / "palace.json",
            report_path=out / "palace_report.json",
            mesh_path=out / "palace_mesh.msh",
            mesh_report_path=out / "palace_mesh_report.json",
            sidecar_path=request.get("sidecar_path"),
            process_path=request.get("process_path"),
            problem_type=str(request.get("problem_type", "Eigenmode")),
            target_frequency_ghz=float(request.get("target_frequency_ghz", 6.0)),
            num_modes=int(request.get("num_modes", 4)),
            run=bool(request.get("run", False)),
        )
        raw_status = result.get("status")
        status = "EXECUTED" if raw_status == "executed" else raw_status.upper()
        values = {}
        modes = result.get("modes") or result.get("eigenmodes") or []
        if modes:
            values["mode_frequency_ghz"] = value_record(
                value=[mode.get("frequency_ghz") for mode in modes],
                unit="GHz",
                source="Palace",
                method="FEM eigenmode solve",
                confidence=0.9 if status == "EXECUTED" else 0.0,
                artifact=result.get("report_path"),
            )
        return self._status(
            status,  # type: ignore[arg-type]
            operation="simulate",
            reason=result.get("reason") or result.get("model_validity") or "Palace project prepared",
            output_dir=out,
            artifacts={
                "config": str(result.get("config_path")),
                "mesh": str(result.get("mesh", {}).get("path")),
                "report": str(result.get("report_path")),
            },
            values=values,
            extra={"raw_result": result},
        )
