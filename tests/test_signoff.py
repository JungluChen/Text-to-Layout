"""Acceptance tests for the production-signoff layer."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from text_to_gds.device_library import JPA, Transmon
from text_to_gds.device_views import render_evidence_view
from text_to_gds.evidence import evidence_bundle
from text_to_gds.fabrication_signoff import run_fabrication_signoff, signoff_drc
from text_to_gds.signoff_extraction import extract_capacitance, extract_sparameters


def _gds(device, tmp_path, stem):
    p = tmp_path / f"{stem}.gds"
    device.geometry().write_gds(p)
    return p


def test_fabrication_signoff_produces_full_artifact_set(tmp_path):
    gds = _gds(JPA(), tmp_path, "jpa")
    bundle = run_fabrication_signoff(gds, tmp_path, "jpa")
    reports = bundle["reports"]
    for key in ("drc", "lvs", "floating_metal", "layer_connectivity", "pdk_rules", "layer_properties_lyp"):
        assert Path(reports[key]).exists() and Path(reports[key]).stat().st_size > 0
    assert bundle["statuses"]["drc"] == "passed"
    assert bundle["statuses"]["lvs"] == "passed"


def test_drc_is_real_micron_check(tmp_path):
    gds = _gds(Transmon(), tmp_path, "tmon")
    drc = signoff_drc(gds)
    assert drc["database_unit_um"] > 0
    # width/space checks must have actually run on the metal layers
    layers = {c["layer"] for c in drc["checks"]}
    assert {"M1", "M2", "M3"} <= layers
    assert drc["status"] in {"passed", "failed"}


def test_lyp_is_valid_klayout_xml(tmp_path):
    gds = _gds(JPA(), tmp_path, "jpa")
    bundle = run_fabrication_signoff(gds, tmp_path, "jpa")
    root = ET.parse(bundle["reports"]["layer_properties_lyp"]).getroot()
    assert root.tag == "layer-properties"
    sources = [p.findtext("source") for p in root.findall("properties")]
    assert any(s and s.startswith("3/0") for s in sources)  # M1


def test_capacitance_hook_skips_without_backend_and_writes_deck(tmp_path):
    gds = _gds(JPA(), tmp_path, "jpa")
    sidecar = tmp_path / "jpa.sidecar.json"
    sidecar.write_text("{}", encoding="utf-8")
    rec = extract_capacitance(
        gds, tmp_path, "jpa_idc", device_label="JPA 6 GHz", source_sidecar=sidecar,
        quantity="idc_capacitance_f", conductor_layers=("M1", "M2"), eps_r=11.45,
    )
    # No FastCap2 on the test machine -> honest SKIPPED, but the input deck exists.
    if rec["solver_status"] == "EXECUTED":
        assert rec["output_file_exists"] is True
    else:
        assert rec["solver_status"] in {"SKIPPED", "FAILED"}
        assert rec["value"] is None
        assert "not on PATH" in (rec["notes"] or "") or "no matrix" in (rec["notes"] or "")
    assert Path(rec["input_file"]).exists()


def test_sparameter_hook_only_executed_with_touchstone(tmp_path):
    sidecar = tmp_path / "jpa.sidecar.json"
    sidecar.write_text("{}", encoding="utf-8")
    rec = extract_sparameters(
        tmp_path, "jpa_cpw", device_label="JPA 6 GHz", source_sidecar=sidecar,
        cpw_width_um=10.0, cpw_gap_um=6.0, length_um=900.0, band_ghz=(5.9, 6.1),
    )
    assert Path(rec["input_file"]).exists()  # runnable deck written
    if rec["solver_status"] == "EXECUTED":
        assert rec["output_file_exists"] is True
    else:
        assert rec["solver_status"] in {"SKIPPED", "FAILED"}
        assert rec["output_file"] is None


def test_evidence_view_renders(tmp_path):
    from text_to_gds.evidence import solver_evidence

    items = [
        solver_evidence(quantity="gain_db", source_device="JPA", source_sidecar=None,
                        solver_name="JosephsonCircuits.jl", solver_status="SKIPPED"),
    ]
    bundle = evidence_bundle(device="JPA", source_sidecar=None, items=items)
    out = tmp_path / "evidence_view.png"
    render_evidence_view(bundle, out, "JPA")
    assert out.exists() and out.stat().st_size > 0
