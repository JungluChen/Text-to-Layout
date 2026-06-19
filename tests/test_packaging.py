from __future__ import annotations

import pytest

from text_to_gds.package_model import (
    bondwire_inductance_nh,
    estimate_package_model,
    rectangular_cavity_modes_ghz,
    write_package_model,
)


def test_bondwire_inductance_matches_rule_of_thumb():
    single = bondwire_inductance_nh(800.0, 25.0)
    # ~1 nH/mm rule of thumb: an 0.8 mm wire lands near 0.6-0.8 nH.
    assert 0.4 < single["single_wire_nh"] < 1.2
    assert single["effective_nh"] == pytest.approx(single["single_wire_nh"])

    parallel = bondwire_inductance_nh(800.0, 25.0, count=4, pitch_um=100.0)
    assert parallel["effective_nh"] < single["single_wire_nh"]
    assert parallel["effective_nh"] > single["single_wire_nh"] / 4.0
    assert 0.0 < parallel["mutual_coupling_k"] < 1.0


def test_rectangular_cavity_modes_are_sorted_and_physical():
    modes = rectangular_cavity_modes_ghz(6.0, 6.0, 3.0)
    assert modes == sorted(modes, key=lambda item: item["frequency_ghz"])
    assert 30.0 < modes[0]["frequency_ghz"] < 40.0
    # Two-zero index modes do not exist and must be excluded.
    assert all(sum(1 for i in mode["mode"] if i == 0) < 2 for mode in modes)


def test_estimate_package_model_flags_and_self_resonance():
    model = estimate_package_model(
        operating_frequency_ghz=6.0,
        coupling_capacitance_ff=100.0,
    )
    assert model["bondwire_series_reactance_ohm"] > 0.0
    assert model["bondwire_self_resonance_ghz"] > 0.0
    assert model["chain"][0] == "chip" and model["chain"][-1] == "connector"


def test_write_package_model_writes_artifacts(tmp_path):
    model = write_package_model(
        report_path=tmp_path / "pkg.package.json",
        plot_path=tmp_path / "pkg.package.png",
        operating_frequency_ghz=6.0,
    )
    assert model["schema"] == "text-to-gds.package-model.v1"
    assert (tmp_path / "pkg.package.json").exists()
    assert (tmp_path / "pkg.package.png").exists()
