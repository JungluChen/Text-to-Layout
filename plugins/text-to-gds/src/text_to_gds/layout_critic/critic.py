"""Layout Critic for engineering review with detailed feedback.

This module provides comprehensive engineering review of quantum device
layouts, with each warning containing issue, physical consequence,
supporting evidence, reference, suggested modification, expected
improvement, and confidence.
"""

from typing import Any

from text_to_gds.layout_critic.types import (
    ReviewIssue,
    ReviewCategory,
    ReviewSeverity,
    ReviewReport,
)


class LayoutCritic:
    """Provides engineering review of quantum device layouts.
    
    The layout critic goes beyond simple rule checking to provide
    engineering review with detailed feedback on how issues affect
    device performance and how to fix them.
    """
    
    def __init__(self) -> None:
        """Initialize the layout critic."""
        self._reviewers = [
            self._review_microwave,
            self._review_quantum,
            self._review_fabrication,
            self._review_packaging,
            self._review_measurement,
        ]
    
    def review(
        self,
        design_id: str,
        geometry_graph: dict[str, Any] | None = None,
        physics_graph: dict[str, Any] | None = None,
        topology: dict[str, Any] | None = None,
        sidecar: dict[str, Any] | None = None,
    ) -> ReviewReport:
        """Perform comprehensive review of a design.
        
        Args:
            design_id: ID of the design being reviewed.
            geometry_graph: Geometry intelligence output.
            physics_graph: Physics graph with parameters.
            topology: Topology recognition output.
            sidecar: Layout sidecar metadata.
            
        Returns:
            ReviewReport with all issues and recommendations.
        """
        issues: list[ReviewIssue] = []
        
        # Run all reviewers
        for reviewer in self._reviewers:
            reviewer_issues = reviewer(
                geometry_graph, physics_graph, topology, sidecar
            )
            issues.extend(reviewer_issues)
        
        # Calculate overall score
        overall_score = self._calculate_score(issues)
        
        # Determine if passed
        passed = overall_score >= 0.7 and not any(
            i.severity == ReviewSeverity.ERROR for i in issues
        )
        
        # Generate summary
        summary = self._generate_summary(issues, overall_score, passed)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(issues)
        
        return ReviewReport(
            design_id=design_id,
            issues=issues,
            overall_score=overall_score,
            passed=passed,
            summary=summary,
            recommendations=recommendations,
        )
    
    def _review_microwave(
        self,
        geometry_graph: dict[str, Any] | None,
        physics_graph: dict[str, Any] | None,
        topology: dict[str, Any] | None,
        sidecar: dict[str, Any] | None,
    ) -> list[ReviewIssue]:
        """Review microwave-related issues."""
        issues = []
        
        if not geometry_graph:
            return issues
        
        features = geometry_graph.get("features", [])
        
        # Check CPW impedance
        for feature in features:
            if feature.get("feature_type") == "cpw":
                dimensions = feature.get("dimensions", {})
                width = dimensions.get("width", 0)
                gap = dimensions.get("gap", 0)
                
                if width > 0 and gap > 0:
                    # Estimate impedance ratio
                    ratio = gap / width
                    if ratio < 0.5 or ratio > 2.0:
                        issues.append(ReviewIssue(
                            id=f"mw_cpw_ratio_{feature.get('id', '')}",
                            category=ReviewCategory.MICROWAVE,
                            severity=ReviewSeverity.WARNING,
                            issue=f"CPW gap/width ratio {ratio:.2f} is outside typical range (0.5-2.0)",
                            physical_consequence="May cause impedance mismatch and reflections",
                            supporting_evidence=[f"Width: {width}m, Gap: {gap}m"],
                            reference="Simons, 'Coplanar Waveguide Circuits, Components, and Systems'",
                            suggested_modification="Adjust gap or width to achieve ratio between 0.5-2.0",
                            expected_improvement="Better impedance matching, reduced reflections",
                            confidence=0.7,
                            location=feature.get("name", ""),
                        ))
        
        return issues
    
    def _review_quantum(
        self,
        geometry_graph: dict[str, Any] | None,
        physics_graph: dict[str, Any] | None,
        topology: dict[str, Any] | None,
        sidecar: dict[str, Any] | None,
    ) -> list[ReviewIssue]:
        """Review quantum-related issues."""
        issues = []
        
        if not physics_graph:
            return issues
        
        nodes = physics_graph.get("nodes", [])
        
        # Check Josephson junction parameters
        for node in nodes:
            if node.get("type") == "josephson_junction":
                params = node.get("parameters", {})
                ic = params.get("critical_current", {})
                
                if ic and "value" in ic:
                    ic_value = ic["value"]
                    
                    # Check if critical current is in reasonable range
                    if ic_value < 1e-9:  # Less than 1 nA
                        issues.append(ReviewIssue(
                            id=f"qj_ic_low_{node.get('id', '')}",
                            category=ReviewCategory.QUANTUM,
                            severity=ReviewSeverity.WARNING,
                            issue=f"Critical current {ic_value*1e6:.2f} uA is very low",
                            physical_consequence="May result in very high Josephson inductance",
                            supporting_evidence=[f"Ic = {ic_value} A"],
                            reference="Koch et al., 'Charge-insensitive qubit design derived from the Cooper pair box'",
                            suggested_modification="Increase junction area or critical current density",
                            expected_improvement="More practical inductance values",
                            confidence=0.8,
                        ))
        
        return issues
    
    def _review_fabrication(
        self,
        geometry_graph: dict[str, Any] | None,
        physics_graph: dict[str, Any] | None,
        topology: dict[str, Any] | None,
        sidecar: dict[str, Any] | None,
    ) -> list[ReviewIssue]:
        """Review fabrication-related issues."""
        issues = []
        
        if not geometry_graph:
            return issues
        
        features = geometry_graph.get("features", [])
        
        # Check minimum feature sizes
        for feature in features:
            dimensions = feature.get("dimensions", {})
            
            # Check for very small features
            for dim_name, dim_value in dimensions.items():
                if isinstance(dim_value, (int, float)) and dim_value < 1e-6:  # Less than 1 um
                    issues.append(ReviewIssue(
                        id=f"fab_small_{feature.get('id', '')}_{dim_name}",
                        category=ReviewCategory.FABRICATION,
                        severity=ReviewSeverity.INFO,
                        issue=f"Feature dimension {dim_name} = {dim_value*1e6:.2f} um is small",
                        physical_consequence="May be difficult to fabricate with standard lithography",
                        supporting_evidence=[f"{dim_name} = {dim_value} m"],
                        reference="PDK design rules",
                        suggested_modification="Verify dimension is achievable with target process",
                        expected_improvement="Improved fabrication yield",
                        confidence=0.6,
                        location=feature.get("name", ""),
                    ))
        
        return issues
    
    def _review_packaging(
        self,
        geometry_graph: dict[str, Any] | None,
        physics_graph: dict[str, Any] | None,
        topology: dict[str, Any] | None,
        sidecar: dict[str, Any] | None,
    ) -> list[ReviewIssue]:
        """Review packaging-related issues."""
        issues = []
        
        # Check for launch pads
        if geometry_graph:
            features = geometry_graph.get("features", [])
            has_launch_pads = any(
                f.get("feature_type") == "launch_pad" for f in features
            )
            
            if not has_launch_pads:
                issues.append(ReviewIssue(
                    id="pkg_no_launch_pads",
                    category=ReviewCategory.PACKAGING,
                    severity=ReviewSeverity.INFO,
                    issue="No launch pads detected",
                    physical_consequence="May be difficult to wirebond or probe",
                    supporting_evidence=["No launch_pad features in geometry graph"],
                    reference="Packaging best practices",
                    suggested_modification="Consider adding launch pads for wirebonding or probing",
                    expected_improvement="Easier packaging and testing",
                    confidence=0.5,
                ))
        
        return issues
    
    def _review_measurement(
        self,
        geometry_graph: dict[str, Any] | None,
        physics_graph: dict[str, Any] | None,
        topology: dict[str, Any] | None,
        sidecar: dict[str, Any] | None,
    ) -> list[ReviewIssue]:
        """Review measurement-related issues."""
        issues = []
        
        # Check for test structures
        if geometry_graph:
            features = geometry_graph.get("features", [])
            has_test_structures = any(
                f.get("feature_type") in ["cpw", "resonator", "launch_pad"]
                for f in features
            )
            
            if not has_test_structures:
                issues.append(ReviewIssue(
                    id="meas_no_test_structures",
                    category=ReviewCategory.MEASUREMENT,
                    severity=ReviewSeverity.INFO,
                    issue="No test structures detected",
                    physical_consequence="May be difficult to characterize device performance",
                    supporting_evidence=["No test features in geometry graph"],
                    reference="Measurement best practices",
                    suggested_modification="Consider adding test structures (CPW, resonator, etc.)",
                    expected_improvement="Easier device characterization",
                    confidence=0.5,
                ))
        
        return issues
    
    def _calculate_score(self, issues: list[ReviewIssue]) -> float:
        """Calculate overall review score from issues."""
        if not issues:
            return 1.0
        
        score = 1.0
        for issue in issues:
            if issue.severity == ReviewSeverity.ERROR:
                score -= 0.2
            elif issue.severity == ReviewSeverity.WARNING:
                score -= 0.1
            elif issue.severity == ReviewSeverity.INFO:
                score -= 0.02
        
        return max(0.0, score)
    
    def _generate_summary(
        self,
        issues: list[ReviewIssue],
        score: float,
        passed: bool,
    ) -> str:
        """Generate review summary."""
        error_count = sum(1 for i in issues if i.severity == ReviewSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == ReviewSeverity.WARNING)
        info_count = sum(1 for i in issues if i.severity == ReviewSeverity.INFO)
        
        status = "PASSED" if passed else "FAILED"
        
        summary = f"Review {status} with score {score:.2f}. "
        summary += f"Found {error_count} errors, {warning_count} warnings, {info_count} info items."
        
        return summary
    
    def _generate_recommendations(self, issues: list[ReviewIssue]) -> list[str]:
        """Generate high-level recommendations from issues."""
        recommendations = []
        
        # Group by category
        by_category: dict[ReviewCategory, list[ReviewIssue]] = {}
        for issue in issues:
            if issue.category not in by_category:
                by_category[issue.category] = []
            by_category[issue.category].append(issue)
        
        # Generate recommendations for each category
        for category, cat_issues in by_category.items():
            errors = [i for i in cat_issues if i.severity == ReviewSeverity.ERROR]
            warnings = [i for i in cat_issues if i.severity == ReviewSeverity.WARNING]
            
            if errors:
                recommendations.append(
                    f"Address {len(errors)} {category.value} errors before proceeding"
                )
            elif warnings:
                recommendations.append(
                    f"Review {len(warnings)} {category.value} warnings for potential improvements"
                )
        
        return recommendations
