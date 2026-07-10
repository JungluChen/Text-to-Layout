"""Layout Quality Score — predict manufacturability and design quality.

Scores a layout on:
    - Fabrication feasibility (DRC-compliant, minimum feature sizes)
    - Design quality (matching, resonator Q, coupling)
    - Performance score (predicted vs targets)
    - Novelty (similarity to known designs in the database)
    - Overall quality rating

Returns a composite score suitable for use as a training reward signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityScore:
    """Multi-dimensional quality score for a quantum device layout."""
    fabrication_score: float = 0.0       # 0-1, can it be made?
    design_quality: float = 0.0          # 0-1, is the design good?
    performance_score: float = 0.0       # 0-1, does it meet specs?
    novelty_score: float = 0.0           # 0-1, is it novel vs database?
    overall_score: float = 0.0           # 0-1, weighted composite
    grade: str = ""                      # A, B, C, D, F
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fabrication_score": round(self.fabrication_score, 4),
            "design_quality": round(self.design_quality, 4),
            "performance_score": round(self.performance_score, 4),
            "novelty_score": round(self.novelty_score, 4),
            "overall_score": round(self.overall_score, 4),
            "grade": self.grade,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


class LayoutQualityScorer:
    """Score a device layout across fabrication, design, and performance axes.

    Usage::

        scorer = LayoutQualityScorer()
        score = scorer.score_layout(sidecar, drc_result, target_specs)
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or {
            "fabrication": 0.3,
            "design": 0.3,
            "performance": 0.25,
            "novelty": 0.15,
        }

    def score_layout(
        self,
        sidecar: dict[str, Any] | None = None,
        drc_result: dict[str, Any] | None = None,
        target_specs: dict[str, Any] | None = None,
        similar_count: int = 0,
        total_devices: int = 0,
    ) -> QualityScore:
        """Score a layout from its sidecar, DRC result, and target specs."""
        score = QualityScore()

        # Fabrication score
        score.fabrication_score = self._score_fabrication(sidecar, drc_result)
        if drc_result and drc_result.get("status") == "failed":
            score.issues.append("DRC violations present")
        if sidecar:
            layers = sidecar.get("layers", [])
            if len(layers) < 2:
                score.issues.append("Very few layers — may indicate incomplete layout")

        # Design quality
        score.design_quality = self._score_design(sidecar)
        if sidecar:
            ports = sidecar.get("ports", [])
            if len(ports) < 2:
                score.issues.append("Fewer than 2 ports — incomplete circuit")
            bbox = sidecar.get("bounding_box", [])
            if bbox and len(bbox) >= 2:
                aspect = max(bbox) / min(bbox) if min(bbox) > 0 else 1.0
                if aspect > 10:
                    score.issues.append(f"High aspect ratio ({aspect:.1f}x) — fabrication risk")

        # Performance score
        score.performance_score = self._score_performance(sidecar, target_specs)
        if target_specs:
            for key, target_val in target_specs.items():
                if key in (sidecar or {}):
                    actual = sidecar[key]
                    if target_val > 0:
                        error = abs(actual - target_val) / target_val
                        if error > 0.2:
                            score.issues.append(f"{key}: {actual:.3f} vs target {target_val:.3f} ({error:.0%} error)")

        # Novelty score
        if total_devices > 0:
            score.novelty_score = 1.0 - (similar_count / total_devices)
        else:
            score.novelty_score = 1.0

        # Composite
        score.overall_score = (
            self.weights["fabrication"] * score.fabrication_score +
            self.weights["design"] * score.design_quality +
            self.weights["performance"] * score.performance_score +
            self.weights["novelty"] * score.novelty_score
        )

        # Grade
        if score.overall_score >= 0.9:
            score.grade = "A"
        elif score.overall_score >= 0.8:
            score.grade = "B"
        elif score.overall_score >= 0.7:
            score.grade = "C"
        elif score.overall_score >= 0.5:
            score.grade = "D"
        else:
            score.grade = "F"

        # Suggestions
        if score.fabrication_score < 0.7:
            score.suggestions.append("Review DRC and increase minimum feature sizes")
        if score.design_quality < 0.7:
            score.suggestions.append("Add missing ports or improve matching network")
        if score.performance_score < 0.7:
            score.suggestions.append("Adjust geometry to meet performance targets")
        if score.novelty_score < 0.3:
            score.suggestions.append("Design is very similar to existing devices — consider novel topologies")

        return score

    def _score_fabrication(
        self,
        sidecar: dict[str, Any] | None,
        drc_result: dict[str, Any] | None,
    ) -> float:
        score = 1.0
        if drc_result:
            violations = drc_result.get("violations", [])
            if violations:
                score -= min(0.5, len(violations) * 0.1)
            if drc_result.get("status") == "passed":
                score = max(score, 0.9)
        if sidecar:
            layers = sidecar.get("layers", [])
            for layer in layers:
                width = layer.get("width_um", 0)
                if 0 < width < 0.1:
                    score -= 0.05
        return max(0.0, min(1.0, score))

    def _score_design(self, sidecar: dict[str, Any] | None) -> float:
        if not sidecar:
            return 0.5
        score = 0.5
        ports = sidecar.get("ports", [])
        layers = sidecar.get("layers", [])
        params = sidecar.get("parameters", {})

        if len(ports) >= 2:
            score += 0.2
        if len(layers) >= 3:
            score += 0.1
        if params:
            score += 0.1
        if sidecar.get("bounding_box"):
            score += 0.1

        return min(1.0, score)

    def _score_performance(
        self,
        sidecar: dict[str, Any] | None,
        target_specs: dict[str, Any] | None,
    ) -> float:
        if not target_specs:
            return 0.7  # neutral if no targets given

        if not sidecar:
            return 0.3

        matches = 0
        total = 0
        for key, target in target_specs.items():
            if key in sidecar:
                total += 1
                actual = sidecar[key]
                if target > 0 and abs(actual - target) / target < 0.1:
                    matches += 1

        return matches / total if total > 0 else 0.5

    def score_batch(
        self,
        layouts: list[dict[str, Any]],
    ) -> list[QualityScore]:
        """Score multiple layouts."""
        return [
            self.score_layout(
                sidecar=lyt.get("sidecar"),
                drc_result=lyt.get("drc"),
                target_specs=lyt.get("targets"),
            )
            for lyt in layouts
        ]

    def rank_layouts(
        self,
        layouts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Score and rank layouts from best to worst."""
        scored = []
        for lyt in layouts:
            score = self.score_layout(
                sidecar=lyt.get("sidecar"),
                drc_result=lyt.get("drc"),
                target_specs=lyt.get("targets"),
            )
            scored.append({"layout": lyt, "score": score})
        scored.sort(key=lambda x: x["score"].overall_score, reverse=True)
        return scored
