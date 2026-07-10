"""Engineering Rule Engine - orchestrates rule-based analysis for superconducting circuits.

This engine evaluates engineering rules across microwave, quantum, fabrication,
packaging, measurement, and cryogenic categories.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout._legacy.engineering_rules.rules import Rule, RuleCategory, RuleResult
from textlayout._legacy.engineering_rules.microwave_rules import MICROWAVE_RULES
from textlayout._legacy.engineering_rules.quantum_rules import QUANTUM_RULES
from textlayout._legacy.engineering_rules.fabrication_rules import FABRICATION_RULES
from textlayout._legacy.engineering_rules.packaging_rules import PACKAGING_RULES
from textlayout._legacy.engineering_rules.measurement_rules import MEASUREMENT_RULES
from textlayout._legacy.engineering_rules.cryogenic_rules import CRYOGENIC_RULES


class EngineeringRuleEngine:
    """Main engine for engineering rule evaluation.
    
    This engine evaluates design rules across multiple categories and
    provides engineering context for rule violations.
    """
    
    def __init__(self) -> None:
        """Initialize the engineering rule engine."""
        self._rules: dict[RuleCategory, list[Rule]] = {
            RuleCategory.MICROWAVE: list(MICROWAVE_RULES),
            RuleCategory.QUANTUM: list(QUANTUM_RULES),
            RuleCategory.FABRICATION: list(FABRICATION_RULES),
            RuleCategory.PACKAGING: list(PACKAGING_RULES),
            RuleCategory.MEASUREMENT: list(MEASUREMENT_RULES),
            RuleCategory.CRYOGENIC: list(CRYOGENIC_RULES),
        }
        self._results: list[RuleResult] = []
    
    def evaluate_rules(
        self,
        design_data: dict[str, Any],
        categories: list[RuleCategory] | None = None,
    ) -> dict[str, Any]:
        """Evaluate engineering rules on design data.
        
        Parameters
        ----------
        design_data:
            Design data including geometry features, physics graph, etc.
        categories:
            Optional list of categories to evaluate. If None, evaluate all.
        
        Returns
        -------
        dict with engineering_rules.json schema.
        """
        self._results = []
        
        # Determine categories to evaluate
        if categories is None:
            categories = list(self._rules.keys())
        
        # Evaluate rules for each category
        for category in categories:
            rules = self._rules.get(category, [])
            for rule in rules:
                result = self._evaluate_rule(rule, design_data)
                self._results.append(result)
        
        # Build result
        result = self._build_result()
        
        return result
    
    def _evaluate_rule(self, rule: Rule, design_data: dict[str, Any]) -> RuleResult:
        """Evaluate a single rule."""
        passed = True
        message = ""
        recommendation = ""
        
        if rule.check_fn:
            try:
                passed = rule.check_fn(design_data)
            except Exception as e:
                passed = False
                message = f"Rule evaluation failed: {e}"
        
        if not passed:
            if rule.message_fn:
                try:
                    message = rule.message_fn(design_data)
                except Exception:
                    message = rule.description
            
            if rule.recommendation_fn:
                try:
                    recommendation = rule.recommendation_fn(design_data)
                except Exception:
                    recommendation = ""
        
        return RuleResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=message,
            recommendation=recommendation,
            affected_subsystem=rule.affected_subsystem,
            confidence=rule.confidence,
            details={
                "category": rule.category.value,
                "description": rule.description,
            },
        )
    
    def _build_result(self) -> dict[str, Any]:
        """Build the engineering rules result."""
        # Count results by severity
        severity_counts = {
            "error": 0,
            "warning": 0,
            "info": 0,
        }
        for result in self._results:
            if not result.passed:
                severity_counts[result.severity.value] += 1
        
        # Count results by category
        category_counts = {}
        for result in self._results:
            category = result.details.get("category", "unknown")
            if category not in category_counts:
                category_counts[category] = {"passed": 0, "failed": 0}
            if result.passed:
                category_counts[category]["passed"] += 1
            else:
                category_counts[category]["failed"] += 1
        
        # Calculate overall score
        total_rules = len(self._results)
        passed_rules = sum(1 for r in self._results if r.passed)
        score = (passed_rules / total_rules * 100) if total_rules > 0 else 100
        
        return {
            "schema": "text-to-gds.engineering-rules.v1",
            "summary": {
                "total_rules": total_rules,
                "passed_rules": passed_rules,
                "failed_rules": total_rules - passed_rules,
                "score": round(score, 1),
                "severity_counts": severity_counts,
                "category_counts": category_counts,
            },
            "results": [r.to_dict() for r in self._results],
            "failed_rules": [r.to_dict() for r in self._results if not r.passed],
        }


def evaluate_engineering_rules(
    design_data: dict[str, Any],
    categories: list[RuleCategory] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """High-level function to evaluate engineering rules.
    
    Parameters
    ----------
    design_data:
        Design data including geometry features, physics graph, etc.
    categories:
        Optional list of categories to evaluate.
    output_path:
        Optional path to write the engineering rules JSON.
    
    Returns
    -------
    dict with engineering_rules.json schema.
    """
    engine = EngineeringRuleEngine()
    result = engine.evaluate_rules(
        design_data=design_data,
        categories=categories,
    )
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    
    return result
