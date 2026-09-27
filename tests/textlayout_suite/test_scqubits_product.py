"""Product transmon execution and honesty guards; optional real-library test."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from textlayout.solvers import scqubits_adapter as adapter


def test_real_scqubits_writes_spectrum(tmp_path):
    pytest.importorskip("scqubits")
    prepared = adapter.prepare_scqubits_input({"ic_a": 4e-8, "capacitance_f": 80e-15}, tmp_path)
    result = adapter.execute_scqubits(prepared)
    assert result.status == "executed", result.reason
    assert result.solver_executed
    assert not result.physics_verified
    payload = json.loads(Path(result.artifacts["result"]).read_text())
    assert payload["engine"] == "scqubits.Transmon.eigenvals"
    assert payload["solver_version"]
    assert len(payload["input_sha256"]) == 64
    q = payload["quantities"]
    assert q["transmon_regime"]
    assert q["anharmonicity_mhz"] < -10
    assert q["f01_ghz"] > q["f12_ghz"] > 0
    # Public legacy behavior is preserved for identical physical inputs.
    from textlayout._legacy.scqubits_adapter import run_scqubits_transmon
    extraction = tmp_path / "extraction.json"
    extraction.write_text(json.dumps({"schema": "text-to-gds.extraction.v1",
        "junction": {"ic_a": 4e-8}, "linear_circuit": {"capacitance_f": 80e-15}}))
    legacy = run_scqubits_transmon(extraction, report_path=tmp_path / "legacy.json")
    for key in ("f01_ghz", "f12_ghz", "anharmonicity_mhz", "ej_ec_ratio"):
        assert q[key] == pytest.approx(legacy[key], rel=1e-12)


@pytest.mark.parametrize("parameters", [{}, {"ic_a": -1, "capacitance_f": 1e-13},
    {"ic_a": float("nan"), "capacitance_f": 1e-13},
    {"ic_a": 4e-8, "capacitance_f": 8e-14, "n_evals": 2},
    {"ic_a": 4e-8, "capacitance_f": 8e-14, "ncut": 1}])
def test_invalid_inputs_never_execute(tmp_path, monkeypatch, parameters):
    monkeypatch.setattr(adapter, "scqubits_available", lambda: True)
    result = adapter.execute_scqubits(adapter.prepare_scqubits_input(parameters, tmp_path))
    assert result.status == "failed"
    assert not result.extracted_quantities
    assert "result" not in result.artifacts


def test_harmonic_spectrum_rejected_and_low_ratio_warning_kept(tmp_path, monkeypatch):
    import numpy as np
    library = SimpleNamespace(__version__="synthetic-test-only", Transmon=lambda **kwargs:
        SimpleNamespace(eigenvals=lambda **kwargs: np.arange(6, dtype=float)))
    monkeypatch.setattr(adapter, "scqubits_available", lambda: True)
    monkeypatch.setattr(adapter.importlib, "import_module", lambda name: library)
    result = adapter.execute_scqubits(adapter.prepare_scqubits_input(
        {"ic_a": 1e-10, "capacitance_f": 8e-14}, tmp_path))
    assert result.status == "failed"
    assert "10 MHz" in result.reason
    assert not result.extracted_quantities
    assert any("< 10" in warning for warning in result.warnings)
    assert any("degeneracy" in warning for warning in result.warnings)
    assert not result.physics_verified


def test_missing_scqubits_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "scqubits_available", lambda: False)
    result = adapter.execute_scqubits(adapter.prepare_scqubits_input(
        {"ic_a": 4e-8, "capacitance_f": 8e-14}, tmp_path))
    assert result.status == "skipped"
    assert "result" not in result.artifacts
