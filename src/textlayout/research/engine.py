"""Research dispatcher: component → :class:`ResearchReport`.

This is the first stage of the safe pipeline (Research → first-principles →
initial parameters → DSL → generate → verify → export). It is injectable and
extensible: register a research function per component without touching callers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from textlayout.models import Technology
from textlayout.errors import InvalidParametersError, MissingResearchError
from textlayout.research.cpw_research import research_cpw, research_quarter_wave_resonator
from textlayout.research.idc_research import research_idc
from textlayout.research.models import ResearchReport
from textlayout.research.spiral_research import research_spiral
from textlayout.research.squid_research import research_squid
from textlayout.schemas.dsl import LayoutSpec

ResearchFn = Callable[[dict[str, float], dict[str, Any], Technology], ResearchReport]

_RESEARCHERS: dict[str, ResearchFn] = {
    "IDC": research_idc,
    "CPW": research_cpw,
    "SpiralInductor": research_spiral,
    "QuarterWaveResonator": research_quarter_wave_resonator,
    "SQUID": research_squid,
}


def research_components() -> list[str]:
    """Return component names with a registered evidence model."""
    return sorted(_RESEARCHERS)


def has_research(component: str) -> bool:
    return component in _RESEARCHERS


def research(spec: LayoutSpec, tech: Technology) -> ResearchReport:
    """Produce a research/evidence report for ``spec`` (raises if no model exists)."""
    try:
        fn = _RESEARCHERS[spec.component]
    except KeyError:
        raise MissingResearchError(spec.component, research_components()) from None
    try:
        return fn(dict(spec.target), dict(spec.parameters), tech)
    except ValueError as exc:
        # A first-principles formula rejected the inputs (e.g. non-positive
        # dimensions). Surface as a structured 400, not an unhandled 500.
        raise InvalidParametersError(spec.component, str(exc)) from exc
