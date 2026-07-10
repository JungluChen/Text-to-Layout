"""Device Classifier module for quantum device type recognition.

This module classifies quantum devices based on their geometry, topology,
and physics characteristics. It provides evidence-based classification
with confidence scores and alternative hypotheses.

The classifier recognizes:
- Pocket Transmon
- Xmon
- Concentric Transmon
- Fluxonium
- Lumped JPA
- Quarter-wave JPA
- TWPA (Traveling Wave Parametric Amplifier)
- IDC Resonator
- CPW Resonator
- Calibration Chip
- JJ Array
- Unknown
"""

from textlayout._legacy.device_classifier.classifier import DeviceClassifier
from textlayout._legacy.device_classifier.types import (
    DeviceType,
    ClassificationResult,
    ClassificationEvidence,
    AlternativeHypothesis,
)

__all__ = [
    "DeviceClassifier",
    "DeviceType",
    "ClassificationResult",
    "ClassificationEvidence",
    "AlternativeHypothesis",
]
