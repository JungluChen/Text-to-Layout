"""Topology Reasoning Engine - orchestrates evidence-based device classification.

This engine analyzes geometry features and physics graph to classify device
topology with evidence-based reasoning, alternative hypotheses, and missing
evidence identification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from text_to_gds.topology_reasoning.classifiers import (
    classify_pocket_transmon,
    classify_xmon,
    classify_concentric_transmon,
    classify_fluxonium,
    classify_lumped_jpa,
    classify_quarter_wave_jpa,
    classify_twpa,
    classify_cpw_resonator,
    classify_idc_resonator,
    classify_jj_array,
    classify_calibration_chip,
)
from text_to_gds.topology_reasoning.evidence import TopologyClassification


# List of all classifiers
_CLASSIFIERS = [
    classify_lumped_jpa,
    classify_quarter_wave_jpa,
    classify_pocket_transmon,
    classify_xmon,
    classify_concentric_transmon,
    classify_twpa,
    classify_fluxonium,
    classify_cpw_resonator,
    classify_idc_resonator,
    classify_jj_array,
    classify_calibration_chip,
]


class TopologyReasoningEngine:
    """Main engine for evidence-based topology classification.
    
    This engine analyzes geometry features and physics graph to classify
    device topology with evidence-based reasoning.
    """
    
    def __init__(self) -> None:
        """Initialize the topology reasoning engine."""
        self._classifications: list[TopologyClassification] = []
    
    def classify_topology(
        self,
        features: dict[str, Any],
        geometry_features: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Classify device topology from extracted features.
        
        Parameters
        ----------
        features:
            Features extracted from physics graph.
        geometry_features:
            Optional geometry features from geometry intelligence engine.
        
        Returns
        -------
        dict with topology_reasoning.json schema.
        """
        self._classifications = []
        
        # Run all classifiers
        for classifier in _CLASSIFIERS:
            classification = classifier(features, geometry_features)
            self._classifications.append(classification)
        
        # Select best classification
        best = self._select_best_classification()
        
        # Build result
        result = self._build_result(best)
        
        return result
    
    def _select_best_classification(self) -> TopologyClassification:
        """Select the best classification based on confidence."""
        if not self._classifications:
            return TopologyClassification(topology="unknown", confidence=0.0)
        
        # Sort by confidence (descending)
        sorted_classifications = sorted(
            self._classifications,
            key=lambda c: c.confidence,
            reverse=True,
        )
        
        return sorted_classifications[0]
    
    def _build_result(self, best: TopologyClassification) -> dict[str, Any]:
        """Build the topology reasoning result."""
        # Build alternative hypotheses from all classifications
        alternative_hypotheses = []
        for classification in self._classifications:
            if classification.topology != best.topology and classification.confidence > 0.1:
                alternative_hypotheses.append({
                    "topology": classification.topology,
                    "confidence": classification.confidence,
                    "supporting_features": len(classification.supporting_evidence),
                })
        
        # Sort alternatives by confidence
        alternative_hypotheses.sort(key=lambda x: x["confidence"], reverse=True)
        
        return {
            "schema": "text-to-gds.topology-reasoning.v1",
            "detected_topology": best.topology,
            "confidence": best.confidence,
            "supporting_evidence": [e.to_dict() for e in best.supporting_evidence],
            "missing_evidence": [e.to_dict() for e in best.missing_evidence],
            "alternative_hypotheses": alternative_hypotheses[:5],  # Top 5 alternatives
            "classification_reasoning": best.classification_reasoning,
            "all_classifications": [
                {
                    "topology": c.topology,
                    "confidence": c.confidence,
                }
                for c in self._classifications
            ],
        }


def classify_topology_reasoning(
    features: dict[str, Any],
    geometry_features: list[dict[str, Any]] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """High-level function to classify topology with reasoning.
    
    Parameters
    ----------
    features:
        Features extracted from physics graph.
    geometry_features:
        Optional geometry features from geometry intelligence engine.
    output_path:
        Optional path to write the topology reasoning JSON.
    
    Returns
    -------
    dict with topology_reasoning.json schema.
    """
    engine = TopologyReasoningEngine()
    result = engine.classify_topology(
        features=features,
        geometry_features=geometry_features,
    )
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    
    return result
