from __future__ import annotations

from pathlib import Path
from typing import Any

from textlayout._legacy.backends.base import Backend, BackendAvailability, python_module_available, value_record
from textlayout._legacy.epr import write_epr_analysis


class PyEPRBackend(Backend):
    name = "pyepr"
    role = "energy participation ratio extraction backend"
    source_url = "https://github.com/zlatko-minev/pyEPR"

    def available(self) -> BackendAvailability:
        if python_module_available("pyEPR"):
            return BackendAvailability(True, "Python module pyEPR is importable")
        return BackendAvailability(False, "pyEPR is not installed")

    def extract(self, request: dict[str, Any], *, output_dir: str | Path) -> dict[str, Any]:
        sidecar = request.get("sidecar")
        if not isinstance(sidecar, dict):
            return self._status(
                "FAILED",
                operation="extract",
                reason="pyEPR requires sidecar metadata and solved field exports",
                output_dir=output_dir,
                extra={"request": request},
            )
        out = Path(output_dir)
        result = write_epr_analysis(
            sidecar,
            report_path=out / "pyepr_report.json",
            script_path=out / "pyepr_analysis.py",
            field_energy_path=request.get("field_energy_path"),
            hfss_project_path=request.get("hfss_project_path"),
            hfss_project_name=str(request.get("hfss_project_name", "text_to_gds_device")),
            hfss_design_name=str(request.get("hfss_design_name", "Eigenmode")),
        )
        status = (
            "EXECUTED"
            if result.get("status") == "executed_from_exported_field_energies"
            else "PREPARED"
        )
        values = {}
        metrics = result.get("metrics") or {}
        if metrics.get("predicted_T1_us") is not None:
            values["predicted_t1"] = value_record(
                value=metrics["predicted_T1_us"],
                unit="us",
                source="pyEPR",
                method="participation-ratio Hamiltonian reduction from field energies",
                confidence=0.85 if status == "EXECUTED" else 0.0,
                artifact=result.get("report_path"),
            )
        return self._status(
            status,  # type: ignore[arg-type]
            operation="extract",
            reason=result.get("validity") or "pyEPR workflow prepared",
            output_dir=out,
            artifacts={"script": str(result.get("script_path")), "report": str(result.get("report_path"))},
            values=values,
            extra={"raw_result": result},
        )
