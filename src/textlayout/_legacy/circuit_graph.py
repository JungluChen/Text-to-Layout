"""Circuit Graph — netlist graph encoder for quantum circuits.

Converts quantum device netlists into graph representations for:
    - Graph neural network input
    - Circuit similarity search
    - Topology classification
    - Netlist-level design rules

Graph representation:
    Nodes = components (JJ, C, L, CPW, port)
    Edges = connections (nets)
    Node features = component type + parameters
    Edge features = net name + impedance
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from importlib.util import find_spec

HAS_NUMPY = find_spec("numpy") is not None


# ---------------------------------------------------------------------------
# Node / Edge types
# ---------------------------------------------------------------------------

_NODE_TYPES: dict[str, int] = {
    "PORT": 0,
    "JJ": 1,
    "CAPACITOR": 2,
    "INDUCTOR": 3,
    "CPW": 4,
    "RESISTOR": 5,
    "VIA": 6,
    "GROUND": 7,
    "SQUID": 8,
    "IDC": 9,
    "RESONATOR": 10,
    "UNKNOWN": 11,
}


@dataclass
class GraphNode:
    """A node in the circuit graph."""
    node_id: int
    node_type: str                          # JJ, CAPACITOR, PORT, ...
    label: str = ""
    features: list[float] = field(default_factory=list)
    layer: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "features": self.features,
            "layer": self.layer,
        }


@dataclass
class GraphEdge:
    """An edge in the circuit graph."""
    source: int
    target: int
    edge_type: str = "electrical"           # electrical, magnetic, thermal
    net_name: str = ""
    impedance_ohm: float = 0.0
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
            "net_name": self.net_name,
            "impedance_ohm": self.impedance_ohm,
            "weight": self.weight,
        }


# ---------------------------------------------------------------------------
# Circuit Graph
# ---------------------------------------------------------------------------

@dataclass
class CircuitGraph:
    """Graph representation of a quantum circuit."""
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def num_nodes(self) -> int:
        return len(self.nodes)

    @property
    def num_edges(self) -> int:
        return len(self.edges)

    def adjacency_matrix(self) -> list[list[int]]:
        """Return adjacency matrix as nested lists."""
        n = self.num_nodes
        adj = [[0] * n for _ in range(n)]
        for edge in self.edges:
            adj[edge.source][edge.target] = 1
            adj[edge.target][edge.source] = 1
        return adj

    def node_type_counts(self) -> dict[str, int]:
        """Count nodes by type."""
        counts: dict[str, int] = {}
        for node in self.nodes:
            counts[node.node_type] = counts.get(node.node_type, 0) + 1
        return counts

    def degree_sequence(self) -> list[int]:
        """Return sorted degree sequence."""
        n = self.num_nodes
        degrees = [0] * n
        for edge in self.edges:
            degrees[edge.source] += 1
            degrees[edge.target] += 1
        return sorted(degrees, reverse=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "num_nodes": self.num_nodes,
            "num_edges": self.num_edges,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "node_type_counts": self.node_type_counts(),
            "metadata": self.metadata,
        }

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Graph builder from sidecar / netlist
# ---------------------------------------------------------------------------

class CircuitGraphBuilder:
    """Build a circuit graph from a sidecar JSON or netlist.

    Usage::

        builder = CircuitGraphBuilder()
        graph = builder.from_sidecar(sidecar_dict)
        graph = builder.from_netlist(netlist_dict)
    """

    def from_sidecar(self, sidecar: dict[str, Any]) -> CircuitGraph:
        """Build graph from a semantic sidecar."""
        graph = CircuitGraph(
            name=sidecar.get("name", "layout"),
            metadata={"source": "sidecar"},
        )

        # Add port nodes
        ports = sidecar.get("ports", [])
        for i, port in enumerate(ports):
            center = port.get("center", [0, 0])
            graph.nodes.append(GraphNode(
                node_id=i,
                node_type="PORT",
                label=port.get("name", f"port_{i}"),
                features=[
                    center[0] / 1000,  # normalised coordinates
                    center[1] / 1000,
                    port.get("width", 0) / 100,
                ],
                layer=port.get("layer", [0, 0])[0] if isinstance(port.get("layer"), list) else 0,
            ))

        # Add layer nodes
        layers = sidecar.get("layers", [])
        port_count = len(ports)
        for i, layer in enumerate(layers):
            graph.nodes.append(GraphNode(
                node_id=port_count + i,
                node_type=self._classify_layer(layer.get("name", "")),
                label=layer.get("name", f"layer_{i}"),
                features=[
                    layer.get("width_um", 0) / 100,
                    layer.get("thickness_um", 0) / 10,
                ],
                layer=layer.get("layer", [0, 0])[0] if isinstance(layer.get("layer"), list) else 0,
            ))

        # Connect ports to their layers
        for i, port in enumerate(ports):
            port_layer = port.get("layer", [3, 0])
            for j, layer in enumerate(layers):
                if layer.get("layer") == port_layer:
                    graph.edges.append(GraphEdge(
                        source=i,
                        target=port_count + j,
                        net_name=port.get("name", ""),
                    ))

        # Connect adjacent layers (vertical stack)
        for j in range(len(layers) - 1):
            graph.edges.append(GraphEdge(
                source=port_count + j,
                target=port_count + j + 1,
                edge_type="stack",
                net_name="via" if "via" in layers[j + 1].get("name", "").lower() else "adjacent",
            ))

        return graph

    def from_netlist(self, netlist: dict[str, Any]) -> CircuitGraph:
        """Build graph from a SPICE-like netlist dict."""
        graph = CircuitGraph(
            name=netlist.get("name", "netlist"),
            metadata={"source": "netlist"},
        )

        node_map: dict[str, int] = {}
        components = netlist.get("components", [])

        node_id = 0
        for comp in components:
            comp_type = comp.get("type", "UNKNOWN").upper()
            if comp_type not in _NODE_TYPES:
                comp_type = "UNKNOWN"

            graph.nodes.append(GraphNode(
                node_id=node_id,
                node_type=comp_type,
                label=comp.get("name", f"comp_{node_id}"),
                features=[
                    comp.get("value", 0),
                    comp.get("area_um2", 0),
                    comp.get("width_um", 0),
                ],
            ))

            # Connect component terminals
            terminals = comp.get("terminals", [])
            for t in terminals:
                if t not in node_map:
                    node_map[t] = len(graph.nodes)
                    graph.nodes.append(GraphNode(
                        node_id=node_map[t],
                        node_type="PORT",
                        label=t,
                    ))
                graph.edges.append(GraphEdge(
                    source=node_id,
                    target=node_map[t],
                    net_name=t,
                ))

            node_id += 1

        return graph

    def _classify_layer(self, name: str) -> str:
        name_lower = name.lower()
        if "jj" in name_lower or "junction" in name_lower:
            return "JJ"
        if "cap" in name_lower or "idc" in name_lower:
            return "CAPACITOR"
        if "ind" in name_lower:
            return "INDUCTOR"
        if "cpw" in name_lower or "waveguide" in name_lower:
            return "CPW"
        if "via" in name_lower:
            return "VIA"
        if "gnd" in name_lower or "ground" in name_lower:
            return "GROUND"
        if "squid" in name_lower:
            return "SQUID"
        return "UNKNOWN"


# ---------------------------------------------------------------------------
# Graph encoder (numpy, no torch required)
# ---------------------------------------------------------------------------

class CircuitGraphEncoder:
    """Encode circuit graphs into fixed-size vectors using graph statistics.

    For full GNN support, see the torch version when available.
    """

    def __init__(self, max_nodes: int = 64):
        self.max_nodes = max_nodes

    def encode(self, graph: CircuitGraph) -> list[float]:
        """Encode graph into a fixed-size feature vector."""
        features: list[float] = []

        # Basic stats
        features.append(graph.num_nodes / self.max_nodes)
        features.append(graph.num_edges / self.max_nodes)
        features.append(graph.num_edges / max(graph.num_nodes, 1))  # avg degree

        # Node type distribution
        counts = graph.node_type_counts()
        for ntype in _NODE_TYPES:
            features.append(counts.get(ntype, 0) / max(graph.num_nodes, 1))

        # Degree sequence stats
        deg = graph.degree_sequence()
        if deg:
            features.append(max(deg) / max(graph.num_nodes, 1))
            features.append(sum(deg) / len(deg) / max(graph.num_nodes, 1))
        else:
            features.extend([0.0, 0.0])

        # Pad to fixed size
        while len(features) < 64:
            features.append(0.0)

        return features[:64]

    def batch_encode(self, graphs: list[CircuitGraph]) -> list[list[float]]:
        return [self.encode(g) for g in graphs]
