"""Observed order, Richardson extrapolation and the Grid Convergence Index.

The failure this suite exists to prevent: an oscillatory sequence places its two
finest values close together, a two-point test reads that as converged, and a
result that is still moving is promoted to PHYSICS_VERIFIED.
"""

from __future__ import annotations

import math

import pytest

from textlayout.simulation.convergence_order import (
    SAFETY_FACTOR_THREE_GRID,
    CategoryResult,
    ConvergenceOrder,
    GridLevel,
    estimate_order,
    evaluate_categories,
)


def _levels(values: list[float], lengths: list[float] | None = None) -> list[GridLevel]:
    lengths = lengths or [4.0, 2.0, 1.0][: len(values)]
    return [
        GridLevel(characteristic_length=length, value=value)
        for length, value in zip(lengths, values)
    ]


class TestGridLevelValidation:
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
    def test_a_non_physical_spacing_is_rejected(self, bad: float) -> None:
        with pytest.raises(ValueError, match="characteristic_length"):
            GridLevel(characteristic_length=bad, value=6.0)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_a_non_finite_value_is_rejected(self, bad: float) -> None:
        with pytest.raises(ValueError, match="value must be finite"):
            GridLevel(characteristic_length=1.0, value=bad)


class TestPreconditions:
    def test_two_levels_cannot_distinguish_monotonic_from_oscillatory(self) -> None:
        with pytest.raises(ValueError, match="at least 3 refinement levels"):
            estimate_order(_levels([6.2, 6.0], [2.0, 1.0]))

    def test_a_non_refining_sequence_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="strictly refined"):
            estimate_order(_levels([6.2, 6.1, 6.0], [4.0, 2.0, 2.0]))

    def test_a_coarsening_sequence_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="strictly refined"):
            estimate_order(_levels([6.2, 6.1, 6.0], [1.0, 2.0, 4.0]))


class TestSecondOrderRecovery:
    """A textbook p=2 sequence must be recovered exactly."""

    def _exact_second_order(self) -> list[GridLevel]:
        # f(h) = 6.0 + 0.1*h^2 on h = 4, 2, 1  ->  7.6, 6.4, 6.1
        return [GridLevel(characteristic_length=h, value=6.0 + 0.1 * h**2) for h in (4.0, 2.0, 1.0)]

    def test_observed_order_is_two(self) -> None:
        result = estimate_order(self._exact_second_order())
        assert result.behaviour == "monotonic"
        assert result.observed_order == pytest.approx(2.0, abs=1e-9)

    def test_richardson_recovers_the_mesh_independent_value(self) -> None:
        result = estimate_order(self._exact_second_order(), expected_order=2.0)
        assert result.richardson_applicable
        assert result.extrapolated_value == pytest.approx(6.0, abs=1e-9)

    def test_a_declared_formal_order_establishes_the_asymptotic_range(self) -> None:
        result = estimate_order(self._exact_second_order(), expected_order=2.0)
        assert result.in_asymptotic_range
        assert result.asymptotic_ratio == pytest.approx(1.0, abs=1e-6)

    def test_the_gci_matches_the_roache_formula(self) -> None:
        """Hand-computed: Fs * |(f1-f2)/f1| / (r^p - 1)."""
        result = estimate_order(self._exact_second_order())
        f1, f2 = 6.1, 6.4
        expected = SAFETY_FACTOR_THREE_GRID * abs((f1 - f2) / f1) / (2.0**2 - 1) * 100
        assert result.gci_percent == pytest.approx(expected, rel=1e-6)

    def test_a_second_order_sequence_is_converged_once_the_order_is_declared(self) -> None:
        assert estimate_order(self._exact_second_order(), expected_order=2.0).converged is True


