from __future__ import annotations

import json
from pathlib import Path

from text_to_gds.layout_quality import classify_pcell, gate_generation
from text_to_gds.process import DEFAULT_PROCESS


def test_fabrication_real_default_rejects_quarantined_demo_pcell(tmp_path, monkeypatch):
    import text_to_gds.server as server

    monkeypatch.setattr(server, "ARTIFACT_ROOT", tmp_path)
    result = server.compile_layout("ground_plane", output_name="ground_only.gds")

    assert result["status"] == "unsupported"
    assert result["layout_quality_mode"] == "fabrication_real"
    assert not (tmp_path / "ground_only.gds").exists()


def test_demo_mode_is_explicit_opt_in_for_toy_pcell(tmp_path, monkeypatch):
    import text_to_gds.server as server

    monkeypatch.setattr(server, "ARTIFACT_ROOT", tmp_path)
    result = server.compile_layout(
        "ground_plane",
        parameters={"width": 5.0, "height": 5.0, "clearance": 1.0},
        output_name="ground_demo.gds",
        layout_quality_mode="demo",
    )

    assert result["status"] == "compiled"
    assert result["layout_quality_mode"] == "demo"
    assert Path(result["gds_path"]).is_file()


def test_reference_import_mode_never_generates_pcell(tmp_path, monkeypatch):
    import text_to_gds.server as server

    monkeypatch.setattr(server, "ARTIFACT_ROOT", tmp_path)
    result = server.compile_layout(
        "manhattan_josephson_junction",
        output_name="reference_import.gds",
        layout_quality_mode="reference_import",
    )

    assert result["status"] == "unsupported"
    assert "reference_import" in result["reason"]
    assert not (tmp_path / "reference_import.gds").exists()


def test_design_intent_path_must_be_ready(tmp_path, monkeypatch):
    import text_to_gds.server as server

    monkeypatch.setattr(server, "ARTIFACT_ROOT", tmp_path)
    intent_path = tmp_path / "blocked.design_intent.json"
    intent_path.write_text(
        json.dumps({"schema": "text-to-gds.design-intent.v1", "status": "blocked", "blockers": ["missing ports"]}),
        encoding="utf-8",
    )

    result = server.compile_layout(
        "manhattan_josephson_junction",
        output_name="blocked_intent.gds",
        design_intent_path=str(intent_path),
    )

    assert result["status"] == "unsupported"
    assert result["reason"] == "design_intent_path is not ready"
    assert not (tmp_path / "blocked_intent.gds").exists()


def test_fabrication_real_classification_is_centralized():
    assert classify_pcell("cpw_quarter_wave_resonator").layout_quality_mode == "fabrication_real"
    assert classify_pcell("via_chain_monitor").layout_quality_mode == "demo"
    assert gate_generation("jj_ic_calibration_array", "fabrication_real").allowed is False


def test_process_layer_map_has_fabrication_roles():
    required = {
        "M1",
        "JJ",
        "M2",
        "VIA12",
        "UNDERCUT",
        "CHIP_BOUNDARY",
        "KEEPOUT",
        "PORT",
        "MARKER",
    }
    assert required.issubset(DEFAULT_PROCESS.layers)
    assert "ground" in DEFAULT_PROCESS.layers["M1"].purpose
    assert "CPW center trace" in DEFAULT_PROCESS.layers["M2"].purpose


def test_required_command_wrappers_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "scripts" / "run_benchmarks.py").is_file()
    assert (root / "scripts" / "render_reports.py").is_file()
