"""Device Understanding Engine - answers engineering questions about devices.

This engine analyzes extracted geometry, physics graph, design graph, and
solver evidence to answer engineering questions about superconducting circuits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from text_to_gds.device_understanding.questions import (
    QuestionType,
    EngineeringQuestion,
    EngineeringAnswer,
)


class DeviceUnderstandingEngine:
    """Main engine for device understanding.
    
    This engine answers engineering questions using extracted knowledge
    from geometry, physics, and solver evidence.
    """
    
    def __init__(self) -> None:
        """Initialize the device understanding engine."""
        self._geometry_graph: dict[str, Any] | None = None
        self._physics_graph: dict[str, Any] | None = None
        self._design_graph: dict[str, Any] | None = None
        self._solver_results: dict[str, Any] | None = None
        self._topology_result: dict[str, Any] | None = None
    
    def load_knowledge(
        self,
        geometry_graph: dict[str, Any] | None = None,
        physics_graph: dict[str, Any] | None = None,
        design_graph: dict[str, Any] | None = None,
        solver_results: dict[str, Any] | None = None,
        topology_result: dict[str, Any] | None = None,
    ) -> None:
        """Load knowledge sources for answering questions.
        
        Parameters
        ----------
        geometry_graph:
            Output of GeometryIntelligenceEngine.
        physics_graph:
            Output of extract_physics_graph().
        design_graph:
            Output of DesignGraphEngine.
        solver_results:
            Solver output results.
        topology_result:
            Output of TopologyReasoningEngine.
        """
        self._geometry_graph = geometry_graph
        self._physics_graph = physics_graph
        self._design_graph = design_graph
        self._solver_results = solver_results
        self._topology_result = topology_result
    
    def answer_question(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer an engineering question.
        
        Parameters
        ----------
        question:
            The engineering question to answer.
        
        Returns
        -------
        EngineeringAnswer with evidence and confidence.
        """
        if question.question_type == QuestionType.DEVICE_IDENTIFICATION:
            return self._answer_device_identification(question)
        elif question.question_type == QuestionType.FEATURE_PURPOSE:
            return self._answer_feature_purpose(question)
        elif question.question_type == QuestionType.OPERATING_FREQUENCY:
            return self._answer_operating_frequency(question)
        elif question.question_type == QuestionType.NONLINEAR_ELEMENT:
            return self._answer_nonlinear_element(question)
        elif question.question_type == QuestionType.CURRENT_FLOW:
            return self._answer_current_flow(question)
        elif question.question_type == QuestionType.ELECTRIC_FIELD:
            return self._answer_electric_field(question)
        elif question.question_type == QuestionType.MAGNETIC_FIELD:
            return self._answer_magnetic_field(question)
        elif question.question_type == QuestionType.BANDWIDTH_LIMIT:
            return self._answer_bandwidth_limit(question)
        elif question.question_type == QuestionType.COUPLING_MECHANISM:
            return self._answer_coupling_mechanism(question)
        elif question.question_type == QuestionType.DESIGN_RATIONALE:
            return self._answer_design_rationale(question)
        else:
            return EngineeringAnswer(
                question_id=question.id,
                answer_text="Question type not supported",
                confidence=0.0,
                limitations=["Question type not implemented"],
            )
    
    def _answer_device_identification(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer device identification question."""
        evidence = []
        answer_parts = []
        confidence = 0.0
        
        # Use topology result
        if self._topology_result:
            topology = self._topology_result.get("detected_topology", "unknown")
            topo_confidence = self._topology_result.get("confidence", 0.0)
            
            answer_parts.append(f"This is a {topology} device.")
            confidence = topo_confidence
            
            # Add supporting evidence
            supporting = self._topology_result.get("supporting_evidence", [])
            for ev in supporting[:3]:  # Top 3 pieces of evidence
                evidence.append({
                    "type": ev.get("evidence_type", ""),
                    "description": ev.get("description", ""),
                    "supporting": ev.get("supporting", True),
                })
        
        # Use geometry features
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            feature_types = [f.get("feature_type", "") for f in features]
            
            if "josephson_junction" in feature_types:
                answer_parts.append("Contains Josephson junction(s).")
                evidence.append({
                    "type": "geometry_feature",
                    "description": "Josephson junction detected",
                    "supporting": True,
                })
            
            if "squid_loop" in feature_types:
                answer_parts.append("Contains SQUID loop for tunability.")
                evidence.append({
                    "type": "geometry_feature",
                    "description": "SQUID loop detected",
                    "supporting": True,
                })
        
        return EngineeringAnswer(
            question_id=question.id,
            answer_text=" ".join(answer_parts) if answer_parts else "Unable to identify device",
            evidence=evidence,
            confidence=confidence,
            supporting_data={
                "topology_result": self._topology_result,
                "feature_count": len(self._geometry_graph.get("features", [])) if self._geometry_graph else 0,
            },
        )
    
    def _answer_feature_purpose(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer feature purpose question."""
        feature_name = question.context.get("feature_name", "")
        evidence = []
        answer_parts = []
        confidence = 0.0
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            for feature in features:
                if feature.get("name", "") == feature_name or feature.get("feature_type", "") == feature_name:
                    feature_type = feature.get("feature_type", "")
                    props = feature.get("engineering_properties", {})
                    
                    # Determine purpose based on feature type
                    if feature_type == "josephson_junction":
                        answer_parts.append(f"The {feature_name} provides nonlinear inductance for parametric amplification or qubit nonlinearity.")
                        confidence = 0.9
                    elif feature_type == "capacitor_paddle":
                        answer_parts.append(f"The {feature_name} provides shunt capacitance for frequency determination.")
                        confidence = 0.85
                    elif feature_type == "cpw":
                        answer_parts.append(f"The {feature_name} is a coplanar waveguide transmission line for signal propagation.")
                        confidence = 0.9
                    elif feature_type == "resonator":
                        freq = props.get("resonance_frequency_ghz", 0)
                        answer_parts.append(f"The {feature_name} is a resonator for frequency-selective coupling at {freq} GHz.")
                        confidence = 0.85
                    elif feature_type == "flux_line":
                        answer_parts.append(f"The {feature_name} provides magnetic flux bias for tuning device parameters.")
                        confidence = 0.8
                    elif feature_type == "launch_pad":
                        answer_parts.append(f"The {feature_name} provides RF signal coupling to the chip.")
                        confidence = 0.9
                    
                    evidence.append({
                        "type": "geometry_feature",
                        "description": f"{feature_type} feature with properties: {props}",
                        "supporting": True,
                    })
                    break
        
        return EngineeringAnswer(
            question_id=question.id,
            answer_text=" ".join(answer_parts) if answer_parts else f"Unable to determine purpose of {feature_name}",
            evidence=evidence,
            confidence=confidence,
        )
    
    def _answer_operating_frequency(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer operating frequency question."""
        evidence = []
        answer_parts = []
        confidence = 0.0
        
        # Check physics graph for frequency information
        if self._physics_graph:
            for node in self._physics_graph.get("nodes", []):
                params = node.get("physics_parameters", {})
                if "frequency" in params:
                    freq = params["frequency"]
                    if isinstance(freq, dict) and "value" in freq:
                        answer_parts.append(f"Operating frequency: {freq['value']} GHz")
                        confidence = 0.85
                        evidence.append({
                            "type": "physics_parameter",
                            "description": f"Frequency from {node.get('name', 'unknown')}",
                            "supporting": True,
                        })
        
        # Check topology result
        if self._topology_result:
            topology = self._topology_result.get("detected_topology", "")
            if topology in ("cpw_resonator", "idc_resonator"):
                answer_parts.append("Resonator-based device with frequency determined by LC parameters.")
                confidence = 0.7
        
        return EngineeringAnswer(
            question_id=question.id,
            answer_text=" ".join(answer_parts) if answer_parts else "Unable to determine operating frequency",
            evidence=evidence,
            confidence=confidence,
        )
    
    def _answer_nonlinear_element(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer nonlinear element question."""
        evidence = []
        answer_parts = []
        confidence = 0.0
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            jj_features = [f for f in features if f.get("feature_type") == "josephson_junction"]
            squid_features = [f for f in features if f.get("feature_type") == "squid_loop"]
            
            if jj_features:
                answer_parts.append(f"Found {len(jj_features)} Josephson junction(s) as nonlinear element(s).")
                confidence = 0.9
                evidence.append({
                    "type": "geometry_feature",
                    "description": "Josephson junction detected",
                    "supporting": True,
                })
            
            if squid_features:
                answer_parts.append("SQUID loop provides tunable nonlinear inductance.")
                confidence = 0.95
                evidence.append({
                    "type": "geometry_feature",
                    "description": "SQUID loop detected",
                    "supporting": True,
                })
        
        return EngineeringAnswer(
            question_id=question.id,
            answer_text=" ".join(answer_parts) if answer_parts else "No nonlinear element detected",
            evidence=evidence,
            confidence=confidence,
        )
    
    def _answer_current_flow(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer current flow question."""
        evidence = []
        answer_parts = []
        confidence = 0.0
        
        if self._physics_graph:
            # Analyze connections to determine current paths
            nodes = self._physics_graph.get("nodes", [])
            
            # Find conductor nodes
            conductors = [n for n in nodes if n.get("type") in ("conductor", "transmission_line")]
            if conductors:
                answer_parts.append(f"Current flows through {len(conductors)} conductor(s)/transmission line(s).")
                confidence = 0.7
                evidence.append({
                    "type": "physics_graph",
                    "description": f"Found {len(conductors)} conductor nodes",
                    "supporting": True,
                })
        
        return EngineeringAnswer(
            question_id=question.id,
            answer_text=" ".join(answer_parts) if answer_parts else "Unable to determine current flow",
            evidence=evidence,
            confidence=confidence,
        )
    
    def _answer_electric_field(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer electric field question."""
        evidence = []
        answer_parts = []
        confidence = 0.0
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            capacitor_features = [f for f in features if f.get("feature_type") in ("capacitor_paddle", "idc", "island")]
            
            if capacitor_features:
                answer_parts.append(f"Electric field concentrated in {len(capacitor_features)} capacitor region(s).")
                confidence = 0.75
                evidence.append({
                    "type": "geometry_feature",
                    "description": "Capacitor features identified",
                    "supporting": True,
                })
        
        return EngineeringAnswer(
            question_id=question.id,
            answer_text=" ".join(answer_parts) if answer_parts else "Unable to determine electric field distribution",
            evidence=evidence,
            confidence=confidence,
        )
    
    def _answer_magnetic_field(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer magnetic field question."""
        evidence = []
        answer_parts = []
        confidence = 0.0
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            jj_features = [f for f in features if f.get("feature_type") == "josephson_junction"]
            squid_features = [f for f in features if f.get("feature_type") == "squid_loop"]
            flux_features = [f for f in features if f.get("feature_type") == "flux_line"]
            
            if jj_features:
                answer_parts.append("Magnetic field concentrated at Josephson junction(s).")
                confidence = 0.8
                evidence.append({
                    "type": "geometry_feature",
                    "description": "Josephson junction detected",
                    "supporting": True,
                })
            
            if squid_features:
                answer_parts.append("SQUID loop provides flux-sensitive magnetic field detection.")
                confidence = 0.85
            
            if flux_features:
                answer_parts.append("Flux line provides external magnetic field bias.")
                confidence = 0.75
        
        return EngineeringAnswer(
            question_id=question.id,
            answer_text=" ".join(answer_parts) if answer_parts else "Unable to determine magnetic field distribution",
            evidence=evidence,
            confidence=confidence,
        )
    
    def _answer_bandwidth_limit(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer bandwidth limit question."""
        evidence = []
        answer_parts = []
        confidence = 0.0
        
        if self._physics_graph:
            for node in self._physics_graph.get("nodes", []):
                if node.get("type") == "transmission_line":
                    params = node.get("physics_parameters", {})
                    q = params.get("quality_factor", {})
                    if isinstance(q, dict) and "value" in q:
                        q_val = q["value"]
                        answer_parts.append(f"Bandwidth limited by resonator Q-factor ({q_val}).")
                        confidence = 0.75
                        evidence.append({
                            "type": "physics_parameter",
                            "description": f"Q-factor from {node.get('name', 'unknown')}",
                            "supporting": True,
                        })
        
        return EngineeringAnswer(
            question_id=question.id,
            answer_text=" ".join(answer_parts) if answer_parts else "Unable to determine bandwidth limits",
            evidence=evidence,
            confidence=confidence,
        )
    
    def _answer_coupling_mechanism(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer coupling mechanism question."""
        evidence = []
        answer_parts = []
        confidence = 0.0
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            coupler_features = [f for f in features if f.get("feature_type") == "coupler"]
            launch_features = [f for f in features if f.get("feature_type") == "launch_pad"]
            
            if coupler_features:
                answer_parts.append(f"Coupling via {len(coupler_features)} coupler(s).")
                confidence = 0.8
                evidence.append({
                    "type": "geometry_feature",
                    "description": "Coupler features detected",
                    "supporting": True,
                })
            
            if launch_features:
                answer_parts.append(f"External coupling via {len(launch_features)} launch pad(s).")
                confidence = 0.85
        
        return EngineeringAnswer(
            question_id=question.id,
            answer_text=" ".join(answer_parts) if answer_parts else "Unable to determine coupling mechanism",
            evidence=evidence,
            confidence=confidence,
        )
    
    def _answer_design_rationale(self, question: EngineeringQuestion) -> EngineeringAnswer:
        """Answer design rationale question."""
        evidence = []
        answer_parts = []
        confidence = 0.0
        
        # Combine information from all sources
        if self._topology_result:
            topology = self._topology_result.get("detected_topology", "unknown")
            answer_parts.append(f"Design follows {topology} topology.")
            confidence = 0.7
        
        if self._geometry_graph:
            features = self._geometry_graph.get("features", [])
            feature_count = len(features)
            answer_parts.append(f"Contains {feature_count} recognized features.")
            confidence = 0.6
        
        if self._solver_results:
            executed_solvers = [k for k, v in self._solver_results.items() if v.get("status") == "executed"]
            if executed_solvers:
                answer_parts.append(f"Verified by {len(executed_solvers)} solver(s).")
                confidence = 0.8
        
        return EngineeringAnswer(
            question_id=question.id,
            answer_text=" ".join(answer_parts) if answer_parts else "Unable to determine design rationale",
            evidence=evidence,
            confidence=confidence,
        )
    
    def answer_all_questions(self) -> dict[str, Any]:
        """Answer a standard set of engineering questions.
        
        Returns
        -------
        dict with device_understanding.json schema.
        """
        questions = [
            EngineeringQuestion(
                question_type=QuestionType.DEVICE_IDENTIFICATION,
                question_text="What device is this?",
            ),
            EngineeringQuestion(
                question_type=QuestionType.FEATURE_PURPOSE,
                question_text="What does each feature do?",
                context={"feature_name": "main"},
            ),
            EngineeringQuestion(
                question_type=QuestionType.OPERATING_FREQUENCY,
                question_text="What determines the operating frequency?",
            ),
            EngineeringQuestion(
                question_type=QuestionType.NONLINEAR_ELEMENT,
                question_text="Where is the nonlinear element?",
            ),
            EngineeringQuestion(
                question_type=QuestionType.CURRENT_FLOW,
                question_text="Where does current flow?",
            ),
            EngineeringQuestion(
                question_type=QuestionType.ELECTRIC_FIELD,
                question_text="Where is electric field concentrated?",
            ),
            EngineeringQuestion(
                question_type=QuestionType.MAGNETIC_FIELD,
                question_text="Where is magnetic field concentrated?",
            ),
            EngineeringQuestion(
                question_type=QuestionType.BANDWIDTH_LIMIT,
                question_text="What limits bandwidth?",
            ),
            EngineeringQuestion(
                question_type=QuestionType.COUPLING_MECHANISM,
                question_text="What determines coupling?",
            ),
            EngineeringQuestion(
                question_type=QuestionType.DESIGN_RATIONALE,
                question_text="What is the design rationale?",
            ),
        ]
        
        answers = {}
        for question in questions:
            answer = self.answer_question(question)
            answers[question.question_type.value] = answer.to_dict()
        
        return {
            "schema": "text-to-gds.device-understanding.v1",
            "questions": [q.to_dict() for q in questions],
            "answers": answers,
        }


def understand_device(
    geometry_graph: dict[str, Any] | None = None,
    physics_graph: dict[str, Any] | None = None,
    design_graph: dict[str, Any] | None = None,
    solver_results: dict[str, Any] | None = None,
    topology_result: dict[str, Any] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """High-level function to understand a device.
    
    Parameters
    ----------
    geometry_graph:
        Output of GeometryIntelligenceEngine.
    physics_graph:
        Output of extract_physics_graph().
    design_graph:
        Output of DesignGraphEngine.
    solver_results:
        Solver output results.
    topology_result:
        Output of TopologyReasoningEngine.
    output_path:
        Optional path to write the device understanding JSON.
    
    Returns
    -------
    dict with device_understanding.json schema.
    """
    engine = DeviceUnderstandingEngine()
    engine.load_knowledge(
        geometry_graph=geometry_graph,
        physics_graph=physics_graph,
        design_graph=design_graph,
        solver_results=solver_results,
        topology_result=topology_result,
    )
    
    result = engine.answer_all_questions()
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    
    return result
