"""Common circuit-adapter interface, JoSIM env detection, evidence labels."""

from __future__ import annotations

from pathlib import Path

import pytest

from textlayout.simulation import (
    CircuitSimulatorAdapter,
    JoSIMCircuitAdapter,
    LCResonanceCheck,
    PSCAN2Adapter,
    WRspiceAdapter,
    backend_label,
    general_stage,
    validate_transition,
)
from textlayout.simulation.evidence import (
    GAIN_CHECKED,
    INPUT_PREPARED,
    RESONANCE_CHECKED,
    SIMULATOR_ABSENT,
)

_ADAPTERS = (JoSIMCircuitAdapter, PSCAN2Adapter, WRspiceAdapter)

_EVIDENCE_KEYS = {
    "schema",
    "simulator",
    "executable",
    "version",
    "input_file",
    "output_file",
    "command",
    "working_directory",
    "stdout_file",
    "stderr_file",
    "return_code",
    "runtime_seconds",
    "waveform_columns",
    "extracted_metrics",
    "status",
    "status_label",
    "failure_reason",
}


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_adapter_interface_conformance(
    adapter_class: type[CircuitSimulatorAdapter], tmp_path: Path
) -> None:
    """Every backend supports the full shared lifecycle with honest defaults."""
    adapter = adapter_class()
    assert adapter.name and adapter.env_var.startswith("TEXTLAYOUT_")
    for method in ("available", "version", "prepare", "run", "parse", "postprocess", "to_evidence"):
        assert callable(getattr(adapter, method)), method

    template = LCResonanceCheck(
        capacitance_pf=0.6, capacitance_source="analytical estimate", inductance_nh=0.3
    )
    prepared = adapter.prepare(template, tmp_path / adapter.name.lower())
    assert prepared.status == "input_files_prepared"
    assert Path(prepared.artifacts["input"]).is_file()
    assert prepared.extracted_quantities["analytical_resonance_ghz"] == pytest.approx(
        template.analytical_resonance_ghz
    )

    # Running against a nonexistent executable must skip, never fabricate.
    result = adapter.run(prepared, executable=str(tmp_path / "definitely-missing"))
    assert result.status == "skipped"
    assert result.solver_executed is False

    evidence = adapter.to_evidence(result)
    assert _EVIDENCE_KEYS <= set(evidence)
    assert evidence["simulator"] == adapter.name
    assert evidence["status_label"] is not None
    assert evidence["failure_reason"] is None  # skipped is honest, not failed


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_adapter_shared_postprocess_checks_resonance(
    adapter_class: type[CircuitSimulatorAdapter],
) -> None:
    import math

    adapter = adapter_class()
    time = [i * 1e-12 for i in range(10000)]
    waveform = {
        "time_s": time,
        "signals": {"v(out)": [math.sin(2.0 * math.pi * 6.0e9 * t) for t in time]},
    }
    metrics = adapter.postprocess(waveform, analytical_resonance_ghz=6.0)
    assert metrics["resonance_ghz"] == pytest.approx(6.0, rel=0.01)
    assert metrics["target_comparison"]["within_tolerance"] is True


def test_josim_env_var_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = JoSIMCircuitAdapter()
    fake = tmp_path / "josim-cli.exe"
    fake.write_text("stub", encoding="ascii")
    monkeypatch.setenv("TEXTLAYOUT_JOSIM", str(fake))
    assert adapter.discover() == str(fake)
    # An explicit path always beats the environment variable.
    other = tmp_path / "other-josim.exe"
    other.write_text("stub", encoding="ascii")
    assert adapter.discover(str(other)) == str(other)


def test_backend_labels_follow_the_fixed_vocabulary() -> None:
    assert backend_label("JoSIM", INPUT_PREPARED) == "JOSIM_INPUT_PREPARED"
    assert backend_label("PSCAN2", SIMULATOR_ABSENT) == "SKIPPED_SOLVER_ABSENT"
    assert backend_label("WRspice", RESONANCE_CHECKED) == "WRSPICE_RESONANCE_CHECKED"
    assert backend_label("WRspice", GAIN_CHECKED) == "WRSPICE_GAIN_CHECKED"
    with pytest.raises(ValueError):
        backend_label("SPECTRE", INPUT_PREPARED)
    assert general_stage("SKIPPED_WRSPICE_ABSENT") == SIMULATOR_ABSENT
    assert general_stage("PSCAN2_TRANSIENT_PARSED") == "TRANSIENT_PARSED"
    with pytest.raises(ValueError):
        general_stage("JOSIM_VIBES_CHECKED")


def test_evidence_label_transitions_are_monotone() -> None:
    # Forward transitions are legal.
    validate_transition(None, "JOSIM_INPUT_PREPARED")
    validate_transition("JOSIM_INPUT_PREPARED", "JOSIM_EXECUTED")
    validate_transition("JOSIM_EXECUTED", "JOSIM_TRANSIENT_PARSED")
    validate_transition("JOSIM_TRANSIENT_PARSED", "JOSIM_RESONANCE_CHECKED")
    validate_transition("WRSPICE_INPUT_PREPARED", "FAILED")
    # Demotions rewrite history and must raise.
    with pytest.raises(ValueError):
        validate_transition("PSCAN2_RESONANCE_CHECKED", "PSCAN2_INPUT_PREPARED")
    with pytest.raises(ValueError):
        validate_transition("WRSPICE_TRANSIENT_PARSED", "WRSPICE_EXECUTED")
    # FAILED is terminal.
    with pytest.raises(ValueError):
        validate_transition("FAILED", "JOSIM_EXECUTED")
