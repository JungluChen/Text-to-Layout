"""Digital Twin type definitions.

Every design has a twin that accumulates all engineering knowledge about it:
Geometry, Physics, Simulation, Measurement, History, Packaging, Fabrication,
expected Yield, Frequency Drift, and Failure Modes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GeometrySnapshot:
    """Frozen snapshot of a design's geometry state."""
    gds_path: str
    sidecar_path: str | None = None
    layer_stack: dict[str, Any] = field(default_factory=dict)
    bounding_box_um: list[float] = field(default_factory=list)
    total_area_um2: float = 0.0
    layer_areas_um2: dict[str, float] = field(default_factory=dict)
    critical_dimensions: dict[str, float] = field(default_factory=dict)
    version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "gds_path": self.gds_path,
            "sidecar_path": self.sidecar_path,
            "layer_stack": self.layer_stack,
            "bounding_box_um": self.bounding_box_um,
            "total_area_um2": self.total_area_um2,
            "layer_areas_um2": self.layer_areas_um2,
            "critical_dimensions": self.critical_dimensions,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GeometrySnapshot:
        return cls(
            gds_path=d["gds_path"],
            sidecar_path=d.get("sidecar_path"),
            layer_stack=d.get("layer_stack", {}),
            bounding_box_um=d.get("bounding_box_um", []),
            total_area_um2=d.get("total_area_um2", 0.0),
            layer_areas_um2=d.get("layer_areas_um2", {}),
            critical_dimensions=d.get("critical_dimensions", {}),
            version=d.get("version", "v1"),
        )


@dataclass
class PhysicsState:
    """Current physics understanding of the device."""
    analytical: dict[str, Any] = field(default_factory=dict)
    extracted: dict[str, Any] = field(default_factory=dict)
    simulated: dict[str, Any] = field(default_factory=dict)
    measured: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    dominant_source: str = "none"

    def best_value(self, key: str) -> Any:
        """Return the best available value for a physics parameter.

        Priority: measured > simulated > extracted > analytical.
        """
        for src in (self.measured, self.simulated, self.extracted, self.analytical):
            if key in src:
                return src[key]
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "analytical": self.analytical,
            "extracted": self.extracted,
            "simulated": self.simulated,
            "measured": self.measured,
            "confidence": self.confidence,
            "dominant_source": self.dominant_source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PhysicsState:
        return cls(
            analytical=d.get("analytical", {}),
            extracted=d.get("extracted", {}),
            simulated=d.get("simulated", {}),
            measured=d.get("measured", {}),
            confidence=d.get("confidence", 0.0),
            dominant_source=d.get("dominant_source", "none"),
        )


@dataclass
class SimulationRun:
    """Record of a single solver execution."""
    solver: str
    status: str  # EXECUTED | SKIPPED | FAILED
    input_path: str | None = None
    output_path: str | None = None
    runtime_s: float = 0.0
    timestamp: str = ""
    results: dict[str, Any] = field(default_factory=dict)
    solver_version: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "solver": self.solver,
            "status": self.status,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "runtime_s": self.runtime_s,
            "timestamp": self.timestamp,
            "results": self.results,
            "solver_version": self.solver_version,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SimulationRun:
        return cls(
            solver=d["solver"],
            status=d["status"],
            input_path=d.get("input_path"),
            output_path=d.get("output_path"),
            runtime_s=d.get("runtime_s", 0.0),
            timestamp=d.get("timestamp", ""),
            results=d.get("results", {}),
            solver_version=d.get("solver_version", ""),
            notes=d.get("notes", ""),
        )


