"""Design Graph Engine - orchestrates hierarchical engineering representation.

This engine builds a design graph from geometry features and physics graph,
organizing them into a hierarchical structure that represents the engineering
meaning of the layout.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout._legacy.design_graph.edges import DesignEdge, EdgeType
from textlayout._legacy.design_graph.nodes import (
    DesignNode,
    DeviceNode,
    SubsystemNode,
    FunctionalBlockNode,
)


class DesignGraphEngine:
    """Main engine for building design graphs.
    
    This engine takes geometry features and physics graph data and builds
    a hierarchical design graph representing the engineering structure.
    """
    
    def __init__(self) -> None:
        """Initialize the design graph engine."""
        self._nodes: dict[str, DesignNode] = {}
        self._edges: list[DesignEdge] = []
        self._root_id: str | None = None
    
    def build_design_graph(
        self,
        geometry_graph: dict[str, Any] | None = None,
        physics_graph: dict[str, Any] | None = None,
        topology_result: dict[str, Any] | None = None,
        sidecar: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a design graph from geometry features and physics graph.
        
        Parameters
        ----------
        geometry_graph:
            Output of GeometryIntelligenceEngine.
        physics_graph:
            Output of extract_physics_graph().
        topology_result:
            Output of recognize_topology().
        sidecar:
            Optional sidecar metadata.
        
        Returns
        -------
        dict with design_graph.json schema.
        """
        self._nodes = {}
        self._edges = []
        
        # Create root device node
        device_node = self._create_device_node(
            topology_result=topology_result,
            sidecar=sidecar,
        )
        self._nodes[device_node.id] = device_node
        self._root_id = device_node.id
        
        # Create subsystem nodes from physics graph
        if physics_graph:
            self._create_subsystems_from_physics_graph(physics_graph, device_node.id)
        
        # Create functional blocks from geometry features
        if geometry_graph:
            self._create_functional_blocks_from_geometry(geometry_graph, device_node.id)
        
        # Create edges for containment hierarchy
        self._create_containment_edges()
        
        # Build the design graph
        design_graph = self._build_design_graph_dict()
        
        return design_graph
    
    def _create_device_node(
        self,
        topology_result: dict[str, Any] | None,
        sidecar: dict[str, Any] | None,
    ) -> DeviceNode:
        """Create the root device node."""
        device_type = "unknown"
        operating_frequency = None
        target_specs = {}
        topology_confidence = 0.0
        
        if topology_result:
            device_type = topology_result.get("detected_device", "unknown")
            topology_confidence = topology_result.get("confidence", 0.0)
        
        if sidecar:
            info = sidecar.get("info", {})
            operating_frequency = info.get("operating_frequency_ghz")
            target_specs = info.get("target_specifications", {})
        
        return DeviceNode(
            name=f"Device_{device_type}",
            description=f"Top-level {device_type} device",
            device_type=device_type,
            operating_frequency_ghz=operating_frequency,
            target_specifications=target_specs,
            topology_confidence=topology_confidence,
        )
    
    def _create_subsystems_from_physics_graph(
        self,
        physics_graph: dict[str, Any],
        device_id: str,
    ) -> None:
        """Create subsystem nodes from physics graph."""
        # Group nodes by type to create subsystems
        node_groups: dict[str, list[dict[str, Any]]] = {}
        for node in physics_graph.get("nodes", []):
            node_type = node.get("type", "")
            if node_type not in node_groups:
                node_groups[node_type] = []
            node_groups[node_type].append(node)
        
        # Create subsystems for each node type group
        for node_type, nodes in node_groups.items():
            if not nodes:
                continue
            
            # Determine subsystem type and function
            subsystem_type, function = self._determine_subsystem_type(node_type, nodes)
            
            # Create subsystem node
            subsystem = SubsystemNode(
                name=f"{subsystem_type}_{len(self._nodes)}",
                description=f"{subsystem_type} subsystem",
                parent_id=device_id,
                subsystem_type=subsystem_type,
                function=function,
                key_parameters=self._extract_key_parameters(nodes),
            )
            self._nodes[subsystem.id] = subsystem
            
            # Create functional block nodes for each physics node
            for node in nodes:
                block = self._create_functional_block_from_physics_node(node, subsystem.id)
                self._nodes[block.id] = block
    
    def _determine_subsystem_type(
        self,
        node_type: str,
        nodes: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """Determine subsystem type and function from node type."""
        if node_type == "josephson_junction":
            return "SQUID", "nonlinear_element"
        elif node_type == "capacitor":
            return "Capacitor", "energy_storage"
        elif node_type == "transmission_line":
            return "Resonator", "frequency_selective"
        elif node_type == "port":
            return "Ports", "signal_coupling"
        elif node_type == "ground":
            return "Ground", "grounding"
        else:
            return node_type.replace("_", " ").title(), "unknown"
    
    def _extract_key_parameters(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """Extract key parameters from physics nodes."""
        params = {}
        for node in nodes:
            node_params = node.get("physics_parameters", {})
            for key, value in node_params.items():
                if isinstance(value, dict) and "value" in value:
                    params[key] = value["value"]
        return params
    
    def _create_functional_block_from_physics_node(
        self,
        node: dict[str, Any],
        subsystem_id: str,
    ) -> FunctionalBlockNode:
        """Create a functional block from a physics graph node."""
        node_type = node.get("type", "")
        name = node.get("name", "")
        geometry = node.get("geometry", {})
        params = node.get("physics_parameters", {})
        
        # Determine block type and electrical role
        block_type, electrical_role = self._determine_block_type(node_type, params)
        
        # Extract dimensions
        dimensions = self._extract_dimensions(geometry, params)
        
        # Extract engineering properties
        engineering_properties = self._extract_engineering_properties(node_type, params)
        
        return FunctionalBlockNode(
            name=name or f"{block_type}_{len(self._nodes)}",
            description=f"{block_type} functional block",
            parent_id=subsystem_id,
            block_type=block_type,
            electrical_role=electrical_role,
            dimensions=dimensions,
            engineering_properties=engineering_properties,
        )
    
    def _determine_block_type(
        self,
        node_type: str,
        params: dict[str, Any],
    ) -> tuple[str, str]:
        """Determine block type and electrical role."""
        if node_type == "josephson_junction":
            return "JJ", "nonlinear_element"
        elif node_type == "capacitor":
            finger_count = params.get("finger_count", {})
            if isinstance(finger_count, dict) and finger_count.get("value", 0) > 0:
                return "IDC", "capacitor"
            else:
                return "Capacitor_Paddle", "capacitor"
        elif node_type == "transmission_line":
            return "CPW", "transmission_line"
        elif node_type == "port":
            return "Port", "signal_coupling"
        elif node_type == "ground":
            return "Ground_Plane", "grounding"
        else:
            return node_type.replace("_", " ").title(), "unknown"
    
    def _extract_dimensions(
        self,
        geometry: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract dimensions from geometry and parameters."""
        dimensions = {}
        
        # Extract from geometry
        bbox = geometry.get("bbox_um", [])
        if bbox and len(bbox) >= 4:
            dimensions["bounding_box_um"] = bbox
            dimensions["width_um"] = bbox[2] - bbox[0]
            dimensions["height_um"] = bbox[3] - bbox[1]
            dimensions["area_um2"] = dimensions["width_um"] * dimensions["height_um"]
        
        # Extract from parameters
        for key, value in params.items():
            if isinstance(value, dict) and "value" in value:
                dimensions[key] = value["value"]
        
        return dimensions
    
    def _extract_engineering_properties(
        self,
        node_type: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract engineering properties from parameters."""
        properties = {}
        
        if node_type == "josephson_junction":
            ic = params.get("critical_current", {})
            if isinstance(ic, dict) and "value" in ic:
                properties["critical_current_ua"] = ic["value"]
            lj = params.get("josephson_inductance", {})
            if isinstance(lj, dict) and "value" in lj:
                properties["josephson_inductance_h"] = lj["value"]
        
        elif node_type == "capacitor":
            cap = params.get("capacitance", {})
            if isinstance(cap, dict) and "value" in cap:
                properties["capacitance_f"] = cap["value"]
            finger_count = params.get("finger_count", {})
            if isinstance(finger_count, dict) and "value" in finger_count:
                properties["finger_count"] = finger_count["value"]
        
        elif node_type == "transmission_line":
            z0 = params.get("z0", {})
            if isinstance(z0, dict) and "value" in z0:
                properties["characteristic_impedance_ohm"] = z0["value"]
            length = params.get("length", {})
            if isinstance(length, dict) and "value" in length:
                properties["electrical_length_um"] = length["value"]
        
        return properties
    
    def _create_functional_blocks_from_geometry(
        self,
        geometry_graph: dict[str, Any],
        device_id: str,
    ) -> None:
        """Create functional blocks from geometry features."""
        for feature_data in geometry_graph.get("features", []):
            feature_type = feature_data.get("feature_type", "")
            name = feature_data.get("name", "")
            dimensions = feature_data.get("dimensions", {})
            engineering_properties = feature_data.get("engineering_properties", {})
            
            # Create functional block for each geometry feature
            block = FunctionalBlockNode(
                name=name or f"{feature_type}_{len(self._nodes)}",
                description=f"{feature_type} functional block",
                parent_id=device_id,
                block_type=feature_type,
                electrical_role=engineering_properties.get("type", "unknown"),
                dimensions=dimensions,
                engineering_properties=engineering_properties,
            )
            self._nodes[block.id] = block
    
    def _create_containment_edges(self) -> None:
        """Create containment edges for the hierarchy."""
        for node in self._nodes.values():
            if node.parent_id and node.parent_id in self._nodes:
                edge = DesignEdge(
                    edge_type=EdgeType.CONTAINS,
                    source_id=node.parent_id,
                    target_id=node.id,
                    confidence=node.confidence,
                )
                self._edges.append(edge)
    
    def _build_design_graph_dict(self) -> dict[str, Any]:
        """Build the design graph dictionary."""
        nodes_list = [node.to_dict() for node in self._nodes.values()]
        edges_list = [edge.to_dict() for edge in self._edges]
        
        # Build summary
        summary = {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "nodes_by_type": self._count_nodes_by_type(),
            "root_id": self._root_id,
        }
        
        return {
            "schema": "text-to-gds.design-graph.v1",
            "nodes": nodes_list,
            "edges": edges_list,
            "summary": summary,
        }
    
    def _count_nodes_by_type(self) -> dict[str, int]:
        """Count nodes by type."""
        counts: dict[str, int] = {}
        for node in self._nodes.values():
            node_type = node.node_type.value
            counts[node_type] = counts.get(node_type, 0) + 1
        return counts
    
    def get_node_by_id(self, node_id: str) -> DesignNode | None:
        """Get a node by its ID."""
        return self._nodes.get(node_id)
    
    def get_children(self, node_id: str) -> list[DesignNode]:
        """Get all children of a node."""
        return [
            node for node in self._nodes.values()
            if node.parent_id == node_id
        ]
    
    def get_parent(self, node_id: str) -> DesignNode | None:
        """Get the parent of a node."""
        node = self._nodes.get(node_id)
        if node and node.parent_id:
            return self._nodes.get(node.parent_id)
        return None
    
    def get_subtree(self, node_id: str) -> dict[str, Any]:
        """Get the subtree rooted at a node."""
        node = self._nodes.get(node_id)
        if node is None:
            return {}
        
        result = {
            "node": node.to_dict(),
            "children": [],
        }
        
        for child in self.get_children(node_id):
            child_subtree = self.get_subtree(child.id)
            result["children"].append(child_subtree)
        
        return result


def build_design_graph(
    geometry_graph: dict[str, Any] | None = None,
    physics_graph: dict[str, Any] | None = None,
    topology_result: dict[str, Any] | None = None,
    sidecar: dict[str, Any] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """High-level function to build a design graph.
    
    Parameters
    ----------
    geometry_graph:
        Output of GeometryIntelligenceEngine.
    physics_graph:
        Output of extract_physics_graph().
    topology_result:
        Output of recognize_topology().
    sidecar:
        Optional sidecar metadata.
    output_path:
        Optional path to write the design graph JSON.
    
    Returns
    -------
    dict with design_graph.json schema.
    """
    engine = DesignGraphEngine()
    design_graph = engine.build_design_graph(
        geometry_graph=geometry_graph,
        physics_graph=physics_graph,
        topology_result=topology_result,
        sidecar=sidecar,
    )
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(design_graph, indent=2), encoding="utf-8")
    
    return design_graph
