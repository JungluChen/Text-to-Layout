from __future__ import annotations

from pathlib import Path
from typing import Any

from text_to_gds.backends.base import Backend, BackendAvailability, python_module_available, value_record
from text_to_gds.scqubits_adapter import run_scqubits_transmon


class ScqubitsBackend(Backend):
    name = "scqubits"
    role = "qubit Hamiltonian simulation backend"
    source_url = "https://github.com/scqubits/scqubits"

    def available(self) -> BackendAvailability:
        if python_module_available("scqubits"):
            return BackendAvailability(True, "Python module scqubits is importable")
        return BackendAvailability(False, "scqubits is not installed")

    def simulate(self, request: dict[str, Any], *, output_dir: str | Path) -> dict[str, Any]:
        extraction_path = request.get("extraction_path")
        if not extraction_path:
            return self._status(
                "FAILED",
                operation="simulate",
                reason="scqubits requires extraction_path with extracted Ic and capacitance",
                output_dir=output_dir,
                extra={"request": request},
            )
        out = Path(output_dir)
        result = run_scqubits_transmon(
            extraction_path,
            report_path=out / "scqubits_report.json",
            plot_path=out / "scqubits_spectrum.png" if request.get("plot", True) else None,
            n_evals=int(request.get("n_evals", 6)),
            ncut=int(request.get("ncut", 30)),
            ng=float(request.get("ng", 0.0)),
        )
        status = "EXECUTED" if result.get("status") == "executed" else result.get("status", "failed").upper()
        values = {}
        for key, unit in {
            "f01_ghz": "GHz",
            "f12_ghz": "GHz",
            "anharmonicity_mhz": "MHz",
            "ej_ghz": "GHz",
            "ec_ghz": "GHz",
        }.items():
            if result.get(key) is not None:
                values[key] = value_record(
                    value=result[key],
                    unit=unit,
                    source="scqubits",
                    method="scqubits.Transmon from extracted Ic and C",
                    confidence=0.9 if status == "EXECUTED" else 0.0,
                    artifact=result.get("report_path"),
                )
        return self._status(
            status,  # type: ignore[arg-type]
            operation="simulate",
            reason=result.get("reason") or result.get("model_validity") or "scqubits completed",
            output_dir=out,
            artifacts={
                "report": str(result.get("report_path")),
                "plot": str(result.get("plot_path")),
            },
            values=values,
            extra={"raw_result": result},
        )
