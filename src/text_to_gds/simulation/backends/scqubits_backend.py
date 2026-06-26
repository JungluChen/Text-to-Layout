from __future__ import annotations

from text_to_gds.simulation.backends.base import BackendLifecycle, BackendRun


class ScqubitsBackend(BackendLifecycle):
    name = "scqubits"

    def run(self, prepared: BackendRun) -> BackendRun:
        try:
            import scqubits  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            return BackendRun(
                backend=self.name,
                status="skipped",
                reason=f"SKIPPED - scqubits unavailable: {exc}",
                prepared_files=prepared.prepared_files,
            )
        return BackendRun(
            backend=self.name,
            status="skipped",
            reason="SKIPPED - use transmon synthesis or server export_hamiltonian_model with traceable EJ/EC",
            prepared_files=prepared.prepared_files,
        )
