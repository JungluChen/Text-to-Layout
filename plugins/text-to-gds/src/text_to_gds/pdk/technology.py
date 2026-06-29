"""Technology adapters tying the PDK package to existing process YAMLs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from text_to_gds.pdk import PDKDatabase, SuperconductingPDK
from text_to_gds.pdk.process import DEFAULT_MANHATTAN_PROCESS, ManhattanProcess


@dataclass(frozen=True)
class QuantumTechnology:
    process: ManhattanProcess
    source_pdk: SuperconductingPDK | None = None
    reference_repositories: tuple[str, ...] = (
        "KQCircuits",
        "qiskit-metal",
        "gdsfactory",
        "klayout",
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "text-to-gds.quantum-technology.v1",
            "process": self.process.to_dict(),
            "source_pdk": self.source_pdk.to_dict() if self.source_pdk else None,
            "reference_repositories": list(self.reference_repositories),
        }


def load_quantum_technology(process_root: str | Path, process_id: str = "ncu_alox_2026") -> QuantumTechnology:
    """Load a versioned YAML PDK and adapt it to the framework process model."""
    pdk = PDKDatabase(process_root).get(process_id)
    process = ManhattanProcess(
        bottom_layer="M1",
        top_layer="M2",
        jj_min_area=pdk.constraints.min_junction_width_um * pdk.constraints.min_junction_height_um,
        jj_max_area=10.0,
        alignment_error=pdk.constraints.overlay_tolerance_um,
    )
    return QuantumTechnology(process=process, source_pdk=pdk)


DEFAULT_TECHNOLOGY = QuantumTechnology(process=DEFAULT_MANHATTAN_PROCESS)
