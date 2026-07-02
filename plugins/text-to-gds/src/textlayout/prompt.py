"""Deterministic natural-language parsing for supported layout prompts.

The parser deliberately has a narrow grammar.  It rejects ambiguous component
requests instead of guessing, records every default as an assumption, and keeps
explicit geometry separate from inferred geometry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from textlayout.errors import PromptCompilationError
from textlayout.schemas.dsl import LayoutSpec


@dataclass(frozen=True, slots=True)
class PromptIntent:
    """Structured values inferred from a user prompt, before layout synthesis."""

    prompt: str
    component: str
    target_capacitance_pf: float | None = None
    target_impedance_ohm: float | None = None
    frequency_ghz: float | None = None
    substrate: str = "silicon"
    substrate_epsilon_r: float = 11.9
    min_width_um: float = 2.0
    min_gap_um: float = 2.0
    finger_pairs: int | None = None
    finger_width_um: float | None = None
    gap_um: float | None = None
    overlap_um: float | None = None
    bus_width_um: float | None = None
    center_width_um: float | None = None
    length_um: float | None = None
    ground_width_um: float | None = None
    assumptions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "textlayout.prompt-intent.v1", **asdict(self)}


_NUMBER = r"(?P<value>\d+(?:\.\d+)?)"


def _quantity(text: str, unit_pattern: str) -> float | None:
    match = re.search(rf"{_NUMBER}\s*(?P<unit>{unit_pattern})\b", text, re.IGNORECASE)
    if match is None:
        return None
    value = float(match.group("value"))
    unit = match.group("unit").lower()
    if unit == "ff":
        return value / 1000.0
    if unit == "mhz":
        return value / 1000.0
    return value


def _dimension(text: str, name: str) -> float | None:
    """Read either ``name 4 um`` or ``4 um name`` without stealing other dimensions."""
    number = r"(\d+(?:\.\d+)?)"
    unit = r"(?:u?m|micrometers?)"
    patterns = (
        rf"{name}(?:\s+of)?\s+{number}\s*{unit}\b",
        rf"{number}\s*{unit}\s+{name}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None:
            return float(match.group(1))
    return None


def parse_prompt(prompt: str) -> PromptIntent:
    """Parse an IDC or CPW request without an LLM or network dependency."""
    text = " ".join(prompt.strip().replace("μ", "u").replace("µ", "u").replace("Ω", "ohm").split())
    lower = text.lower()
    if not text:
        raise PromptCompilationError("prompt must not be empty", ["Describe the requested component."])

    matches: list[str] = []
    if any(token in lower for token in ("idc", "interdigital", "interdigitated")):
        matches.append("IDC")
    if "cpw" in lower or "coplanar waveguide" in lower:
        matches.append("CPW")
    if len(matches) != 1:
        if not matches:
            question = "Specify either an IDC or CPW component."
            message = "prompt does not identify a supported component"
        else:
            question = "Choose one component: IDC or CPW."
            message = "prompt identifies multiple components"
        raise PromptCompilationError(message, [question])
    component = matches[0]

    capacitance_pf = _quantity(text, "pF|fF")
    frequency_ghz = _quantity(text, "GHz|MHz")
    impedance_ohm = _quantity(text, "ohm|ohms")
    min_gap_match = re.search(
        r"(?:minimum|min)\s+gap(?:\s+of)?\s+(\d+(?:\.\d+)?)\s*(?:um|micrometers?)",
        text,
        re.IGNORECASE,
    )
    if min_gap_match is None:
        min_gap_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:um|micrometers?)\s+(?:minimum|min)\s+gap",
            text,
            re.IGNORECASE,
        )
    min_width_match = re.search(
        rf"(?:minimum|min)\s+(?:finger\s+)?width(?:\s+of)?\s+{_NUMBER}\s*(?:um|micrometers?)",
        text,
        re.IGNORECASE,
    )

    min_gap = float(min_gap_match.group(1)) if min_gap_match else 2.0
    min_width = float(min_width_match.group("value")) if min_width_match else 2.0

    finger_pairs_match = re.search(r"(\d+)\s+finger\s+pairs?\b", text, re.IGNORECASE)
    finger_width = _dimension(text, r"(?:finger\s+)?width") if component == "IDC" else None
    gap = _dimension(text, "gap")
    overlap = _dimension(text, "overlap") if component == "IDC" else None
    bus_width = _dimension(text, r"bus\s+width") if component == "IDC" else None
    center_width = _dimension(text, r"(?:center|centre)(?:\s+conductor)?\s+width")
    length = _dimension(text, "length")
    ground_width = _dimension(text, r"ground\s+width")

    substrate = "silicon" if "silicon" in lower or " si " in f" {lower} " else "silicon"
    epsilon_match = re.search(
        r"(?:epsilon(?:_r)?|relative permittivity|er)\s*(?:=|of)?\s*(\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    epsilon_r = float(epsilon_match.group(1)) if epsilon_match else 11.9

    if component == "IDC" and capacitance_pf is None:
        raise PromptCompilationError(
            "IDC prompt is missing a capacitance target",
            ["What capacitance should the IDC target, in pF or fF?"],
        )

    assumptions: list[str] = []
    if "silicon" not in lower and not re.search(r"\bsi\b", lower):
        assumptions.append("substrate defaults to silicon")
    if epsilon_match is None:
        assumptions.append("substrate relative permittivity defaults to 11.9")
    if min_width_match is None:
        assumptions.append("minimum width defaults to 2 um")
    if min_gap_match is None:
        assumptions.append("minimum gap defaults to 2 um")
    if component == "CPW" and impedance_ohm is None:
        assumptions.append("CPW target impedance defaults to 50 ohm")

    return PromptIntent(
        prompt=text,
        component=component,
        target_capacitance_pf=capacitance_pf,
        target_impedance_ohm=impedance_ohm,
        frequency_ghz=frequency_ghz,
        substrate=substrate,
        substrate_epsilon_r=epsilon_r,
        min_width_um=min_width,
        min_gap_um=min_gap,
        finger_pairs=int(finger_pairs_match.group(1)) if finger_pairs_match else None,
        finger_width_um=finger_width,
        gap_um=gap,
        overlap_um=overlap,
        bus_width_um=bus_width,
        center_width_um=center_width,
        length_um=length,
        ground_width_um=ground_width,
        assumptions=tuple(assumptions),
    )


def cpw_spec_from_intent(intent: PromptIntent) -> LayoutSpec:
    """Compile a parsed CPW intent into a conservative straight-line DSL."""
    if intent.component != "CPW":
        raise ValueError("intent is not a CPW request")
    target_z0 = intent.target_impedance_ohm or 50.0
    return LayoutSpec(
        component="CPW",
        target={"impedance_ohm": target_z0, **(
            {"frequency_ghz": intent.frequency_ghz} if intent.frequency_ghz else {}
        )},
        parameters={
            "center_width_um": intent.center_width_um or max(10.0, intent.min_width_um),
            "gap_um": intent.gap_um or max(6.0, intent.min_gap_um),
            "length_um": intent.length_um or 1000.0,
            "ground_width_um": intent.ground_width_um or 50.0,
            "metal": "M1",
        },
        rules={"min_width_um": intent.min_width_um, "min_gap_um": intent.min_gap_um},
        metadata={
            "source": "deterministic_prompt_parser",
            "prompt": intent.prompt,
            "assumptions": list(intent.assumptions),
        },
    )
