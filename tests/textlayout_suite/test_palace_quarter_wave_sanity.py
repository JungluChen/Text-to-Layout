from __future__ import annotations

import numpy as np
import pytest

from textlayout.solvers.palace.mode_sanity import (
    evaluate_quarter_wave_energy_profiles,
    QuarterWaveSanityResult,
    ResonatorEndpointMetadata,
)


def _evaluate(
    electric: np.ndarray,
    magnetic: np.ndarray,
    *,
    positions: np.ndarray | None = None,
    endpoints: ResonatorEndpointMetadata | None = None,
) -> QuarterWaveSanityResult:
    coordinate = np.linspace(0.0, 1.0, len(electric)) if positions is None else positions
    metadata = endpoints or ResonatorEndpointMetadata(
        grounded_coordinate=0.0,
        open_coordinate=1.0,
        local_mesh_size=0.002,
        conductor_dimension=0.01,
    )
    weights = np.ones_like(coordinate)
    return evaluate_quarter_wave_energy_profiles(
        electric_positions=coordinate,
        electric_energy_phasors=electric**2,
        electric_weights=weights,
        magnetic_positions=coordinate,
        magnetic_energy_phasors=magnetic**2,
        magnetic_weights=weights,
        endpoints=metadata,
    )


def _ideal(samples: int = 1001) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    coordinate = np.linspace(0.0, 1.0, samples)
    return coordinate, np.sin(np.pi * coordinate / 2.0), np.cos(np.pi * coordinate / 2.0)


def test_ideal_quarter_wave_profile_passes() -> None:
    coordinate, electric, magnetic = _ideal()
    result = _evaluate(electric, magnetic, positions=coordinate)
    assert result.passed
    assert result.quarter_wave_profile_correlation > 0.99
    assert result.phase_progression_score == pytest.approx(1.0)
    assert result.endpoint_exclusion_length == pytest.approx(0.005)


def test_coordinate_reversal_passes_with_physical_endpoint_metadata() -> None:
    coordinate, electric, magnetic = _ideal()
    result = _evaluate(
        electric[::-1],
        magnetic[::-1],
        positions=coordinate,
        endpoints=ResonatorEndpointMetadata(
            grounded_coordinate=1.0,
            open_coordinate=0.0,
            local_mesh_size=0.002,
            conductor_dimension=0.01,
        ),
    )
    assert result.passed
    assert result.coordinate_direction == -1


def test_swapped_physical_endpoints_fail() -> None:
    coordinate, electric, magnetic = _ideal()
    result = _evaluate(
        electric,
        magnetic,
        positions=coordinate,
        endpoints=ResonatorEndpointMetadata(
            grounded_coordinate=1.0,
            open_coordinate=0.0,
            local_mesh_size=0.002,
            conductor_dimension=0.01,
        ),
    )
    assert not result.passed
    assert result.electric_open_to_ground_ratio < 1.0


@pytest.mark.parametrize(
    ("electric", "magnetic"),
    [
        (lambda x: np.sin(np.pi * x), lambda x: np.cos(np.pi * x)),
        (lambda x: np.ones_like(x), lambda x: np.ones_like(x)),
        (lambda x: np.sin(2.0 * np.pi * x), lambda x: np.cos(2.0 * np.pi * x)),
    ],
    ids=["half-wave", "uniform", "package-like"],
)
def test_incorrect_profiles_fail(electric, magnetic) -> None:
    coordinate, _, _ = _ideal()
    assert not _evaluate(electric(coordinate), magnetic(coordinate), positions=coordinate).passed


def test_global_complex_phase_does_not_change_result() -> None:
    coordinate, electric, magnetic = _ideal()
    phase = np.exp(1j * 1.234)
    result = _evaluate(electric * phase, magnetic * phase, positions=coordinate)
    assert result.passed
    assert result.phase_progression_score == pytest.approx(1.0)


def test_noisy_quarter_wave_profile_passes() -> None:
    coordinate, electric, magnetic = _ideal()
    generator = np.random.default_rng(936074)
    result = _evaluate(
        electric * (1.0 + 0.03 * generator.normal(size=len(electric))),
        magnetic * (1.0 + 0.03 * generator.normal(size=len(magnetic))),
        positions=coordinate,
    )
    assert result.passed


def test_endpoint_singularities_are_excluded() -> None:
    coordinate, electric, magnetic = _ideal()
    electric[coordinate < 0.004] = 1e6
    magnetic[coordinate > 0.996] = 1e6
    result = _evaluate(electric, magnetic, positions=coordinate)
    assert result.passed


def test_longitudinal_phase_variation_fails() -> None:
    coordinate, electric, magnetic = _ideal()
    phase = np.exp(1j * np.pi * coordinate)
    result = _evaluate(electric * phase, magnetic * phase, positions=coordinate)
    assert not result.passed
    assert result.phase_progression_score < 0.9


def test_coupler_localized_profile_fails_shape_gate() -> None:
    coordinate, electric, magnetic = _ideal()
    electric += 8.0 * np.exp(-((coordinate - 0.88) / 0.015) ** 2)
    result = _evaluate(electric, magnetic, positions=coordinate)
    assert not result.passed
    assert not result.profile_shape_passed


def test_mesh_ordering_does_not_change_metrics() -> None:
    coordinate, electric, magnetic = _ideal()
    generator = np.random.default_rng(57)
    ordering = generator.permutation(len(coordinate))
    baseline = _evaluate(electric, magnetic, positions=coordinate)
    shuffled = _evaluate(
        electric[ordering], magnetic[ordering], positions=coordinate[ordering]
    )
    assert shuffled.passed == baseline.passed
    assert shuffled.electric_profile == pytest.approx(baseline.electric_profile)
    assert shuffled.magnetic_profile == pytest.approx(baseline.magnetic_profile)
    assert shuffled.electric_open_to_ground_ratio == pytest.approx(
        baseline.electric_open_to_ground_ratio
    )
    assert shuffled.magnetic_ground_to_open_ratio == pytest.approx(
        baseline.magnetic_ground_to_open_ratio
    )
    assert shuffled.quarter_wave_profile_correlation == pytest.approx(
        baseline.quarter_wave_profile_correlation
    )
    assert shuffled.phase_progression_score == pytest.approx(
        baseline.phase_progression_score
    )
