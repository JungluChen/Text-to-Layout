"""Design Memory for storing and retrieving design cases.

This module stores every design as an engineering case with layout,
parameters, physics, solver results, measurements, reviews, and
fabrication data. It supports nearest-neighbor search and similarity
search for finding related designs.
"""

import json
from pathlib import Path
from typing import Any

from text_to_gds.design_memory.types import (
    DesignCase,
    DesignSearchResult,
    DesignSimilarity,
)


class DesignMemory:
    """Stores and retrieves design cases for engineering knowledge reuse.
    
    The design memory maintains a database of all designs with their
    complete engineering context. It supports similarity search to find
    related designs and expected performance based on past results.
    """
    
    def __init__(self, database_path: str | Path | None = None) -> None:
        """Initialize the design memory.
        
        Args:
            database_path: Path to the design database directory.
                If None, uses a default location.
        """
        if database_path is None:
            database_path = Path("design_database")
        
        self._db_path = Path(database_path)
        self._db_path.mkdir(parents=True, exist_ok=True)
        
        self._cases: dict[str, DesignCase] = {}
        self._load_database()
    
    def store(self, case: DesignCase) -> None:
        """Store a design case in the database.
        
        Args:
            case: The design case to store.
        """
        self._cases[case.id] = case
        self._save_case(case)
    
    def retrieve(self, case_id: str) -> DesignCase | None:
        """Retrieve a design case by ID.
        
        Args:
            case_id: The ID of the design case to retrieve.
            
        Returns:
            The design case if found, None otherwise.
        """
        return self._cases.get(case_id)
    
    def search(
        self,
        query: dict[str, Any],
        max_results: int = 10,
        min_similarity: float = 0.3,
    ) -> list[DesignSearchResult]:
        """Search for similar designs.
        
        Args:
            query: Query parameters to match against.
            max_results: Maximum number of results to return.
            min_similarity: Minimum similarity score to include.
            
        Returns:
            List of matching design cases sorted by similarity.
        """
        results = []
        
        for case in self._cases.values():
            similarity, matching_features = self._compute_similarity(
                case, query
            )
            
            if similarity >= min_similarity:
                explanation = self._generate_explanation(
                    case, matching_features
                )
                
                results.append(DesignSearchResult(
                    design=case,
                    similarity=similarity,
                    matching_features=matching_features,
                    explanation=explanation,
                ))
        
        # Sort by similarity (highest first)
        results.sort(key=lambda r: r.similarity, reverse=True)
        
        return results[:max_results]
    
    def find_similar(
        self,
        case_id: str,
        max_results: int = 5,
    ) -> list[DesignSimilarity]:
        """Find designs similar to a given design.
        
        Args:
            case_id: ID of the reference design.
            max_results: Maximum number of results to return.
            
        Returns:
            List of similar designs sorted by similarity.
        """
        reference = self._cases.get(case_id)
        if not reference:
            return []
        
        similarities = []
        
        for other_id, other_case in self._cases.items():
            if other_id == case_id:
                continue
            
            similarity = self._compute_design_similarity(
                reference, other_case
            )
            
            if similarity.similarity > 0.1:
                similarities.append(similarity)
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda s: s.similarity, reverse=True)
        
        return similarities[:max_results]
    
    def get_expected_performance(
        self,
        device_type: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Get expected performance based on similar past designs.
        
        Args:
            device_type: Type of device.
            parameters: Design parameters.
            
        Returns:
            Dictionary of expected performance metrics.
        """
        # Find similar designs
        query = {"device_type": device_type, **parameters}
        similar_designs = self.search(query, max_results=5, min_similarity=0.2)
        
        if not similar_designs:
            return {"status": "no_similar_designs"}
        
        # Aggregate performance from similar designs
        performance = {
            "status": "estimated",
            "similar_designs_count": len(similar_designs),
            "average_signoff_level": sum(
                d.design.signoff_level for d in similar_designs
            ) / len(similar_designs),
        }
        
        # Aggregate physics parameters
        physics_values: dict[str, list[float]] = {}
        for result in similar_designs:
            for key, value in result.design.physics_params.items():
                if isinstance(value, (int, float)):
                    if key not in physics_values:
                        physics_values[key] = []
                    physics_values[key].append(value)
        
        for key, values in physics_values.items():
            performance[f"expected_{key}_mean"] = sum(values) / len(values)
            performance[f"expected_{key}_min"] = min(values)
            performance[f"expected_{key}_max"] = max(values)
        
        return performance
    
    def list_designs(
        self,
        device_type: str | None = None,
        tags: list[str] | None = None,
        min_signoff_level: int = 0,
    ) -> list[DesignCase]:
        """List designs with optional filters.
        
        Args:
            device_type: Filter by device type.
            tags: Filter by tags (design must have all specified tags).
            min_signoff_level: Minimum signoff level.
            
        Returns:
            List of matching design cases.
        """
        results = []
        
        for case in self._cases.values():
            if device_type and case.device_type != device_type:
                continue
            
            if tags and not all(tag in case.tags for tag in tags):
                continue
            
            if case.signoff_level < min_signoff_level:
                continue
            
            results.append(case)
        
        return results
    
    def _compute_similarity(
        self,
        case: DesignCase,
        query: dict[str, Any],
    ) -> tuple[float, list[str]]:
        """Compute similarity between a case and a query."""
        score = 0.0
        matching_features = []
        
        # Check device type match
        if "device_type" in query:
            if case.device_type == query["device_type"]:
                score += 0.3
                matching_features.append("device_type")
        
        # Check geometry parameter match
        if "geometry_params" in query:
            query_geom = query["geometry_params"]
            for key, value in query_geom.items():
                if key in case.geometry_params:
                    case_value = case.geometry_params[key]
                    if isinstance(value, (int, float)) and isinstance(case_value, (int, float)):
                        # Numerical similarity (inverse of relative difference)
                        if value != 0:
                            diff = abs(value - case_value) / abs(value)
                            similarity = max(0, 1 - diff)
                            if similarity > 0.5:
                                score += 0.1 * similarity
                                matching_features.append(f"geometry_{key}")
        
        # Check physics parameter match
        if "physics_params" in query:
            query_physics = query["physics_params"]
            for key, value in query_physics.items():
                if key in case.physics_params:
                    case_value = case.physics_params[key]
                    if isinstance(value, (int, float)) and isinstance(case_value, (int, float)):
                        if value != 0:
                            diff = abs(value - case_value) / abs(value)
                            similarity = max(0, 1 - diff)
                            if similarity > 0.5:
                                score += 0.15 * similarity
                                matching_features.append(f"physics_{key}")
        
        # Check tag match
        if "tags" in query:
            query_tags = set(query["tags"])
            case_tags = set(case.tags)
            common = query_tags & case_tags
            if common:
                score += 0.1 * len(common) / len(query_tags)
                matching_features.extend([f"tag_{t}" for t in common])
        
        return min(score, 1.0), matching_features
    
    def _compute_design_similarity(
        self,
        design_a: DesignCase,
        design_b: DesignCase,
    ) -> DesignSimilarity:
        """Compute similarity between two designs."""
        feature_similarities: dict[str, float] = {}
        
        # Device type match
        if design_a.device_type == design_b.device_type:
            feature_similarities["device_type"] = 1.0
        else:
            feature_similarities["device_type"] = 0.0
        
        # Geometry parameter similarity
        geom_sim = self._compute_param_similarity(
            design_a.geometry_params,
            design_b.geometry_params,
        )
        feature_similarities["geometry"] = geom_sim
        
        # Physics parameter similarity
        physics_sim = self._compute_param_similarity(
            design_a.physics_params,
            design_b.physics_params,
        )
        feature_similarities["physics"] = physics_sim
        
        # Tag similarity
        common_tags = set(design_a.tags) & set(design_b.tags)
        all_tags = set(design_a.tags) | set(design_b.tags)
        tag_sim = len(common_tags) / len(all_tags) if all_tags else 0.0
        feature_similarities["tags"] = tag_sim
        
        # Overall similarity (weighted average)
        overall = (
            0.3 * feature_similarities["device_type"] +
            0.3 * feature_similarities["geometry"] +
            0.3 * feature_similarities["physics"] +
            0.1 * feature_similarities["tags"]
        )
        
        return DesignSimilarity(
            design_a_id=design_a.id,
            design_b_id=design_b.id,
            similarity=overall,
            feature_similarities=feature_similarities,
            common_tags=list(common_tags),
        )
    
    def _compute_param_similarity(
        self,
        params_a: dict[str, Any],
        params_b: dict[str, Any],
    ) -> float:
        """Compute similarity between two parameter dictionaries."""
        if not params_a or not params_b:
            return 0.0
        
        common_keys = set(params_a.keys()) & set(params_b.keys())
        if not common_keys:
            return 0.0
        
        similarities = []
        for key in common_keys:
            val_a = params_a[key]
            val_b = params_b[key]
            
            if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                if val_a != 0:
                    diff = abs(val_a - val_b) / abs(val_a)
                    similarities.append(max(0, 1 - diff))
                elif val_b == 0:
                    similarities.append(1.0)
                else:
                    similarities.append(0.0)
            elif val_a == val_b:
                similarities.append(1.0)
            else:
                similarities.append(0.0)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _generate_explanation(
        self,
        case: DesignCase,
        matching_features: list[str],
    ) -> str:
        """Generate explanation for why a design matched."""
        if not matching_features:
            return "No specific features matched."
        
        parts = [f"Design '{case.name}' matched on:"]
        for feature in matching_features:
            parts.append(f"  - {feature}")
        
        return "\n".join(parts)
    
    def _load_database(self) -> None:
        """Load all design cases from the database directory."""
        for case_file in self._db_path.glob("*.json"):
            try:
                with open(case_file, "r") as f:
                    data = json.load(f)
                case = DesignCase.from_dict(data)
                self._cases[case.id] = case
            except (json.JSONDecodeError, KeyError):
                continue
    
    def _save_case(self, case: DesignCase) -> None:
        """Save a design case to the database directory."""
        case_file = self._db_path / f"{case.id}.json"
        with open(case_file, "w") as f:
            json.dump(case.to_dict(), f, indent=2)
