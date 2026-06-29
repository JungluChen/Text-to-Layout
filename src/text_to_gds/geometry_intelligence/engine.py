"""Geometry Intelligence Engine - orchestrates feature recognition from GDS layouts.

This engine analyzes GDS geometry and produces a semantic geometry graph
with recognized features, their engineering properties, and provenance.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from text_to_gds.geometry_intelligence.features import FeatureType, GeometryFeature
from text_to_gds.geometry_intelligence.recognizers import (
    recognize_cpw,
    recognize_idc,
    recognize_launch_pad,
    recognize_bond_pad,
    recognize_josephson_junction,
    recognize_capacitor_paddle,
    recognize_flux_line,
    recognize_via_fence,
    recognize_ground_pocket,
)


class GeometryIntelligenceEngine:
    """Main engine for semantic geometry recognition.
    
    This engine analyzes GDS layouts and produces a geometry graph with
    recognized features, their engineering properties, and provenance.
    """
    
    def __init__(self) -> None:
        """Initialize the geometry intelligence engine."""
        self._features: list[GeometryFeature] = []
        self._feature_map: dict[str, GeometryFeature] = {}
    
    def analyze_layout(
        self,
        gds_path: str | Path,
        physics_graph: dict[str, Any] | None = None,
        extraction_data: dict[str, Any] | None = None,
        sidecar: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze a GDS layout and produce a geometry graph.
        
        Parameters
        ----------
        gds_path:
            Path to the GDS file.
        physics_graph:
            Optional output of extract_physics_graph().
        extraction_data:
            Optional geometry extraction data.
        sidecar:
            Optional sidecar metadata.
        
        Returns
        -------
        dict with geometry_graph.json schema.
        """
        self._features = []
        self._feature_map = {}
        
        # Extract features from physics graph
        if physics_graph:
            self._extract_from_physics_graph(physics_graph)
        
        # Extract features from extraction data
        if extraction_data:
            self._extract_from_extraction_data(extraction_data)
        
        # Extract features from sidecar
        if sidecar:
            self._extract_from_sidecar(sidecar)
        
        # Build connections between features
        self._build_connections()
        
        # Build the geometry graph
        geometry_graph = self._build_geometry_graph(gds_path)
        
        return geometry_graph
    
    def _extract_from_physics_graph(self, graph: dict[str, Any]) -> None:
        """Extract features from physics graph nodes."""
        for node in graph.get("nodes", []):
            node_type = node.get("type", "")
            name = node.get("name", "")
            geometry = node.get("geometry", {})
            params = node.get("physics_parameters", {})
            bbox = geometry.get("bbox_um", [0.0, 0.0, 0.0, 0.0])
            
            # Extract JJ features
            if node_type == "josephson_junction":
                area = geometry.get("area_um2", 0.0)
                width = params.get("width", {})
                if isinstance(width, dict):
                    width = width.get("value", 0.0)
                ic = params.get("critical_current", {})
                if isinstance(ic, dict):
                    ic = ic.get("value", None)
                
                feature = recognize_josephson_junction(
                    bbox=bbox,
                    junction_area=area,
                    junction_width=width if isinstance(width, (int, float)) else 0.0,
                    critical_current_ua=ic,
                    name=name,
                )
                self._add_feature(feature)
            
            # Extract capacitor features
            elif node_type == "capacitor":
                area = geometry.get("area_um2", 0.0)
                finger_count = params.get("finger_count", {})
                if isinstance(finger_count, dict):
                    finger_count = finger_count.get("value", 0)
                
                if finger_count and finger_count > 0:
                    # IDC
                    feature = recognize_idc(
                        bbox=bbox,
                        finger_count=finger_count,
                        finger_width=5.0,  # Default
                        finger_gap=3.0,  # Default
                        finger_length=50.0,  # Default
                        name=name,
                    )
                else:
                    # Capacitor paddle
                    feature = recognize_capacitor_paddle(
                        bbox=bbox,
                        paddle_area=area,
                        gap=5.0,  # Default
                        name=name,
                    )
                self._add_feature(feature)
            
            # Extract transmission line features
            elif node_type == "transmission_line":
                width = params.get("width", {})
                if isinstance(width, dict):
                    width = width.get("value", 0.0)
                gap = params.get("gap", {})
                if isinstance(gap, dict):
                    gap = gap.get("value", 0.0)
                length = params.get("length", {})
                if isinstance(length, dict):
                    length = length.get("value", 0.0)
                z0 = params.get("z0", {})
                if isinstance(z0, dict):
                    z0 = z0.get("value", None)
                
                feature = recognize_cpw(
                    bbox=bbox,
                    width=width if isinstance(width, (int, float)) else 0.0,
                    gap=gap if isinstance(gap, (int, float)) else 0.0,
                    length=length if isinstance(length, (int, float)) else 0.0,
                    z0=z0,
                    name=name,
                )
                self._add_feature(feature)
            
            # Extract port features
            elif node_type == "port":
                port_name = name.lower()
                if any(kw in port_name for kw in ("rf", "in", "out", "signal", "pump", "readout")):
                    feature = recognize_launch_pad(
                        bbox=bbox,
                        pad_width=100.0,  # Default
                        pad_length=100.0,  # Default
                        gsg_config="gsg" in port_name,
                        name=name,
                    )
                elif any(kw in port_name for kw in ("flux", "bias", "dc")):
                    feature = recognize_flux_line(
                        bbox=bbox,
                        line_width=5.0,  # Default
                        line_length=100.0,  # Default
                        coupling_gap=5.0,  # Default
                        name=name,
                    )
                else:
                    feature = recognize_bond_pad(
                        bbox=bbox,
                        pad_diameter=100.0,  # Default
                        name=name,
                    )
                self._add_feature(feature)
            
            # Extract ground features
            elif node_type == "ground":
                area = geometry.get("total_area_um2", geometry.get("area_um2", 0.0))
                feature = recognize_ground_pocket(
                    bbox=bbox,
                    pocket_area=area if isinstance(area, (int, float)) else 0.0,
                    isolation_depth=0.0,
                    name=name,
                )
                self._add_feature(feature)
    
    def _extract_from_extraction_data(self, extraction: dict[str, Any]) -> None:
        """Extract features from geometry extraction data."""
        # Extract device features
        for device in extraction.get("devices", []):
            device_type = device.get("device_type", "")
            params = device.get("parameters", {})
            bbox = device.get("bbox_um", [0.0, 0.0, 0.0, 0.0])
            
            if device_type == "jj":
                bridge_width = float(params.get("bridge_width_um", 0.0))
                area = float(params.get("area_um2", 0.0))
                
                feature = recognize_josephson_junction(
                    bbox=bbox,
                    junction_area=area,
                    junction_width=bridge_width,
                    name=f"JJ_{len(self._features)}",
                )
                self._add_feature(feature)
            
            elif device_type in ("cpw", "tline"):
                width = float(params.get("center_width_um", params.get("trace_width_um", 0.0)))
                length = float(params.get("length_um", 0.0))
                
                feature = recognize_cpw(
                    bbox=bbox,
                    width=width,
                    gap=width * 0.6,  # Assume 60% gap ratio
                    length=length,
                    name=f"CPW_{len(self._features)}",
                )
                self._add_feature(feature)
            
            elif device_type == "via":
                area = float(params.get("area_um2", 0.0))
                diameter = math.sqrt(4 * area / math.pi) if area > 0 else 0.0
                
                feature = recognize_via_fence(
                    bbox=bbox,
                    via_count=1,
                    via_diameter=diameter,
                    via_spacing=diameter * 2,
                    name=f"Via_{len(self._features)}",
                )
                self._add_feature(feature)
    
    def _extract_from_sidecar(self, sidecar: dict[str, Any]) -> None:
        """Extract features from sidecar metadata."""
        ports = sidecar.get("ports", [])
        
        # Extract port features
        for port in ports:
            name = port.get("name", "")
            center = port.get("center", [0.0, 0.0])
            width = port.get("width", 0.0)
            
            # Create bounding box from center and width
            bbox = [
                center[0] - width / 2,
                center[1] - width / 2,
                center[0] + width / 2,
                center[1] + width / 2,
            ]
            
            port_name = name.lower()
            if any(kw in port_name for kw in ("rf", "in", "out", "signal", "pump", "readout")):
                feature = recognize_launch_pad(
                    bbox=bbox,
                    pad_width=width,
                    pad_length=width,
                    gsg_config="gsg" in port_name,
                    name=name,
                )
                self._add_feature(feature)
    
    def _add_feature(self, feature: GeometryFeature) -> None:
        """Add a feature to the engine."""
        self._features.append(feature)
        self._feature_map[feature.id] = feature
    
    def _build_connections(self) -> None:
        """Build connections between features based on spatial proximity."""
        # Simple proximity-based connection
        for i, f1 in enumerate(self._features):
            for j, f2 in enumerate(self._features):
                if i >= j:
                    continue
                
                # Check if features are close enough to be connected
                center1 = f1.center
                center2 = f2.center
                distance = math.hypot(center2[0] - center1[0], center2[1] - center1[1])
                
                # Connect if within reasonable distance
                max_dim = max(f1.width_um, f1.height_um, f2.width_um, f2.height_um)
                if distance < max_dim * 2:
                    f1.connected_nets.append(f2.id)
                    f2.connected_nets.append(f1.id)
    
    def _build_geometry_graph(self, gds_path: str | Path) -> dict[str, Any]:
        """Build the geometry graph dictionary."""
        # Group features by type
        features_by_type: dict[str, list[dict[str, Any]]] = {}
        for feature in self._features:
            feature_type = feature.feature_type.value
            if feature_type not in features_by_type:
                features_by_type[feature_type] = []
            features_by_type[feature_type].append(feature.to_dict())
        
        # Build feature list
        feature_list = [f.to_dict() for f in self._features]
        
        # Build summary
        summary = {
            "total_features": len(self._features),
            "features_by_type": {k: len(v) for k, v in features_by_type.items()},
            "confidence_statistics": self._compute_confidence_stats(),
        }
        
        return {
            "schema": "text-to-gds.geometry-graph.v1",
            "source_gds": str(gds_path),
            "features": feature_list,
            "features_by_type": features_by_type,
            "summary": summary,
        }
    
    def _compute_confidence_stats(self) -> dict[str, Any]:
        """Compute confidence statistics."""
        if not self._features:
            return {"mean": 0.0, "min": 0.0, "max": 0.0}
        
        confidences = [f.confidence for f in self._features]
        return {
            "mean": sum(confidences) / len(confidences),
            "min": min(confidences),
            "max": max(confidences),
        }
    
    def get_features_by_type(self, feature_type: FeatureType) -> list[GeometryFeature]:
        """Get all features of a specific type."""
        return [f for f in self._features if f.feature_type == feature_type]
    
    def get_feature_by_id(self, feature_id: str) -> GeometryFeature | None:
        """Get a feature by its ID."""
        return self._feature_map.get(feature_id)
    
    def get_connected_features(self, feature_id: str) -> list[GeometryFeature]:
        """Get all features connected to a given feature."""
        feature = self._feature_map.get(feature_id)
        if feature is None:
            return []
        return [self._feature_map[nid] for nid in feature.connected_nets if nid in self._feature_map]


def analyze_geometry_intelligence(
    gds_path: str | Path,
    physics_graph: dict[str, Any] | None = None,
    extraction_data: dict[str, Any] | None = None,
    sidecar: dict[str, Any] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """High-level function to analyze geometry intelligence.
    
    Parameters
    ----------
    gds_path:
        Path to the GDS file.
    physics_graph:
        Optional output of extract_physics_graph().
    extraction_data:
        Optional geometry extraction data.
    sidecar:
        Optional sidecar metadata.
    output_path:
        Optional path to write the geometry graph JSON.
    
    Returns
    -------
    dict with geometry_graph.json schema.
    """
    engine = GeometryIntelligenceEngine()
    geometry_graph = engine.analyze_layout(
        gds_path=gds_path,
        physics_graph=physics_graph,
        extraction_data=extraction_data,
        sidecar=sidecar,
    )
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(geometry_graph, indent=2), encoding="utf-8")
    
    return geometry_graph
