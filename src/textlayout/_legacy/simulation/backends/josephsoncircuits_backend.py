from __future__ import annotations

from textlayout._legacy.simulation.backends.base import BackendLifecycle, BackendRun


class JosephsonCircuitsBackend(BackendLifecycle):
    name = "josephsoncircuits"

    def run(self, prepared: BackendRun) -> BackendRun:
        return BackendRun(
            backend=self.name,
            status="skipped",
            reason="SKIPPED - JosephsonCircuits.jl netlist execution not requested by lifecycle wrapper",
            prepared_files=prepared.prepared_files,
        )
