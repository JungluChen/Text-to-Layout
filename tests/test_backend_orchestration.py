from __future__ import annotations

from pathlib import Path

from text_to_gds.backends import (
    BACKEND_CLASSES,
    GDSFactoryBackend,
    KQCircuitsBackend,
    get_backend,
    list_backends,
    validate_value_records,
    value_record,
)
from text_to_gds.supercad import compile_supercad, parse_supercad


def test_backend_registry_exposes_professional_stack():
    assert {
        "kqcircuits",
        "qiskit_metal",
        "gdsfactory",
        "scqubits",
        "josephsoncircuits",
        "openems",
        "palace",
        "elmer",
        "pyepr",
    } <= set(BACKEND_CLASSES)
    assert get_backend("openems").role.startswith("open-source RF")
    rows = list_backends()
    assert all({"name", "role", "source_url", "availability"} <= set(row) for row in rows)


def test_value_records_reject_llm_guess():
    ok = {
        "f0": value_record(
            value=6.0,
            unit="GHz",
            source="scqubits",
            method="solver",
            confidence=0.9,
        )
    }
    bad = {"gain": {"value": 20.0, "unit": "dB", "source": "LLM", "confidence": 0.0}}
    assert validate_value_records(ok) == []
    assert validate_value_records(bad)


def test_kqcircuits_backend_never_writes_empty_gds(tmp_path: Path):
    backend = KQCircuitsBackend()
    result = backend.generate(
        {"device": "cpw_resonator", "components": ["cpw"], "parameters": {"frequency": "6GHz"}},
        output_dir=tmp_path,
    )
    assert result["status"] in {"SKIPPED", "UNSUPPORTED"}
    assert not list(tmp_path.glob("*.gds"))
    assert Path(result["artifacts"]["plan"]).exists()


def test_gdsfactory_refuses_superconducting_device_library(tmp_path: Path):
    result = GDSFactoryBackend().generate({"device": "transmon"}, output_dir=tmp_path)
    assert result["status"] == "UNSUPPORTED"
    assert "KQCircuits or Qiskit Metal" in result["reason"]
    assert not list(tmp_path.glob("*.gds"))


def test_supercad_forced_kqcircuits_fails_without_placeholder_gds(tmp_path: Path):
    seq = parse_supercad(
        """
        DEVICE cpw_resonator
        TECH mit_ll_sfq
        ADD cpw width=10um gap=6um
        """
    )
    result = compile_supercad(seq, output_dir=tmp_path, backend_name="kqcircuits")
    assert result["status"] == "failed"
    assert result["gds_path"] is None
    assert not (tmp_path / "cpw_resonator.gds").exists()