@dataclass
class MeasurementRecord:
    """Record of a physical measurement."""
    measurement_type: str
    value: float | None = None
    unit: str = ""
    uncertainty: float | None = None
    temperature_mk: float | None = None
    date: str = ""
    setup: str = ""
    raw_data_path: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "measurement_type": self.measurement_type,
            "value": self.value,
            "unit": self.unit,
            "uncertainty": self.uncertainty,
            "temperature_mk": self.temperature_mk,
            "date": self.date,
            "setup": self.setup,
            "raw_data_path": self.raw_data_path,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MeasurementRecord:
        return cls(
            measurement_type=d["measurement_type"],
            value=d.get("value"),
            unit=d.get("unit", ""),
            uncertainty=d.get("uncertainty"),
            temperature_mk=d.get("temperature_mk"),
            date=d.get("date", ""),
            setup=d.get("setup", ""),
            raw_data_path=d.get("raw_data_path"),
            notes=d.get("notes", ""),
        )


@dataclass
class DesignIteration:
    """One iteration in the design history."""
    iteration: int
    description: str = ""
    changes: list[str] = field(default_factory=list)
    committee_score: float = 0.0
    approved: bool = False
    geometry_snapshot: GeometrySnapshot | None = None
    physics_state: PhysicsState | None = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "description": self.description,
            "changes": self.changes,
            "committee_score": self.committee_score,
            "approved": self.approved,
            "geometry_snapshot": self.geometry_snapshot.to_dict() if self.geometry_snapshot else None,
            "physics_state": self.physics_state.to_dict() if self.physics_state else None,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DesignIteration:
        geo = d.get("geometry_snapshot")
        phys = d.get("physics_state")
        return cls(
            iteration=d["iteration"],
            description=d.get("description", ""),
            changes=d.get("changes", []),
            committee_score=d.get("committee_score", 0.0),
            approved=d.get("approved", False),
            geometry_snapshot=GeometrySnapshot.from_dict(geo) if geo else None,
            physics_state=PhysicsState.from_dict(phys) if phys else None,
            timestamp=d.get("timestamp", ""),
        )


@dataclass
class FabricationMetadata:
    """Fabrication process and yield information."""
    process: str = ""
    foundry: str = ""
    run_id: str = ""
    tapeout_date: str = ""
    delivery_date: str = ""
    expected_yield_pct: float | None = None
    actual_yield_pct: float | None = None
    fabrication_notes: str = ""
    layer_thicknesses_nm: dict[str, float] = field(default_factory=dict)
    critical_current_density_ua_um2: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "process": self.process,
            "foundry": self.foundry,
            "run_id": self.run_id,
            "tapeout_date": self.tapeout_date,
            "delivery_date": self.delivery_date,
            "expected_yield_pct": self.expected_yield_pct,
            "actual_yield_pct": self.actual_yield_pct,
            "fabrication_notes": self.fabrication_notes,
            "layer_thicknesses_nm": self.layer_thicknesses_nm,
            "critical_current_density_ua_um2": self.critical_current_density_ua_um2,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FabricationMetadata:
        return cls(
            process=d.get("process", ""),
            foundry=d.get("foundry", ""),
            run_id=d.get("run_id", ""),
            tapeout_date=d.get("tapeout_date", ""),
            delivery_date=d.get("delivery_date", ""),
            expected_yield_pct=d.get("expected_yield_pct"),
            actual_yield_pct=d.get("actual_yield_pct"),
            fabrication_notes=d.get("fabrication_notes", ""),
            layer_thicknesses_nm=d.get("layer_thicknesses_nm", {}),
            critical_current_density_ua_um2=d.get("critical_current_density_ua_um2"),
        )


