from __future__ import annotations

import pytest

from text_to_gds.superconductivity import (
    current_crowding_profile,
    export_superconducting_material,
    sheet_kinetic_inductance_from_rn_ph,
    sheet_kinetic_inductance_ph,
    write_superconducting_material,
)


def test_sheet_kinetic_inductance_paths_agree_with_known_values():
    # NbTiN-like film from Rn + Tc lands near the ~10 pH/sq regime.
    ls_rn = sheet_kinetic_inductance_from_rn_ph(100.0, 14.0)
    assert 8.0 < ls_rn < 12.0
    # Penetration-depth path is positive and grows as the film gets thinner.
    thick = sheet_kinetic_inductance_ph(300.0, 200.0)
    thin = sheet_kinetic_inductance_ph(300.0, 50.0)
    assert thin > thick > 0.0


def test_current_crowding_profile_peaks_at_edges():
    profile = current_crowding_profile(41)
    density = profile["normalized_current_density"]
    center = density[len(density) // 2]
    assert density[0] > center and density[-1] > center


def test_export_material_computes_total_lk_and_participation():
    model = export_superconducting_material(
        material="NbTiN",
        thickness_nm=100.0,
        tc_k=14.0,
        rn_sheet_ohm=100.0,
        trace_width_um=1.0,
        trace_length_um=100.0,
        geometric_inductance_ph=50.0,
    )
    assert model["number_of_squares"] == pytest.approx(100.0)
    assert model["total_kinetic_inductance_ph"] > 0.0
    assert 0.0 < model["kinetic_inductance_participation"] < 1.0
    assert model["method"] == "mattis_bardeen_rn_tc"


def test_material_default_path_and_artifacts(tmp_path):
    model = write_superconducting_material(
        report_path=tmp_path / "nb.superconductor.json",
        plot_path=tmp_path / "nb.superconductor.png",
        material="Nb",
        thickness_nm=180.0,
    )
    # Nb has a process-default sheet kinetic inductance when no film data is given.
    assert model["method"] == "process_material_default"
    assert model["sheet_kinetic_inductance_ph_per_square"] == pytest.approx(0.10)
    assert (tmp_path / "nb.superconductor.json").exists()
    assert (tmp_path / "nb.superconductor.png").exists()
