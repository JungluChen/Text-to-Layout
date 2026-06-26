"""Device Classifier for quantum device type recognition.

This module classifies quantum devices based on their geometry, topology,
and physics characteristics. It provides evidence-based classification
with confidence scores and alternative hypotheses.
"""

from typing import Any

from text_to_gds.device_classifier.types import (
    DeviceType,
    ClassificationResult,
    ClassificationEvidence,
    AlternativeHypothesis,
)


class DeviceClassifier:
    """Classifies quantum devices based on geometry, topology, and physics.
    
    The classifier uses a rule-based approach with evidence accumulation.
    Each device type has a set of required and optional features that are
    checked against the input data.
    """
    
    def __init__(self) -> None:
        """Initialize the device classifier."""
        self._classifiers: dict[DeviceType, Any] = {
            DeviceType.POCKET_TRANSMON: self._classify_pocket_transmon,
            DeviceType.XMON: self._classify_xmon,
            DeviceType.CONCENTRIC_TRANSMON: self._classify_concentric_transmon,
            DeviceType.FLUXONIUM: self._classify_fluxonium,
            DeviceType.LUMPED_JPA: self._classify_lumped_jpa,
            DeviceType.QUARTER_WAVE_JPA: self._classify_quarter_wave_jpa,
            DeviceType.TWPA: self._classify_twpa,
            DeviceType.IDC_RESONATOR: self._classify_idc_resonator,
            DeviceType.CPW_RESONATOR: self._classify_cpw_resonator,
            DeviceType.CALIBRATION_CHIP: self._classify_calibration_chip,
            DeviceType.JJ_ARRAY: self._classify_jj_array,
        }
    
    def classify(
        self,
        geometry_graph: dict[str, Any] | None = None,
        physics_graph: dict[str, Any] | None = None,
        topology: dict[str, Any] | None = None,
        sidecar: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        """Classify a quantum device based on available data.
        
        Args:
            geometry_graph: Geometry intelligence output with features.
            physics_graph: Physics graph with extracted parameters.
            topology: Topology recognition output.
            sidecar: Layout sidecar metadata.
            
        Returns:
            ClassificationResult with device type, confidence, and evidence.
        """
        evidence: list[ClassificationEvidence] = []
        alternatives: list[AlternativeHypothesis] = []
        
        # Collect all evidence from input data
        self._collect_geometry_evidence(geometry_graph, evidence)
        self._collect_physics_evidence(physics_graph, evidence)
        self._collect_topology_evidence(topology, evidence)
        self._collect_sidecar_evidence(sidecar, evidence)
        
        # Score each device type
        scores: dict[DeviceType, float] = {}
        for device_type, classifier in self._classifiers.items():
            score = classifier(evidence)
            scores[device_type] = score
        
        # Find best classification
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # Generate alternatives (all types with score > 0.2)
        for device_type, score in scores.items():
            if device_type != best_type and score > 0.2:
                alternatives.append(AlternativeHypothesis(
                    device_type=device_type,
                    confidence=score,
                    reasoning=f"Score {score:.2f} based on available evidence",
                    missing_evidence=self._get_missing_evidence(device_type, evidence),
                ))
        
        # Sort alternatives by confidence
        alternatives.sort(key=lambda a: a.confidence, reverse=True)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(best_type, best_score, evidence)
        
        # Extract feature lists
        geometry_features = self._extract_geometry_features(geometry_graph)
        topology_features = self._extract_topology_features(topology)
        physics_features = self._extract_physics_features(physics_graph)
        
        return ClassificationResult(
            device_type=best_type,
            confidence=best_score,
            evidence=evidence,
            alternatives=alternatives,
            reasoning=reasoning,
            geometry_features=geometry_features,
            topology_features=topology_features,
            physics_features=physics_features,
        )
    
    def _collect_geometry_evidence(
        self,
        geometry_graph: dict[str, Any] | None,
        evidence: list[ClassificationEvidence],
    ) -> None:
        """Collect evidence from geometry graph."""
        if not geometry_graph:
            return
        
        features = geometry_graph.get("features", [])
        for feature in features:
            feature_type = feature.get("feature_type", "")
            
            # Josephson junction evidence
            if feature_type == "josephson_junction":
                evidence.append(ClassificationEvidence(
                    feature_type="geometry",
                    description="josephson_junction detected",
                    value=feature.get("dimensions", {}),
                    source="geometry_graph",
                    confidence=0.9,
                ))
            
            # SQUID loop evidence
            elif feature_type == "squid_loop":
                evidence.append(ClassificationEvidence(
                    feature_type="geometry",
                    description="squid_loop detected",
                    value=feature.get("dimensions", {}),
                    source="geometry_graph",
                    confidence=0.95,
                ))
            
            # CPW evidence
            elif feature_type == "cpw":
                evidence.append(ClassificationEvidence(
                    feature_type="geometry",
                    description="cpw detected",
                    value=feature.get("dimensions", {}),
                    source="geometry_graph",
                    confidence=0.7,
                ))
            
            # IDC evidence
            elif feature_type == "idc":
                evidence.append(ClassificationEvidence(
                    feature_type="geometry",
                    description="idc detected",
                    value=feature.get("dimensions", {}),
                    source="geometry_graph",
                    confidence=0.8,
                ))
            
            # Resonator evidence
            elif feature_type == "resonator":
                evidence.append(ClassificationEvidence(
                    feature_type="geometry",
                    description="resonator detected",
                    value=feature.get("dimensions", {}),
                    source="geometry_graph",
                    confidence=0.6,
                ))
            
            # Capacitor paddle evidence
            elif feature_type == "capacitor_paddle":
                evidence.append(ClassificationEvidence(
                    feature_type="geometry",
                    description="capacitor_paddle detected",
                    value=feature.get("dimensions", {}),
                    source="geometry_graph",
                    confidence=0.7,
                ))
            
            # Flux line evidence
            elif feature_type == "flux_line":
                evidence.append(ClassificationEvidence(
                    feature_type="geometry",
                    description="flux_line detected",
                    value=feature.get("dimensions", {}),
                    source="geometry_graph",
                    confidence=0.8,
                ))
            
            # Ground pocket evidence
            elif feature_type == "ground_pocket":
                evidence.append(ClassificationEvidence(
                    feature_type="geometry",
                    description="ground_pocket detected",
                    value=feature.get("dimensions", {}),
                    source="geometry_graph",
                    confidence=0.6,
                ))
    
    def _collect_physics_evidence(
        self,
        physics_graph: dict[str, Any] | None,
        evidence: list[ClassificationEvidence],
    ) -> None:
        """Collect evidence from physics graph."""
        if not physics_graph:
            return
        
        nodes = physics_graph.get("nodes", [])
        for node in nodes:
            node_type = node.get("type", "")
            
            # Josephson junction physics
            if node_type == "josephson_junction":
                params = node.get("parameters", {})
                ic = params.get("critical_current", {})
                lj = params.get("inductance", {})
                
                evidence.append(ClassificationEvidence(
                    feature_type="physics",
                    description="Josephson junction with physical parameters",
                    value={"Ic": ic, "Lj": lj},
                    source="physics_graph",
                    confidence=0.95,
                ))
            
            # Resonator physics
            elif node_type == "resonator":
                params = node.get("parameters", {})
                frequency = params.get("frequency", {})
                
                evidence.append(ClassificationEvidence(
                    feature_type="physics",
                    description="Resonator with frequency parameter",
                    value=frequency,
                    source="physics_graph",
                    confidence=0.7,
                ))
    
    def _collect_topology_evidence(
        self,
        topology: dict[str, Any] | None,
        evidence: list[ClassificationEvidence],
    ) -> None:
        """Collect evidence from topology recognition."""
        if not topology:
            return
        
        device_type = topology.get("device_type", "")
        if device_type:
            evidence.append(ClassificationEvidence(
                feature_type="topology",
                description=f"Topology recognized as {device_type}",
                value=device_type,
                source="topology",
                confidence=0.8,
            ))
        
        components = topology.get("components", [])
        for component in components:
            component_type = component.get("type", "")
            evidence.append(ClassificationEvidence(
                feature_type="topology",
                description=f"Component type: {component_type}",
                value=component,
                source="topology",
                confidence=0.6,
            ))
    
    def _collect_sidecar_evidence(
        self,
        sidecar: dict[str, Any] | None,
        evidence: list[ClassificationEvidence],
    ) -> None:
        """Collect evidence from sidecar metadata."""
        if not sidecar:
            return
        
        # Device type from sidecar
        device_type = sidecar.get("device_type", "")
        if device_type:
            evidence.append(ClassificationEvidence(
                feature_type="sidecar",
                description=f"Sidecar device type: {device_type}",
                value=device_type,
                source="sidecar",
                confidence=0.5,
            ))
        
        # Port information
        ports = sidecar.get("ports", [])
        if ports:
            evidence.append(ClassificationEvidence(
                feature_type="port",
                description=f"Has {len(ports)} ports",
                value=len(ports),
                source="sidecar",
                confidence=0.4,
            ))
    
    def _classify_pocket_transmon(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for pocket transmon classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "josephson_junction" in e.description.lower():
                    score += 0.3
                if "capacitor_paddle" in e.description.lower():
                    score += 0.2
                if "ground_pocket" in e.description.lower():
                    score += 0.3
                if "cpw" in e.description.lower():
                    score += 0.1
            
            elif e.feature_type == "topology":
                if "pocket_transmon" in str(e.value).lower():
                    score += 0.4
                if "transmon" in str(e.value).lower():
                    score += 0.2
            
            elif e.feature_type == "physics":
                if "josephson_junction" in str(e.value).lower():
                    score += 0.2
        
        return min(score, 1.0)
    
    def _classify_xmon(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for Xmon classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "josephson_junction" in e.description.lower():
                    score += 0.3
                if "cpw" in e.description.lower():
                    score += 0.2
                # Xmon has cross-shaped island
                if "cross" in str(e.value).lower():
                    score += 0.3
            
            elif e.feature_type == "topology":
                if "xmon" in str(e.value).lower():
                    score += 0.4
                if "transmon" in str(e.value).lower():
                    score += 0.1
            
            elif e.feature_type == "physics":
                if "josephson_junction" in str(e.value).lower():
                    score += 0.2
        
        return min(score, 1.0)
    
    def _classify_concentric_transmon(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for concentric transmon classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "josephson_junction" in e.description.lower():
                    score += 0.3
                if "capacitor_paddle" in e.description.lower():
                    score += 0.2
                # Concentric has circular geometry
                if "circular" in str(e.value).lower():
                    score += 0.3
            
            elif e.feature_type == "topology":
                if "concentric" in str(e.value).lower():
                    score += 0.4
                if "transmon" in str(e.value).lower():
                    score += 0.1
        
        return min(score, 1.0)
    
    def _classify_fluxonium(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for fluxonium classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "josephson_junction" in e.description.lower():
                    score += 0.3
                if "flux_line" in e.description.lower():
                    score += 0.3
                if "cpw" in e.description.lower():
                    score += 0.1
            
            elif e.feature_type == "topology":
                if "fluxonium" in str(e.value).lower():
                    score += 0.4
            
            elif e.feature_type == "physics":
                if "josephson_junction" in str(e.value).lower():
                    score += 0.2
                # Fluxonium has large inductance
                if "inductance" in str(e.value).lower():
                    score += 0.1
        
        return min(score, 1.0)
    
    def _classify_lumped_jpa(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for lumped JPA classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "josephson_junction" in e.description.lower():
                    score += 0.3
                if "squid_loop" in e.description.lower():
                    score += 0.3
                if "idc" in e.description.lower():
                    score += 0.2
                if "cpw" in e.description.lower():
                    score += 0.1
            
            elif e.feature_type == "topology":
                if "jpa" in str(e.value).lower():
                    score += 0.4
                if "lumped" in str(e.value).lower():
                    score += 0.2
            
            elif e.feature_type == "physics":
                if "josephson_junction" in str(e.value).lower():
                    score += 0.2
                if "squid" in str(e.value).lower():
                    score += 0.2
        
        return min(score, 1.0)
    
    def _classify_quarter_wave_jpa(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for quarter-wave JPA classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "josephson_junction" in e.description.lower():
                    score += 0.3
                if "squid_loop" in e.description.lower():
                    score += 0.3
                if "cpw" in e.description.lower():
                    score += 0.2
                if "resonator" in e.description.lower():
                    score += 0.2
            
            elif e.feature_type == "topology":
                if "jpa" in str(e.value).lower():
                    score += 0.3
                if "quarter_wave" in str(e.value).lower():
                    score += 0.3
        
        return min(score, 1.0)
    
    def _classify_twpa(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for TWPA classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "josephson_junction" in e.description.lower():
                    score += 0.2
                if "cpw" in e.description.lower():
                    score += 0.3
                # TWPA has many JJs
                if "array" in str(e.value).lower():
                    score += 0.2
            
            elif e.feature_type == "topology":
                if "twpa" in str(e.value).lower():
                    score += 0.4
                if "traveling_wave" in str(e.value).lower():
                    score += 0.3
        
        return min(score, 1.0)
    
    def _classify_idc_resonator(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for IDC resonator classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "idc" in e.description.lower():
                    score += 0.4
                if "resonator" in e.description.lower():
                    score += 0.3
                if "cpw" in e.description.lower():
                    score += 0.1
            
            elif e.feature_type == "topology":
                if "idc" in str(e.value).lower():
                    score += 0.3
                if "resonator" in str(e.value).lower():
                    score += 0.3
        
        return min(score, 1.0)
    
    def _classify_cpw_resonator(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for CPW resonator classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "cpw" in e.description.lower():
                    score += 0.4
                if "resonator" in e.description.lower():
                    score += 0.3
                if "launch_pad" in e.description.lower():
                    score += 0.1
            
            elif e.feature_type == "topology":
                if "cpw" in str(e.value).lower():
                    score += 0.3
                if "resonator" in str(e.value).lower():
                    score += 0.3
        
        return min(score, 1.0)
    
    def _classify_calibration_chip(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for calibration chip classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "launch_pad" in e.description.lower():
                    score += 0.2
                if "cpw" in e.description.lower():
                    score += 0.2
                # Calibration chips have multiple standards
                if "multiple" in str(e.value).lower():
                    score += 0.3
            
            elif e.feature_type == "topology":
                if "calibration" in str(e.value).lower():
                    score += 0.4
        
        return min(score, 1.0)
    
    def _classify_jj_array(
        self, evidence: list[ClassificationEvidence]
    ) -> float:
        """Score evidence for JJ array classification."""
        score = 0.0
        
        for e in evidence:
            if e.feature_type == "geometry":
                if "josephson_junction" in e.description.lower():
                    score += 0.3
                # Multiple JJs
                if "array" in str(e.value).lower():
                    score += 0.3
            
            elif e.feature_type == "topology":
                if "jj_array" in str(e.value).lower():
                    score += 0.4
                if "array" in str(e.value).lower():
                    score += 0.2
        
        return min(score, 1.0)
    
    def _get_missing_evidence(
        self,
        device_type: DeviceType,
        evidence: list[ClassificationEvidence],
    ) -> list[str]:
        """Get missing evidence for a device type."""
        missing = []
        
        evidence_types = {e.feature_type for e in evidence}
        
        if device_type in (
            DeviceType.POCKET_TRANSMON,
            DeviceType.XMON,
            DeviceType.CONCENTRIC_TRANSMON,
        ):
            if "geometry" not in evidence_types:
                missing.append("geometry features")
            if "physics" not in evidence_types:
                missing.append("physics parameters")
        
        elif device_type in (DeviceType.LUMPED_JPA, DeviceType.QUARTER_WAVE_JPA):
            if "geometry" not in evidence_types:
                missing.append("geometry features")
            if "physics" not in evidence_types:
                missing.append("physics parameters")
            if "port" not in evidence_types:
                missing.append("port information")
        
        elif device_type == DeviceType.TWPA:
            if "geometry" not in evidence_types:
                missing.append("geometry features")
            if "physics" not in evidence_types:
                missing.append("physics parameters")
        
        return missing
    
    def _generate_reasoning(
        self,
        device_type: DeviceType,
        confidence: float,
        evidence: list[ClassificationEvidence],
    ) -> str:
        """Generate human-readable reasoning for classification."""
        evidence_count = len(evidence)
        
        if confidence > 0.8:
            strength = "strong"
        elif confidence > 0.5:
            strength = "moderate"
        else:
            strength = "weak"
        
        reasoning = f"Classified as {device_type.value} with {strength} confidence ({confidence:.2f}). "
        reasoning += f"Based on {evidence_count} evidence items from geometry, topology, and physics analysis."
        
        return reasoning
    
    def _extract_geometry_features(
        self, geometry_graph: dict[str, Any] | None
    ) -> list[str]:
        """Extract key geometry features for classification."""
        if not geometry_graph:
            return []
        
        features = []
        for feature in geometry_graph.get("features", []):
            feature_type = feature.get("feature_type", "")
            if feature_type:
                features.append(feature_type)
        
        return list(set(features))
    
    def _extract_topology_features(
        self, topology: dict[str, Any] | None
    ) -> list[str]:
        """Extract key topology features for classification."""
        if not topology:
            return []
        
        features = []
        device_type = topology.get("device_type", "")
        if device_type:
            features.append(device_type)
        
        for component in topology.get("components", []):
            component_type = component.get("type", "")
            if component_type:
                features.append(component_type)
        
        return list(set(features))
    
    def _extract_physics_features(
        self, physics_graph: dict[str, Any] | None
    ) -> list[str]:
        """Extract key physics features for classification."""
        if not physics_graph:
            return []
        
        features = []
        for node in physics_graph.get("nodes", []):
            node_type = node.get("type", "")
            if node_type:
                features.append(node_type)
        
        return list(set(features))
