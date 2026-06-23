from __future__ import annotations

from pathlib import Path
from typing import Any

from text_to_gds.backends.base import Backend, BackendAvailability, python_module_available, write_json


class QiskitMetalBackend(Backend):
    name = "qiskit_metal"
    role = "secondary quantum CAD backend"
    source_url = "https://github.com/Qiskit/qiskit-metal"

    _SUPPORTED = {
        "transmon",
        "transmon_pocket",
        "transmon_cross",
        "resonator",
        "coupler",
        "cpw",
        "cpw_route",
        "launchpad",
        "launch_pad",
    }

    def available(self) -> BackendAvailability:
        if python_module_available("qiskit_metal"):
            return BackendAvailability(True, "Python module qiskit_metal is importable")
        return BackendAvailability(
            False,
            "qiskit_metal is not installed; install in a compatible Python environment",
        )

    def generate(self, request: dict[str, Any], *, output_dir: str | Path) -> dict[str, Any]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        device = str(request.get("device") or "").lower()
        components = [str(c).lower() for c in request.get("components", [])]
        requested = {device, *components} - {""}
        unsupported = sorted(name for name in requested if name not in self._SUPPORTED)
        if unsupported:
            return self._status(
                "UNSUPPORTED",
                operation="generate",
                reason=f"Qiskit Metal backend does not map requested components: {unsupported}",
                output_dir=out,
                extra={"request": request},
            )

        plan = {
            "schema": "text-to-gds.qiskit-metal-plan.v1",
            "backend": self.name,
            "device": request.get("device"),
            "components": request.get("components", []),
            "parameters": request.get("parameters", {}),
            "component_policy": "Instantiate Qiskit Metal QComponents; do not hand-draw rectangles.",
        }
        plan_path = out / "qiskit_metal_plan.json"
        write_json(plan_path, plan)

        if not self.available().available:
            return self._status(
                "SKIPPED",
                operation="generate",
                reason="Qiskit Metal runtime unavailable; wrote QComponent parameter plan only",
                output_dir=out,
                artifacts={"plan": str(plan_path)},
                extra={"request": request},
            )

        return self._status(
            "UNSUPPORTED",
            operation="generate",
            reason=(
                "Qiskit Metal is importable, but this adapter has no verified QDesign-to-GDS "
                "export path for the requested SuperCAD sequence yet"
            ),
            output_dir=out,
            artifacts={"plan": str(plan_path)},
            extra={"request": request},
        )
