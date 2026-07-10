from __future__ import annotations

from pathlib import Path
from typing import Any

from textlayout._legacy.backends.base import Backend, BackendAvailability, executable_available, value_record
from textlayout._legacy.elmer_bridge import write_elmer_project


class ElmerBackend(Backend):
    name = "elmer"
    role = "open-source electrostatic capacitance extraction backend"
    source_url = "https://github.com/ElmerCSC/elmerfem"

    def available(self) -> BackendAvailability:
        for executable in ("ElmerSolver", "ElmerSolver_mpi", "elmersolver"):
            if executable_available(executable):
                return BackendAvailability(True, f"{executable} executable is on PATH")
        return BackendAvailability(False, "ElmerSolver executable is not on PATH")

    def extract(self, request: dict[str, Any], *, output_dir: str | Path) -> dict[str, Any]:
        gds_path = request.get("gds_path")
        if not gds_path:
            return self._status(
                "FAILED",
                operation="extract",
                reason="Elmer requires gds_path",
                output_dir=output_dir,
                extra={"request": request},
            )
        out = Path(output_dir)
        result = write_elmer_project(
            gds_path,
            sif_path=out / "case.sif",
            report_path=out / "elmer_report.json",
            mesh_path=out / "elmer_mesh.msh",
            mesh_report_path=out / "elmer_mesh_report.json",
            sidecar_path=request.get("sidecar_path"),
            process_path=request.get("process_path"),
            run=bool(request.get("run", False)),
        )
        raw_status = result.get("status")
        status = "EXECUTED" if raw_status == "executed" else raw_status.upper()
        values = {}
        if result.get("capacitance_matrix_pf") is not None:
            values["capacitance_matrix"] = value_record(
                value=result["capacitance_matrix_pf"],
                unit="pF",
                source="Elmer FEM",
                method="StatElecSolver capacitance matrix",
                confidence=0.9 if status == "EXECUTED" else 0.0,
                artifact=result.get("report_path"),
            )
        return self._status(
            status,  # type: ignore[arg-type]
            operation="extract",
            reason=result.get("reason") or result.get("model_validity") or "Elmer project prepared",
            output_dir=out,
            artifacts={
                "sif": str(result.get("sif_path")),
                "mesh": str(result.get("mesh", {}).get("path")),
                "report": str(result.get("report_path")),
            },
            values=values,
            extra={"raw_result": result},
        )
