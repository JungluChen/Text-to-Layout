"""Literature Knowledge Graph Engine - manages literature devices and comparisons.

This engine provides a knowledge graph of literature devices and enables
feature-by-feature comparison with generated designs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout._legacy.literature_graph.devices import LiteratureDevice, DeviceTopology
from textlayout._legacy.literature_graph.comparison import compare_features


class LiteratureKnowledgeGraph:
    """Main engine for literature knowledge graph.
    
    This engine manages literature devices and enables comparison
    with generated designs.
    """
    
    def __init__(self) -> None:
        """Initialize the literature knowledge graph."""
        self._devices: dict[str, LiteratureDevice] = {}
        self._load_default_devices()
    
    def _load_default_devices(self) -> None:
        """Load real literature devices from the paper knowledge base."""
        from textlayout._legacy.literature_graph.paper_kb import ALL_LITERATURE_DEVICES
        for device in ALL_LITERATURE_DEVICES:
            self._devices[device.id] = device
    
    def add_device(self, device: LiteratureDevice) -> None:
        """Add a literature device to the knowledge graph."""
        self._devices[device.id] = device
    
    def get_device(self, device_id: str) -> LiteratureDevice | None:
        """Get a device by ID."""
        return self._devices.get(device_id)
    
    def get_devices_by_topology(self, topology: DeviceTopology) -> list[LiteratureDevice]:
        """Get devices by topology type."""
        return [d for d in self._devices.values() if d.topology == topology]
    
    def compare_with_generated(
        self,
        generated_device: dict[str, Any],
        literature_device_id: str | None = None,
    ) -> dict[str, Any]:
        """Compare generated device with literature device.
        
        Parameters
        ----------
        generated_device:
            Generated device data.
        literature_device_id:
            Optional specific literature device ID. If None, find best match.
        
        Returns
        -------
        dict with literature_comparison.json schema.
        """
        # Find literature device to compare with
        if literature_device_id:
            literature_device = self._devices.get(literature_device_id)
            if literature_device is None:
                return {"error": f"Literature device {literature_device_id} not found"}
        else:
            # Find best matching literature device
            literature_device = self._find_best_match(generated_device)
            if literature_device is None:
                return {"error": "No matching literature device found"}
        
        # Perform comparison
        comparison = compare_features(generated_device, literature_device)
        
        return {
            "schema": "text-to-gds.literature-comparison.v1",
            "generated_device": generated_device.get("name", "Unknown"),
            "literature_device": literature_device.name,
            "literature_reference": literature_device.reference,
            "comparison": comparison.to_dict(),
        }
    
    def _find_best_match(self, generated_device: dict[str, Any]) -> LiteratureDevice | None:
        """Find the best matching literature device."""
        generated_topology = generated_device.get("topology", "unknown")
        
        # First try exact topology match
        for device in self._devices.values():
            if device.topology.value == generated_topology:
                return device
        
        # If no exact match, return first device
        if self._devices:
            return next(iter(self._devices.values()))
        
        return None
    
    def get_knowledge_graph(self) -> dict[str, Any]:
        """Get the complete knowledge graph."""
        devices = [d.to_dict() for d in self._devices.values()]
        
        # Group by topology
        devices_by_topology: dict[str, list[dict[str, Any]]] = {}
        for device in devices:
            topology = device["topology"]
            if topology not in devices_by_topology:
                devices_by_topology[topology] = []
            devices_by_topology[topology].append(device)
        
        return {
            "schema": "text-to-gds.literature-knowledge-graph.v1",
            "total_devices": len(devices),
            "devices": devices,
            "devices_by_topology": devices_by_topology,
        }


def load_literature_knowledge_graph(
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """High-level function to load the literature knowledge graph.
    
    Parameters
    ----------
    output_path:
        Optional path to write the knowledge graph JSON.
    
    Returns
    -------
    dict with literature knowledge graph.
    """
    engine = LiteratureKnowledgeGraph()
    knowledge_graph = engine.get_knowledge_graph()
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(knowledge_graph, indent=2), encoding="utf-8")
    
    return knowledge_graph
