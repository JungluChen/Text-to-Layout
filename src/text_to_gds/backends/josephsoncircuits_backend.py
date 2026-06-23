from __future__ import annotations

from pathlib import Path
from typing import Any

from text_to_gds.backends.base import Backend, BackendAvailability, executable_available, value_record
from text_to_gds.josephsoncircuits_adapter import run_josephsoncircuits


class JosephsonCircuitsBackend(Backend):
    name = "josephsoncircuits"
    role = "Josephson nonlinear circuit simulation backend"
    source_url = "https://github.com/kpobrien/JosephsonCircuits.jl"

    def available(self) -> BackendAvailability:
        from text_to_gds.tool_discovery import tool_paths
        julia = tool_paths().julia
        if julia:
            return BackendAvailability(True, f"Julia found at {julia}")
        if executable_available("julia"):
            return BackendAvailability(True, "Julia executable is on PATH")
        return BackendAvailability(False, "Julia not found in .tools/ or on PATH")

    def simulate(self, request: dict[str, Any], *, output_dir: str | Path) -> dict[str, Any]:
        extraction_path = request.get("extraction_path")
        if not extraction_path:
            return self._status(
                "FAILED",
                operation="simulate",
                reason="JosephsonCircuits.jl requires extraction_path with Lj, Ic, and capacitance",
                output_dir=output_dir,
                extra={"request": request},
            )
        out = Path(output_dir)
        mode = str(request.get("mode", "jpa"))
        result = run_josephsoncircuits(
            extraction_path,
            script_path=out / "josephsoncircuits.jl",
            result_path=out / "josephsoncircuits_result.json",
            report_path=out / "josephsoncircuits_report.json",
            plot_path=out / "josephsoncircuits.png" if request.get("plot", True) else None,
            mode=mode,
            pump_frequency_ghz=request.get("pump_frequency_ghz"),
            n_pump_points=int(request.get("n_pump_points", 12)),
            julia_executable=request.get("julia_executable"),
        )
        status = "EXECUTED" if result.get("status") == "executed" else result.get("status", "failed").upper()
        values = {}
        if mode == "jpa" and result.get("best_peak_gain_db") is not None:
            values["peak_gain_db"] = value_record(
                value=result["best_peak_gain_db"],
                unit="dB",
                source="JosephsonCircuits.jl",
                method="harmonic-balance pump sweep",
                confidence=0.9,
                artifact=result.get("result_path"),
            )
        return self._status(
            status,  # type: ignore[arg-type]
            operation="simulate",
            reason=result.get("reason") or result.get("model_validity") or "JosephsonCircuits completed",
            output_dir=out,
            artifacts={
                "script": str(result.get("script_path")),
                "result": str(result.get("result_path")),
                "report": str(result.get("report_path")),
                "plot": str(result.get("plot_path")),
            },
            values=values,
            extra={"raw_result": result},
        )