class TestThreeLevelsCannotSelfCertify:
    """p is fitted to the three finest points; it cannot then validate itself."""

    def _second_order(self, count: int) -> list[GridLevel]:
        spacings = [8.0, 4.0, 2.0, 1.0][-count:]
        return [GridLevel(characteristic_length=h, value=6.0 + 0.1 * h**2) for h in spacings]

    def test_three_levels_alone_do_not_establish_the_asymptotic_range(self) -> None:
        result = estimate_order(self._second_order(3))
        assert result.observed_order == pytest.approx(2.0, abs=1e-9)
        assert result.in_asymptotic_range is False
        assert result.converged is False
        assert any("asymptotic range cannot be established" in note for note in result.notes)

    def test_richardson_is_withheld_without_an_established_asymptotic_range(self) -> None:
        assert estimate_order(self._second_order(3)).extrapolated_value is None

    def test_a_fourth_level_certifies_the_order_independently(self) -> None:
        result = estimate_order(self._second_order(4))
        assert result.in_asymptotic_range is True
        assert result.converged is True
        assert result.asymptotic_ratio == pytest.approx(1.0, abs=1e-6)

    def test_a_drifting_order_across_triples_is_not_asymptotic(self) -> None:
        """Order 1 on the coarse triple, order 2 on the fine one: not settled."""
        levels = [
            GridLevel(characteristic_length=8.0, value=6.0 + 0.5 * 8.0),
            GridLevel(characteristic_length=4.0, value=6.0 + 0.5 * 4.0),
            GridLevel(characteristic_length=2.0, value=6.0 + 0.1 * 2.0**2),
            GridLevel(characteristic_length=1.0, value=6.0 + 0.1 * 1.0**2),
        ]
        result = estimate_order(levels)
        assert result.in_asymptotic_range is False
        assert result.converged is False

    def test_an_observed_order_far_from_the_declared_one_is_not_asymptotic(self) -> None:
        result = estimate_order(self._second_order(3), expected_order=4.0)
        assert result.in_asymptotic_range is False
        assert result.converged is False
        assert any("differs from the declared formal order" in note for note in result.notes)


class TestFirstOrderRecovery:
    def test_observed_order_is_one(self) -> None:
        levels = [GridLevel(characteristic_length=h, value=6.0 + 0.2 * h) for h in (4.0, 2.0, 1.0)]
        result = estimate_order(levels, expected_order=1.0)
        assert result.observed_order == pytest.approx(1.0, abs=1e-9)
        assert result.extrapolated_value == pytest.approx(6.0, abs=1e-9)


class TestNonUniformRefinement:
    """q(p) vanishes only for a constant ratio; the solver must handle r21 != r32."""

    def test_a_non_uniform_second_order_sequence_still_yields_p_two(self) -> None:
        # h = 6, 2, 1  ->  r32 = 3, r21 = 2
        levels = [GridLevel(characteristic_length=h, value=6.0 + 0.1 * h**2) for h in (6.0, 2.0, 1.0)]
        result = estimate_order(levels, expected_order=2.0)
        assert result.observed_order == pytest.approx(2.0, abs=1e-6)
        assert result.extrapolated_value == pytest.approx(6.0, abs=1e-6)


class TestOscillatoryDetection:
    """The case a two-point test gets wrong."""

    def _oscillating(self) -> list[GridLevel]:
        # Values straddle 6.0 with a decaying but sign-alternating error.
        return _levels([6.40, 5.90, 6.02])

    def test_an_oscillating_sequence_is_named_oscillatory(self) -> None:
        assert self._oscillating()[0].value == 6.40
        assert estimate_order(self._oscillating()).behaviour == "oscillatory"

    def test_an_oscillating_sequence_is_never_converged(self) -> None:
        result = estimate_order(self._oscillating())
        assert result.converged is False

    def test_richardson_is_withheld_for_an_oscillating_sequence(self) -> None:
        result = estimate_order(self._oscillating())
        assert result.richardson_applicable is False
        assert result.extrapolated_value is None
        assert any("oscillates" in note for note in result.notes)

    def test_the_two_finest_values_can_be_arbitrarily_close_while_oscillating(self) -> None:
        """Exactly the trap: |f1 - f2| is tiny, yet nothing has converged."""
        levels = _levels([7.00, 5.99, 6.01])
        result = estimate_order(levels)
        two_point_delta = abs(6.01 - 5.99) / 6.01 * 100
        assert two_point_delta < 0.5  # a naive 1% threshold would pass this
        assert result.behaviour == "oscillatory"
        assert result.converged is False


