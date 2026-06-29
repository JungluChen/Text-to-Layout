"""Type definitions for the Design Memory module."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DesignCase:
    """A complete design case with all engineering data."""
    
    id: str
    """Unique identifier for this design case."""
    
    name: str
    """Human-readable name for this design."""
    
    device_type: str
    """Type of device (e.g., pocket_transmon, lumped_jpa)."""
    
    created_at: datetime
    """When this design was created."""
    
    # Layout data
    gds_path: str = ""
    """Path to the GDS file."""
    
    sidecar: dict[str, Any] = field(default_factory=dict)
    """Sidecar metadata."""
    
    # Parameters
    geometry_params: dict[str, Any] = field(default_factory=dict)
    """Geometry parameters (dimensions, etc.)."""
    
    physics_params: dict[str, Any] = field(default_factory=dict)
    """Physics parameters (Ic, Lj, frequency, etc.)."""
    
    process_params: dict[str, Any] = field(default_factory=dict)
    """Process parameters (metal height, epsilon_r, etc.)."""
    
    # Solver results
    solver_results: dict[str, Any] = field(default_factory=dict)
    """Solver output data (S-parameters, eigenvalues, etc.)."""
    
    solver_status: dict[str, str] = field(default_factory=dict)
    """Status of each solver (executed, skipped, failed)."""
    
    # Measurement data
    measurements: dict[str, Any] = field(default_factory=dict)
    """Measurement results (if available)."""
    
    # Review and signoff
    review_scores: dict[str, float] = field(default_factory=dict)
    """Review scores from different reviewers."""
    
    signoff_level: int = 0
    """Signoff level achieved (0-6)."""
    
    # Similarity features
    feature_vector: list[float] = field(default_factory=list)
    """Feature vector for similarity search."""
    
    tags: list[str] = field(default_factory=list)
    """Tags for categorization."""
    
    notes: str = ""
    """Additional notes about this design."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "device_type": self.device_type,
            "created_at": self.created_at.isoformat(),
            "gds_path": self.gds_path,
            "sidecar": self.sidecar,
            "geometry_params": self.geometry_params,
            "physics_params": self.physics_params,
            "process_params": self.process_params,
            "solver_results": self.solver_results,
            "solver_status": self.solver_status,
            "measurements": self.measurements,
            "review_scores": self.review_scores,
            "signoff_level": self.signoff_level,
            "feature_vector": self.feature_vector,
            "tags": self.tags,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DesignCase":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            device_type=data["device_type"],
            created_at=datetime.fromisoformat(data["created_at"]),
            gds_path=data.get("gds_path", ""),
            sidecar=data.get("sidecar", {}),
            geometry_params=data.get("geometry_params", {}),
            physics_params=data.get("physics_params", {}),
            process_params=data.get("process_params", {}),
            solver_results=data.get("solver_results", {}),
            solver_status=data.get("solver_status", {}),
            measurements=data.get("measurements", {}),
            review_scores=data.get("review_scores", {}),
            signoff_level=data.get("signoff_level", 0),
            feature_vector=data.get("feature_vector", []),
            tags=data.get("tags", []),
            notes=data.get("notes", ""),
        )


@dataclass
class DesignSearchResult:
    """Result of a design search query."""
    
    design: DesignCase
    """The matched design case."""
    
    similarity: float
    """Similarity score (0.0 to 1.0)."""
    
    matching_features: list[str]
    """Features that matched the query."""
    
    explanation: str = ""
    """Explanation of why this design matched."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "design": self.design.to_dict(),
            "similarity": self.similarity,
            "matching_features": self.matching_features,
            "explanation": self.explanation,
        }


@dataclass
class DesignSimilarity:
    """Similarity between two designs."""
    
    design_a_id: str
    """ID of the first design."""
    
    design_b_id: str
    """ID of the second design."""
    
    similarity: float
    """Overall similarity score (0.0 to 1.0)."""
    
    feature_similarities: dict[str, float]
    """Similarity scores for individual features."""
    
    common_tags: list[str]
    """Tags shared between the designs."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "design_a_id": self.design_a_id,
            "design_b_id": self.design_b_id,
            "similarity": self.similarity,
            "feature_similarities": self.feature_similarities,
            "common_tags": self.common_tags,
        }
