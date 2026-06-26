"""Dependency Graph for performance-geometry-process mapping.

This module builds a directed acyclic graph (DAG) showing how performance
metrics depend on physics parameters, which depend on geometry, which depends
on process parameters, which depend on mask layout.
"""

from typing import Any

import networkx as nx

from text_to_gds.dependency_graph.types import (
    DependencyNode,
    DependencyEdge,
    DependencyLayer,
    CausalPath,
)


class DependencyGraph:
    """Builds and analyzes dependency graphs for quantum devices.
    
    The dependency graph maps the causal chain from mask layout through
    process, geometry, physics, to performance metrics. This enables
    answering questions like "Why did the frequency shift?" by tracing
    the dependency chain.
    """
    
    def __init__(self) -> None:
        """Initialize the dependency graph."""
        self._graph = nx.DiGraph()
        self._nodes: dict[str, DependencyNode] = {}
        self._edges: list[DependencyEdge] = []
    
    def build_from_design(
        self,
        geometry_graph: dict[str, Any] | None = None,
        physics_graph: dict[str, Any] | None = None,
        topology: dict[str, Any] | None = None,
        process: dict[str, Any] | None = None,
    ) -> None:
        """Build dependency graph from design data.
        
        Args:
            geometry_graph: Geometry intelligence output.
            physics_graph: Physics graph with parameters.
            topology: Topology recognition output.
            process: Process definition with fabrication parameters.
        """
        # Add process nodes
        self._add_process_nodes(process)
        
        # Add geometry nodes
        self._add_geometry_nodes(geometry_graph)
        
        # Add physics nodes
        self._add_physics_nodes(physics_graph)
        
        # Add performance nodes
        self._add_performance_nodes(physics_graph)
        
        # Add edges based on physical relationships
        self._add_physical_relationships()
    
    def _add_process_nodes(self, process: dict[str, Any] | None) -> None:
        """Add process-related nodes to the graph."""
        if not process:
            return
        
        # Layer thickness
        if "metal_height" in process:
            node = DependencyNode(
                id="process_metal_height",
                name="Metal Height",
                layer=DependencyLayer.PROCESS,
                value=process["metal_height"],
                unit="m",
                description="Thickness of superconducting metal layer",
                source="process",
            )
            self._add_node(node)
        
        # Substrate permittivity
        if "substrate_permittivity" in process:
            node = DependencyNode(
                id="process_epsilon_r",
                name="Substrate Permittivity",
                layer=DependencyLayer.PROCESS,
                value=process["substrate_permittivity"],
                unit="",
                description="Relative permittivity of substrate",
                source="process",
            )
            self._add_node(node)
        
        # JJ critical current density
        if "critical_current_density" in process:
            node = DependencyNode(
                id="process_jc",
                name="Critical Current Density",
                layer=DependencyLayer.PROCESS,
                value=process["critical_current_density"],
                unit="A/m^2",
                description="Josephson junction critical current density",
                source="process",
            )
            self._add_node(node)
        
        # Lithography bias
        if "lithography_bias" in process:
            node = DependencyNode(
                id="process_litho_bias",
                name="Lithography Bias",
                layer=DependencyLayer.PROCESS,
                value=process["lithography_bias"],
                unit="m",
                description="Systematic bias from lithography process",
                source="process",
            )
            self._add_node(node)
    
    def _add_geometry_nodes(self, geometry_graph: dict[str, Any] | None) -> None:
        """Add geometry-related nodes to the graph."""
        if not geometry_graph:
            return
        
        for feature in geometry_graph.get("features", []):
            feature_type = feature.get("feature_type", "")
            feature_id = feature.get("id", "")
            dimensions = feature.get("dimensions", {})
            
            if feature_type == "idc":
                # IDC finger length
                if "finger_length" in dimensions:
                    node = DependencyNode(
                        id=f"geom_{feature_id}_finger_length",
                        name="IDC Finger Length",
                        layer=DependencyLayer.GEOMETRY,
                        value=dimensions["finger_length"],
                        unit="m",
                        description="Length of IDC fingers",
                        source="geometry_graph",
                    )
                    self._add_node(node)
                
                # IDC finger width
                if "finger_width" in dimensions:
                    node = DependencyNode(
                        id=f"geom_{feature_id}_finger_width",
                        name="IDC Finger Width",
                        layer=DependencyLayer.GEOMETRY,
                        value=dimensions["finger_width"],
                        unit="m",
                        description="Width of IDC fingers",
                        source="geometry_graph",
                    )
                    self._add_node(node)
                
                # IDC gap
                if "gap" in dimensions:
                    node = DependencyNode(
                        id=f"geom_{feature_id}_gap",
                        name="IDC Gap",
                        layer=DependencyLayer.GEOMETRY,
                        value=dimensions["gap"],
                        unit="m",
                        description="Gap between IDC fingers",
                        source="geometry_graph",
                    )
                    self._add_node(node)
            
            elif feature_type == "cpw":
                # CPW center width
                if "width" in dimensions:
                    node = DependencyNode(
                        id=f"geom_{feature_id}_width",
                        name="CPW Center Width",
                        layer=DependencyLayer.GEOMETRY,
                        value=dimensions["width"],
                        unit="m",
                        description="Width of CPW center conductor",
                        source="geometry_graph",
                    )
                    self._add_node(node)
                
                # CPW gap
                if "gap" in dimensions:
                    node = DependencyNode(
                        id=f"geom_{feature_id}_gap",
                        name="CPW Gap",
                        layer=DependencyLayer.GEOMETRY,
                        value=dimensions["gap"],
                        unit="m",
                        description="Gap between CPW center and ground",
                        source="geometry_graph",
                    )
                    self._add_node(node)
            
            elif feature_type == "josephson_junction":
                # JJ area
                if "area" in dimensions:
                    node = DependencyNode(
                        id=f"geom_{feature_id}_area",
                        name="JJ Area",
                        layer=DependencyLayer.GEOMETRY,
                        value=dimensions["area"],
                        unit="m^2",
                        description="Josephson junction area",
                        source="geometry_graph",
                    )
                    self._add_node(node)
            
            elif feature_type == "resonator":
                # Resonator length
                if "length" in dimensions:
                    node = DependencyNode(
                        id=f"geom_{feature_id}_length",
                        name="Resonator Length",
                        layer=DependencyLayer.GEOMETRY,
                        value=dimensions["length"],
                        unit="m",
                        description="Length of resonator",
                        source="geometry_graph",
                    )
                    self._add_node(node)
    
    def _add_physics_nodes(self, physics_graph: dict[str, Any] | None) -> None:
        """Add physics-related nodes to the graph."""
        if not physics_graph:
            return
        
        for node_data in physics_graph.get("nodes", []):
            node_type = node_data.get("type", "")
            node_id = node_data.get("id", "")
            params = node_data.get("parameters", {})
            
            if node_type == "josephson_junction":
                # Critical current
                ic = params.get("critical_current", {})
                if ic and "value" in ic:
                    node = DependencyNode(
                        id=f"physics_{node_id}_ic",
                        name="Critical Current",
                        layer=DependencyLayer.PHYSICS,
                        value=ic["value"],
                        unit=ic.get("unit", "A"),
                        description="Josephson junction critical current",
                        source="physics_graph",
                    )
                    self._add_node(node)
                
                # Josephson inductance
                lj = params.get("inductance", {})
                if lj and "value" in lj:
                    node = DependencyNode(
                        id=f"physics_{node_id}_lj",
                        name="Josephson Inductance",
                        layer=DependencyLayer.PHYSICS,
                        value=lj["value"],
                        unit=lj.get("unit", "H"),
                        description="Josephson junction inductance",
                        source="physics_graph",
                    )
                    self._add_node(node)
            
            elif node_type == "resonator":
                # Resonance frequency
                freq = params.get("frequency", {})
                if freq and "value" in freq:
                    node = DependencyNode(
                        id=f"physics_{node_id}_frequency",
                        name="Resonance Frequency",
                        layer=DependencyLayer.PHYSICS,
                        value=freq["value"],
                        unit=freq.get("unit", "Hz"),
                        description="Resonator resonance frequency",
                        source="physics_graph",
                    )
                    self._add_node(node)
                
                # Quality factor
                q = params.get("quality_factor", {})
                if q and "value" in q:
                    node = DependencyNode(
                        id=f"physics_{node_id}_q",
                        name="Quality Factor",
                        layer=DependencyLayer.PHYSICS,
                        value=q["value"],
                        unit="",
                        description="Resonator quality factor",
                        source="physics_graph",
                    )
                    self._add_node(node)
            
            elif node_type == "capacitor":
                # Capacitance
                cap = params.get("capacitance", {})
                if cap and "value" in cap:
                    node = DependencyNode(
                        id=f"physics_{node_id}_cap",
                        name="Capacitance",
                        layer=DependencyLayer.PHYSICS,
                        value=cap["value"],
                        unit=cap.get("unit", "F"),
                        description="Lumped capacitance",
                        source="physics_graph",
                    )
                    self._add_node(node)
    
    def _add_performance_nodes(self, physics_graph: dict[str, Any] | None) -> None:
        """Add performance-related nodes to the graph."""
        if not physics_graph:
            return
        
        # Add common performance metrics
        # These would be populated from solver results or measurements
        pass
    
    def _add_physical_relationships(self) -> None:
        """Add edges based on known physical relationships."""
        # JJ area → Critical current
        for node_id, node in self._nodes.items():
            if node.layer == DependencyLayer.GEOMETRY and "area" in node.name.lower():
                # Find corresponding physics node
                for physics_id, physics_node in self._nodes.items():
                    if (physics_node.layer == DependencyLayer.PHYSICS and 
                        "critical current" in physics_node.name.lower()):
                        edge = DependencyEdge(
                            source_id=node_id,
                            target_id=physics_id,
                            relationship="determines",
                            description="JJ area determines critical current via Jc × A",
                            formula="Ic = Jc × A",
                        )
                        self._add_edge(edge)
            
            # CPW dimensions → Impedance
            if node.layer == DependencyLayer.GEOMETRY and "width" in node.name.lower():
                for physics_id, physics_node in self._nodes.items():
                    if (physics_node.layer == DependencyLayer.PHYSICS and 
                        "impedance" in physics_node.name.lower()):
                        edge = DependencyEdge(
                            source_id=node_id,
                            target_id=physics_id,
                            relationship="determines",
                            description="CPW dimensions determine impedance",
                            formula="Z0 = f(w, g, h, εr)",
                        )
                        self._add_edge(edge)
            
            # Critical current → Josephson inductance
            if node.layer == DependencyLayer.PHYSICS and "critical current" in node.name.lower():
                for physics_id, physics_node in self._nodes.items():
                    if (physics_node.layer == DependencyLayer.PHYSICS and 
                        "inductance" in physics_node.name.lower()):
                        edge = DependencyEdge(
                            source_id=node_id,
                            target_id=physics_id,
                            relationship="determines",
                            description="Critical current determines Josephson inductance",
                            formula="Lj = Φ0 / (2π × Ic)",
                        )
                        self._add_edge(edge)
    
    def _add_node(self, node: DependencyNode) -> None:
        """Add a node to the graph."""
        self._nodes[node.id] = node
        self._graph.add_node(node.id, layer=node.layer.value)
    
    def _add_edge(self, edge: DependencyEdge) -> None:
        """Add an edge to the graph."""
        self._edges.append(edge)
        self._graph.add_edge(
            edge.source_id,
            edge.target_id,
            relationship=edge.relationship,
            sensitivity=edge.sensitivity,
        )
    
    def get_causal_path(
        self,
        source_id: str,
        target_id: str,
    ) -> CausalPath | None:
        """Find the causal path between two nodes.
        
        Args:
            source_id: ID of the source node (cause).
            target_id: ID of the target node (effect).
            
        Returns:
            CausalPath if a path exists, None otherwise.
        """
        try:
            path = nx.shortest_path(self._graph, source_id, target_id)
        except nx.NetworkXNoPath:
            return None
        
        # Build causal path
        nodes = [self._nodes[nid] for nid in path]
        edges = []
        for i in range(len(path) - 1):
            for edge in self._edges:
                if edge.source_id == path[i] and edge.target_id == path[i + 1]:
                    edges.append(edge)
                    break
        
        # Calculate total sensitivity
        total_sensitivity = 1.0
        for edge in edges:
            if edge.sensitivity != 0:
                total_sensitivity *= edge.sensitivity
        
        # Generate description
        description = self._generate_path_description(nodes, edges)
        
        return CausalPath(
            nodes=nodes,
            edges=edges,
            total_sensitivity=total_sensitivity,
            description=description,
        )
    
    def get_nodes_by_layer(self, layer: DependencyLayer) -> list[DependencyNode]:
        """Get all nodes in a specific layer."""
        return [
            node for node in self._nodes.values()
            if node.layer == layer
        ]
    
    def get_dependents(self, node_id: str) -> list[DependencyNode]:
        """Get all nodes that depend on the given node."""
        dependents = []
        for successor in self._graph.successors(node_id):
            dependents.append(self._nodes[successor])
        return dependents
    
    def get_dependencies(self, node_id: str) -> list[DependencyNode]:
        """Get all nodes that the given node depends on."""
        dependencies = []
        for predecessor in self._graph.predecessors(node_id):
            dependencies.append(self._nodes[predecessor])
        return dependencies
    
    def explain_shift(
        self,
        metric_id: str,
        original_value: float,
        new_value: float,
    ) -> list[CausalPath]:
        """Explain why a performance metric shifted.
        
        Args:
            metric_id: ID of the metric that shifted.
            original_value: Original value of the metric.
            new_value: New value of the metric.
            
        Returns:
            List of causal paths that could explain the shift.
        """
        paths = []
        
        # Find all nodes that could affect this metric
        for node_id in self._graph.predecessors(metric_id):
            path = self.get_causal_path(node_id, metric_id)
            if path:
                paths.append(path)
        
        # Sort by sensitivity (most impactful first)
        paths.sort(key=lambda p: abs(p.total_sensitivity), reverse=True)
        
        return paths
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "nodes": {nid: node.to_dict() for nid, node in self._nodes.items()},
            "edges": [edge.to_dict() for edge in self._edges],
            "layers": {
                layer.value: [n.to_dict() for n in self.get_nodes_by_layer(layer)]
                for layer in DependencyLayer
            },
        }
    
    def _generate_path_description(
        self,
        nodes: list[DependencyNode],
        edges: list[DependencyEdge],
    ) -> str:
        """Generate human-readable description of a causal path."""
        if not nodes:
            return "No path found."
        
        parts = []
        for i, node in enumerate(nodes):
            parts.append(f"{node.name}")
            if i < len(edges):
                parts.append(f"--[{edges[i].relationship}]-->")
        
        return " ".join(parts)
