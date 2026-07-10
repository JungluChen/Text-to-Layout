"""Engineering Reasoner for answering engineering questions.

This module answers engineering questions based on geometry, topology,
physics graph, dependency graph, and solver evidence. It never answers
from prompt - always from the available data sources.
"""

from typing import Any

from textlayout._legacy.engineering_reasoner.types import (
    EngineeringQuestion,
    EngineeringAnswer,
    AnswerSource,
)


class EngineeringReasoner:
    """Answers engineering questions based on available data sources.
    
    The engineering reasoner uses geometry, topology, physics graph,
    dependency graph, and solver evidence to answer questions about
    device performance and design.
    """
    
    def __init__(self) -> None:
        """Initialize the engineering reasoner."""
        self._question_handlers = {
            EngineeringQuestion.WHY_BANDWIDTH_LOW: self._why_bandwidth_low,
            EngineeringQuestion.WHY_GAIN_DROPPED: self._why_gain_dropped,
            EngineeringQuestion.WHY_Q_CHANGED: self._why_q_changed,
            EngineeringQuestion.WHY_RESONANCE_SHIFTED: self._why_resonance_shifted,
            EngineeringQuestion.WHERE_CURRENT_CONCENTRATES: self._where_current_concentrates,
            EngineeringQuestion.WHERE_ELECTRIC_FIELD_CONCENTRATES: self._where_electric_field_concentrates,
            EngineeringQuestion.WHICH_GEOMETRY_DOMINATES_CAPACITANCE: self._which_geometry_dominates_capacitance,
            EngineeringQuestion.WHICH_GEOMETRY_DOMINATES_INDUCTANCE: self._which_geometry_dominates_inductance,
            EngineeringQuestion.WHAT_LIMITS_PERFORMANCE: self._what_limits_performance,
            EngineeringQuestion.HOW_TO_IMPROVE: self._how_to_improve,
        }
    
    def answer(
        self,
        question: EngineeringQuestion,
        custom_question: str = "",
        geometry_graph: dict[str, Any] | None = None,
        physics_graph: dict[str, Any] | None = None,
        topology: dict[str, Any] | None = None,
        dependency_graph: dict[str, Any] | None = None,
        solver_results: dict[str, Any] | None = None,
        measurements: dict[str, Any] | None = None,
    ) -> EngineeringAnswer:
        """Answer an engineering question based on available data.
        
        Args:
            question: The engineering question to answer.
            custom_question: Custom question text if question is CUSTOM.
            geometry_graph: Geometry intelligence output.
            physics_graph: Physics graph with parameters.
            topology: Topology recognition output.
            dependency_graph: Dependency graph.
            solver_results: Solver output data.
            measurements: Measurement data.
            
        Returns:
            EngineeringAnswer with the answer and supporting evidence.
        """
        # Collect all available data
        data = {
            "geometry": geometry_graph,
            "physics": physics_graph,
            "topology": topology,
            "dependency": dependency_graph,
            "solver": solver_results,
            "measurements": measurements,
        }
        
        # Handle the question
        if question in self._question_handlers:
            return self._question_handlers[question](data)
        elif question == EngineeringQuestion.CUSTOM:
            return self._answer_custom_question(custom_question, data)
        else:
            return EngineeringAnswer(
                question=question,
                answer="Question type not recognized.",
                sources=[AnswerSource.NONE],
                confidence=0.0,
                evidence=[],
                reasoning="No handler available for this question type.",
            )
    
    def _why_bandwidth_low(
        self, data: dict[str, Any]
    ) -> EngineeringAnswer:
        """Answer why bandwidth is low."""
        evidence = []
        sources = []
        reasoning_parts = []
        
        # Check geometry for narrow features
        geometry = data.get("geometry")
        if geometry:
            features = geometry.get("features", [])
            for feature in features:
                if feature.get("feature_type") == "cpw":
                    dimensions = feature.get("dimensions", {})
                    width = dimensions.get("width", 0)
                    if width < 5e-6:  # Less than 5 um
                        evidence.append({
                            "type": "geometry",
                            "feature": feature.get("name", ""),
                            "detail": f"Narrow CPW width ({width*1e6:.1f} um)",
                        })
                        reasoning_parts.append(
                            f"Narrow CPW width ({width*1e6:.1f} um) limits bandwidth"
                        )
            sources.append(AnswerSource.GEOMETRY)
        
        # Check physics for high Q
        physics = data.get("physics")
        if physics:
            nodes = physics.get("nodes", [])
            for node in nodes:
                if node.get("type") == "resonator":
                    params = node.get("parameters", {})
                    q = params.get("quality_factor", {})
                    if q and "value" in q and q["value"] > 10000:
                        evidence.append({
                            "type": "physics",
                            "parameter": "quality_factor",
                            "value": q["value"],
                        })
                        reasoning_parts.append(
                            f"High quality factor ({q['value']:.0f}) limits bandwidth"
                        )
            sources.append(AnswerSource.PHYSICS_GRAPH)
        
        # Check solver results
        solver = data.get("solver")
        if solver:
            # Check for S-parameter data
            if "s_parameters" in solver:
                s_data = solver["s_parameters"]
                if "bandwidth" in s_data:
                    bw = s_data["bandwidth"]
                    if bw < 1e6:  # Less than 1 MHz
                        evidence.append({
                            "type": "solver",
                            "parameter": "bandwidth",
                            "value": bw,
                        })
                        reasoning_parts.append(
                            f"Solver shows narrow bandwidth ({bw/1e6:.2f} MHz)"
                        )
                sources.append(AnswerSource.SOLVER_EVIDENCE)
        
        # Generate answer
        if evidence:
            answer = "Bandwidth is limited by: " + "; ".join(reasoning_parts)
            confidence = 0.7
        else:
            answer = "Insufficient data to determine why bandwidth is low."
            confidence = 0.3
        
        return EngineeringAnswer(
            question=EngineeringQuestion.WHY_BANDWIDTH_LOW,
            answer=answer,
            sources=sources,
            confidence=confidence,
            evidence=evidence,
            reasoning="Analyzed geometry, physics, and solver data for bandwidth limitations.",
            alternatives=["Consider increasing CPW width or reducing Q factor"],
            references=["Simons, 'Coplanar Waveguide Circuits, Components, and Systems'"],
        )
    
    def _why_gain_dropped(
        self, data: dict[str, Any]
    ) -> EngineeringAnswer:
        """Answer why gain dropped."""
        evidence = []
        sources = []
        reasoning_parts = []
        
        # Check physics for JPA parameters
        physics = data.get("physics")
        if physics:
            nodes = physics.get("nodes", [])
            for node in nodes:
                if node.get("type") == "josephson_junction":
                    params = node.get("parameters", {})
                    ic = params.get("critical_current", {})
                    if ic and "value" in ic:
                        evidence.append({
                            "type": "physics",
                            "parameter": "critical_current",
                            "value": ic["value"],
                        })
                        reasoning_parts.append(
                            f"Junction critical current: {ic['value']*1e6:.2f} uA"
                        )
            sources.append(AnswerSource.PHYSICS_GRAPH)
        
        # Check solver results
        solver = data.get("solver")
        if solver:
            if "gain" in solver:
                gain = solver["gain"]
                if "peak_gain" in gain:
                    evidence.append({
                        "type": "solver",
                        "parameter": "peak_gain",
                        "value": gain["peak_gain"],
                    })
                    reasoning_parts.append(
                        f"Peak gain: {gain['peak_gain']:.1f} dB"
                    )
                sources.append(AnswerSource.SOLVER_EVIDENCE)
        
        if evidence:
            answer = "Gain analysis: " + "; ".join(reasoning_parts)
            confidence = 0.6
        else:
            answer = "Insufficient data to determine why gain dropped."
            confidence = 0.3
        
        return EngineeringAnswer(
            question=EngineeringQuestion.WHY_GAIN_DROPPED,
            answer=answer,
            sources=sources,
            confidence=confidence,
            evidence=evidence,
            reasoning="Analyzed physics and solver data for gain limitations.",
            alternatives=["Check pump power, junction nonlinearity, impedance matching"],
            references=["Yamamoto et al., 'A quantum-limited parametric amplifier'"],
        )
    
    def _why_q_changed(
        self, data: dict[str, Any]
    ) -> EngineeringAnswer:
        """Answer why Q factor changed."""
        return EngineeringAnswer(
            question=EngineeringQuestion.WHY_Q_CHANGED,
            answer="Q factor analysis requires comparison data.",
            sources=[AnswerSource.NONE],
            confidence=0.3,
            evidence=[],
            reasoning="Need before/after measurements or simulations to compare Q factors.",
        )
    
    def _why_resonance_shifted(
        self, data: dict[str, Any]
    ) -> EngineeringAnswer:
        """Answer why resonance shifted."""
        evidence = []
        sources = []
        reasoning_parts = []
        
        # Check geometry for dimensional changes
        geometry = data.get("geometry")
        if geometry:
            features = geometry.get("features", [])
            for feature in features:
                if feature.get("feature_type") == "resonator":
                    dimensions = feature.get("dimensions", {})
                    length = dimensions.get("length", 0)
                    if length > 0:
                        evidence.append({
                            "type": "geometry",
                            "feature": feature.get("name", ""),
                            "parameter": "length",
                            "value": length,
                        })
                        reasoning_parts.append(
                            f"Resonator length: {length*1e6:.1f} um"
                        )
            sources.append(AnswerSource.GEOMETRY)
        
        # Check physics for frequency
        physics = data.get("physics")
        if physics:
            nodes = physics.get("nodes", [])
            for node in nodes:
                if node.get("type") == "resonator":
                    params = node.get("parameters", {})
                    freq = params.get("frequency", {})
                    if freq and "value" in freq:
                        evidence.append({
                            "type": "physics",
                            "parameter": "frequency",
                            "value": freq["value"],
                        })
                        reasoning_parts.append(
                            f"Resonance frequency: {freq['value']/1e9:.3f} GHz"
                        )
            sources.append(AnswerSource.PHYSICS_GRAPH)
        
        if evidence:
            answer = "Resonance characteristics: " + "; ".join(reasoning_parts)
            confidence = 0.6
        else:
            answer = "Insufficient data to determine resonance shift."
            confidence = 0.3
        
        return EngineeringAnswer(
            question=EngineeringQuestion.WHY_RESONANCE_SHIFTED,
            answer=answer,
            sources=sources,
            confidence=confidence,
            evidence=evidence,
            reasoning="Analyzed geometry and physics data for resonance information.",
            alternatives=["Check dimensional variations, material properties, temperature"],
            references=["Pozar, 'Microwave Engineering'"],
        )
    
    def _where_current_concentrates(
        self, data: dict[str, Any]
    ) -> EngineeringAnswer:
        """Answer where current concentrates."""
        evidence = []
        sources = []
        reasoning_parts = []
        
        # Check geometry for narrow features
        geometry = data.get("geometry")
        if geometry:
            features = geometry.get("features", [])
            narrow_features = []
            
            for feature in features:
                dimensions = feature.get("dimensions", {})
                width = dimensions.get("width", 0)
                
                if width > 0 and width < 10e-6:  # Less than 10 um
                    narrow_features.append({
                        "name": feature.get("name", ""),
                        "type": feature.get("feature_type", ""),
                        "width": width,
                    })
            
            if narrow_features:
                narrow_features.sort(key=lambda x: x["width"])
                evidence.append({
                    "type": "geometry",
                    "narrow_features": narrow_features[:5],
                })
                reasoning_parts.append(
                    f"Current concentrates in {len(narrow_features)} narrow features"
                )
                sources.append(AnswerSource.GEOMETRY)
        
        if evidence:
            answer = "Current concentrates in: " + "; ".join(reasoning_parts)
            confidence = 0.7
        else:
            answer = "Insufficient data to determine current concentration."
            confidence = 0.3
        
        return EngineeringAnswer(
            question=EngineeringQuestion.WHERE_CURRENT_CONCENTRATES,
            answer=answer,
            sources=sources,
            confidence=confidence,
            evidence=evidence,
            reasoning="Analyzed geometry for narrow features where current concentrates.",
            alternatives=["Check solver current density results for confirmation"],
            references=["Pozar, 'Microwave Engineering'"],
        )
    
    def _where_electric_field_concentrates(
        self, data: dict[str, Any]
    ) -> EngineeringAnswer:
        """Answer where electric field concentrates."""
        evidence = []
        sources = []
        reasoning_parts = []
        
        # Check geometry for small gaps
        geometry = data.get("geometry")
        if geometry:
            features = geometry.get("features", [])
            small_gaps = []
            
            for feature in features:
                dimensions = feature.get("dimensions", {})
                gap = dimensions.get("gap", 0)
                
                if gap > 0 and gap < 5e-6:  # Less than 5 um
                    small_gaps.append({
                        "name": feature.get("name", ""),
                        "type": feature.get("feature_type", ""),
                        "gap": gap,
                    })
            
            if small_gaps:
                small_gaps.sort(key=lambda x: x["gap"])
                evidence.append({
                    "type": "geometry",
                    "small_gaps": small_gaps[:5],
                })
                reasoning_parts.append(
                    f"Electric field concentrates in {len(small_gaps)} small gaps"
                )
                sources.append(AnswerSource.GEOMETRY)
        
        if evidence:
            answer = "Electric field concentrates in: " + "; ".join(reasoning_parts)
            confidence = 0.7
        else:
            answer = "Insufficient data to determine electric field concentration."
            confidence = 0.3
        
        return EngineeringAnswer(
            question=EngineeringQuestion.WHERE_ELECTRIC_FIELD_CONCENTRATES,
            answer=answer,
            sources=sources,
            confidence=confidence,
            evidence=evidence,
            reasoning="Analyzed geometry for small gaps where electric field concentrates.",
            alternatives=["Check solver electric field results for confirmation"],
            references=["Pozar, 'Microwave Engineering'"],
        )
    
    def _which_geometry_dominates_capacitance(
        self, data: dict[str, Any]
    ) -> EngineeringAnswer:
        """Answer which geometry dominates capacitance."""
        evidence = []
        sources = []
        reasoning_parts = []
        
        # Check geometry for IDC features
        geometry = data.get("geometry")
        if geometry:
            features = geometry.get("features", [])
            idc_features = []
            
            for feature in features:
                if feature.get("feature_type") == "idc":
                    idc_features.append(feature)
            
            if idc_features:
                evidence.append({
                    "type": "geometry",
                    "idc_features": len(idc_features),
                })
                reasoning_parts.append(
                    f"IDC features dominate capacitance ({len(idc_features)} found)"
                )
                sources.append(AnswerSource.GEOMETRY)
        
        # Check physics for capacitance
        physics = data.get("physics")
        if physics:
            nodes = physics.get("nodes", [])
            for node in nodes:
                if node.get("type") == "capacitor":
                    params = node.get("parameters", {})
                    cap = params.get("capacitance", {})
                    if cap and "value" in cap:
                        evidence.append({
                            "type": "physics",
                            "parameter": "capacitance",
                            "value": cap["value"],
                        })
                        reasoning_parts.append(
                            f"Capacitance: {cap['value']*1e15:.2f} fF"
                        )
            sources.append(AnswerSource.PHYSICS_GRAPH)
        
        if evidence:
            answer = "Capacitance dominated by: " + "; ".join(reasoning_parts)
            confidence = 0.7
        else:
            answer = "Insufficient data to determine capacitance dominance."
            confidence = 0.3
        
        return EngineeringAnswer(
            question=EngineeringQuestion.WHICH_GEOMETRY_DOMINATES_CAPACITANCE,
            answer=answer,
            sources=sources,
            confidence=confidence,
            evidence=evidence,
            reasoning="Analyzed geometry and physics for capacitance contributions.",
            alternatives=["Check solver capacitance matrix for confirmation"],
            references=["Pozar, 'Microwave Engineering'"],
        )
    
    def _which_geometry_dominates_inductance(
        self, data: dict[str, Any]
    ) -> EngineeringAnswer:
        """Answer which geometry dominates inductance."""
        evidence = []
        sources = []
        reasoning_parts = []
        
        # Check physics for inductance
        physics = data.get("physics")
        if physics:
            nodes = physics.get("nodes", [])
            for node in nodes:
                if node.get("type") == "josephson_junction":
                    params = node.get("parameters", {})
                    lj = params.get("inductance", {})
                    if lj and "value" in lj:
                        evidence.append({
                            "type": "physics",
                            "parameter": "josephson_inductance",
                            "value": lj["value"],
                        })
                        reasoning_parts.append(
                            f"Josephson inductance: {lj['value']*1e9:.2f} nH"
                        )
            sources.append(AnswerSource.PHYSICS_GRAPH)
        
        if evidence:
            answer = "Inductance dominated by: " + "; ".join(reasoning_parts)
            confidence = 0.7
        else:
            answer = "Insufficient data to determine inductance dominance."
            confidence = 0.3
        
        return EngineeringAnswer(
            question=EngineeringQuestion.WHICH_GEOMETRY_DOMINATES_INDUCTANCE,
            answer=answer,
            sources=sources,
            confidence=confidence,
            evidence=evidence,
            reasoning="Analyzed physics for inductance contributions.",
            alternatives=["Check solver inductance matrix for confirmation"],
            references=["Koch et al., 'Charge-insensitive qubit design derived from the Cooper pair box'"],
        )
    
    def _what_limits_performance(
        self, data: dict[str, Any]
    ) -> EngineeringAnswer:
        """Answer what limits performance."""
        evidence = []
        sources = []
        
        # Analyze multiple factors
        geometry = data.get("geometry")
        physics = data.get("physics")
        solver = data.get("solver")
        
        if geometry:
            features = geometry.get("features", [])
            evidence.append({
                "type": "geometry",
                "feature_count": len(features),
            })
            sources.append(AnswerSource.GEOMETRY)
        
        if physics:
            nodes = physics.get("nodes", [])
            evidence.append({
                "type": "physics",
                "node_count": len(nodes),
            })
            sources.append(AnswerSource.PHYSICS_GRAPH)
        
        if solver:
            evidence.append({
                "type": "solver",
                "available": True,
            })
            sources.append(AnswerSource.SOLVER_EVIDENCE)
        
        if evidence:
            answer = "Performance limited by multiple factors. See evidence for details."
            confidence = 0.5
        else:
            answer = "Insufficient data to determine performance limitations."
            confidence = 0.3
        
        return EngineeringAnswer(
            question=EngineeringQuestion.WHAT_LIMITS_PERFORMANCE,
            answer=answer,
            sources=sources,
            confidence=confidence,
            evidence=evidence,
            reasoning="Analyzed geometry, physics, and solver data for performance limitations.",
            alternatives=["Run full simulation suite for detailed analysis"],
            references=["IEEE Microwave Magazine guidelines"],
        )
    
    def _how_to_improve(
        self, data: dict[str, Any]
    ) -> EngineeringAnswer:
        """Answer how to improve the design."""
        evidence = []
        sources = []
        reasoning_parts = []
        
        # Generate improvement suggestions based on analysis
        geometry = data.get("geometry")
        if geometry:
            features = geometry.get("features", [])
            for feature in features:
                if feature.get("feature_type") == "cpw":
                    dimensions = feature.get("dimensions", {})
                    width = dimensions.get("width", 0)
                    if width < 5e-6:
                        reasoning_parts.append(
                            f"Increase CPW width from {width*1e6:.1f} to >10 um"
                        )
                        evidence.append({
                            "type": "suggestion",
                            "feature": feature.get("name", ""),
                            "action": "increase_width",
                        })
            
            sources.append(AnswerSource.GEOMETRY)
        
        if reasoning_parts:
            answer = "Suggested improvements: " + "; ".join(reasoning_parts)
            confidence = 0.6
        else:
            answer = "No specific improvements identified. Consider running full optimization."
            confidence = 0.3
        
        return EngineeringAnswer(
            question=EngineeringQuestion.HOW_TO_IMPROVE,
            answer=answer,
            sources=sources,
            confidence=confidence,
            evidence=evidence,
            reasoning="Generated improvement suggestions based on design analysis.",
            alternatives=["Run closed-loop optimization for automated improvement"],
            references=["IEEE Microwave Magazine guidelines"],
        )
    
    def _answer_custom_question(
        self,
        question: str,
        data: dict[str, Any],
    ) -> EngineeringAnswer:
        """Answer a custom engineering question."""
        return EngineeringAnswer(
            question=EngineeringQuestion.CUSTOM,
            answer=f"Custom question analysis: {question}",
            sources=[AnswerSource.NONE],
            confidence=0.3,
            evidence=[],
            reasoning="Custom question handling not yet implemented.",
            alternatives=["Rephrase as a standard question type"],
            references=[],
        )
