"""Type definitions for the Measurement Knowledge Base module."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MeasurementType(Enum):
    """Types of measurements."""
    S_PARAMETERS = "s_parameters"
    TRANSMON_SPECTRUM = "transmon_spectrum"
    RESONATOR_SPECTRUM = "resonator_spectrum"
    JPA_GAIN = "jpa_gain"
    JPA_NOISE = "jpa_noise"
    FLUX_TUNING = "flux_tuning"
    Q_FACTOR = "q_factor"
    ANHARMONICITY = "anharmicity"
    COUPLING_STRENGTH = "coupling_strength"
    OTHER = "other"


@dataclass
class MeasurementRecord:
    """A single measurement record."""
    
    id: str
    """Unique identifier for this measurement."""
    
    design_id: str
    """ID of the design being measured."""
    
    measurement_type: MeasurementType
    """Type of measurement."""
    
    timestamp: datetime
    """When the measurement was performed."""
    
    # Measurement data
    data: dict[str, Any] = field(default_factory=dict)
    """Measurement data (frequency, amplitude, phase, etc.)."""
    
    # Metadata
    instrument: str = ""
    """Instrument used for measurement."""
    
    temperature: float = 0.0
    """Measurement temperature in Kelvin."""
    
    magnetic_field: float = 0.0
    """Applied magnetic field in Tesla."""
    
    notes: str = ""
    """Additional notes about the measurement."""
    
    # Analysis results
    extracted_params: dict[str, Any] = field(default_factory=dict)
    """Parameters extracted from measurement (Q, f0, etc.)."""
    
    uncertainty: dict[str, float] = field(default_factory=dict)
    """Uncertainty in extracted parameters."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "design_id": self.design_id,
            "measurement_type": self.measurement_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "instrument": self.instrument,
            "temperature": self.temperature,
            "magnetic_field": self.magnetic_field,
            "notes": self.notes,
            "extracted_params": self.extracted_params,
            "uncertainty": self.uncertainty,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeasurementRecord":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            design_id=data["design_id"],
            measurement_type=MeasurementType(data["measurement_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data.get("data", {}),
            instrument=data.get("instrument", ""),
            temperature=data.get("temperature", 0.0),
            magnetic_field=data.get("magnetic_field", 0.0),
            notes=data.get("notes", ""),
            extracted_params=data.get("extracted_params", {}),
            uncertainty=data.get("uncertainty", {}),
        )


@dataclass
class MeasurementAnalysis:
    """Analysis of measurement data."""
    
    measurement_id: str
    """ID of the measurement being analyzed."""
    
    analysis_type: str
    """Type of analysis performed."""
    
    results: dict[str, Any] = field(default_factory=dict)
    """Analysis results."""
    
    confidence: float = 0.0
    """Confidence in the analysis (0.0 to 1.0)."""
    
    warnings: list[str] = field(default_factory=list)
    """Warnings about the analysis."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "measurement_id": self.measurement_id,
            "analysis_type": self.analysis_type,
            "results": self.results,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }
