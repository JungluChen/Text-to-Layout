"""Feature comparison logic for literature knowledge graph."""

from __future__ import annotations

from typing import Any

from text_to_gds.literature_graph.devices import (
    FeatureComparison,
    ComparisonResult,
    LiteratureDevice,
)


def compare_features(
    generated_device: dict[str, Any],
    literature_device: LiteratureDevice,
) -> ComparisonResult:
    """Compare generated device with literature device feature-by-feature.
    
    Parameters
    ----------
    generated_device:
        Generated device data (geometry graph, physics graph, etc.).
    literature_device:
        Literature device to compare against.
    
    Returns
    -------
    ComparisonResult with detailed feature comparisons.
    """
    result = ComparisonResult(
        generated_device_id=generated_device.get("id", ""),
        literature_device_id=literature_device.id,
    )
    
    # Compare topology
    _compare_topology(generated_device, literature_device, result)
    
    # Compare geometry features
    _compare_geometry_features(generated_device, literature_device, result)
    
    # Compare parameters
    _compare_parameters(generated_device, literature_device, result)
    
    # Compare fabrication
    _compare_fabrication(generated_device, literature_device, result)
    
    # Calculate overall match score
    _calculate_overall_score(result)
    
    return result


def _compare_topology(
    generated_device: dict[str, Any],
    literature_device: LiteratureDevice,
    result: ComparisonResult,
) -> None:
    """Compare device topology."""
    generated_topology = generated_device.get("topology", "unknown")
    literature_topology = literature_device.topology.value
    
    comparison = FeatureComparison(
        feature_name="topology",
        generated_value=generated_topology,
        literature_value=literature_topology,
        match=generated_topology == literature_topology,
        notes="Device topology classification",
    )
    result.feature_comparisons.append(comparison)
    
    if comparison.match:
        result.matching_features.append("topology")
    else:
        result.mismatching_features.append("topology")
        result.recommendations.append(
            f"Generated topology ({generated_topology}) differs from literature ({literature_topology})"
        )


def _compare_geometry_features(
    generated_device: dict[str, Any],
    literature_device: LiteratureDevice,
    result: ComparisonResult,
) -> None:
    """Compare geometry features."""
    generated_features = generated_device.get("geometry_features", [])
    literature_features = literature_device.features
    
    # Extract feature types
    generated_types = set(f.get("feature_type", "") for f in generated_features)
    literature_types = set(f.get("feature_type", "") for f in literature_features)
    
    # Find matching features
    matching = generated_types & literature_types
    missing = literature_types - generated_types
    extra = generated_types - literature_types
    
    for feature_type in matching:
        comparison = FeatureComparison(
            feature_name=f"feature_{feature_type}",
            generated_value=True,
            literature_value=True,
            match=True,
            notes=f"Feature {feature_type} present in both",
        )
        result.feature_comparisons.append(comparison)
        result.matching_features.append(f"feature_{feature_type}")
    
    for feature_type in missing:
        comparison = FeatureComparison(
            feature_name=f"feature_{feature_type}",
            generated_value=False,
            literature_value=True,
            match=False,
            notes=f"Feature {feature_type} missing in generated device",
        )
        result.feature_comparisons.append(comparison)
        result.missing_features.append(f"feature_{feature_type}")
        result.recommendations.append(
            f"Add {feature_type} feature to match literature device"
        )
    
    for feature_type in extra:
        comparison = FeatureComparison(
            feature_name=f"feature_{feature_type}",
            generated_value=True,
            literature_value=False,
            match=False,
            notes=f"Feature {feature_type} extra in generated device",
        )
        result.feature_comparisons.append(comparison)
        result.extra_features.append(f"feature_{feature_type}")


def _compare_parameters(
    generated_device: dict[str, Any],
    literature_device: LiteratureDevice,
    result: ComparisonResult,
) -> None:
    """Compare device parameters."""
    generated_params = generated_device.get("parameters", {})
    literature_params = literature_device.parameters
    
    for param_name, literature_value in literature_params.items():
        generated_value = generated_params.get(param_name)
        
        if generated_value is None:
            comparison = FeatureComparison(
                feature_name=f"param_{param_name}",
                generated_value=None,
                literature_value=literature_value,
                match=False,
                notes=f"Parameter {param_name} missing in generated device",
            )
            result.feature_comparisons.append(comparison)
            result.missing_features.append(f"param_{param_name}")
            result.recommendations.append(
                f"Add parameter {param_name} to match literature device"
            )
        else:
            # Compare values
            if isinstance(literature_value, (int, float)) and isinstance(generated_value, (int, float)):
                if literature_value != 0:
                    deviation = abs(generated_value - literature_value) / abs(literature_value) * 100
                    match = deviation < 20.0  # Within 20%
                else:
                    deviation = 0.0
                    match = generated_value == 0
                
                comparison = FeatureComparison(
                    feature_name=f"param_{param_name}",
                    generated_value=generated_value,
                    literature_value=literature_value,
                    match=match,
                    deviation_percent=deviation,
                    notes=f"Parameter {param_name} comparison",
                )
            else:
                comparison = FeatureComparison(
                    feature_name=f"param_{param_name}",
                    generated_value=generated_value,
                    literature_value=literature_value,
                    match=generated_value == literature_value,
                    notes=f"Parameter {param_name} comparison",
                )
            
            result.feature_comparisons.append(comparison)
            
            if comparison.match:
                result.matching_features.append(f"param_{param_name}")
            else:
                result.mismatching_features.append(f"param_{param_name}")
                result.recommendations.append(
                    f"Adjust {param_name} from {generated_value} to {literature_value}"
                )


def _compare_fabrication(
    generated_device: dict[str, Any],
    literature_device: LiteratureDevice,
    result: ComparisonResult,
) -> None:
    """Compare fabrication parameters."""
    generated_fab = generated_device.get("fabrication", {})
    literature_fab = literature_device.fabrication
    
    for fab_param, literature_value in literature_fab.items():
        generated_value = generated_fab.get(fab_param)
        
        if generated_value is not None:
            comparison = FeatureComparison(
                feature_name=f"fab_{fab_param}",
                generated_value=generated_value,
                literature_value=literature_value,
                match=generated_value == literature_value,
                notes=f"Fabrication parameter {fab_param} comparison",
            )
            result.feature_comparisons.append(comparison)
            
            if comparison.match:
                result.matching_features.append(f"fab_{fab_param}")
            else:
                result.mismatching_features.append(f"fab_{fab_param}")


def _calculate_overall_score(result: ComparisonResult) -> None:
    """Calculate overall match score."""
    total_features = len(result.feature_comparisons)
    if total_features == 0:
        result.overall_match_score = 0.0
        return
    
    matching_count = len(result.matching_features)
    result.overall_match_score = (matching_count / total_features) * 100.0
