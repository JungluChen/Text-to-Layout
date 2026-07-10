"""KQCircuits process-isolated bridge policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KQCircuitsBridgePolicy:
    """Policy record for the GPL KQCircuits integration boundary."""

    integration_mode: str = "process-isolated GDS/JSON/runset/result file exchange"
    copies_source_into_core: bool = False
    physics_verified_by_presence: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "textlayout.kqcircuits-bridge-policy.v1",
            "integration_mode": self.integration_mode,
            "copies_source_into_core": self.copies_source_into_core,
            "physics_verified_by_presence": self.physics_verified_by_presence,
        }
