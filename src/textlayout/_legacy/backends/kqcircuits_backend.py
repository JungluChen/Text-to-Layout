from __future__ import annotations

from pathlib import Path
from typing import Any

from textlayout._legacy.backends.base import Backend, BackendAvailability, python_module_available, write_json


class KQCircuitsBackend(Backend):
    name = "kqcircuits"
    role = "primary superconducting layout backend"
    source_url = "https://github.com/iqm-finland/KQCircuits"

    _SUPPORTED = {
        "cpw",
        "cpw_feedline",
        "cpw_resonator",
        "cpw_quarter_wave_resonator",
        "resonator",
        "waveguide",
        "airbridge",
        "junction",
        "manhattan_jj",
        "transmon",
        "qubit",
    }

    def available(self) -> BackendAvailability:
        if python_module_available("kqcircuits"):
            return BackendAvailability(True, "Python module kqcircuits is importable")
        return BackendAvailability(
            False,
            "KQCircuits is not installed or not on PYTHONPATH; install IQM KQCircuits/KLayout stack",
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
                reason=f"KQCircuits backend does not map requested components: {unsupported}",
                output_dir=out,
                extra={"request": request},
            )

        plan = {
            "schema": "text-to-gds.kqcircuits-plan.v1",
            "backend": self.name,
            "device": request.get("device"),
            "components": request.get("components", []),
            "parameters": request.get("parameters", {}),
            "notes": [
                "This file is an adapter plan, not geometry.",
                "A real KQCircuits/KLayout export implementation must instantiate KQCircuits elements.",
            ],
        }
        plan_path = out / "kqcircuits_plan.json"
        write_json(plan_path, plan)

        if not self.available().available:
            return self._status(
                "SKIPPED",
                operation="generate",
                reason="KQCircuits runtime unavailable; wrote parameter plan only",
                output_dir=out,
                artifacts={"plan": str(plan_path)},
                extra={"request": request},
            )

        return self._status(
            "UNSUPPORTED",
            operation="generate",
            reason=(
                "KQCircuits is importable, but this adapter has no verified element-to-GDS "
                "export path for the requested SuperCAD sequence yet"
            ),
            output_dir=out,
            artifacts={"plan": str(plan_path)},
            extra={"request": request},
        )
