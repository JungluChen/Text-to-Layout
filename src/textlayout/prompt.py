"""Deterministic natural-language → design-intent parser (no LLM, no API key).

The parser is rule-based on purpose: the default demo must be reproducible from
a fresh clone with zero credentials, and a wrong guess here poisons everything
downstream. It therefore extracts only what the prompt actually states and
raises :class:`~textlayout.errors.PromptParseError` when the request is
ambiguous — silent guessing is treated as a bug, not a convenience.

Supported: IDC, CPW, spiral inductors, quarter-wave resonators, SQUID candidates,
IDC+CPW test structures, and multi-device test-chip tiles.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from textlayout.errors import PromptParseError

INTENT_SCHEMA = "textlayout.design-intent.v1"

_COMPONENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "IDC",
        re.compile(r"\b(?:idc|interdigit(?:at)?ed?\s+capacitor|interdigital\s+capacitor)\b", re.I),
    ),
    ("CPW", re.compile(r"\b(?:cpw|coplanar\s+waveguide)\b", re.I)),
    ("SpiralInductor", re.compile(r"\b(?:spiral\s+inductor|planar\s+spiral)\b", re.I)),
    (
        "QuarterWaveResonator",
        re.compile(
            r"\b(?:quarter[- ]wave|lambda\s*/?\s*4|λ\s*/?\s*4).*\bresonator\b|\bquarter[- ]wave\s+resonator\b",
            re.I,
        ),
    ),
    ("SQUID", re.compile(r"\b(?:dc[- ]?)?squid\b", re.I)),
)

_NUM = r"(\d+(?:\.\d+)?)"
_UM = r"(?:um|µm|μm|micron(?:s)?|micrometer(?:s)?|micrometre(?:s)?)"

_CAPACITANCE_RE = re.compile(rf"{_NUM}\s*(pf|ff|nf)\b", re.I)
_FREQUENCY_RE = re.compile(rf"(?:\bat\s+)?{_NUM}\s*(ghz|mhz)\b", re.I)
_BANDWIDTH_RE = re.compile(rf"{_NUM}\s*(ghz|mhz)\s+bandwidth\b", re.I)
_GAIN_RE = re.compile(rf"{_NUM}\s*dB\s+gain(?:\s+target)?\b", re.I)
_IMPEDANCE_RE = re.compile(rf"{_NUM}\s*(?:ohm|Ω)s?\b", re.I)
_INDUCTANCE_RE = re.compile(rf"{_NUM}\s*(nh|ph|uh|µh)\b", re.I)
_TURNS_RE = re.compile(r"(\d+)\s+turns?\b", re.I)
_MIN_GAP_RE = re.compile(rf"{_NUM}\s*{_UM}\s+(?:min(?:imum)?\.?\s+)?gap", re.I)
_MIN_GAP_ALT_RE = re.compile(rf"(?:min(?:imum)?\.?\s+)gap\s+(?:of\s+)?{_NUM}\s*{_UM}", re.I)
_MIN_WIDTH_RE = re.compile(rf"{_NUM}\s*{_UM}\s+(?:min(?:imum)?\.?\s+)?(?:finger\s+)?width", re.I)
_OVERLAP_RE = re.compile(
    rf"{_NUM}\s*{_UM}\s+overlap|overlap\s+(?:of\s+|length\s+)?{_NUM}\s*{_UM}", re.I
)
_FINGER_PAIRS_RE = re.compile(r"(\d+)\s+finger\s+pairs?", re.I)
_METAL_LAYER_RE = re.compile(r"\bon\s+(M\d+)\b|\blayer\s+(M\d+)\b", re.I)
_SUBSTRATE_RE = re.compile(r"\bon\s+(silicon|sapphire|quartz|gaas|fused\s+silica)\b", re.I)

_CAP_UNIT_TO_PF = {"pf": 1.0, "ff": 1e-3, "nf": 1e3}
_FREQ_UNIT_TO_GHZ = {"ghz": 1.0, "mhz": 1e-3}

# Multi-device structures take precedence over single-component detection
# (their prompts legitimately mention several components at once).
_TEST_CHIP_RE = re.compile(r"\btest\s+chip\b|\bchip\s+tile\b|\btest[- ]chip\s+tile\b", re.I)
_TEST_STRUCTURE_RE = re.compile(r"\btest\s+structure\b|\bmeasurement\s+structure\b", re.I)
_TILE_SIZE_RE = re.compile(rf"{_NUM}\s*mm\s*(?:by|x|×)\s*{_NUM}\s*mm", re.I)
_TURNS_WORD_RE = re.compile(r"(\d+)[- ]turn\b", re.I)

#: Substrates the built-in technology library can actually model today.
_KNOWN_SUBSTRATES = {"silicon": "generic_2metal"}


class DesignIntent(BaseModel):
    """Structured, typed record of what the user asked for — nothing more."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=INTENT_SCHEMA)
    prompt: str
    component: str
    technology: str = Field(default="generic_2metal")
    substrate: str | None = None
    target: dict[str, float] = Field(default_factory=dict)
    constraints: dict[str, float] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    topology: str | None = None
    capacitor_type: str | None = None
    inductance_assumption: dict[str, Any] | None = None
    simulator_requests: list[str] = Field(default_factory=list)
    evidence_status: list[str] = Field(default_factory=lambda: ["INTENT_PARSED"])


