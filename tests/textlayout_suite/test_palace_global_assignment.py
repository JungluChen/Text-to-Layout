from __future__ import annotations

import pytest

from textlayout.solvers.palace.global_assignment import (
    assign_modes_globally,
    AssignmentModeSignature,
    PairMac,
)


def _mode(index: int, frequency: float, signature: tuple[float, float], cls: str = "RESONATOR"):
    return AssignmentModeSignature(
        mode_index=index,
        frequency_ghz=frequency,
        regional_signature={"resonator": signature[0], "package": signature[1]},
        resonator_localization=signature[0],
        physical_class=cls,
    )


def _macs(values: dict[tuple[int, int], tuple[float, float]]) -> list[PairMac]:
    return [
        PairMac(from_mode=left, to_mode=right, electric_mac=e, magnetic_mac=h)
        for (left, right), (e, h) in values.items()
    ]


def test_global_assignment_follows_fields_through_frequency_crossing() -> None:
    previous = [_mode(1, 5.0, (0.95, 0.05)), _mode(2, 5.2, (0.1, 0.9), "PACKAGE")]
    current = [_mode(1, 4.98, (0.1, 0.9), "PACKAGE"), _mode(2, 5.22, (0.95, 0.05))]
    result = assign_modes_globally(
        previous,
        current,
        _macs({
            (1, 1): (0.1, 0.1), (1, 2): (0.995, 0.994),
            (2, 1): (0.996, 0.997), (2, 2): (0.1, 0.1),
        }),
    )
    assert result.status == "MODE_TRACKING_ASSIGNED"
    assert result.promotion_allowed
    assert [(pair.from_mode, pair.to_mode) for pair in result.pairs] == [(1, 2), (2, 1)]


def test_global_near_degeneracy_is_ambiguous() -> None:
    previous = [_mode(1, 6.0, (0.8, 0.2)), _mode(2, 6.01, (0.8, 0.2))]
    current = [_mode(1, 6.005, (0.8, 0.2)), _mode(2, 6.006, (0.8, 0.2))]
    result = assign_modes_globally(
        previous,
        current,
        _macs({edge: (0.99, 0.99) for edge in ((1, 1), (1, 2), (2, 1), (2, 2))}),
    )
    assert result.status == "MODE_TRACKING_AMBIGUOUS"
    assert not result.promotion_allowed
    assert any(pair.ambiguous for pair in result.pairs)


def test_class_mismatch_prevents_frequency_only_swap() -> None:
    previous = [_mode(1, 6.0, (0.9, 0.1))]
    current = [
        _mode(1, 6.0, (0.1, 0.9), "PACKAGE"),
        _mode(2, 6.3, (0.9, 0.1)),
    ]
    result = assign_modes_globally(
        previous,
        current,
        _macs({(1, 1): (0.2, 0.2), (1, 2): (0.99, 0.99)}),
    )
    assert result.pairs[0].to_mode == 2
    assert result.pairs[0].components["class_mismatch_cost"] == 0.0


def test_incomplete_mac_matrix_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be complete"):
        assign_modes_globally(
            [_mode(1, 6.0, (0.9, 0.1))],
            [_mode(1, 6.1, (0.9, 0.1)), _mode(2, 6.2, (0.1, 0.9))],
            _macs({(1, 1): (0.99, 0.99)}),
        )
