"""Digital Twin module for complete quantum device engineering knowledge.

Every design gets a twin that stores:
  Geometry → Physics → Simulation → Measurement → History → Packaging →
  Fabrication → Current Version → Expected Yield → Frequency Drift →
  Expected Failure Modes

The twin is the authoritative record for a design across all iterations.
"""

from text_to_gds.digital_twin.twin import DigitalTwinEngine
from text_to_gds.digital_twin.types import (
    DesignIteration,
    DigitalTwin,
    FabricationMetadata,
    GeometrySnapshot,
    MeasurementRecord,
    PhysicsState,
    ReliabilityPrediction,
    SimulationRun,
)

__all__ = [
    "DigitalTwinEngine",
    "DigitalTwin",
    "GeometrySnapshot",
    "PhysicsState",
    "SimulationRun",
    "MeasurementRecord",
    "DesignIteration",
    "FabricationMetadata",
    "ReliabilityPrediction",
]