def parse_prompt(prompt: str) -> DesignIntent:
    """Parse a layout request into a :class:`DesignIntent`.

    Raises :class:`PromptParseError` when the component cannot be identified or
    an explicitly-stated quantity cannot be interpreted.
    """
    text = prompt.strip()
    if not text:
        raise PromptParseError(prompt, "the prompt is empty")

    component = _parse_component(text)
    notes: list[str] = []

    target: dict[str, float] = {}
    cap = _CAPACITANCE_RE.search(text)
    if cap:
        target["capacitance_pf"] = round(
            float(cap.group(1)) * _CAP_UNIT_TO_PF[cap.group(2).lower()], 6
        )
    # Parse bandwidth first and blank its span out of the frequency search:
    # "500 MHz bandwidth at 6 GHz" must not read 0.5 GHz as the frequency.
    bandwidth = _BANDWIDTH_RE.search(text)
    if bandwidth:
        target["bandwidth_mhz"] = round(
            float(bandwidth.group(1)) * (1000.0 if bandwidth.group(2).lower() == "ghz" else 1.0),
            6,
        )
    frequency_text = (
        text[: bandwidth.start()] + " " * (bandwidth.end() - bandwidth.start())
        + text[bandwidth.end():]
        if bandwidth
        else text
    )
    freq = _FREQUENCY_RE.search(frequency_text)
    if freq:
        target["frequency_ghz"] = round(
            float(freq.group(1)) * _FREQ_UNIT_TO_GHZ[freq.group(2).lower()], 6
        )
    gain = _GAIN_RE.search(text)
    if gain:
        target["gain_db"] = float(gain.group(1))
    impedance = _IMPEDANCE_RE.search(text)
    if impedance:
        target["impedance_ohm"] = float(impedance.group(1))
    inductance = _INDUCTANCE_RE.search(text)
    if inductance:
        scale = {"ph": 1e-3, "nh": 1.0, "uh": 1e3, "µh": 1e3}
        target["inductance_nh"] = float(inductance.group(1)) * scale[inductance.group(2).lower()]

    substrate: str | None = None
    technology = "generic_2metal"
    sub = _SUBSTRATE_RE.search(text)
    if sub:
        substrate = sub.group(1).lower()
        mapped = _KNOWN_SUBSTRATES.get(substrate)
        if mapped is None:
            raise PromptParseError(
                prompt,
                f"substrate {substrate!r} has no registered technology",
                hints=[f"supported substrates: {sorted(_KNOWN_SUBSTRATES)}"],
            )
        technology = mapped

    constraints: dict[str, float] = {}
    gap = _MIN_GAP_RE.search(text) or _MIN_GAP_ALT_RE.search(text)
    if gap:
        constraints["min_gap_um"] = float(gap.group(1))
    width = _MIN_WIDTH_RE.search(text)
    if width:
        constraints["min_width_um"] = float(width.group(1))

    parameters: dict[str, Any] = {}
    pairs = _FINGER_PAIRS_RE.search(text)
    if pairs:
        parameters["finger_pairs"] = int(pairs.group(1))
    overlap = _OVERLAP_RE.search(text)
    if overlap:
        parameters["overlap_um"] = float(overlap.group(1) or overlap.group(2))
    if width:
        parameters["finger_width_um"] = float(width.group(1))
    if gap:
        parameters["gap_um"] = float(gap.group(1))
    layer = _METAL_LAYER_RE.search(text)
    if layer:
        parameters["metal_layer"] = (layer.group(1) or layer.group(2)).upper()
    turns = _TURNS_RE.search(text) or _TURNS_WORD_RE.search(text)
    if turns:
        parameters["turns"] = int(turns.group(1))
    if component == "SpiralInductor":
        trace = re.search(rf"{_NUM}\s*{_UM}\s+trace\s+width", text, re.I)
        if trace:
            parameters["trace_width_um"] = float(trace.group(1))
            parameters.pop("finger_width_um", None)
        spacing = re.search(rf"{_NUM}\s*{_UM}\s+spacing", text, re.I)
        if spacing:
            parameters["spacing_um"] = float(spacing.group(1))
    tile = _TILE_SIZE_RE.search(text)
    if tile and component == "TestChip":
        parameters["tile_width_um"] = float(tile.group(1)) * 1000.0
        parameters["tile_height_um"] = float(tile.group(2)) * 1000.0
    if component == "TestChip":
        # The tile spec namespaces sub-device parameters.
        if "turns" in parameters:
            parameters["spiral_turns"] = parameters.pop("turns")
        if "finger_width_um" in parameters:
            parameters["idc_finger_width_um"] = parameters.pop("finger_width_um")
        if "gap_um" in parameters:
            parameters["idc_gap_um"] = parameters.pop("gap_um")
        if "finger_pairs" in parameters:
            parameters["idc_finger_pairs"] = parameters.pop("finger_pairs")
        parameters.pop("overlap_um", None)
    wants_jj = bool(re.search(r"\b(?:jj|josephson|squid|jpa)\b", text, re.I))
    if re.search(r"\bjosim\b|\bcircuit(?:-level)?\s+check\b", text, re.I):
        parameters["josim_check"] = True
        parameters["josim_jj_check"] = wants_jj
    if re.search(r"\bpscan\s*2?\b", text, re.I):
        parameters["pscan2_check"] = True
        parameters["pscan2_jj_check"] = wants_jj
    if re.search(r"\bwr[- ]?spice\b", text, re.I):
        parameters["wrspice_check"] = True
        parameters["wrspice_jj_check"] = wants_jj
    simulator_requests = [
        name.upper() if name != "wrspice" else "WRspice"
        for name in ("josim", "pscan2", "wrspice")
        if parameters.get(f"{name}_check")
    ]
    if component == "IDC" and "inductance_nh" in target:
        # For an IDC, a stated inductance is the LC-check companion inductor,
        # not a design target of the capacitor itself.
        parameters["lc_inductance_nh"] = target.pop("inductance_nh")

    if component == "IDC" and not target and not parameters:
        raise PromptParseError(
            prompt,
            "an IDC request needs a target capacitance or explicit geometry parameters",
            hints=["e.g. 'Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap'"],
        )
    if component == "IDC" and "capacitance_pf" not in target and "finger_pairs" not in parameters:
        notes.append(
            "No target capacitance or finger count stated; a default finger count "
            "will be used downstream."
        )

    if "frequency_ghz" not in target and component == "IDC":
        notes.append("No operating frequency stated; self-resonance headroom is unchecked.")

    return DesignIntent(
        prompt=text,
        component=component,
        technology=technology,
        substrate=substrate,
        target=target,
        constraints=constraints,
        parameters=parameters,
        notes=notes,
        topology="lumped_element_jpa" if component == "JPA" else None,
        capacitor_type="IDC" if component == "JPA" else None,
        inductance_assumption=(
            {
                "type": "SQUID-equivalent",
                "value_nh": float(target.get("inductance_nh", 3.0)),
                "source": ("user_provided" if "inductance_nh" in target else "workflow_default"),
                "user_provided": "inductance_nh" in target,
            }
            if component == "JPA"
            else None
        ),
        simulator_requests=simulator_requests,
    )


def _parse_component(text: str) -> str:
    if re.search(r"\bjpa\b|josephson\s+parametric\s+amplifier", text, re.I):
        return "JPA"
    if _TEST_CHIP_RE.search(text):
        return "TestChip"
    if _TEST_STRUCTURE_RE.search(text):
        return "TestStructure"
    matches = [name for name, pattern in _COMPONENT_PATTERNS if pattern.search(text)]
    if not matches:
        raise PromptParseError(
            text,
            "no supported component was recognised",
            hints=[
                "supported: IDC, CPW, spiral inductor, quarter-wave resonator, SQUID, "
                "test structure, test chip",
                "e.g. 'Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap'",
            ],
        )
    if len(matches) > 1:
        raise PromptParseError(
            text,
            f"the prompt mentions multiple components {matches}; ask for one at a time",
        )
    return matches[0]
