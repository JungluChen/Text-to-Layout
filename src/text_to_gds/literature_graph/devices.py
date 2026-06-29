"""Literature device structures for knowledge graph."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeviceTopology(str, Enum):
    """Device topology types."""
    
    POCKET_TRANSMON = "pocket_transmon"
    XMON = "xmon"
    CONCENTRIC_TRANSMON = "concentric_transmon"
    FLUXONIUM = "fluxonium"
    LUMPED_JPA = "lumped_jpa"
    QUARTER_WAVE_JPA = "quarter_wave_jpa"
    TWPA = "twpa"
    CPW_RESONATOR = "cpw_resonator"
    IDC_RESONATOR = "idc_resonator"
    JJ_ARRAY = "jj_array"
    CALIBRATION_CHIP = "calibration_chip"
    UNKNOWN = "unknown"


@dataclass
class LiteratureDevice:
    """A device from literature with its parameters."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    reference: str = ""  # Paper/reference identifier
    topology: DeviceTopology = DeviceTopology.UNKNOWN
    geometry: dict[str, Any] = field(default_factory=dict)
    features: list[dict[str, Any]] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    fabrication: dict[str, Any] = field(default_factory=dict)
    operating_frequency_ghz: float | None = None
    coupling_strategy: str = ""
    flux_strategy: str = ""
    readout_strategy: str = ""
    packaging: dict[str, Any] = field(default_factory=dict)
    advantages: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "reference": self.reference,
            "topology": self.topology.value,
            "geometry": self.geometry,
            "features": self.features,
            "parameters": self.parameters,
            "fabrication": self.fabrication,
            "operating_frequency_ghz": self.operating_frequency_ghz,
            "coupling_strategy": self.coupling_strategy,
            "flux_strategy": self.flux_strategy,
            "readout_strategy": self.readout_strategy,
            "packaging": self.packaging,
            "advantages": self.advantages,
            "limitations": self.limitations,
            "year": self.year,
            "authors": self.authors,
        }


@dataclass
class FeatureComparison:
    """Comparison of a specific feature between generated and literature device."""
    
    feature_name: str = ""
    generated_value: Any = None
    literature_value: Any = None
    match: bool = False
    deviation_percent: float = 0.0
    notes: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "feature_name": self.feature_name,
            "generated_value": self.generated_value,
            "literature_value": self.literature_value,
            "match": self.match,
            "deviation_percent": self.deviation_percent,
            "notes": self.notes,
        }


@dataclass
class ComparisonResult:
    """Result of comparing generated device with literature."""
    
    generated_device_id: str = ""
    literature_device_id: str = ""
    overall_match_score: float = 0.0
    feature_comparisons: list[FeatureComparison] = field(default_factory=list)
    matching_features: list[str] = field(default_factory=list)
    mismatching_features: list[str] = field(default_factory=list)
    missing_features: list[str] = field(default_factory=list)
    extra_features: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "generated_device_id": self.generated_device_id,
            "literature_device_id": self.literature_device_id,
            "overall_match_score": self.overall_match_score,
            "feature_comparisons": [fc.to_dict() for fc in self.feature_comparisons],
            "matching_features": self.matching_features,
            "mismatching_features": self.mismatching_features,
            "missing_features": self.missing_features,
            "extra_features": self.extra_features,
            "recommendations": self.recommendations,
        }