@dataclass
class ReliabilityPrediction:
    """Predicted reliability and failure mode analysis."""
    expected_frequency_drift_mhz_per_year: float | None = None
    expected_1_over_f_noise_sqrt_hz: float | None = None
    expected_t1_us: float | None = None
    expected_t2_us: float | None = None
    dominant_loss_mechanism: str = "unknown"
    failure_modes: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    analysis_method: str = "analytical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_frequency_drift_mhz_per_year": self.expected_frequency_drift_mhz_per_year,
            "expected_1_over_f_noise_sqrt_hz": self.expected_1_over_f_noise_sqrt_hz,
            "expected_t1_us": self.expected_t1_us,
            "expected_t2_us": self.expected_t2_us,
            "dominant_loss_mechanism": self.dominant_loss_mechanism,
            "failure_modes": self.failure_modes,
            "confidence": self.confidence,
            "analysis_method": self.analysis_method,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReliabilityPrediction:
        return cls(
            expected_frequency_drift_mhz_per_year=d.get("expected_frequency_drift_mhz_per_year"),
            expected_1_over_f_noise_sqrt_hz=d.get("expected_1_over_f_noise_sqrt_hz"),
            expected_t1_us=d.get("expected_t1_us"),
            expected_t2_us=d.get("expected_t2_us"),
            dominant_loss_mechanism=d.get("dominant_loss_mechanism", "unknown"),
            failure_modes=d.get("failure_modes", []),
            confidence=d.get("confidence", 0.0),
            analysis_method=d.get("analysis_method", "analytical"),
        )


@dataclass
class DigitalTwin:
    """Complete digital representation of a quantum device design.

    The twin accumulates all engineering knowledge:
    - Geometry (GDS, layer stack, dimensions)
    - Physics (analytical + extracted + simulated + measured)
    - Simulation history (every solver run)
    - Measurement history (every physical measurement)
    - Design iteration history
    - Fabrication metadata
    - Reliability prediction
    - Literature comparison
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    device_type: str = "unknown"
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    tags: list[str] = field(default_factory=list)

    # Core state
    current_geometry: GeometrySnapshot | None = None
    current_physics: PhysicsState | None = None
    fabrication: FabricationMetadata | None = None
    reliability: ReliabilityPrediction | None = None

    # History
    design_iterations: list[DesignIteration] = field(default_factory=list)
    simulation_runs: list[SimulationRun] = field(default_factory=list)
    measurements: list[MeasurementRecord] = field(default_factory=list)

    # Derived state
    committee_score: float = 0.0
    signoff_level: int = 0
    literature_refs: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "text-to-gds.digital-twin.v1",
            "id": self.id,
            "name": self.name,
            "device_type": self.device_type,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "current_geometry": self.current_geometry.to_dict() if self.current_geometry else None,
            "current_physics": self.current_physics.to_dict() if self.current_physics else None,
            "fabrication": self.fabrication.to_dict() if self.fabrication else None,
            "reliability": self.reliability.to_dict() if self.reliability else None,
            "design_iterations": [i.to_dict() for i in self.design_iterations],
            "simulation_runs": [r.to_dict() for r in self.simulation_runs],
            "measurements": [m.to_dict() for m in self.measurements],
            "committee_score": self.committee_score,
            "signoff_level": self.signoff_level,
            "literature_refs": self.literature_refs,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DigitalTwin:
        geo = d.get("current_geometry")
        phys = d.get("current_physics")
        fab = d.get("fabrication")
        rel = d.get("reliability")
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=d.get("name", ""),
            device_type=d.get("device_type", "unknown"),
            description=d.get("description", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            tags=d.get("tags", []),
            current_geometry=GeometrySnapshot.from_dict(geo) if geo else None,
            current_physics=PhysicsState.from_dict(phys) if phys else None,
            fabrication=FabricationMetadata.from_dict(fab) if fab else None,
            reliability=ReliabilityPrediction.from_dict(rel) if rel else None,
            design_iterations=[DesignIteration.from_dict(i) for i in d.get("design_iterations", [])],
            simulation_runs=[SimulationRun.from_dict(r) for r in d.get("simulation_runs", [])],
            measurements=[MeasurementRecord.from_dict(m) for m in d.get("measurements", [])],
            committee_score=d.get("committee_score", 0.0),
            signoff_level=d.get("signoff_level", 0),
            literature_refs=d.get("literature_refs", []),
            notes=d.get("notes", ""),
        )
