from __future__ import annotations

from pathlib import Path
from typing import Any

from text_to_gds.automatic_mesh import generate_solver_inputs_from_graph
from text_to_gds.simulation.backends.base import BackendLifecycle, BackendRun


class OpenEMSBackend(BackendLifecycle):
    name = "openems"

    def prepare(self, request: dict[str, Any], output_dir: str | Path) -> BackendRun:
        graph_path = request.get("physics_graph_path")
        if graph_path:
            files = generate_solver_inputs_from_graph(graph_path, output_dir=output_dir)["openems"]
            return BackendRun(
                backend=self.name,
                status="input_files_prepared",
                reason="INPUT PREPARED - no numerical result yet",
                prepared_files=tuple(str(path) for path in files.values()),
            )
        return super().prepare(request, output_dir)