class TestDegenerateSequences:
    def test_identical_finest_values_are_exact_not_infinitely_converged(self) -> None:
        result = estimate_order(_levels([6.5, 6.0, 6.0]))
        assert result.behaviour == "exact"
        assert result.converged is True
        assert result.gci_percent == 0.0
        assert result.extrapolated_value == 6.0

    def test_identical_coarsest_values_are_indeterminate(self) -> None:
        result = estimate_order(_levels([6.0, 6.0, 6.3]))
        assert result.behaviour == "indeterminate"
        assert result.converged is False
        assert result.extrapolated_value is None

    def test_a_stalled_sequence_yields_no_usable_order(self) -> None:
        """The error stops shrinking under refinement: p collapses to zero."""
        result = estimate_order(_levels([6.30, 6.20, 6.10]))  # eps32 == eps21
        assert result.behaviour == "indeterminate"
        assert result.converged is False
        assert any("no usable observed order" in note for note in result.notes)


class TestSafetyFactor:
    def test_a_larger_safety_factor_widens_the_declared_uncertainty(self) -> None:
        levels = [GridLevel(characteristic_length=h, value=6.0 + 0.1 * h**2) for h in (4.0, 2.0, 1.0)]
        loose = estimate_order(levels, safety_factor=3.0)
        tight = estimate_order(levels, safety_factor=1.25)
        assert loose.gci_percent is not None and tight.gci_percent is not None
        assert loose.gci_percent > tight.gci_percent

    def test_a_non_positive_safety_factor_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="safety_factor must be positive"):
            estimate_order(_levels([6.4, 6.1, 6.0]), safety_factor=0.0)


class TestMandatoryCategories:
    """PHYSICS_VERIFIED requires every mandatory category, never an average."""

    def _converged(self) -> ConvergenceOrder:
        return estimate_order(
            [GridLevel(characteristic_length=h, value=6.0 + 0.1 * h**2) for h in (4.0, 2.0, 1.0)],
            expected_order=2.0,
        )

    def _oscillating(self) -> ConvergenceOrder:
        return estimate_order(_levels([6.40, 5.90, 6.02]), expected_order=2.0)

    def test_all_mandatory_categories_passing_is_a_pass(self) -> None:
        verdict = evaluate_categories(
            [
                CategoryResult(name="frequency", order=self._converged()),
                CategoryResult(name="field_energy", order=self._converged()),
            ]
        )
        assert verdict.passed is True
        assert verdict.failures == []

    def test_one_failing_mandatory_category_sinks_the_study(self) -> None:
        """A converged frequency inside an unconverged domain is the wrong answer."""
        verdict = evaluate_categories(
            [
                CategoryResult(name="frequency", order=self._converged()),
                CategoryResult(name="domain_size", order=self._oscillating()),
            ]
        )
        assert verdict.passed is False
        assert verdict.failures == ["domain_size"]

    def test_an_optional_category_cannot_sink_the_study(self) -> None:
        verdict = evaluate_categories(
            [
                CategoryResult(name="frequency", order=self._converged()),
                CategoryResult(
                    name="participation", order=self._oscillating(), mandatory=False
                ),
            ]
        )
        assert verdict.passed is True

    def test_the_worst_mandatory_gci_is_reported_not_the_mean(self) -> None:
        wide = estimate_order(
            [GridLevel(characteristic_length=h, value=6.0 + 2.0 * h**2) for h in (4.0, 2.0, 1.0)],
            expected_order=2.0,
        )
        narrow = self._converged()
        verdict = evaluate_categories(
            [
                CategoryResult(name="frequency", order=narrow),
                CategoryResult(name="field_energy", order=wide),
            ]
        )
        assert verdict.worst_gci_percent == pytest.approx(wide.gci_percent)
        assert wide.gci_percent is not None and narrow.gci_percent is not None
        assert wide.gci_percent > narrow.gci_percent

    def test_a_verdict_needs_a_mandatory_category(self) -> None:
        with pytest.raises(ValueError, match="at least one convergence category must be mandatory"):
            evaluate_categories(
                [CategoryResult(name="participation", order=self._converged(), mandatory=False)]
            )

    def test_an_empty_verdict_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="at least one category"):
            evaluate_categories([])


class TestGciIsAnUncertainty:
    def test_the_extrapolated_value_lies_within_the_gci_band(self) -> None:
        levels = [GridLevel(characteristic_length=h, value=6.0 + 0.1 * h**2) for h in (4.0, 2.0, 1.0)]
        result = estimate_order(levels, expected_order=2.0)
        assert result.gci_percent is not None and result.extrapolated_value is not None
        finest = levels[-1].value
        band = abs(finest) * result.gci_percent / 100.0
        assert math.isclose(finest, result.extrapolated_value, abs_tol=band)
