"""Regression coverage for quantities that must survive prompt conditioning."""

import pytest

from textlayout.errors import PromptParseError
from textlayout.prompt import parse_prompt


@pytest.mark.parametrize("quantity", [".6", "6e-1", "+0.6"])
def test_capacitance_numeric_notation_is_preserved(quantity: str) -> None:
    intent = parse_prompt(f"Create a {quantity} pF IDC on silicon")
    assert intent.target["capacitance_pf"] == pytest.approx(0.6)


@pytest.mark.parametrize(
    "prompt",
    [
        "Create a -0.6 pF IDC",
        "Create a 0 pF IDC",
        "Create a CPW at -6 GHz with 50 ohm impedance",
        "Create a CPW at 6 GHz with -50 ohm impedance",
        "Create a 0.6 pF IDC with -2 um gap",
        "Create a 0.6 pF IDC with 0 um finger width",
        "Create a -3 nH spiral inductor with 4 turns",
        "Create a 3 nH spiral inductor with -4 turns",
        "Create an IDC with -12 finger pairs",
    ],
)
def test_nonpositive_design_quantities_are_rejected(prompt: str) -> None:
    with pytest.raises(PromptParseError, match="positive"):
        parse_prompt(prompt)
