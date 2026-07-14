from __future__ import annotations

import numpy as np
import pytest

from textlayout.solvers.palace.mode_classification import (
    classify_mode,
    ModeClass,
    select_target_mode,
    SpatialEnergyFractions,
)
from textlayout.solvers.palace.mode_sanity import (
    evaluate_quarter_wave_energy_profiles,
    ResonatorEndpointMetadata,
)


def _sanity(*, reverse: bool = False):
    coordinate = np.linspace(0.0, 1.0, 1001)
    electric = np.sin(np.pi * coordinate / 2.0)
    magnetic = np.cos(np.pi * coordinate / 2.0)
    if reverse:
        electric, magnetic = magnetic, electric
    weights = np.ones_like(coordinate)
    return evaluate_quarter_wave_energy_profiles(
        electric_positions=coordinate,
        electric_energy_phasors=electric**2,
        electric_weights=weights,
        magnetic_positions=coordinate,
        magnetic_energy_phasors=magnetic**2,
        magnetic_weights=weights,
        endpoints=ResonatorEndpointMetadata(
            grounded_coordinate=0.0,
            open_coordinate=1.0,
            local_mesh_size=0.002,
            conductor_dimension=0.01,
        ),
    )


def _spatial(**updates: float) -> SpatialEnergyFractions:
    values = {
        "cpw_gap_participation": 0.7,
        "coupling_region_participation": 0.05,
        "substrate_bulk_fraction": 0.55,
        "package_energy_fraction": 0.2,
        "boundary_energy_fraction": 0.05,
        "slotline_score": 0.0,
    }
    values.update(updates)
    return SpatialEnergyFractions(**values)


def test_ideal_mode_is_classified_as_quarter_wave() -> None:
    signature = classify_mode(
        mode_index=3,
        frequency_ghz=6.2,
        search_window_ghz=(4.0, 8.0),
        sanity=_sanity(),
        resonator_localization=0.8,
        spatial=_spatial(),
    )
    assert signature.mode_class == ModeClass.QUARTER_WAVE_RESONATOR
    assert signature.hard_quarter_wave_gates_passed
    assert abs(sum(signature.score_components.values()) - signature.quarter_wave_weighted_score) < 1e-12


def test_nearest_frequency_package_mode_cannot_override_physical_candidate() -> None:
    package = classify_mode(
        mode_index=1,
        frequency_ghz=6.0,
        search_window_ghz=(4.0, 8.0),
        sanity=_sanity(reverse=True),
        resonator_localization=0.2,
        spatial=_spatial(package_energy_fraction=0.8, cpw_gap_participation=0.05),
    )
    physical = classify_mode(
        mode_index=4,
        frequency_ghz=6.7,
        search_window_ghz=(4.0, 8.0),
        sanity=_sanity(),
        resonator_localization=0.8,
        spatial=_spatial(),
    )
    selection = select_target_mode([package, physical])
    assert package.mode_class == ModeClass.PACKAGE_MODE
    assert selection.target_mode == 4


def test_no_physical_candidate_returns_target_not_found() -> None:
    signature = classify_mode(
        mode_index=1,
        frequency_ghz=6.0,
        search_window_ghz=(4.0, 8.0),
        sanity=_sanity(reverse=True),
        resonator_localization=0.4,
        spatial=_spatial(),
    )
    selection = select_target_mode([signature])
    assert selection.status == "TARGET_MODE_NOT_FOUND"
    assert selection.target_mode is None


def test_supported_non_target_classes_are_explainable() -> None:
    sanity = _sanity(reverse=True)
    cases = [
        (_spatial(coupling_region_participation=0.7), ModeClass.COUPLING_STRUCTURE_MODE),
        (_spatial(package_energy_fraction=0.8), ModeClass.PACKAGE_MODE),
        (
            _spatial(substrate_bulk_fraction=0.9, cpw_gap_participation=0.05),
            ModeClass.SUBSTRATE_MODE,
        ),
        (_spatial(slotline_score=0.9), ModeClass.SLOTLINE_MODE),
        (_spatial(boundary_energy_fraction=0.8), ModeClass.LOCALIZED_EDGE_MODE),
    ]
    for index, (spatial, expected) in enumerate(cases, start=1):
        signature = classify_mode(
            mode_index=index,
            frequency_ghz=5.0 + index / 10.0,
            search_window_ghz=(4.0, 8.0),
            sanity=sanity,
            resonator_localization=0.2,
            spatial=spatial,
        )
        assert signature.mode_class == expected
        assert signature.rejection_reasons


def test_spatial_extractor_rejects_nonphysical_dimensions(tmp_path) -> None:
    from textlayout.solvers.palace.mode_classification import (
        extract_spatial_energy_fractions,
    )

    with pytest.raises(ValueError, match="dimensions"):
        extract_spatial_energy_fractions(
            tmp_path / "unused.pvtu",
            material_map=object(),  # type: ignore[arg-type]
            center_width=0.0,
            gap=6.0,
            coupling_gap=4.0,
            electrical_length=4918.0,
        )
