"""Quantum circuit analysis on top of solver outputs.

:mod:`textlayout.quantum.epr` quantises linear eigenmodes with the
energy-participation-ratio method and persists ``quantum_analysis.json``.
Optional ``scqubits``/``pyEPR`` cross-checks are imported lazily.
"""

from textlayout.quantum.epr import (
    QUANTUM_ANALYSIS_SCHEMA,
    JunctionModel,
    ModeEnergy,
    QuantumAnalysis,
    ScqubitsCrossCheck,
    analyze_palace_output,
    embed_in_report,
    epr_from_participations,
    modes_from_palace_output,
    render_quantum_summary,
    write_quantum_analysis,
)
from textlayout.quantum.pipeline import (
    FieldToQubitPipelineResult,
    geometry_from_gds,
    run_field_to_qubit_pipeline,
)

__all__ = [
    "FieldToQubitPipelineResult",
    "QUANTUM_ANALYSIS_SCHEMA",
    "JunctionModel",
    "ModeEnergy",
    "QuantumAnalysis",
    "ScqubitsCrossCheck",
    "analyze_palace_output",
    "embed_in_report",
    "epr_from_participations",
    "geometry_from_gds",
    "modes_from_palace_output",
    "render_quantum_summary",
    "run_field_to_qubit_pipeline",
    "write_quantum_analysis",
]
