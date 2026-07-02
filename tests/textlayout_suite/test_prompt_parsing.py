"""Phase 9 category 1 — text prompt parsing (deterministic, no LLM)."""

from __future__ import annotations

import pytest

from textlayout.errors import PromptParseError
from textlayout.prompt import parse_prompt


def test_full_idc_prompt_parses_all_fields() -> None:
    intent = parse_prompt("Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap.")
    assert intent.component == "IDC"
    assert intent.target == {"capacitance_pf": 0.6, "frequency_ghz": 6.0}
    assert intent.substrate == "silicon"
    assert intent.technology == "generic_2metal"
    assert intent.constraints["min_gap_um"] == 2.0
    assert intent.parameters["gap_um"] == 2.0


def test_interdigitated_capacitor_with_target_capacitance() -> None:
    intent = parse_prompt("Generate an interdigitated capacitor with 0.8 pF target capacitance.")
    assert intent.component == "IDC"
    assert intent.target["capacitance_pf"] == 0.8
    assert "frequency_ghz" not in intent.target


def test_idc_with_explicit_finger_width_and_gap() -> None:
    intent = parse_prompt("Design an IDC using 3 um finger width and 2 um gap.")
    assert intent.component == "IDC"
    assert intent.parameters["finger_width_um"] == 3.0
    assert intent.parameters["gap_um"] == 2.0
    # No target and no finger count: allowed, but flagged for a downstream default.
    assert any("default finger count" in note for note in intent.notes)


def test_unit_conversion_ff_and_mhz() -> None:
    intent = parse_prompt("Create a 600 fF IDC at 6000 MHz with 12 finger pairs")
    assert intent.target["capacitance_pf"] == pytest.approx(0.6)
    assert intent.target["frequency_ghz"] == pytest.approx(6.0)
    assert intent.parameters["finger_pairs"] == 12


def test_malformed_prompt_fails_loudly_not_silently() -> None:
    with pytest.raises(PromptParseError, match="no supported component"):
        parse_prompt("Draw me something nice for my chip")


def test_empty_prompt_rejected() -> None:
    with pytest.raises(PromptParseError, match="empty"):
        parse_prompt("   ")


def test_bare_idc_request_rejected() -> None:
    with pytest.raises(PromptParseError, match="target capacitance or explicit geometry"):
        parse_prompt("Create an IDC on silicon")


def test_unknown_substrate_rejected_not_guessed() -> None:
    with pytest.raises(PromptParseError, match="no registered technology"):
        parse_prompt("Create a 0.6 pF IDC on sapphire")


def test_ambiguous_multi_component_prompt_rejected() -> None:
    with pytest.raises(PromptParseError, match="multiple components"):
        parse_prompt("Create a 0.6 pF IDC and a CPW feedline")


@pytest.mark.parametrize(
    ("prompt", "component", "target_key", "target_value"),
    [
        (
            "Design a CPW transmission line on silicon at 6 GHz with 50 ohm impedance",
            "CPW",
            "impedance_ohm",
            50.0,
        ),
        ("Create a 3 nH spiral inductor with 4 turns", "SpiralInductor", "inductance_nh", 3.0),
        ("Create a 6 GHz quarter-wave resonator", "QuarterWaveResonator", "frequency_ghz", 6.0),
        ("Create a symmetric DC SQUID", "SQUID", None, None),
    ],
)
def test_extended_component_prompts(
    prompt: str, component: str, target_key: str | None, target_value: float | None
) -> None:
    intent = parse_prompt(prompt)
    assert intent.component == component
    if target_key is not None:
        assert intent.target[target_key] == target_value
