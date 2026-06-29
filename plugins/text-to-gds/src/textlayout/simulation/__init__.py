"""Open-source simulation preparation with explicit evidence status."""

from textlayout.simulation.engine import simulate_layout
from textlayout.simulation.fastercap import prepare_idc_fastercap, run_fastercap
from textlayout.simulation.models import READINESS_LABELS, SimulationResult

__all__ = [
    "READINESS_LABELS",
    "SimulationResult",
    "prepare_idc_fastercap",
    "run_fastercap",
    "simulate_layout",
]
