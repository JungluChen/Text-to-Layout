"""Open-source simulation preparation with explicit evidence status."""

from textlayout.simulation.engine import simulate_layout
from textlayout.simulation.adapters import (
    FastHenryAdapter,
    FasterCapAdapter,
    JoSIMAdapter,
    OpenEMSAdapter,
    adapter_for,
)
from textlayout.simulation.base import (
    CircuitSimulatorAdapter,
    capture_version,
    find_simulator,
)
from textlayout.simulation.evidence import (
    CIRCUIT_SIMULATORS,
    GENERAL_LABELS,
    backend_label,
    circuit_evidence,
    general_stage,
    validate_transition,
)
from textlayout.simulation.pscan2 import (
    PSCAN2Adapter,
    find_pscan2,
    prepare_idc_pscan2,
    run_idc_pscan2,
)
from textlayout.simulation.templates import (
    JJTransientCheck,
    LCResonanceCheck,
    PumpSignalExperiment,
)
from textlayout.simulation.postprocess import (
    Waveform,
    amplitude_spectrum,
    estimate_resonance_ghz,
    parse_waveform_table,
    pump_signal_gain,
    tone_amplitude,
)
from textlayout.simulation.wrspice import (
    WRspiceAdapter,
    find_wrspice,
    parse_wrspice_output,
    prepare_idc_wrspice,
    run_idc_wrspice,
)
from textlayout.simulation.fastercap import prepare_idc_fastercap, run_fastercap
from textlayout.simulation.models import EVIDENCE_STAGES, READINESS_LABELS, SimulationResult
from textlayout.simulation.josim import (
    JoSIMCircuitAdapter,
    parse_josim_csv,
    parse_josim_transient,
    prepare_idc_josim,
    prepare_squid_josim,
    run_idc_josim,
    run_josim,
)
from textlayout.simulation.open_source import (
    prepare_cpw_openems,
    prepare_resonator_openems,
    prepare_spiral_fasthenry,
    prepare_squid_plan,
)
from textlayout.simulation.runners import (
    extract_resonance_from_touchstone,
    find_executable,
    parse_fasthenry_inductance,
    run_fasthenry,
    run_openems,
)

__all__ = [
    "CIRCUIT_SIMULATORS",
    "CircuitSimulatorAdapter",
    "EVIDENCE_STAGES",
    "FastHenryAdapter",
    "FasterCapAdapter",
    "GENERAL_LABELS",
    "JJTransientCheck",
    "JoSIMAdapter",
    "JoSIMCircuitAdapter",
    "LCResonanceCheck",
    "OpenEMSAdapter",
    "PSCAN2Adapter",
    "PumpSignalExperiment",
    "READINESS_LABELS",
    "SimulationResult",
    "WRspiceAdapter",
    "Waveform",
    "amplitude_spectrum",
    "backend_label",
    "capture_version",
    "circuit_evidence",
    "find_pscan2",
    "find_simulator",
    "find_wrspice",
    "general_stage",
    "parse_waveform_table",
    "parse_wrspice_output",
    "prepare_idc_pscan2",
    "prepare_idc_wrspice",
    "pump_signal_gain",
    "run_idc_pscan2",
    "run_idc_wrspice",
    "tone_amplitude",
    "validate_transition",
    "extract_resonance_from_touchstone",
    "adapter_for",
    "find_executable",
    "parse_fasthenry_inductance",
    "parse_josim_csv",
    "parse_josim_transient",
    "estimate_resonance_ghz",
    "prepare_idc_fastercap",
    "prepare_idc_josim",
    "prepare_cpw_openems",
    "prepare_resonator_openems",
    "prepare_spiral_fasthenry",
    "prepare_squid_plan",
    "prepare_squid_josim",
    "run_fastercap",
    "run_fasthenry",
    "run_openems",
    "run_josim",
    "run_idc_josim",
    "simulate_layout",
]
