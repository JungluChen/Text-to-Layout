import pytest

from textlayout.solvers.palace.models import classify_mac_applicability


def test_ordinary_mac_is_gate_for_closed_lossless_hermitian_problem() -> None:
    applicability = classify_mac_applicability("closed_lossless_hermitian")
    assert applicability.ordinary_energy_mac_use == "mandatory_gate"
    assert applicability.promotion_allowed_from_ordinary_mac is True
    assert applicability.required_method is None


@pytest.mark.parametrize(
    "problem_class",
    ["lossy", "radiative", "pml", "dispersive", "non_hermitian"],
)
def test_ordinary_mac_is_diagnostic_for_incompatible_problem(problem_class: str) -> None:
    applicability = classify_mac_applicability(problem_class)  # type: ignore[arg-type]
    assert applicability.ordinary_energy_mac_use == "diagnostic_only"
    assert applicability.promotion_allowed_from_ordinary_mac is False
    assert "biorthogonal" in (applicability.required_method or "")
