"""Engineering Visualization Engine - generates publication-quality figures.

This engine creates various visualization views for superconducting quantum
circuits based on extracted knowledge.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout._legacy.engineering_visualization.views import ViewType, VisualizationView


class EngineeringVisualizationEngine:
    """Main engine for engineering visualization.
    
    This engine generates publication-quality figures for different
    visualization views.
    """
    
    def __init__(self) -> None:
        """Initialize the engineering visualization engine."""
        self._geometry_graph: dict[str, Any] | None = None
        self._physics_graph: dict[str, Any] | None = None
        self._design_graph: dict[str, Any] | None = None
        self._topology_result: dict[str, Any] | None = None
        self._review_result: dict[str, Any] | None = None
    
    def load_knowledge(
        self,
        geometry_graph: dict[str, Any] | None = None,
        physics_graph: dict[str, Any] | None = None,
        design_graph: dict[str, Any] | None = None,
        topology_result: dict[str, Any] | None = None,
        review_result: dict[str, Any] | None = None,
    ) -> None:
        """Load knowledge sources for visualization.
        
        Parameters
        ----------
        geometry_graph:
            Output of GeometryIntelligenceEngine.
        physics_graph:
            Output of extract_physics_graph().
        design_graph:
            Output of DesignGraphEngine.
        topology_result:
            Output of TopologyReasoningEngine.
        review_result:
            Review committee result.
        """
        self._geometry_graph = geometry_graph
        self._physics_graph = physics_graph
        self._design_graph = design_graph
        self._topology_result = topology_result
        self._review_result = review_result
    
    def generate_view(self, view_type: ViewType) -> VisualizationView:
        """Generate a visualization view.
        
        Parameters
        ----------
        view_type:
            Type of view to generate.
        
        Returns
        -------
        VisualizationView with generated data.
        """
        if view_type == ViewType.GEOMETRY_VIEW:
            return self._generate_geometry_view()
        elif view_type == ViewType.TOPOLOGY_VIEW:
            return self._generate_topology_view()
        elif view_type == ViewType.CURRENT_FLOW_VIEW:
            return self._generate_current_flow_view()
        elif view_type == ViewType.ELECTRIC_FIELD_VIEW:
            return self._generate_electric_field_view()
        elif view_type == ViewType.MAGNETIC_FIELD_VIEW:
            return self._generate_magnetic_field_view()
        elif view_type == ViewType.CRITICAL_DIMENSION_VIEW:
            return self._generate_critical_dimension_view()
        elif view_type == ViewType.SUBSYSTEM_VIEW:
            return self._generate_subsystem_view()
        elif view_type == ViewType.FEATURE_IMPORTANCE_VIEW:
            return self._generate_feature_importance_view()
        elif view_type == ViewType.DESIGN_GRAPH_VIEW:
            return self._generate_design_graph_view()
        elif view_type == ViewType.REVIEW_OVERLAY:
            return self._generate_review_overlay()
        else:
            return VisualizationView(
                view_type=view_type,
                title="Unknown View",
                description="View type not supported",
            )
    
    def _generate_geometry_view(self) -> VisualizationView:
        """Generate geometry view."""
        data = {
            "features": [],
            "bounding_boxes": [],
            "feature_types": {},
        }
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            for feature in features:
                data["features"].append({
                    "name": feature.get("name", ""),
                    "type": feature.get("feature_type", ""),
                    "bbox": feature.get("bounding_box", []),
                })
                data["bounding_boxes"].append(feature.get("bounding_box", []))
                
                feature_type = feature.get("feature_type", "unknown")
                data["feature_types"][feature_type] = data["feature_types"].get(feature_type, 0) + 1
        
        return VisualizationView(
            view_type=ViewType.GEOMETRY_VIEW,
            title="Geometry View",
            description="Layout geometry with recognized features",
            data=data,
        )
    
    def _generate_topology_view(self) -> VisualizationView:
        """Generate topology view."""
        data = {
            "topology": "unknown",
            "confidence": 0.0,
            "subsystems": [],
            "connections": [],
        }
        
        if self._topology_result:
            data["topology"] = self._topology_result.get("detected_topology", "unknown")
            data["confidence"] = self._topology_result.get("confidence", 0.0)
        
        if self._design_graph:
            nodes = self._design_graph.get("nodes", [])
            edges = self._design_graph.get("edges", [])
            
            for node in nodes:
                if node.get("node_type") == "subsystem":
                    data["subsystems"].append({
                        "name": node.get("name", ""),
                        "type": node.get("subsystem_type", ""),
                    })
            
            for edge in edges:
                data["connections"].append({
                    "source": edge.get("source_id", ""),
                    "target": edge.get("target_id", ""),
                    "type": edge.get("edge_type", ""),
                })
        
        return VisualizationView(
            view_type=ViewType.TOPOLOGY_VIEW,
            title="Topology View",
            description="Device topology and subsystem connections",
            data=data,
        )
    
    def _generate_current_flow_view(self) -> VisualizationView:
        """Generate current flow view."""
        data = {
            "current_paths": [],
            "bottlenecks": [],
            "return_paths": [],
        }
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            
            # Identify current paths through conductors
            conductors = [f for f in features if f.get("feature_type") in ("cpw", "feedline")]
            for conductor in conductors:
                data["current_paths"].append({
                    "name": conductor.get("name", ""),
                    "bbox": conductor.get("bounding_box", []),
                    "width": conductor.get("dimensions", {}).get("center_width_um", 0),
                })
            
            # Identify bottlenecks
            bottlenecks = [f for f in features if f.get("feature_type") == "current_bottleneck"]
            for bottleneck in bottlenecks:
                data["bottlenecks"].append({
                    "name": bottleneck.get("name", ""),
                    "bbox": bottleneck.get("bounding_box", []),
                    "min_width": bottleneck.get("dimensions", {}).get("min_width_um", 0),
                })
        
        return VisualizationView(
            view_type=ViewType.CURRENT_FLOW_VIEW,
            title="Current Flow View",
            description="Current paths and bottlenecks",
            data=data,
        )
    
    def _generate_electric_field_view(self) -> VisualizationView:
        """Generate electric field view."""
        data = {
            "field_regions": [],
            "capacitive_elements": [],
            "coupling_gaps": [],
        }
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            
            # Identify capacitive elements
            capacitors = [f for f in features if f.get("feature_type") in ("capacitor_paddle", "idc", "island")]
            for cap in capacitors:
                data["capacitive_elements"].append({
                    "name": cap.get("name", ""),
                    "bbox": cap.get("bounding_box", []),
                    "type": cap.get("feature_type", ""),
                })
                data["field_regions"].append({
                    "name": cap.get("name", ""),
                    "bbox": cap.get("bounding_box", []),
                    "field_strength": "high",
                })
        
        return VisualizationView(
            view_type=ViewType.ELECTRIC_FIELD_VIEW,
            title="Electric Field View",
            description="Electric field concentration regions",
            data=data,
        )
    
    def _generate_magnetic_field_view(self) -> VisualizationView:
        """Generate magnetic field view."""
        data = {
            "field_regions": [],
            "junction_locations": [],
            "flux_coupling": [],
        }
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            
            # Identify JJ locations
            jj_features = [f for f in features if f.get("feature_type") == "josephson_junction"]
            for jj in jj_features:
                data["junction_locations"].append({
                    "name": jj.get("name", ""),
                    "bbox": jj.get("bounding_box", []),
                })
                data["field_regions"].append({
                    "name": jj.get("name", ""),
                    "bbox": jj.get("bounding_box", []),
                    "field_strength": "high",
                })
            
            # Identify flux coupling
            flux_features = [f for f in features if f.get("feature_type") == "flux_line"]
            for flux in flux_features:
                data["flux_coupling"].append({
                    "name": flux.get("name", ""),
                    "bbox": flux.get("bounding_box", []),
                })
        
        return VisualizationView(
            view_type=ViewType.MAGNETIC_FIELD_VIEW,
            title="Magnetic Field View",
            description="Magnetic field concentration and flux coupling",
            data=data,
        )
    
    def _generate_critical_dimension_view(self) -> VisualizationView:
        """Generate critical dimension view."""
        data = {
            "critical_dimensions": [],
            "feature_dimensions": {},
        }
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            for feature in features:
                dims = feature.get("dimensions", {})
                if dims:
                    data["feature_dimensions"][feature.get("name", "")] = dims
                    
                    # Identify critical dimensions
                    for key, value in dims.items():
                        if isinstance(value, (int, float)) and value > 0:
                            data["critical_dimensions"].append({
                                "feature": feature.get("name", ""),
                                "parameter": key,
                                "value": value,
                                "unit": "um" if "um" in key else "",
                            })
        
        return VisualizationView(
            view_type=ViewType.CRITICAL_DIMENSION_VIEW,
            title="Critical Dimension View",
            description="Critical dimensions for fabrication and performance",
            data=data,
        )
    
    def _generate_subsystem_view(self) -> VisualizationView:
        """Generate subsystem view."""
        data = {
            "subsystems": [],
            "hierarchy": [],
        }
        
        if self._design_graph:
            nodes = self._design_graph.get("nodes", [])
            
            for node in nodes:
                if node.get("node_type") in ("device", "subsystem", "functional_block"):
                    data["subsystems"].append({
                        "name": node.get("name", ""),
                        "type": node.get("node_type", ""),
                        "parent": node.get("parent_id", ""),
                    })
        
        return VisualizationView(
            view_type=ViewType.SUBSYSTEM_VIEW,
            title="Subsystem View",
            description="Device subsystem hierarchy",
            data=data,
        )
    
    def _generate_feature_importance_view(self) -> VisualizationView:
        """Generate feature importance view."""
        data = {
            "features": [],
            "importance_scores": {},
        }
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            for feature in features:
                confidence = feature.get("confidence", 0.0)
                feature_type = feature.get("feature_type", "unknown")
                
                data["features"].append({
                    "name": feature.get("name", ""),
                    "type": feature_type,
                    "confidence": confidence,
                })
                
                # Track importance by type
                if feature_type not in data["importance_scores"]:
                    data["importance_scores"][feature_type] = []
                data["importance_scores"][feature_type].append(confidence)
        
        # Calculate average importance by type
        for feature_type, scores in data["importance_scores"].items():
            data["importance_scores"][feature_type] = sum(scores) / len(scores) if scores else 0.0
        
        return VisualizationView(
            view_type=ViewType.FEATURE_IMPORTANCE_VIEW,
            title="Feature Importance View",
            description="Feature importance based on confidence scores",
            data=data,
        )
    
    def _generate_design_graph_view(self) -> VisualizationView:
        """Generate design graph view."""
        data = {
            "nodes": [],
            "edges": [],
            "summary": {},
        }
        
        if self._design_graph:
            data["nodes"] = self._design_graph.get("nodes", [])
            data["edges"] = self._design_graph.get("edges", [])
            data["summary"] = self._design_graph.get("summary", {})
        
        return VisualizationView(
            view_type=ViewType.DESIGN_GRAPH_VIEW,
            title="Design Graph View",
            description="Hierarchical design graph visualization",
            data=data,
        )
    
    def _generate_review_overlay(self) -> VisualizationView:
        """Generate review overlay view."""
        data = {
            "score": 0.0,
            "findings": [],
            "passed": False,
        }
        
        if self._review_result:
            data["score"] = self._review_result.get("score", 0.0)
            data["findings"] = self._review_result.get("findings", [])
            data["passed"] = self._review_result.get("passed", False)
        
        return VisualizationView(
            view_type=ViewType.REVIEW_OVERLAY,
            title="Review Overlay",
            description="Review findings overlaid on design",
            data=data,
        )
    
    def generate_all_views(self) -> dict[str, Any]:
        """Generate all visualization views.
        
        Returns
        -------
        dict with engineering_visualization.json schema.
        """
        views = []
        for view_type in ViewType:
            view = self.generate_view(view_type)
            views.append(view.to_dict())
        
        return {
            "schema": "text-to-gds.engineering-visualization.v1",
            "total_views": len(views),
            "views": views,
        }


def generate_engineering_visualizations(
    geometry_graph: dict[str, Any] | None = None,
    physics_graph: dict[str, Any] | None = None,
    design_graph: dict[str, Any] | None = None,
    topology_result: dict[str, Any] | None = None,
    review_result: dict[str, Any] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """High-level function to generate engineering visualizations.
    
    Parameters
    ----------
    geometry_graph:
        Output of GeometryIntelligenceEngine.
    physics_graph:
        Output of extract_physics_graph().
    design_graph:
        Output of DesignGraphEngine.
    topology_result:
        Output of TopologyReasoningEngine.
    review_result:
        Review committee result.
    output_path:
        Optional path to write the visualization JSON.
    
    Returns
    -------
    dict with engineering_visualization.json schema.
    """
    engine = EngineeringVisualizationEngine()
    engine.load_knowledge(
        geometry_graph=geometry_graph,
        physics_graph=physics_graph,
        design_graph=design_graph,
        topology_result=topology_result,
        review_result=review_result,
    )
    
    result = engine.generate_all_views()
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    
    return result
