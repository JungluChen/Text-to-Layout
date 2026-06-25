"""Acceptance tests for the four-view renderer and single-frequency JPA reports."""

from __future__ import annotations

import json

from text_to_gds.device_library import JPA, Transmon
from text_to_gds.device_views import render_device_views
from text_to_gds.verification.connectivity import extract_connectivity


def _views_for(device, tmp_path, stem, title):
    gds = tmp_path / f"{stem}.gds"
    device.geometry().write_gds(gds)
    conn = extract_connectivity(gds)
    paths = render_device_views(gds, tmp_path, stem, connectivity=conn,
                                ports=device.ports(), title=title)
    return paths


def test_transmon_four_views_exist(tmp_path):
    paths = _views_for(Transmon(), tmp_path, "transmon", "5 GHz transmon")
    assert set(paths) == {"mask_view", "layer_view", "net_view", "circuit_view"}
    for p in paths.values():
        from pathlib import Path

        assert Path(p).exists() and Path(p).stat().st_size > 0


def test_jpa_four_views_exist(tmp_path):
    paths = _views_for(JPA(), tmp_path, "jpa", "6 GHz JPA")
    assert set(paths) == {"mask_view", "layer_view", "net_view", "circuit_view"}
    for p in paths.values():
        from pathlib import Path

        assert Path(p).exists() and Path(p).stat().st_size > 0


def test_jpa_report_is_single_frequency_6ghz(tmp_path):
    # The 6 GHz JPA must never carry a 2.1 GHz (axion-search) artifact.
    device = JPA(frequency_ghz=6.0, impedance_ohm=50.0, target_gain_db=20.0, bandwidth_mhz=200.0)
    syn = device._synthesis()
    assert syn["frequency_ghz"] == 6.0
    blob = json.dumps(syn) + json.dumps(device.extract())
    assert "2.1" not in blob
    assert "2100" not in blob
